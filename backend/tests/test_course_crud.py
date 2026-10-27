"""课程接口回归，使用 SQLite 内存库和真实 JWT 鉴权。"""

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
    BusinessException, bussiness_excpetion_hadler,
    http_excpetion_hadler, validation_excpetion_hadler,
)
from app.config import settings
from app.database import Base, get_db
from app.models.course import Course
from app.models.user import User
from app.utils.jwt import create_access_token


class CourseCrudTests(unittest.TestCase):
    def setUp(self):
        secret = patch.object(settings, "JWT_SECRET_KEY", "course-tests-only-secret-key-32-characters")
        secret.start()
        self.addCleanup(secret.stop)
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine)
        with self.session_factory() as db:
            for user_id, role, status in ((1, "admin", 1), (2, "student", 1), (3, "admin", 0)):
                db.add(User(id=user_id, username=f"user{user_id}", name=role,
                            password="unused", role=role, status=status))
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

    def request(self, method, suffix="", user_id=1, **kwargs):
        return self.client.request(method, f"/api/courses{suffix}",
            headers={"Authorization": f"Bearer {create_access_token(user_id)}"}, **kwargs)

    def create(self, **payload):
        body = self.request("POST", json={"name": "数据结构", **payload}).json()
        self.assertEqual(body["code"], 200)
        return body["data"]

    def test_crud_search_and_detail(self):
        course = self.create(name=" 数据结构 ", code=" DS101 ", description=" 树与图 ")
        self.assertEqual((course["name"], course["code"], course["description"]), ("数据结构", "DS101", "树与图"))
        self.assertEqual(self.request("GET", f"/{course['id']}").json()["data"], course)
        for keywords in (" 数据 ", "ds101", "树", " "):
            self.assertEqual(self.request("GET", params={"keywords": keywords}).json()["data"], [course])
        self.assertEqual(self.request("GET", params={"keywords": "不存在"}).json()["data"], [])
        edited = self.request("PUT", f"/{course['id']}", json={"description": " 新简介 ", "status": 0}).json()
        self.assertEqual(edited["data"]["description"], "新简介")
        self.assertEqual(edited["data"]["status"], 0)
        self.assertEqual(edited["data"]["code"], "DS101")
        self.assertEqual(self.request("DELETE", f"/{course['id']}").json()["code"], 200)
        self.assertEqual(self.request("GET").json()["data"], [])

    def test_codes_optional_unique_and_clearable(self):
        first = self.create(code="DS101", description="简介")
        second = self.create(code="ENG101")
        duplicate = self.request("POST", json={"name": "重复", "code": " DS101 "}).json()
        self.assertEqual(duplicate["message"], "课程代码已存在")
        conflict = self.request("PUT", f"/{second['id']}", json={"code": "DS101"}).json()
        self.assertEqual(conflict["message"], "课程代码已存在")
        self.assertEqual(self.request("PUT", f"/{first['id']}", json={"code": "DS101"}).json()["code"], 200)
        for code in (None, "", "   "):
            self.assertIsNone(self.create(code=code)["code"])
        self.assertIsNone(self.create()["code"])
        for payload in ({"code": None, "description": None}, {"code": " ", "description": " "}):
            body = self.request("PUT", f"/{first['id']}", json=payload).json()
            self.assertEqual(body["code"], 200)
            self.assertIsNone(body["data"]["code"])
            self.assertIsNone(body["data"]["description"])
        self.create(code="DS101")

    def test_list_order_and_missing_course(self):
        first, second = self.create(), self.create()
        self.assertEqual([row["id"] for row in self.request("GET").json()["data"]], [second["id"], first["id"]])
        for method, kwargs in (("GET", {}), ("PUT", {"json": {"status": 0}}), ("DELETE", {})):
            self.assertEqual(self.request(method, "/999", **kwargs).json()["message"], "课程不存在")

    def test_invalid_fields_do_not_mutate(self):
        course = self.create(code="DS101")
        for payload in ({"name": " "}, {"name": "x" * 101}, {"code": "x" * 51}, {"status": 2}):
            self.assertEqual(self.request("POST", json={"name": "invalid", **payload}).status_code, 422)
            self.assertEqual(self.request("PUT", f"/{course['id']}", json=payload).status_code, 422)
        self.assertEqual(self.request("GET").json()["data"], [course])

    def test_all_endpoints_require_active_admin(self):
        for method, suffix, kwargs in (
            ("GET", "", {}), ("GET", "/1", {}),
            ("POST", "", {"json": {"name": "课程"}}),
            ("PUT", "/1", {"json": {"name": "课程"}}), ("DELETE", "/1", {}),
        ):
            with self.subTest(method=method, suffix=suffix):
                body = self.request(method, suffix, user_id=2, **kwargs).json()
                self.assertEqual((body["code"], body["message"]), (403, "无权限访问"))
                for user_id in (3, 999):
                    self.assertEqual(self.request(method, suffix, user_id=user_id, **kwargs).status_code, 401)
                for headers in ({}, {"Authorization": "Bearer invalid"}):
                    self.assertEqual(self.client.request(method, f"/api/courses{suffix}", headers=headers, **kwargs).status_code, 401)
        with self.session_factory() as db:
            self.assertEqual(db.query(Course).count(), 0)


if __name__ == "__main__":
    unittest.main()
