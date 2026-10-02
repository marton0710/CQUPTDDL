from cquptddl import core

from . import event_handlers as event_handlers
from .actions import bind, is_bound, unbind
from .refresh_task import shutdown_refresh as shutdown_refresh
from .refresh_task import start_refresh


def init():
    start_refresh()


core.symbol.export("meetschedule.bind", bind)
core.symbol.export("meetschedule.unbind", unbind)
core.symbol.export("meetschedule.is_bound", is_bound)
