from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .strategy import QQPushStrategy

scheduler = AsyncIOScheduler()
user_strategies: dict[str, QQPushStrategy] = {}  # 用户id: job集合
