from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import time
from uuid import UUID

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.schema.qqpush import QQPushStrategyEnum
from cquptddl.service.qqpush.db import get_dying_homeworks

from .push import push_dying_homeworks


class QQPushStrategy(ABC):
    scheduler: AsyncIOScheduler
    user_id: str
    qqchan_id: str
    qq_push_strategy: QQPushStrategyEnum
    qq_push_at: time
    qq_push_scope: int

    @abstractmethod
    async def on_create(self):
        """执行程序启动时的初始设置"""

    @abstractmethod
    async def _job(self, **kw):
        """每次触发后执行的任务"""

    def __init__(self, scheduler: AsyncIOScheduler, config: QQPushConfig):
        self.scheduler = scheduler
        self.user_id = config.user_id
        assert config.qqchan_id is not None
        self.qqchan_id = config.qqchan_id
        self.qq_push_strategy = config.qq_push_strategy
        self.qq_push_at = config.qq_push_at
        self.qq_push_scope = config.qq_push_scope

    @classmethod
    def from_strategy_name(
        cls, strategy_name: QQPushStrategyEnum
    ) -> type[QQPushStrategy]:
        match strategy_name:
            case QQPushStrategyEnum.SCHEDULED:
                return ScheduledStrategy
            # case QQPushStrategyEnum.REALTIME:
            #     return RealtimeStrategy

    def _generate_job_id(self, homework_id: UUID | None = None) -> str:
        # if self.qq_push_strategy == QQPushStrategyEnum.REALTIME and homework_id is None:
        #     raise ValueError('实时推送任务需要设置作业id')
        return f"qqpush-{self.user_id}{f'-{homework_id}' if homework_id else ''}"

    def _clear_current_user_job(self):
        jobs: Iterable[Job] = self.scheduler.get_jobs()
        for job in jobs:
            if job.id.startswith(f"qqpush-{self.user_id}"):
                job.remove()


class ScheduledStrategy(QQPushStrategy):
    async def on_create(self):
        trigger = CronTrigger(hour=self.qq_push_at.hour, minute=self.qq_push_at.minute)
        self.scheduler.add_job(self._job, trigger, id=self._generate_job_id())

    async def _job(self):  # ty: ignore[invalid-method-override]
        homeworks_to_push = await get_dying_homeworks(self.user_id, self.qq_push_scope)
        await push_dying_homeworks(self.user_id, homeworks_to_push)
