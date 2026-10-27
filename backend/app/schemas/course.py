from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourseCreateRequest(BaseModel):
    """新增课程的请求对象。"""

    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = None
    status: Literal[0, 1] = 1

    @field_validator("name", "code", "description", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CourseUpdateRequest(BaseModel):
    """更新课程（字段可选）。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = None
    status: Literal[0, 1] | None = None

    @field_validator("name", "code", "description", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CourseResponse(BaseModel):
    """课程返回的数据。"""

    id: int
    name: str
    code: str | None = None
    description: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)
