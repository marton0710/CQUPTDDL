from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.model.db import User
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.event import (
    InvalidQQChanIDEvent,
    QQPushConfigChangedEvent,
    UserRegisterEvent,
)
from cquptddl.model.schema.qqpush import QQPushConfigSchema


async def configure_qqpush(
    session: AsyncSession, user: User, model: QQPushConfigSchema
):
    await session.merge(QQPushConfig(user_id=user.id, **model.model_dump()))
    await session.commit()
    core.bus.emit(QQPushConfigChangedEvent(uid=user.id))


async def get_configure(session: AsyncSession, user_id: str) -> QQPushConfigSchema:
    config = await session.get_one(QQPushConfig, user_id)
    return QQPushConfigSchema(
        qqchan_id=config.qqchan_id,
        qq_push_strategy=config.qq_push_strategy,
        qq_push_at=config.qq_push_at,
        qq_push_scope=config.qq_push_scope,
    )


async def _generate_qqpush_config_after_register(event: UserRegisterEvent):
    async with core.factory.get_session() as session:
        session.add(QQPushConfig(user_id=event.uid))


async def _clear_invalid_qqchan_id(event: InvalidQQChanIDEvent):
    async with core.factory.get_session() as session:
        c = await session.get_one(QQPushConfig, event.uid)
        c.qqchan_id = None
    core.bus.emit(QQPushConfigChangedEvent(uid=event.uid))


core.bus.on(UserRegisterEvent, _generate_qqpush_config_after_register)
core.bus.on(InvalidQQChanIDEvent, _clear_invalid_qqchan_id)
