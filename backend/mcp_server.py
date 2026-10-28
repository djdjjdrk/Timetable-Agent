import logging
import re
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from pydantic import Field
from sqlalchemy import select
from app.common.exceptions import BusinessException
from app.config import settings
from app.database import SessionLocal
from app.dependencies.mcp_auth import user_id_form_authorization
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.schemas.study_plan import StudyPlanCreateRequest
from app.services.study_plan_service import create_study_plan
from app.services import rag_service
from app.services.schedule_service import list_schedules_as_dict

mcp = FastMCP("campus-course-agent")
logger = logging.getLogger(__name__)


def _current_user_id() -> int:
    """从当前的HTTP的请求头拿到authorization 然后解析出 user_id"""

    headers = get_http_headers(include_all=True) or {}
    auth = headers.get("authorization") or headers.get("Authorization")
    return user_id_form_authorization(auth)  # type: ignore


@mcp.tool()
def get_my_schedules(
    date: Annotated[
        str | None,
        Field(
            description="可选的上课日期，格式为 YYYY-MM-DD；省略或传 null 时查询全部课表"
        ),
    ] = None,
) -> dict:
    """查询当前登录用户自己的课表，不能通过参数指定其他用户。
    可查询指定日期或全部课表，不支持日期范围参数。
    查询一周等日期范围时，可省略 date 获取全部课表，再按目标日期范围筛选。
    成功返回 items 和 count；每条记录包含 date、period、course_id、
    course_name 和 location，分别表示上课日期、节次、课程 ID、课程名称和地点。
    失败返回 error 和空 items；含 error 时表示查询失败，不能解释为没有课程。
    """
    try:
        user_id = _current_user_id()
        db = SessionLocal()
        try:
            items = list_schedules_as_dict(db, user_id, date)
            return {"items": items, "count": len(items)}
        finally:
            db.close()
    except BusinessException as exc:
        return {"error": exc.message, "items": []}
    except Exception:
        logger.exception("MCP 查询课表失败")
        return {"error": "查询课表服务异常，请查看后端日志", "items": []}


@mcp.tool()
def search_course_docs(
    query: Annotated[str, Field(description="要从课程资料中检索的问题或关键词")],
) -> dict:
    """只读检索全站共享的课程资料；用户身份来自 JWT，不由模型填写。"""
    try:
        # 身份只决定是否允许检索；共享资料不按这个用户 ID 筛选。
        _current_user_id()
    except BusinessException as exc:
        return {"error": exc.message, "items": []}
    except Exception:
        logger.exception("MCP 检索工具鉴权失败")
        return {"error": "身份验证服务异常，请稍后重试", "items": []}

    result = rag_service.search_docs(query)
    # 检索失败时保留 error，避免模型把服务故障解释成资料中没有答案。
    if not result["ok"]:
        return {
            "error": result["error"],
            "items": [],
            "message": "资料检索当前不可用，请如实告知用户，不要编造资料内容。",
        }
    # 正常空结果保留说明；有片段时仅返回模型需要的 items。
    if not result["items"]:
        return {"items": [], "message": result["message"]}
    return {"items": result["items"]}


@mcp.tool()
def save_study_plan(
    content: Annotated[str, Field(description="要保存的完整学习计划正文")],
) -> dict:
    """仅在用户明确要求保存时，将计划写入当前用户的数据库。"""
    try:
        user_id = _current_user_id()
    except BusinessException as exc:
        return {"ok": False, "error": exc.message}
    except Exception:
        logger.exception("MCP 保存工具鉴权失败")
        return {"ok": False, "error": "身份验证服务异常，请稍后重试"}

    # 请求头由后端生成；模型只能填写正文，不能选择身份或轮次。
    turn_id = (get_http_headers(include_all=True) or {}).get("x-chat-turn-id", "")
    if not re.fullmatch(r"[0-9a-f]{32}", turn_id):
        return {"ok": False, "error": "缺少有效的对话轮次标识，请重新发起对话"}
    try:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user is None or user.status != 1:
                return {"ok": False, "error": "登录已失效，请重新登录"}
            existing = db.scalar(select(StudyPlan).where(
                StudyPlan.user_id == user_id, StudyPlan.turn_id == turn_id
            ))
            if existing is not None:
                return {"ok": False, "error": "本轮已保存学习计划，请勿重复保存"}
            plan = create_study_plan(
                db, user, StudyPlanCreateRequest(content=content), turn_id=turn_id
            )
            return {
                "ok": True, "id": plan.id, "content": plan.content,
                "message": "学习计划已保存，本轮不要再次调用 save_study_plan。",
            }
    except BusinessException as exc:
        return {"ok": False, "error": exc.message}
    except Exception:
        logger.exception("MCP 保存学习计划失败，user_id=%s", user_id)
        try:
            # 新连接核对：覆盖并发唯一冲突，以及提交成功但确认丢失的情况。
            with SessionLocal() as verify_db:
                saved = verify_db.scalar(select(StudyPlan).where(
                    StudyPlan.user_id == user_id, StudyPlan.turn_id == turn_id
                ))
                if saved is not None:
                    return {"ok": False, "error": "本轮已保存学习计划，请到学习计划页面核对"}
        except Exception:
            logger.exception("MCP 核对保存结果失败，user_id=%s", user_id)
            return {"ok": False, "error": "保存状态不确定，请到学习计划页面核对"}
        return {"ok": False, "error": "保存学习计划失败，请查看后端日志"}


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        path=settings.MCP_PATH,
        uvicorn_config={"ws": "websockets"},
    )
