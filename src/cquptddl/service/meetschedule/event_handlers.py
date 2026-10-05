from logging import INFO, getLogger
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import MeetscheduleNotBound
from cquptddl.model.db import User
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig

from .actions import (
    add_new_homeworks_by_homework_ids,
    unbind,
    update_homeworks_by_homewok_ids,
)

_logger = getLogger(__name__)
_logger.setLevel(INFO)


@core.hook.on("homework.after_refresh", background=True)
async def _on_recv_new_homework(user_id: str, new_homework_ids: set[UUID], **_):
    _logger.debug("收到作业刷新事件")
    if not new_homework_ids:
        _logger.debug("没有发现新作业")
        return

    async with core.factory.get_session() as session:
        # 查config
        config = await session.get(MeetscheduleConfig, user_id)
        if config is None:
            return

        ids = ((hid, user_id) for hid in new_homework_ids)
        await add_new_homeworks_by_homework_ids(session, ids)


@core.hook.on("homework.after_done", background=True)
async def _on_recv_homework_done_event(homework_id: UUID):
    async with core.factory.get_session() as session:
        await update_homeworks_by_homewok_ids(session, (homework_id,))


@core.hook.on("auth.before_delete_user", fatal=True)
async def on_delete_user(session: AsyncSession, user: User):
    try:
        await unbind(session, user.id)
    except MeetscheduleNotBound:
        pass
