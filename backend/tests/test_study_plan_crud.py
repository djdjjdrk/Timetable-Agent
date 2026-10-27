"""学习计划接口验证：真实 JWT、隔离数据库及越权保护。"""

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.exceptions import HTTPException

from app.api import api
from app.common.exceptions import (
    BusinessException, bussiness_excpetion_hadler,
    http_excpetion_hadler, validation_excpetion_hadler,
)
from app.config import settings, STUDY_PLAN_MAX_LENGTH
from app.database import Base, get_db
from app.models import User
from app.utils.jwt import create_access_token


class StudyPlanCrudTests(unittest.TestCase):
    def setUp(self):
        secret = patch.object(settings, "JWT_SECRET_KEY", "study-plan-tests-only-secret-key-32-characters")
        secret.start()
        self.addCleanup(secret.stop)
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(engine.dispose)

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        with factory() as db:
            for user_id, username, role, status in (
                (1, "aaa", "student", 1), (2, "bbb", "student", 1),
                (3, "admin", "admin", 1), (4, "disabled", "student", 0),
            ):
                db.add(User(id=user_id, username=username, name=username,
                            password="unused", role=role, status=status))
            db.commit()

        def override_get_db():
            with factory() as db:
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
        return self.client.request(method, f"/api/study-plans{suffix}",
            headers={"Authorization": f"Bearer {create_access_token(user_id)}"}, **kwargs)

    def create(self, content, **kwargs):
        body = self.request("POST", json={"content": content, **kwargs}).json()
        self.assertEqual(body["code"], 200, body)
        return body["data"]

    def test_save_markdown_order_pagination_and_delete(self):
        first = self.create("  明天数据结构课前，把链表与二叉树笔记过一遍，并完成课后习题 1～3。  ")
        markdown = "## 本周复习\n- 高等数学：导数练习\n- 大学英语：Unit 3 单词"
        second = self.create(markdown)
        self.assertFalse(first["content"].startswith(" "))
        self.assertEqual(second["content"], markdown)
        self.assertIsNotNone(second["create_time"])
        self.assertNotIn("user_id", second)
        self.assertEqual(self.request("GET").json()["data"], {"list": [second, first], "total": 2})
        self.assertEqual(self.request("GET", params={"page": 2, "page_size": 1}).json()["data"],
                         {"list": [first], "total": 2})
        self.assertEqual(self.request("GET", params={"page": 99}).json()["data"], {"list": [], "total": 2})
        self.assertEqual(self.request("DELETE", f"/{second['id']}").json()["code"], 200)
        self.assertEqual(self.request("GET").json()["data"], {"list": [first], "total": 1})
        self.assertEqual(self.request("DELETE", f"/{second['id']}").json()["message"], "学习计划不存在")

    def test_jwt_ownership_ignores_supplied_user_id(self):
        row = self.create("本人的计划", user_id=2)
        for user_id in (2, 3):
            self.assertEqual(self.request("GET", user_id=user_id, params={"user_id": 1}).json()["data"],
                             {"list": [], "total": 0})
            self.assertEqual(self.request("DELETE", f"/{row['id']}", user_id=user_id).json()["message"],
                             "学习计划不存在")
        self.assertEqual(self.request("GET").json()["data"], {"list": [row], "total": 1})

    def test_content_limits_and_invalid_parameters(self):
        for content in ("", " \t\r\n "):
            self.assertEqual(self.request("POST", json={"content": content}).json()["message"], "计划内容不能为空")
        self.assertEqual(self.request("POST", json={"content": "学" * (STUDY_PLAN_MAX_LENGTH + 1)}).json()["message"],
                         f"计划内容不能超过{STUDY_PLAN_MAX_LENGTH}字")
        self.create("学" * STUDY_PLAN_MAX_LENGTH)
        for payload in ({}, {"content": None}, {"content": 123}):
            self.assertEqual(self.request("POST", json=payload).status_code, 422)
        for params in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
            self.assertEqual(self.request("GET", params=params).status_code, 422)
        self.assertEqual(self.request("GET").json()["data"]["total"], 1)

    def test_all_endpoints_require_active_login(self):
        for method, suffix, kwargs in (("GET", "", {}), ("POST", "", {"json": {"content": "计划"}}),
                                      ("DELETE", "/1", {})):
            for headers in ({}, {"Authorization": "Bearer invalid"}):
                self.assertEqual(self.client.request(method, f"/api/study-plans{suffix}", headers=headers, **kwargs).status_code, 401)
            for user_id in (4, 999):
                self.assertEqual(self.request(method, suffix, user_id=user_id, **kwargs).status_code, 401)


if __name__ == "__main__":
    unittest.main()
