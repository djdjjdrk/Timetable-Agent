import json
import logging
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.common.exceptions import BusinessException
from app.config import settings
from app.schemas.chat import ChatMessage
from datetime import date
from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError
from app.common.exceptions import BusinessException
from app.config import settings
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是校园课程智能助手，使用中文回答。
今天是 {today}。本周按周一至周日计算。
将相对日期换算为明确日期；日期含义不明确时，先询问用户。
回答规则：
1. 查询个人课表时，必须使用可用的课表查询工具，
   只根据本轮查询结果回答，不编造课程。
2. 查询失败时明确说明失败，不能解释为没有课程。
3. 查询成功且没有符合条件的课程时，说明没有课程安排。
4. 列出日期、节次、课程和地点，按日期、节次排序。
5. 闲聊直接回答；缺少相应实时查询能力时，说明无法实时查询。
"""


def _build_model() -> ChatOpenAI:
    """根据配置创建模型的客户端请求，此时尚未发送实际的对话请求"""

    # 缺少密钥时立即提示配置问题，避免到远端调用时才失败
    if not settings.LLM_API_KEY.strip():
        raise BusinessException(message="未配置 LLM_API_KEY，请先填写模型密钥")
    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,  # type: ignore
        temperature=0.3,
        extra_body={"thinking": {"type": "disabled"}},
    )


async def _load_mcp_tools(authorization: str):
    """加载绑定本次JWT请求凭证的MCP工具"""
    client = MultiServerMCPClient(
        {
            "campus": {  # 本地连接别名，必须与 get_tools 的 server_name 一致
                "transport": "streamable_http",
                "url": f"http://{settings.MCP_HOST}:{settings.MCP_PORT}{settings.MCP_PATH}",
                "headers": {"Authorization": authorization},
            }
        }
    )
    try:
        # 这里只加载工具定义；具体选哪个工具、传什么参数，交给 Agent 决定
        return await client.get_tools(server_name="campus")
    except Exception as exc:
        logger.exception("加载 campus MCP 工具失败")
        raise BusinessException(
            message="加载课表工具失败，请检查 MCP 服务和后端日志"
        ) from exc


def _build_messages(history: list[ChatMessage], question: str) -> list[BaseMessage]:
    """根据历史对话构建模型请求"""
    # 接口角色已由 Literal 校验；按角色选择消息类，保留用户与助手的发言身份
    message_types = {"user": HumanMessage, "assistant": AIMessage}
    messages = [message_types[item.role](content=item.content) for item in history]
    # 当前问题必须排在历史之后，避免模型把旧问题当作本次需要处理的问题
    return [*messages, HumanMessage(content=question)]


def _read_result(messages: list[BaseMessage]) -> dict:
    """读取模型的最终的回复，收集请求的工具名+最终的回复消息，回复格式：
    {"answer": "你好，我是 campus-course-agent，我可以帮助你查询课表",
     "tools_used": ["get_my_schedules"]}
    """
    last_message = messages[-1] if messages else None
    # 只接受本轮最后一条无工具调用的助手消息，避免误取中间消息
    if not isinstance(last_message, AIMessage) or last_message.tool_calls:
        raise BusinessException(message="助手未生成最终回答，请重新提问")
    # text 兼容字符串正文与文本块；去掉首尾空白后再检查
    answer = last_message.text.strip()
    if not answer:
        raise BusinessException(message="助手未生成最终回答，请重新提问")
    # 同一工具可能被重复调用；按首次出现顺序去重，只返回名称清单
    tools_used = list(
        dict.fromkeys(
            call["name"]
            for message in messages
            if isinstance(message, AIMessage)
            for call in message.tool_calls
        )
    )
    # dict.fromkeys({"get_my_shedules": None}) -> ["get_my_shedules"]
    return {"answer": answer, "tools_used": tools_used}


async def ask(question: str, history: list[ChatMessage], authorization: str) -> dict:
    """根据历史对话构建模型请求，加载MCP工具，创建本次请求的Agent，发送请求，返回模型回复"""
    model = _build_model()
    tools = await _load_mcp_tools(authorization)
    if not tools:
        raise BusinessException(
            message="MCP未返回任何可用的 tool，请检查 MCP 服务和后端日志"
        )
    agent = create_agent(
        model, tools, system_prompt=SYSTEM_PROMPT.format(today=date.today().isoformat())
    )
    input_messages = _build_messages(history, question)
    try:
        result = await agent.ainvoke(
            {
                "messages": input_messages,  # type: ignore
            },
            config={"recursion_limit": settings.AGENT_RECURSION_LIMIT},
        )
        logger.info("大模型输出的结果：%s", result)
    except GraphRecursionError as exc:
        logger.exception("Agent 达到了图步骤达到上限")
        raise BusinessException(
            message="本次处理的步骤过多，请缩小问题范围重试"
        ) from exc
    except Exception as exc:
        logger.exception("模型调用失败")
        raise BusinessException(
            message="模型调用失败，请检查模型服务和后端日志"
        ) from exc
    new_messages = result["messages"][len(input_messages) :]
    return _read_result(new_messages)


def _sse(event_type: str, data: dict) -> str:
    """将事件类型和数据编码为一条 SSE 消息。"""
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def stream_ask(question: str, history: list[ChatMessage], authorization: str):
    """执行 Agent，并依次返回处理状态、工具过程和回答。"""
    try:
        yield _sse("status", {"message": "正在加载课表工具"})
        model = _build_model()
        # 工具按本次 JWT 加载，查询身份仍由 MCP 确定。
        tools = await _load_mcp_tools(authorization)
        # 没有工具时停止，避免模型假装已完成课表查询。
        if not tools:
            raise BusinessException(message="MCP 未返回可用工具，请检查 MCP 服务")

        agent = create_agent(
            model,
            tools,
            system_prompt=SYSTEM_PROMPT.format(today=date.today().isoformat()),
        )
        messages = _build_messages(history, question)
        model_messages = []
        yield _sse("status", {"message": "正在生成回答"})
        async for event in agent.astream_events(
            {"messages": messages},  # type: ignore
            version="v2",
            config={"recursion_limit": settings.AGENT_RECURSION_LIMIT},
        ):  # type: ignore
            kind = event["event"]
            # 模型生成中的文字用于即时显示；工具参数不作为正文显示。
            if kind == "on_chat_model_stream":
                text = event["data"]["chunk"].text
                if text:
                    yield _sse("token", {"content": text})
            # 工具开始和返回只展示过程，返回不等于业务查询成功。
            elif kind == "on_tool_start":
                yield _sse("tool_start", {"name": event["name"]})
            elif kind == "on_tool_end":
                yield _sse("tool_end", {"name": event["name"]})
            # 每次模型调用结束后收集完整消息，复用第 08 节的最终答案检查。
            elif kind == "on_chat_model_end":
                model_messages.append(event["data"]["output"])

        result = _read_result(model_messages)
        yield _sse("done", result)
    except GraphRecursionError:
        logger.exception("流式 Agent 执行步数达到上限")
        yield _sse("error", {"message": "本次处理的步骤过多，请缩小问题范围重试"})
    except BusinessException as exc:
        logger.warning("流式对话业务失败：%s", exc.message)
        yield _sse("error", {"message": exc.message})
    except Exception:
        # 响应已经开始，错误也通过 SSE 返回，具体异常保留在日志中。
        logger.exception("流式 Agent 执行失败")
        yield _sse("error", {"message": "对话处理失败，请检查后端日志"})
