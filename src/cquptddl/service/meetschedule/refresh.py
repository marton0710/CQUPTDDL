from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from cquptddl import core

from .actions import sync_done_status_for_all_tracked_homeworks

scheduler = AsyncIOScheduler()
scheduler.add_job(
    sync_done_status_for_all_tracked_homeworks,
    IntervalTrigger(seconds=core.config.meetschedule_sync_interval),
)


def start_refresh():
    scheduler.start()


def shutdown_refresh():
    scheduler.shutdown()
