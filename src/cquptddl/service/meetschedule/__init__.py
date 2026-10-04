from . import event_handlers as event_handlers
from .refresh_task import shutdown_refresh as shutdown_refresh
from .refresh_task import start_refresh


def init():
    start_refresh()
