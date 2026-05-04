from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """存储user数据库模型"""
    __tablename__ = "user"

    # id
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 用户名
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # 密码
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)

    # 邮箱
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    # cookies
    # cookies: Mapped[list["Cookie"]] = relationship(
    #     back_populates="user",
    #     cascade="all, delete-orphan",
    # )
