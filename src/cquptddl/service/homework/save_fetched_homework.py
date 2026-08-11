from asyncio import CancelledError, Queue
from logging import INFO, getLogger

from cquptddl import core
from cquptddl.model.db import Homework

queue: Queue[Homework] = Queue()
logger = getLogger(__name__)
logger.setLevel(INFO)


def get_queue() -> Queue[Homework]:
    return queue


async def save_fetched_homework_worker(queue: Queue):
    while True:
        homework: Homework = await queue.get()  # 没有从queue拿到东西，不能调task_done
        try:
            async for session in core.get_session():
                await session.merge(homework)
        except CancelledError:
            break
        except Exception as e:
            logger.error("error while saving fetched homework: %s", e, exc_info=e)
        finally:
            queue.task_done()
