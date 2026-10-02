from cquptddl import core

from . import auth, fetch
from .chaoxing import Chaoxing as Chaoxing
from .xzcy import Xzcy as Xzcy
from .yuketang import Yuketang as Yuketang

core.symbol.export("platform.get_auth_method", auth.get_auth_method)
core.symbol.export("platform.bind", auth.bind)
core.symbol.export("platform.valid_cookie", auth.valid_cookie)
core.symbol.export("platform.unbind", auth.unbind)
core.symbol.export("platform.fetch_homework", fetch.fetch_homework)
