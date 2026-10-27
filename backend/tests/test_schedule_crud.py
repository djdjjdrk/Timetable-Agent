"""课表接口回归：真实 JWT、SQLite 外键约束和隔离数据。"""

from datetime import date
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
from app.config import settings
from app.database import Base, get_db
from app.models import Course, Schedule, User
from app.services import schedule_service
from app.utils.jwt import create_access_token


class ScheduleCrudTests(unittest.TestCase):
    def setUp(self):
        secret = patch.object(settings, "JWT_SECRET_KEY", "schedule-tests-only-secret-key-32-characters")
        secret.start()
        self.addCleanup(secret.stop)
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(engine.dispose)

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine)
        with self.session_factory() as db:
            for user_id, username, role, status in (
                (1, "admin", "admin", 1), (2, "aaa", "student", 1),
                (3, "bbb", "student", 1), (4, "disabled", "student", 0),
            ):
                db.add(User(id=user_id, username=username, name=username,
                            password="unused", role=role, status=status))
            for course_id, name, code in (
                (1, "大学英语", "ENG101"), (2, "数据结构", "DS101"),
                (3, "高等数学", "MATH101"),
            ):
                db.add(Course(id=course_id, name=name, code=code, status=1))
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
        return self.client.request(method, f"/api/schedules{suffix}",
            headers={"Authorization": f"Bearer {create_access_token(user_id)}"}, **kwargs)

    def create(self, **payload):
        body = self.request("POST", json={
            "user_id": 2, "course_id": 1, "class_date": "2026-10-21",
            "period": "1-2节", "location": "教学楼 A201", **payload,
        }).json()
        self.assertEqual(body["code"], 200, body)
        return body["data"]

    def test_crud_joined_fields_and_partial_update(self):
        row = self.create(period=" 1-2节 ", location=" 教学楼 A201 ")
        self.assertEqual((row["username"], row["user_name"], row["course_name"]),
                         ("aaa", "aaa", "大学英语"))
        self.assertEqual((row["period"], row["location"]), ("1-2节", "教学楼 A201"))
        edited = self.request("PUT", f"/{row['id']}", json={"user_id": 3, "course_id": 2}).json()["data"]
        self.assertEqual((edited["username"], edited["course_name"], edited["class_date"]),
                         ("bbb", "数据结构", "2026-10-21"))
        self.assertEqual(self.request("PUT", f"/{row['id']}", json={"period": None}).json()["data"], edited)
        self.assertEqual(self.request("DELETE", f"/{row['id']}").json()["code"], 200)
        self.assertEqual(self.request("GET").json()["data"], {"list": [], "total": 0})

    def test_admin_filters_pagination_and_student_isolation(self):
        self.create()
        second = self.create(course_id=2, class_date="2026-10-22", period="3-4节")
        third = self.create(course_id=3, class_date="2026-10-23")
        self.assertEqual(self.request("GET", user_id=3).json()["data"], {"list": [], "total": 0})
        self.create(user_id=3)
        for params in ({}, {"user_id": 3}, {"user_id": 1}):
            data = self.request("GET", user_id=2, params=params).json()["data"]
            self.assertEqual(data["total"], 3)
            self.assertTrue(all(row["user_id"] == 2 for row in data["list"]))
        data = self.request("GET", params={"user_id": 2, "page_size": 1, "page": 2}).json()["data"]
        self.assertEqual(data, {"list": [second], "total": 3})
        self.assertEqual(self.request("GET", params={"user_id": 2, "date": "2026-10-23"}).json()["data"],
                         {"list": [third], "total": 1})
        self.assertEqual(self.request("GET", user_id=2, params={"date": "2026-10-22"}).json()["data"],
                         {"list": [second], "total": 1})
        self.assertEqual(self.request("GET").json()["data"]["total"], 4)
        self.assertEqual(self.request("GET", params={"page": 99}).json()["data"], {"list": [], "total": 4})

    def test_invalid_relations_and_missing_schedule(self):
        row = self.create()
        for payload, message in (({"user_id": 999}, "用户不存在"),
                                 ({"user_id": 1}, "只能给学生安排课表"),
                                 ({"course_id": 999}, "课程不存在")):
            full = {"user_id": 2, "course_id": 1, "class_date": "2026-10-21",
                    "period": "1-2节", "location": "A201", **payload}
            self.assertEqual(self.request("POST", json=full).json()["message"], message)
            self.assertEqual(self.request("PUT", f"/{row['id']}", json=payload).json()["message"], message)
        self.assertEqual(self.request("GET").json()["data"], {"list": [row], "total": 1})
        for method, kwargs in (("PUT", {"json": {}}), ("DELETE", {})):
            self.assertEqual(self.request(method, "/999", **kwargs).json()["message"], "课表不存在")

    def test_validation_rejects_bad_dates_paging_and_text(self):
        row = self.create()
        for payload in ({"class_date": "2026-02-30"}, {"period": " "}, {"period": "x" * 51},
                        {"location": " "}, {"location": "x" * 101}):
            full = {"user_id": 2, "course_id": 1, "class_date": "2026-10-21",
                    "period": "1-2节", "location": "A201", **payload}
            self.assertEqual(self.request("POST", json=full).status_code, 422)
            self.assertEqual(self.request("PUT", f"/{row['id']}", json=payload).status_code, 422)
        for params in ({"page": 0}, {"page_size": 0}, {"page_size": 101}, {"date": "invalid"}):
            self.assertEqual(self.request("GET", params=params).status_code, 422)
        self.assertEqual(self.request("GET").json()["data"]["list"], [row])

    def test_authentication_and_student_write_protection(self):
        row = self.create()
        for method, suffix, kwargs in (("GET", "", {}), ("POST", "", {"json": {}}),
                                      ("PUT", f"/{row['id']}", {"json": {}}),
                                      ("DELETE", f"/{row['id']}", {})):
            for user_id in (4, 999):
                self.assertEqual(self.request(method, suffix, user_id=user_id, **kwargs).status_code, 401)
            for headers in ({}, {"Authorization": "Bearer invalid"}):
                self.assertEqual(self.client.request(method, f"/api/schedules{suffix}", headers=headers, **kwargs).status_code, 401)
            if method != "GET":
                self.assertEqual(self.request(method, suffix, user_id=2, **kwargs).json()["code"], 403)
        self.assertEqual(self.request("GET").json()["data"]["list"], [row])

    def test_linked_course_delete_blocked_until_schedule_removed(self):
        row = self.create(course_id=2)
        headers = {"Authorization": f"Bearer {create_access_token(1)}"}
        body = self.client.delete("/api/courses/2", headers=headers).json()
        self.assertEqual(body["message"], "该课程已关联课表，无法删除")
        self.assertEqual(self.request("GET").json()["data"]["total"], 1)
        self.request("DELETE", f"/{row['id']}")
        self.assertEqual(self.client.delete("/api/courses/2", headers=headers).json()["code"], 200)

    def test_full_list_service_for_future_mcp(self):
        row = self.create()
        self.create(user_id=3, class_date="2026-10-22")
        with self.session_factory() as db:
            rows = schedule_service.list_schedules(db, user_id=2, class_date=date(2026, 10, 21))
            self.assertEqual([item.model_dump(mode="json") for item in rows], [row])
            self.assertEqual(len(schedule_service.list_schedules(db)), 2)


if __name__ == "__main__":
    unittest.main()
