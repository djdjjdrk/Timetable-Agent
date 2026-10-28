from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # 后端项目的根路径

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
STUDY_PLAN_MAX_LENGTH = 2000
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
}

# 课程资料单独归档，不放进已公开挂载的 uploads 目录。
KB_DIR: Path = BASE_DIR / "data" / "kb"
KB_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    # MCP 服务
    MCP_HOST: str = "127.0.0.1"
    MCP_PORT: int = 8001
    MCP_PATH: str = "/mcp"

    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""
    LLM_MODEL_NAME: str = "deepseek-flash"
    AGENT_RECURSION_LIMIT: int = 14

    # RAG 向量模型与 Chroma 服务
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    CHROMA_COLLECTION: str = "course_docs"
    CHROMA_HOST: str = "127.0.0.1"
    CHROMA_PORT: int = 8002

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8"
    )


settings = Settings()  # type: ignore
