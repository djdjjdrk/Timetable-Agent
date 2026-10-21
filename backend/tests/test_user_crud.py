"""用户管理接口回归：仅使用 SQLite 内存库，不修改业务数据。"""

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.exceptions import HTTPException

from app.api import api
from app.common.exceptions import (
    BusinessException,
    bussiness_excpetion_hadler,
    http_excpetion_hadler,
    validation_excpetion_hadler,
)
from app.config import settings
from app.database import Base, get_db
from app.models.user import User
from app.utils.jwt import create_access_token
from app.utils.password import hash_password, verify_password


class UserCrudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial_hash = hash_password("old123")

    def setUp(self):
        secret_patch = patch.object(
            settings, "JWT_SECRET_KEY", "user-crud-tests-only-secret-key-32-characters"
        )
        secret_patch.start()
        self.addCleanup(secret_patch.stop)
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory() as db:
            db.add_all([
                User(id=1, username="admin", name="管理员", role="admin",
                     password=self.initial_hash, status=1),
                User(id=2, username="student", name="学生", role="student",
                     password=self.initial_hash, status=1),
                User(id=3, username="disabled", name="禁用管理员", role="admin",
                     password=self.initial_hash, status=0),
            ])
            db.commit()

        def override_get_db():
            with self.session_factory() as db:
                yield db

        app = FastAPI()
        app.add_exception_handler(BusinessException, bussiness_excpetion_hadler)
        app.add_exception_handler(HTTPException, http_excpetion_hadler)
        app.add_exception_handler(RequestValidationError, validation_excpetion_hadler)
        app.include_router(api)
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def request(self, method, path="/api/user", user_id=1, **kwargs):
        return self.client.request(
            method, path,
            headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
            **kwargs,
        )

    def login(self, username, password):
        return self.client.post(
            "/api/auth/login", json={"username": username, "password": password}
        ).json()

    def test_create_hashes_password_and_account_can_log_in(self):
        payload = {
            "username": "zhangsan", "password": "123456", "name": "张三",
            "email": "zhang@example.com", "phone": "13800138000",
            "avatar": "/uploads/avatar.png", "role": "student", "status": 1,
        }
        body = self.request("POST", json=payload).json()
        self.assertEqual(body["code"], 200)
        user = body["data"]
        self.assertNotIn("password", user)
        for field, value in payload.items():
            if field != "password":
                self.assertEqual(user[field], value)
        with self.session_factory() as db:
            stored = db.get(User, user["id"])
            self.assertNotEqual(stored.password, payload["password"])
            self.assertTrue(verify_password(payload["password"], stored.password))
        login = self.login("zhangsan", "123456")
        self.assertEqual(login["code"], 200)
        self.assertTrue(login["data"]["token"])
        self.assertNotIn("password", login["data"]["user"])
        page = self.request("GET", "/api/user/list", params={"keywords": "张三"}).json()
        self.assertEqual(page["data"]["total"], 1)
        self.assertEqual(page["data"]["list"][0], user)

    def test_create_defaults_support_omitted_name_and_password(self):
        body = self.request("POST", json={"username": "default_user"}).json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["name"], "default_user")
        self.assertEqual(body["data"]["role"], "student")
        self.assertEqual(body["data"]["status"], 1)
        self.assertEqual(self.login("default_user", "123")["code"], 200)

    def test_duplicate_username_is_business_error_and_does_not_replace_account(self):
        body = self.request(
            "POST", json={"username": "student", "password": "new456", "role": "admin"}
        ).json()
        self.assertNotEqual(body["code"], 200)
        self.assertEqual(body["message"], "账号已存在")
        with self.session_factory() as db:
            self.assertEqual(db.query(User).count(), 3)
            self.assertEqual(db.get(User, 2).password, self.initial_hash)
            self.assertEqual(db.get(User, 2).role, "student")

    def test_edit_updates_management_fields_and_retains_password(self):
        payload = {
            "name": "张三丰", "email": "new@example.com", "phone": "13900139000",
            "avatar": "/uploads/new.png", "role": "admin", "status": 1,
        }
        body = self.request("PUT", "/api/user/2", json=payload).json()
        self.assertEqual(body["code"], 200)
        for field, value in payload.items():
            self.assertEqual(body["data"][field], value)
        self.assertNotIn("password", body["data"])
        with self.session_factory() as db:
            self.assertEqual(db.get(User, 2).password, self.initial_hash)
        self.assertEqual(self.login("student", "old123")["code"], 200)
        self.assertEqual(self.request("GET", "/api/user/list", user_id=2).json()["code"], 200)

    def test_edit_blank_or_null_password_keeps_existing_hash(self):
        for password in ("", None):
            with self.subTest(password=password):
                body = self.request("PUT", "/api/user/2", json={"password": password}).json()
                self.assertEqual(body["code"], 200)
                with self.session_factory() as db:
                    self.assertEqual(db.get(User, 2).password, self.initial_hash)
        self.assertEqual(self.login("student", "old123")["code"], 200)

    def test_edit_nonempty_password_is_hashed_and_changes_login(self):
        body = self.request("PUT", "/api/user/2", json={"password": "new456"}).json()
        self.assertEqual(body["code"], 200)
        self.assertNotIn("password", body["data"])
        with self.session_factory() as db:
            stored = db.get(User, 2)
            self.assertNotEqual(stored.password, "new456")
            self.assertTrue(verify_password("new456", stored.password))
        self.assertEqual(self.login("student", "new456")["code"], 200)
        self.assertNotEqual(self.login("student", "old123")["code"], 200)

    def test_disable_blocks_login_and_existing_token(self):
        token = self.login("student", "old123")["data"]["token"]
        body = self.request("PUT", "/api/user/2", json={"status": 0}).json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["status"], 0)
        self.assertEqual(self.login("student", "old123")["message"], "账号被禁用")
        response = self.client.get("/api/user/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_delete_removes_user_and_invalidates_existing_token(self):
        token = self.login("student", "old123")["data"]["token"]
        body = self.request("DELETE", "/api/user/2").json()
        self.assertEqual(body["code"], 200)
        with self.session_factory() as db:
            self.assertIsNone(db.get(User, 2))
        self.assertNotEqual(self.login("student", "old123")["code"], 200)
        response = self.client.get("/api/user/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_current_admin_cannot_be_deleted(self):
        body = self.request("DELETE", "/api/user/1").json()
        self.assertNotEqual(body["code"], 200)
        self.assertIn("不能删除当前登录", body["message"])
        with self.session_factory() as db:
            self.assertIsNotNone(db.get(User, 1))

    def test_missing_user_edit_and_delete_are_business_errors(self):
        for method, kwargs in (("PUT", {"json": {"name": "不存在"}}), ("DELETE", {})):
            with self.subTest(method=method):
                body = self.request(method, "/api/user/999", **kwargs).json()
                self.assertNotEqual(body["code"], 200)
                self.assertEqual(body["message"], "用户不存在")

    def test_student_cannot_create_edit_or_delete(self):
        for method, path, kwargs in (
            ("POST", "/api/user", {"json": {"username": "hacker"}}),
            ("PUT", "/api/user/2", {"json": {"role": "admin"}}),
            ("DELETE", "/api/user/1", {}),
        ):
            with self.subTest(method=method):
                body = self.request(method, path, user_id=2, **kwargs).json()
                self.assertEqual(body["code"], 403)
                self.assertEqual(body["message"], "无权限访问")
        with self.session_factory() as db:
            self.assertEqual(db.query(User).count(), 3)
            self.assertEqual(db.get(User, 2).role, "student")

    def test_missing_invalid_disabled_and_deleted_identity_cannot_mutate(self):
        for method, path, kwargs in (
            ("POST", "/api/user", {"json": {"username": "blocked"}}),
            ("PUT", "/api/user/2", {"json": {"name": "blocked"}}),
            ("DELETE", "/api/user/2", {}),
        ):
            for headers in (
                {}, {"Authorization": "Bearer invalid-token"},
                {"Authorization": f"Bearer {create_access_token(3)}"},
                {"Authorization": f"Bearer {create_access_token(999)}"},
            ):
                with self.subTest(method=method, headers=headers):
                    response = self.client.request(method, path, headers=headers, **kwargs)
                    self.assertEqual(response.status_code, 401)
        with self.session_factory() as db:
            self.assertEqual(db.query(User).count(), 3)
            self.assertEqual(db.get(User, 2).name, "学生")

    def test_profile_update_ignores_role_status_and_password(self):
        body = self.request("PUT", "/api/user/me", user_id=2, json={
            "name": "学生新名称", "role": "admin", "status": 0, "password": "new456",
        }).json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["name"], "学生新名称")
        self.assertEqual(body["data"]["role"], "student")
        self.assertEqual(body["data"]["status"], 1)
        with self.session_factory() as db:
            self.assertEqual(db.get(User, 2).password, self.initial_hash)

    def test_fixed_password_route_still_changes_own_password(self):
        body = self.request("PUT", "/api/user/password", user_id=2, json={
            "old_password": "old123", "new_password": "new456",
        }).json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(self.login("student", "new456")["code"], 200)

    def test_invalid_management_values_are_rejected_without_changes(self):
        for payload in ({"role": "teacher"}, {"status": 2}, {"password": "12"}):
            for method, path, data in (
                ("POST", "/api/user", {"username": "invalid", **payload}),
                ("PUT", "/api/user/2", payload),
            ):
                with self.subTest(method=method, payload=payload):
                    response = self.request(method, path, json=data)
                    self.assertEqual(response.status_code, 422)
        with self.session_factory() as db:
            self.assertEqual(db.query(User).count(), 3)
            student = db.get(User, 2)
            self.assertEqual(student.role, "student")
            self.assertEqual(student.status, 1)
            self.assertEqual(student.password, self.initial_hash)


if __name__ == "__main__":
    unittest.main()
