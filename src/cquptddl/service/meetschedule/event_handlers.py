from logging import INFO, getLogger

from cquptddl import core
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.event import (
    HomeworkDoneEvent,
    HomeworkRefreshedEvent,
)
from cquptddl.service.meetschedule.actions import (
    add_new_homeworks_by_homework_ids,
    update_homeworks_by_homewok_ids,
)

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def _on_recv_new_homework(event: HomeworkRefreshedEvent):
    _logger.debug("收到作业刷新事件")
    if not event.new_homework_ids:
        _logger.debug("没有发现新作业")
        return

    async with core.factory.get_session() as session:
        # 查config
        config = await session.get(MeetscheduleConfig, event.uid)
        if config is None:
            return

        ids = ((hid, event.uid) for hid in event.new_homework_ids)
        await add_new_homeworks_by_homework_ids(session, ids)


async def _on_recv_homework_done_event(event: HomeworkDoneEvent):
    async with core.factory.get_session() as session:
        await update_homeworks_by_homewok_ids(session, (event.homework_id,))


core.bus.on(HomeworkRefreshedEvent, _on_recv_new_homework)
core.bus.on(HomeworkDoneEvent, _on_recv_homework_done_event)
