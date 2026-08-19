import asyncio
from logging import INFO, getLogger

from sqlmodel import select

from cquptddl import core
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.event import QQPushConfigChangedEvent
from cquptddl.service.qqpush.globals import scheduler, user_strateges
from cquptddl.service.qqpush.push import push_buffered_homeworks
from cquptddl.service.qqpush.strategy import QQPushStrategy

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
    if old_s := user_strateges.get(user_config.user_id):
        old_s.clear()
    obj = QQPushStrategy.from_strategy_name(user_config.qq_push_strategy)(
        scheduler, user_config
    )
    await obj.on_create()
    user_strateges[user_config.user_id] = obj
    _logger.debug("已加载用户%s的推送策略", user_config.user_id)


async def _refresh_user(e: QQPushConfigChangedEvent):
    await asyncio.sleep(0.1)  # 等落库
    async with core.factory.get_session() as session:
        user_config = await session.get(QQPushConfig, e.uid)
        assert user_config
        await _init_user(user_config)


core.bus.on(QQPushConfigChangedEvent, _refresh_user)
