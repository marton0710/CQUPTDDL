from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core import settings


engine: AsyncEngine = create_async_engine(
    url=settings.database_url,
    echo=settings.db_echo,
    future=True,
    pool_pre_ping = True,
)
