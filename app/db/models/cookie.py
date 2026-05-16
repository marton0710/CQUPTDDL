from sqlalchemy import String, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Cookie(Base):
    """存储cookie数据库模型"""
    __tablename__ = "cookie"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_cookie_user_platform"),
    )

    # id
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # user_id
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user.username", ondelete="CASCADE"),
        nullable=False,
    )

    # cookie
    cookies: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)

    # 平台
    platform: Mapped[str] = mapped_column(String(24), nullable=False)

    # user
    user: Mapped["User"] = relationship(back_populates="cookies")
