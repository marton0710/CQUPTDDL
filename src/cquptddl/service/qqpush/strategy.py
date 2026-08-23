from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import time
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
        # if self.qq_push_strategy == QQPushStrategyEnum.REALTIME and homework_id is None:
        #     raise ValueError("实时推送任务需要设置作业id")
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
        async with core.factory.get_session() as session:
            homeworks_to_push: Iterable[Homework] = await core.symbol.call(
                "homework.get_user_dying_homeworks",
                session,
                self.user_id,
                self.qq_push_scope,
            )
            if not homeworks_to_push:
                return
        await push_dying_homeworks(self.user_id, homeworks_to_push)


class RealtimeStrategy(QQPushStrategy):
    _reminded: set[UUID]

    async def on_create(self):
        self._reminded = set[UUID]()
        # await self._reconcile()
        job = self.scheduler.add_job(
            self._job,
            "interval",
            id=self._generate_job_id(),
            seconds=core.config.qqpush_realtime_reconcile_interval,
        )
        self._record_user_job(job)

    async def _job(self):  # ty: ignore[invalid-method-override]
        async with core.factory.get_session() as session:
            homeworks: Iterable[Homework] = await core.symbol.call(
                "homework.get_user_dying_homeworks",
                session,
                self.user_id,
                self.qq_push_scope,
            )
        for h in homeworks:
            if h.id not in self._reminded:
                await push_dying_homework(h)
                self._reminded.add(h.id)
        self._reminded &= {
            h.id for h in homeworks
        }  # 离开窗口的释放，再次进入时重新提醒

    # async def _job(self, homework_id: UUID):  # ty: ignore[invalid-method-override]
    #     async with core.factory.get_session() as session:
    #         h = await session.get(Homework, homework_id)
    #         if h is None or h.done or h.id in self._reminded:
    #             return  # 跳过已完成或已删除的作业
    #     await push_dying_homework(h)
    #     self._reminded.add(h.id)

    # async def _reconcile(self):
    #     async with core.factory.get_session() as session:
    #         homeworks: Iterable[Homework] = await core.symbol.call(
    #             "homework.get_user_dying_homeworks", session, self.user_id
    #         )
    #         desired = {h.id: h.deadline for h in homeworks}
    #         for hid, run_at in desired.items():
    #             if hid in self._reminded:
    #                 continue

    #             assert run_at is not None
    #             run_at = run_at - timedelta(seconds=self.qq_push_scope)
    #             job_id = self._generate_job_id(hid)
    #             job: Job | None = self.scheduler.get_job(job_id)

    #             # 全新作业
    #             if job is None:
    #                 job = self.scheduler.add_job(
    #                     self._job,
    #                     kwargs={"homework_id": hid},
    #                     id=job_id,
    #                     next_run_time=run_at,
    #                 )
    #                 self._record_user_job(job)

    #             # 前向储备，当作业截止时间变更时生效
    #             elif abs(job.next_run_time - run_at) > timedelta(seconds=30):
    #                 job.reschedule(trigger=DateTrigger(run_date=run_at))

    #         # 已经删除的作业
    #         for job in self._user_jobs:
    #             hid = job.id.split(":", 2)[-1]
    #             if hid not in desired:
    #                 with suppress(JobLookupError, ValueError):
    #                     self._user_jobs.remove(job)
    #                     self.scheduler.remove_job(job_id)
