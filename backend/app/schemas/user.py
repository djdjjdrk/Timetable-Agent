from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserResponse(BaseModel):
    id: int
    username: str
    name: str
    role: str
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(default="123", min_length=3, max_length=10)
    name: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=50)
    avatar: str | None = Field(default=None, max_length=255)
    role: Literal["student", "admin"] = "student"
    status: Literal[0, 1] = 1

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=50)
    avatar: str | None = Field(default=None, max_length=255)
    role: Literal["student", "admin"] | None = None
    status: Literal[0, 1] | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def validate_optional_password(cls, value: str | None) -> str | None:
        if value and not 3 <= len(value) <= 10:
            raise ValueError("密码长度须为3～10位")
        return value


class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str
