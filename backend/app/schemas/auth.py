import re

from pydantic import BaseModel, field_validator
from app.schemas.user import UserResponse

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: UserResponse

class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", value):
            raise ValueError("账号须为3～20位英文字母、数字或下划线")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not 8 <= len(value) <= 20:
            raise ValueError("密码长度须为8～20位")
        if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value):
            raise ValueError("密码须至少包含英文字母和数字")
        if not re.fullmatch(r"[!-~]+", value):
            raise ValueError("密码仅允许英文字母、数字和ASCII特殊符号，不允许空格")
        return value
