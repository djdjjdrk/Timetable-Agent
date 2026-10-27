from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class KbDocument(Base):
    __tablename__ = "kb_documents"
    __table_args__ = {"comment": "知识库文档"}

    original_name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="原始文件名"
    )
    disk_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="磁盘文件名"
    )
    rel_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="相对 data/kb 的路径"
    )
    size: Mapped[int] = mapped_column(Integer, nullable=False, comment="字节数")
    ext: Mapped[str] = mapped_column(String(20), nullable=False, comment="扩展名")
