from logging import INFO, getLogger

from sqlmodel import select

from cquptddl import core
from cquptddl.model.db.qqpush_config import QQPushConfig
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
        obj = QQPushStrategy.from_strategy_name(c.qq_push_strategy)(scheduler, c)
        await obj.on_create()
        user_strateges[c.user_id] = obj

    _logger.info("QQ推送初始化成功，共处理%s个用户", len(user_configs))
