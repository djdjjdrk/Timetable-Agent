from typing import Literal

from openai import BaseModel
from pydantic import Field


class ChatMessage(BaseModel):
    """历史消息: 用户消息或者助手消息"""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """一次提问的请求"""

    question: str = Field(min_length=1, description="用户问题")
    history: list[ChatMessage] = Field(default_factory=list)
