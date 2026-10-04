from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from cquptddl import core
from cquptddl.model.db.qqpush_config import QQPushConfig


@core.symbol.qqpush_get_user_config_from_qqchan_id.register
async def get_user_config_from_qqchan_id(
    session: AsyncSession, qqchan_id: str
) -> QQPushConfig | None:
    sql = select(QQPushConfig).where(QQPushConfig.qqchan_id == qqchan_id)
    resp = await session.execute(sql)
    return resp.scalar_one_or_none()
