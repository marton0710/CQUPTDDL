import asyncio
import logging
import uuid
from asyncio import Task
from collections.abc import Coroutine

tasks: set[Task] = set()
_pending_start: set[tuple[Coroutine, str | None]] = set()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def background(coro: Coroutine, name: str | None = None) -> Task:
    """立即放在后台运行
    **警告：不可在事件循环未开始前调用**
    """
    if name is None:
        name = str(uuid.uuid4())
    task = asyncio.create_task(coro, name=name)
    tasks.add(task)
    task.add_done_callback(_on_task_done)
    logger.debug("task %s created", name)
    return task


def register(coro: Coroutine, name: str | None = None) -> Coroutine:
    """提前注册后台任务
    会在事件循环开始后自动调度
    """
    _pending_start.add((coro, name))
    return coro


def start():
    """开始所有已注册的后台任务"""
    for coro in _pending_start:
        background(*coro)
    _pending_start.clear()


async def shutdown():
    pending_tasks = list(tasks)
    for task in pending_tasks:
        task.cancel()
    logger.info("waiting for tasks shutdown...")
    if pending_tasks:
        ret = await asyncio.gather(*pending_tasks, return_exceptions=True)
        for r in ret:
            if isinstance(r, Exception):
                logger.error("task error: %s", r, exc_info=r)
            else:
                logger.info("task returned %s", r)
    logger.info("所有后台任务已成功停止")


def _on_task_done(t: Task):
    tasks.discard(t)
    if t.cancelled():
        return
    exc = t.exception()
    if exc is not None:
        logger.error("task %s error: %s", t, exc, exc_info=exc)
