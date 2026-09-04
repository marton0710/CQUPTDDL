from logging import INFO, getLogger

from sqlmodel import select

from cquptddl import core
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.event import (
    AccountDeletedEvent,
    HomeworkRefreshedEvent,
    QQPushConfigChangedEvent,
)

from .globals import scheduler, user_strategies
from .push import push_buffered_homeworks
from .strategy import QQPushStrategy

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def on_boot():
    scheduler.start()
    scheduler.add_job(push_buffered_homeworks, "interval", seconds=5)
    sql = select(QQPushConfig).where(QQPushConfig.qqchan_id != None)
    async with core.factory.get_session() as session:
        resp = await session.execute(sql)
        user_configs = resp.scalars().all()

    for c in user_configs:
        await _init_user(c)

    _logger.info("QQ推送初始化成功，共处理%s个用户", len(user_configs))


async def _init_user(user_config: QQPushConfig):
    if old_s := user_strategies.get(user_config.user_id):
        old_s.clear()
    obj = QQPushStrategy.from_strategy_name(user_config.qq_push_strategy)(
        scheduler, user_config
    )
    await obj.on_create()
    user_strategies[user_config.user_id] = obj
    _logger.debug("已加载用户%s的推送策略", user_config.user_id)


def unbind(user_id: str):
    if old := user_strategies.pop(user_id, None):
        old.clear()


async def _refresh_user(e: QQPushConfigChangedEvent | HomeworkRefreshedEvent):
    async with core.factory.get_session() as session:
        user_config = await session.get_one(QQPushConfig, e.uid)
        if user_config.qqchan_id is None:  # 解绑情况
            unbind(user_config.user_id)
        else:
            await _init_user(user_config)


def _handle_account_delete_event(e: AccountDeletedEvent):
    unbind(e.uid)


core.bus.on(QQPushConfigChangedEvent, _refresh_user)
core.bus.on(HomeworkRefreshedEvent, _refresh_user)
core.bus.on(AccountDeletedEvent, _handle_account_delete_event)
