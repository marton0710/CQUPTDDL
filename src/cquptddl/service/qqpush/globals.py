from apscheduler.schedulers.asyncio import AsyncIOScheduler

from cquptddl.service.qqpush.strategy import QQPushStrategy

scheduler = AsyncIOScheduler()
user_strateges: dict[str, QQPushStrategy] = {}  # 用户id: job集合
