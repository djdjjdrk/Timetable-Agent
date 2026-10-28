"""真实 JWT + 隔离数据库验证 MCP 写入边界，不调用外部模型或业务库。"""

import asyncio
import re
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import mcp_server
from app.config import settings, STUDY_PLAN_MAX_LENGTH
from app.database import Base
from app.models import StudyPlan, User
from app.schemas.study_plan import StudyPlanCreateRequest
from app.services import agent_service
from app.services.study_plan_service import create_study_plan
from app.utils.jwt import create_access_token


class McpStudyPlanTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            for user_id, status in ((1, 1), (2, 1), (3, 0)):
                db.add(User(id=user_id, username=f"user{user_id}", name="测试学生",
                            password="unused", role="student", status=status))
            db.commit()
        for target, value in (
            ("mcp_server.SessionLocal", self.factory),
            ("app.dependencies.mcp_auth.SessionLocal", self.factory),
        ):
            mocked = patch(target, value)
            mocked.start()
            self.addCleanup(mocked.stop)
        secret = patch.object(settings, "JWT_SECRET_KEY", "mcp-tests-only-secret-key-at-least-32-characters")
        secret.start()
        self.addCleanup(secret.stop)
        self.headers = {"authorization": f"Bearer {create_access_token(1)}",
                        "x-chat-turn-id": "a" * 32}
        headers = patch("mcp_server.get_http_headers", side_effect=lambda **_: self.headers)
        headers.start()
        self.addCleanup(headers.stop)

    def rows(self):
        with self.factory() as db:
            return list(db.scalars(select(StudyPlan)).all())

    def test_save_duplicate_and_user_isolation(self):
        result = mcp_server.save_study_plan("  ## 本周计划\n- 复习链表  ")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["content"], "## 本周计划\n- 复习链表")
        self.assertIn("本轮已保存", mcp_server.save_study_plan("不同正文")["error"])
        self.headers["authorization"] = f"Bearer {create_access_token(2)}"
        self.assertTrue(mcp_server.save_study_plan("学生二的计划")["ok"])
        self.assertEqual([(r.user_id, r.turn_id) for r in self.rows()], [(1, "a" * 32), (2, "a" * 32)])
        self.headers["x-chat-turn-id"] = "b" * 32
        self.assertTrue(mcp_server.save_study_plan("下一轮")["ok"])

    def test_validation_failure_does_not_consume_turn(self):
        for content in ("  ", "学" * (STUDY_PLAN_MAX_LENGTH + 1)):
            self.assertFalse(mcp_server.save_study_plan(content)["ok"])
        self.assertEqual(self.rows(), [])
        self.assertTrue(mcp_server.save_study_plan("修正后的计划")["ok"])

    def test_invalid_headers_and_inactive_users(self):
        for turn_id in ("", "x" * 32, "A" * 32, "a" * 33):
            self.headers["x-chat-turn-id"] = turn_id
            self.assertFalse(mcp_server.save_study_plan("计划")["ok"])
        self.headers["x-chat-turn-id"] = "a" * 32
        for user_id in (3, 999):
            self.headers["authorization"] = f"Bearer {create_access_token(user_id)}"
            self.assertFalse(mcp_server.save_study_plan("计划")["ok"])
        for authorization in ("", "Bearer invalid"):
            self.headers["authorization"] = authorization
            self.assertFalse(mcp_server.save_study_plan("计划")["ok"])
        self.assertEqual(self.rows(), [])

    def test_database_constraint_and_manual_null_turns(self):
        with self.factory() as db:
            user = db.get(User, 1)
            data = StudyPlanCreateRequest(content="手动保存")
            create_study_plan(db, user, data)
            create_study_plan(db, user, data)
            create_study_plan(db, user, data, turn_id="a" * 32)
            with self.assertRaises(IntegrityError):
                create_study_plan(db, user, data, turn_id="a" * 32)
            db.rollback()
        self.assertEqual(len(self.rows()), 3)

    def test_commit_succeeded_but_confirmation_lost(self):
        def save_then_fail(*args, **kwargs):
            create_study_plan(*args, **kwargs)
            raise RuntimeError("private database details")
        with patch("mcp_server.create_study_plan", side_effect=save_then_fail):
            result = mcp_server.save_study_plan("已提交")
        self.assertIn("本轮已保存", result["error"])
        self.assertNotIn("private", str(result))
        self.assertFalse(mcp_server.save_study_plan("再次调用")["ok"])
        self.assertEqual(len(self.rows()), 1)

    def test_failed_write_can_retry_and_uncertain_status_is_safe(self):
        with patch("mcp_server.create_study_plan", side_effect=RuntimeError("private")):
            self.assertIn("保存学习计划失败", mcp_server.save_study_plan("计划")["error"])
        self.assertTrue(mcp_server.save_study_plan("重试")["ok"])
        # 第一轮 Session 与结果核对连接都故障。
        with patch("mcp_server.SessionLocal", side_effect=RuntimeError("private")):
            result = mcp_server.save_study_plan("计划")
        self.assertIn("保存状态不确定", result["error"])
        self.assertNotIn("private", str(result))

    def test_authentication_faults_do_not_leak_database_details(self):
        with patch("mcp_server._current_user_id", side_effect=RuntimeError("private")):
            for tool, args in ((mcp_server.get_my_schedules, ()),
                               (mcp_server.search_course_docs, ("问题",)),
                               (mcp_server.save_study_plan, ("计划",))):
                result = tool(*args)
                self.assertIn("error", result)
                self.assertNotIn("private", str(result))

    def test_tool_schema_exposes_only_content(self):
        async def inspect_tools():
            from fastmcp import Client
            async with Client(mcp_server.mcp) as client:
                tools = await client.list_tools()
                tool = next(tool for tool in tools if tool.name == "save_study_plan")
                self.assertEqual(set(tool.inputSchema["properties"]), {"content"})
                self.assertEqual(tool.inputSchema["required"], ["content"])
        asyncio.run(inspect_tools())


class AgentTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_client_receives_authorization_and_fixed_turn(self):
        with patch.object(agent_service, "MultiServerMCPClient") as client:
            client.return_value.get_tools = AsyncMock(return_value=["tool"])
            await agent_service._load_mcp_tools("Bearer test", "a" * 32)
            headers = client.call_args.args[0]["campus"]["headers"]
            self.assertEqual(headers, {"Authorization": "Bearer test", "X-Chat-Turn-Id": "a" * 32})

    async def test_normal_and_streaming_requests_generate_independent_turns(self):
        class FakeAgent:
            async def ainvoke(self, *_args, **_kwargs):
                return {"messages": [AIMessage(content="已给出计划")]}

            async def astream_events(self, *_args, **_kwargs):
                yield {"event": "on_chat_model_end", "data": {"output": AIMessage(content="已给出计划")}}

        with patch.object(agent_service, "_build_model"), \
             patch.object(agent_service, "_load_mcp_tools", new_callable=AsyncMock, return_value=["tool"]) as load, \
             patch.object(agent_service, "create_agent", return_value=FakeAgent()):
            # 为普通入口保留输入消息，模拟 LangGraph 的累计消息返回。
            agent = FakeAgent()
            async def invoke(payload, **_kwargs):
                return {"messages": [*payload["messages"], AIMessage(content="已给出计划")]}
            agent.ainvoke = invoke
            with patch.object(agent_service, "create_agent", return_value=agent):
                await agent_service.ask("规划一下", [], "Bearer test")
                events = [event async for event in agent_service.stream_ask("规划一下", [], "Bearer test")]
            self.assertTrue(any('"type": "done"' in event for event in events))
            self.assertEqual(load.await_count, 2)
            turns = [call.args[1] for call in load.await_args_list]
            self.assertTrue(all(re.fullmatch(r"[0-9a-f]{32}", turn) for turn in turns))
            self.assertNotEqual(turns[0], turns[1])


if __name__ == "__main__":
    unittest.main()
