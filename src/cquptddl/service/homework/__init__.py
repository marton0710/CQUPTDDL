from cquptddl import core

from .complete import complete_homework
from .get_cached_homework import (
    delete_platform_homework,
    get_cached_homework,
    get_cached_homework_count,
    get_last_refresh_time,
)
from .refresh_homework import refresh_homework
from .refresh_task import init_refresh_task
from .refresh_task import scheduler as refresh_scheduler

core.export("homework.refresh_homework", refresh_homework)
core.export("homework.complete", complete_homework)
core.export("homework.get_cached_homework", get_cached_homework)
core.export("homework.get_cached_homework_count", get_cached_homework_count)
core.export("homework.get_last_refresh_time", get_last_refresh_time)
core.export("homework.delete_platform_homework", delete_platform_homework)
core.export("homework.get_refresh_scheduler", lambda: refresh_scheduler)
core.export("homework.init_refresh_task", init_refresh_task)
