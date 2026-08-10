from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from . import config

engine = create_async_engine(config.DATABASE_URL)

_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _migrate_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# def auto_session[**P, T](func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
#     @functools.wraps(func)
#     async def wrapper(*args, **kw) -> Any:
#         if "session" in kw and kw["session"] is not None:
#             return func(*args, **kw)
#         async with get_session() as session:
#             kw["session"] = session
#             return await func(*args, **kw)

#     return wrapper
