from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import time, timedelta
from logging import INFO, getLogger
from uuid import UUID

from apscheduler.job import Job
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cquptddl import core
from cquptddl.model.db import Homework
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.schema.qqpush import QQPushStrategyEnum

from .push import push_dying_homework, push_dying_homeworks

_logger = getLogger(__name__)
_logger.setLevel(INFO)


class QQPushStrategy(ABC):
    scheduler: AsyncIOScheduler
    user_id: str
    qqchan_id: str
    qq_push_strategy: QQPushStrategyEnum
    qq_push_at: time
    qq_push_scope: int
    _user_jobs: list[Job]

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
        self._user_jobs = []

    @classmethod
    def from_strategy_name(
        cls, strategy_name: QQPushStrategyEnum
    ) -> type[QQPushStrategy]:
        match strategy_name:
            case QQPushStrategyEnum.SCHEDULED:
                return ScheduledStrategy
            case QQPushStrategyEnum.REALTIME:
                return RealtimeStrategy

    def _generate_job_id(self, homework_id: UUID | None = None) -> str:
        if self.qq_push_strategy == QQPushStrategyEnum.REALTIME and homework_id is None:
            raise ValueError("实时推送任务需要设置作业id")
        return f"qqpush:{self.user_id}{f':{homework_id}' if homework_id else ''}"

    def _record_user_job(self, job: Job):
        self._user_jobs.append(job)

    def clear(self):
        for job in self._user_jobs:
            try:
                job.remove()
                _logger.debug("任务%s已移除", job.id)
            except JobLookupError:
                _logger.warning("移除时未找到id为%s的job", job.id)
        self._user_jobs.clear()


class ScheduledStrategy(QQPushStrategy):
    async def on_create(self):
        trigger = CronTrigger(hour=self.qq_push_at.hour, minute=self.qq_push_at.minute)
        job: Job = self.scheduler.add_job(
            self._job, trigger, id=self._generate_job_id()
        )
        self._record_user_job(job)
        _logger.debug(
            "已创建用户%s的定时推送任务，将于%s运行",
            self.user_id,
            job.next_run_time,
        )

    async def _job(self):  # ty: ignore[invalid-method-override]
        homeworks_to_push: Iterable[Homework] = await core.symbol.call(
            "homework.get_user_dying_homeworks", self.user_id, self.qq_push_scope
        )
        await push_dying_homeworks(self.user_id, homeworks_to_push)


class RealtimeStrategy(QQPushStrategy):
    async def on_create(self):
        for h in await core.symbol.call(
            "homework.get_user_homeworks_with_deadline", self.user_id
        ):
            assert h.deadline
            job: Job = self.scheduler.add_job(
                self._job,
                kwargs={"homework": h},
                id=self._generate_job_id(h.id),
                next_run_time=h.deadline - timedelta(hours=self.qq_push_scope),
            )
            self._record_user_job(job)
            _logger.debug(
                "已创建用户%s、作业%s的实时推送任务，将于%s运行",
                self.user_id,
                h.id,
                job.next_run_time,
            )

    async def _job(self, homework: Homework):  # ty: ignore[invalid-method-override]
        await push_dying_homework(homework)
