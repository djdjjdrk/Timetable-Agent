"""真实模型、HTTP MCP 与 PostgreSQL 联调；临时账号和业务记录在 finally 清理。

需先启动 FastAPI、MCP、Chroma，配置模型密钥。会调用外部模型并产生少量费用。
从 backend 运行：python scripts/smoke_study_plan_agent.py
"""

import asyncio
from datetime import date, timedelta
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from sqlalchemy import delete, select

from app.config import settings
from app.database import SessionLocal
from app.models import Course, Schedule, StudyPlan, User
from app.utils.jwt import create_access_token


async def main():
    user_id = course_id = None
    try:
        with SessionLocal() as db:
            user = User(username=f"smoke_{uuid4().hex[:16]}", name="联调临时学生",
                        password="unused-no-login", role="student", status=1)
            course = Course(name="数据结构联调课程", status=1)
            db.add_all([user, course])
            db.flush()
            user_id, course_id = user.id, course.id
            db.add(Schedule(user_id=user_id, course_id=course_id,
                            class_date=date.today() + timedelta(days=1),
                            period="1-2节", location="联调教室"))
            db.commit()
        auth = f"Bearer {create_access_token(user_id)}"
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=180) as client:
            response = await client.post("/api/chat/ask", headers={"Authorization": auth},
                json={"question": "请给我一个100字以内的链表复习计划，只规划，不要保存。", "history": []})
            response.raise_for_status()
            body = response.json()
            assert body["code"] == 200, body
            assert "save_study_plan" not in body["data"]["tools_used"], body
            with SessionLocal() as db:
                assert not db.scalar(select(StudyPlan).where(StudyPlan.user_id == user_id))
            print("PASS: 普通聊天只规划，不写数据库", flush=True)

            events = []
            async with client.stream("POST", "/api/chat/stream", headers={"Authorization": auth},
                json={"question": "查询我明天的课表，并检索课程资料中的链表知识。根据查到的课表和资料制定一个200字以内的课后复习计划，并保存这个学习计划。资料没找到也可保存通用计划，请说明依据。", "history": []}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
            assert not [e for e in events if e["type"] == "error"], events
            done = next(e for e in events if e["type"] == "done")
            assert {"get_my_schedules", "search_course_docs", "save_study_plan"} <= set(done["tools_used"]), done
            with SessionLocal() as db:
                rows = db.scalars(select(StudyPlan).where(StudyPlan.user_id == user_id)).all()
                assert len(rows) == 1 and rows[0].turn_id, [(r.id, r.turn_id) for r in rows]
                turn_id = rows[0].turn_id
            print("PASS: 流式聊天调用三个工具，仅落库一条计划", flush=True)

            # 同轮重复调用通过真实 HTTP 请求头进入工具，仍应被拒绝。
            transport = StreamableHttpTransport(
                f"http://{settings.MCP_HOST}:{settings.MCP_PORT}{settings.MCP_PATH}",
                headers={"Authorization": auth, "X-Chat-Turn-Id": turn_id})
            async with Client(transport) as mcp:
                result = await mcp.call_tool("save_study_plan", {"content": "不应再次保存"})
                data = result.data
                assert data["ok"] is False and "本轮已保存" in data["error"], data
            plans = (await client.get("/api/study-plans", headers={"Authorization": auth})).json()
            assert plans["data"]["total"] == 1, plans
            print("PASS: HTTP MCP 重复调用被拒绝，学习计划页面 API 可查询记录", flush=True)
            print(json.dumps({"tools_used": done["tools_used"], "answer": done["answer"]}, ensure_ascii=False), flush=True)
    finally:
        with SessionLocal() as db:
            if user_id is not None:
                db.execute(delete(StudyPlan).where(StudyPlan.user_id == user_id))
                db.execute(delete(Schedule).where(Schedule.user_id == user_id))
                db.execute(delete(User).where(User.id == user_id))
            if course_id is not None:
                db.execute(delete(Course).where(Course.id == course_id))
            db.commit()
        print("CLEANUP: 已清理临时账号、课程、课表和学习计划", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
