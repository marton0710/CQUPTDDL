from logging import INFO, getLogger

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from .config import config

_logger = getLogger(__name__)
_logger.setLevel(INFO)
engine = create_async_engine(
    config.DATABASE_URL,
    pool_pre_ping=config.db_pool_pre_ping,
    pool_recycle=config.db_pool_recycle,
)

if make_url(config.DATABASE_URL).get_backend_name() == "sqlite":
    _logger.warning("检测到sqlite连接")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _migrate_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
