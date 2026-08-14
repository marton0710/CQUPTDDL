from cquptddl import core

from . import auth, fetch
from .chaoxing import Chaoxing
from .xzcy import Xzcy
from .yuketang import Yuketang

__all__ = ["Chaoxing", "Xzcy", "Yuketang"]


core.export("platform.get_auth_method", auth.get_auth_method)
core.export("platform.bind", auth.bind)
core.export("platform.valid_cookie", auth.valid_cookie)
core.export("platform.unbind", auth.unbind)
core.export("platform.fetch_homework", fetch.fetch_homework)
