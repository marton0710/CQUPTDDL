from collections.abc import AsyncGenerator

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .db import _session_maker


async def get_client(*args, **kw) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(*args, **kw) as client:
        yield client


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with _session_maker() as session:
        yield session
        await session.commit()
