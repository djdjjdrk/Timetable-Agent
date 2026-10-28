from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class StudyPlan(Base):
    __tablename__ = "study_plans"
    __table_args__ = (
        UniqueConstraint("user_id", "turn_id", name="uq_study_plan_user_turn"),
        {"comment": "学习计划"},
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, comment="用户ID"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="计划内容")
    turn_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="MCP对话轮次ID"
    )
