from app.db.engine import engine
from app.db.base import Base

import app.db.models


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
