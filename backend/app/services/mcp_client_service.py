import json
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.common.exceptions import BusinessException
from app.config import settings


async def call_get_my_schedules(authorization: str, date: str | None = None) -> dict:
    """调用MCP服务的客户端"""
    # 1 建client  这是固定的模板
    client = MultiServerMCPClient(
        {
            "campus": {
                "transport": "streamable_http",
                "url": f"http://{settings.MCP_HOST}:{settings.MCP_PORT}{settings.MCP_PATH}",  # http://127.0.0.1:8001/mcp
                "headers": {"Authorization": authorization},
            }
        }
    )
    # 2. 拿tool
    tools = await client.get_tools(server_name="campus")
    tool = next((t for t in tools if t.name == "get_my_schedules"), None)
    if tool is None:
        raise BusinessException(
            message="未找到工具【get_my_schedules】，请确认MCP服务是否正常启动"
        )
    # 3. 调用tool
    payload = {}
    if date:
        payload["date"] = date
    result = await tool.ainvoke(payload)

    return json.loads(result[0]["text"])
