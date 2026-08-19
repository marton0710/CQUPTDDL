from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.model.db import User
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.event import UserRegisterEvent
from cquptddl.model.schema.meetschedule import MeetscheduleConfigSchema


async def configure_meetschedule(
    session: AsyncSession, user: User, model: MeetscheduleConfigSchema
):
    await session.merge(MeetscheduleConfig(user_id=user.id, **model.model_dump()))


async def _generate_meetschedule_config_after_register(event: UserRegisterEvent):
    async with core.factory.get_session() as session:
        session.add(MeetscheduleConfig(user_id=event.uid))


core.bus.on(UserRegisterEvent, _generate_meetschedule_config_after_register)
