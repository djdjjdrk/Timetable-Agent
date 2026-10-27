"""Export the actual API routes for Apifox without starting the app or touching its DB."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Generic, TypeVar

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
# Documentation generation never needs production credentials or a DB connection.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "documentation-export-only-not-a-real-secret"

from fastapi import FastAPI  # noqa: E402
from fastapi.openapi.models import OpenAPI  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from pydantic import BaseModel, TypeAdapter  # noqa: E402

from app.api import api  # noqa: E402
from app.common.response import Response  # noqa: E402
from app.dependencies.auth import get_current_admin  # noqa: E402
from app.schemas.auth import LoginResponse  # noqa: E402
from app.schemas.course import CourseResponse  # noqa: E402
from app.schemas.schedule import ScheduleResponse  # noqa: E402
from app.schemas.study_plan import StudyPlanResponse  # noqa: E402
from app.schemas.user import UserResponse  # noqa: E402

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: int
    message: str
    data: T


class Page(BaseModel, Generic[T]):
    list: list[T]
    total: int


class UploadResponse(BaseModel):
    original_name: str
    disk_name: str
    size: int | None
    url: str


# Names/descriptions and success payloads supplement the route's real request models.
OPERATIONS = {
    "login": ("登录", LoginResponse),
    "register": ("注册学生账号", type(None)),
    "get_user_list": ("分页查询用户（管理员）", Page[UserResponse]),
    "get_user_info": ("获取我的资料", UserResponse),
    "update_user_info": ("修改我的资料", UserResponse),
    "update_password": ("修改我的密码", type(None)),
    "create_user": ("新增用户（管理员）", UserResponse),
    "update_user": ("修改用户（管理员）", UserResponse),
    "delete_user": ("删除用户（管理员）", type(None)),
    "list_courses": ("查询课程列表（管理员）", list[CourseResponse]),
    "get_course": ("查询课程详情（管理员）", CourseResponse),
    "create_course": ("新增课程（管理员）", CourseResponse),
    "update_course": ("修改课程（管理员）", CourseResponse),
    "delete_course": ("删除课程（管理员）", type(None)),
    "list_page_schedules": ("分页查询课表", Page[ScheduleResponse]),
    "create_schedule": ("新增课表（管理员）", ScheduleResponse),
    "update_schedule": ("修改课表（管理员）", ScheduleResponse),
    "delete_schedule": ("删除课表（管理员）", type(None)),
    "get_my_page_plans": ("分页查询我的学习计划", Page[StudyPlanResponse]),
    "create_plan": ("保存我的学习计划", StudyPlanResponse),
    "delete_plan": ("删除我的学习计划", type(None)),
    "upload": ("上传文件", UploadResponse),
}

EXAMPLES = {
    "login": {"username": "demo_user", "password": "Demo12345"},
    "register": {"username": "demo_user", "password": "Demo12345", "name": "示例学生"},
    "create_user": {"username": "apifox_student_001", "password": "Test123456", "name": "联调学生", "role": "student", "status": 1},
    "update_user": {"name": "联调学生", "status": 1},
    "update_user_info": {"name": "我的姓名", "email": "student@example.com"},
    "update_password": {"old_password": "Demo12345", "new_password": "NewDemo12345"},
    "create_course": {"name": "示例课程", "code": "DEMO101", "description": "Apifox 调试示例", "status": 1},
    "update_course": {"name": "示例课程（已修改）", "status": 1},
    "create_schedule": {"user_id": 2, "course_id": 1, "class_date": "2026-10-24", "period": "1-2节", "location": "教学楼 A201"},
    "update_schedule": {"class_date": "2026-10-25", "period": "3-4节", "location": "教学楼 B305"},
    "create_plan": {"content": "## 今日学习计划\n- 复习英语单词\n- 完成数据结构练习"},
}

NOTES = {
    "login": "JSON 登录，成功后复制 data.token。示例账号并非系统预置账号，请替换为自己的账号。",
    "register": "账号为 3～20 位字母、数字或下划线。密码 8～20 位，至少含字母和数字，仅允许可见 ASCII 字符且不能有空格。注册角色固定为 student。",
    "update_user_info": "只更新 name、email、phone、avatar；role、status、password 即使提交也会忽略，null 字段保持原值。",
    "update_password": "检查原密码及新旧密码不同；当前实现没有注册接口的密码复杂度校验。",
    "create_user": "账号去除首尾空白后为 1～50 位；密码 3～10 位，省略时默认 123。",
    "update_user": "不可修改账号；非空密码为 3～10 位，省略、空字符串或 null 保留原密码。",
    "delete_user": "不能删除当前登录管理员。删除操作立即生效。",
    "delete_course": "课程已关联课表时禁止删除。",
    "list_page_schedules": "学生只能查本人，传其他 user_id 也会忽略；管理员不传 user_id 时查全部。date 为 YYYY-MM-DD。结果按 ID 倒序。",
    "create_schedule": "user_id 必须是学生 ID，course_id 必须是已有课程 ID；示例 ID 和日期请按实际修改。",
    "update_schedule": "省略或传 null 的字段保持原值。user_id 必须是学生 ID。",
    "get_my_page_plans": "仅返回当前用户本人的学习计划，按 ID 倒序。",
    "create_plan": "content 去除首尾空白后不能为空，最多 2000 字；支持 Markdown。",
    "delete_plan": "只能删除本人的计划，他人的或不存在的记录都提示学习计划不存在。",
    "upload": "无需登录。Body 使用 multipart/form-data，file 字段选择本地文件。上限 100 MB；允许 jpg/jpeg/png/gif/webp/pdf/doc/docx/xls/xlsx/zip。成功后可通过服务地址加 data.url 访问文件。",
}


def has_dependency(dependant, target):
    return dependant.call is target or any(
        has_dependency(child, target) for child in dependant.dependencies
    )


def build_document(server: str) -> dict:
    app = FastAPI(
        title="Timetable Agent 课表管理 API",
        version="1.0.0",
        description=(
            "可直接导入 Apifox。选择本地开发环境，先调用登录接口，再将 data.token 填入 Bearer Auth。\n\n"
            "统一返回 {code, message, data}。HTTP 200 也可能是业务失败，应同时检查 code；"
            "code=200 成功，默认 500 为业务失败，403 为非管理员。"
            "未登录 HTTP 401，参数校验 HTTP 422，内部错误 HTTP 500。\n\n"
            "示例账号、ID 和日期均为占位示例，请按实际修改。"
        ),
        servers=[{"url": server, "description": "本地开发环境"}],
    )
    routes = [r for r in api.routes if isinstance(r, APIRoute)]
    # Fail visibly when an endpoint is added, so its response documentation is reviewed.
    assert {r.name for r in routes} == set(OPERATIONS), "接口发生变化，请更新 OPERATIONS"
    for route in routes:
        summary, payload = OPERATIONS[route.name]
        description = NOTES.get(route.name, route.endpoint.__doc__ or "")
        if has_dependency(route.dependant, get_current_admin):
            description += "\n\n权限：管理员。学生请求会返回 HTTP 200、业务 code=403。"
        app.add_api_route(
            route.path, route.endpoint, methods=sorted(route.methods),
            dependencies=route.dependencies,
            response_model=Envelope[payload],
            tags=[route.tags[-1]], summary=summary, description=description,
            operation_id=route.name,
        )

    @app.get("/", response_model=Response, tags=["服务检查"], summary="检查服务状态", operation_id="health_check")
    def root():
        return Response.success(message="Hello FastAPI")

    document = app.openapi()
    # The app accepts JSON credentials, not the OAuth2 form/password flow advertised
    # by OAuth2PasswordBearer's default schema. Document its actual Bearer usage.
    document["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT",
                       "description": "填写登录响应 data.token，不要重复添加 Bearer 前缀。"}
    }
    error_response = {
        "description": "失败响应，具体原因见 message",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Response"}}},
    }
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            name = operation["operationId"]
            secured = bool(operation.get("security"))
            operation["security"] = [{"BearerAuth": []}] if secured else []
            if secured:
                operation["responses"]["401"] = {
                    **error_response, "description": "未登录、Token 无效/过期或账号被禁用",
                }
            if "422" in operation["responses"]:
                operation["responses"]["422"] = {
                    **error_response, "description": "参数校验失败，统一返回 code=422、message、data=null",
                }
            operation["responses"]["500"] = {**error_response, "description": "服务器内部错误"}
            operation["responses"]["200"]["description"] = "请求已处理；同时检查业务 code，200 才表示成功"
            if name in EXAMPLES:
                example = EXAMPLES[name]
                source = next(r for r in routes if r.name == name)
                TypeAdapter(source.body_field.type_).validate_python(example)
                operation["requestBody"]["content"]["application/json"]["example"] = example
            for parameter in operation.get("parameters", []):
                key = parameter["name"]
                values = {"page": 1, "page_size": 10, "date": "2026-10-24", "keywords": "示例", "user_id": 2, "course_id": 1, "schedule_id": 1, "plan_id": 1}
                if key in values:
                    parameter["example"] = values[key]
    OpenAPI.model_validate(document)
    validate_refs(document, document)
    return document


def validate_refs(value, document):
    if isinstance(value, dict):
        if "$ref" in value:
            assert value["$ref"].startswith("#/"), "只允许本地引用"
            node = document
            for part in value["$ref"][2:].split("/"):
                node = node[part.replace("~1", "/").replace("~0", "~")]
        for child in value.values():
            validate_refs(child, document)
    elif isinstance(value, list):
        for child in value:
            validate_refs(child, document)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=BACKEND.parent / "docs" / "apifox-openapi.json")
    args = parser.parse_args()
    document = build_document(args.server.rstrip("/"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    count = sum(len(methods) for methods in document["paths"].values())
    print(f"Exported {count} operations to {args.output}")
