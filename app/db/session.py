from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import engine


SessonLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """提供一个可复用的session生成器（适合依赖注入或统一封装）。"""
    async with SessonLocal() as session:
        yield session
