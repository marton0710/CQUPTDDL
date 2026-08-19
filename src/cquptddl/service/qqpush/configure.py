from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.model.db import User
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.event import UserRegisterEvent
from cquptddl.model.schema.qqpush import QQPushConfigSchema


async def configure_qqpush(
    session: AsyncSession, user: User, model: QQPushConfigSchema
):
    await session.merge(QQPushConfig(user_id=user.id, **model.model_dump()))


async def _generate_qqpush_config_after_register(event: UserRegisterEvent):
    async with core.factory.get_session() as session:
        session.add(QQPushConfig(user_id=event.uid))


core.bus.on(UserRegisterEvent, _generate_qqpush_config_after_register)
