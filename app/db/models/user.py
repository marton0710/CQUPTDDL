from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """存储user数据库模型"""
    __tablename__ = "user"

    # id
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # username
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # cookies
    cookies: Mapped[list["Cookie"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
