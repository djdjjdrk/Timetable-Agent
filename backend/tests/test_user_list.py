"""使用内存数据库验证用户列表，不连接或修改本地业务数据库。"""

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


class UserListTests(unittest.TestCase):
    def setUp(self):
        self.secret_patch = patch.object(
            settings, "JWT_SECRET_KEY", "user-list-tests-only-secret-key-32-characters"
        )
        self.secret_patch.start()
        self.addCleanup(self.secret_patch.stop)
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory() as db:
            db.add_all(
                [
                    User(
                        id=1, username="AdminUser", name="管理员", role="admin",
                        password="never-return-this-password", status=1,
                        email="admin@example.com", phone="13800138000",
                        avatar="/uploads/admin.png",
                    ),
                    User(
                        id=2, username="student01", name="张三", role="student",
                        password="never-return-this-password", status=1,
                    ),
                    User(
                        id=3, username="student02", name="张四", role="student",
                        password="never-return-this-password", status=0,
                    ),
                    User(
                        id=4, username="disabledAdmin", name="禁用管理员", role="admin",
                        password="never-return-this-password", status=0,
                    ),
                ]
            )
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

    def get_list(self, user_id=1, **params):
        return self.client.get(
            "/api/user/list", params=params,
            headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
        )

    def test_admin_default_list_and_public_fields(self):
        response = self.get_list()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["total"], 4)
        self.assertEqual([item["id"] for item in body["data"]["list"]], [4, 3, 2, 1])
        for item in body["data"]["list"]:
            self.assertEqual(
                set(item),
                {"id", "username", "name", "avatar", "email", "phone", "role", "status"},
            )
        admin = body["data"]["list"][-1]
        self.assertEqual(admin["avatar"], "/uploads/admin.png")
        self.assertEqual(admin["email"], "admin@example.com")
        self.assertEqual(admin["phone"], "13800138000")

    def test_pagination_keeps_matching_total(self):
        body = self.get_list(page=2, page_size=2).json()
        self.assertEqual(body["data"]["total"], 4)
        self.assertEqual([item["id"] for item in body["data"]["list"]], [2, 1])

    def test_search_username_is_case_insensitive(self):
        body = self.get_list(keywords="ADMINUSER").json()
        self.assertEqual(body["data"]["total"], 1)
        self.assertEqual(body["data"]["list"][0]["id"], 1)

    def test_search_name_and_paginate_filtered_results(self):
        body = self.get_list(keywords="张", page=2, page_size=1).json()
        self.assertEqual(body["data"]["total"], 2)
        self.assertEqual([item["id"] for item in body["data"]["list"]], [2])

    def test_empty_search_returns_all_users(self):
        self.assertEqual(self.get_list(keywords="").json()["data"]["total"], 4)

    def test_no_matches_and_page_beyond_end(self):
        self.assertEqual(
            self.get_list(keywords="不存在").json()["data"], {"list": [], "total": 0}
        )
        self.assertEqual(
            self.get_list(page=10).json()["data"], {"list": [], "total": 4}
        )

    def test_student_is_forbidden(self):
        body = self.get_list(user_id=2).json()
        self.assertEqual(body["code"], 403)
        self.assertEqual(body["message"], "无权限访问")
        self.assertIsNone(body["data"])

    def test_missing_and_invalid_tokens_are_unauthorized(self):
        for headers in ({}, {"Authorization": "Bearer invalid-token"}):
            with self.subTest(headers=headers):
                response = self.client.get("/api/user/list", headers=headers)
                self.assertEqual(response.status_code, 401)

    def test_disabled_and_missing_users_are_unauthorized(self):
        for user_id in (3, 4, 999):
            with self.subTest(user_id=user_id):
                self.assertEqual(self.get_list(user_id=user_id).status_code, 401)

    def test_invalid_pagination_is_rejected(self):
        for params in (
            {"page": 0}, {"page": -1}, {"page": "invalid"},
            {"page_size": 0}, {"page_size": -1}, {"page_size": 101},
        ):
            with self.subTest(params=params):
                response = self.get_list(**params)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["code"], 422)


if __name__ == "__main__":
    unittest.main()
