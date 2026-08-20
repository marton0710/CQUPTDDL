from cquptddl import core
from cquptddl.service.qqpush.db import get_user_config_from_qqchan_id
from cquptddl.service.qqpush.push import push_dying_homeworks

from . import globals, on_boot  # noqa: F401
from .configure import configure_qqpush

core.symbol.export("qqpush.configure", configure_qqpush)
core.symbol.export(
    "qqpush.get_user_config_from_qqchan_id", get_user_config_from_qqchan_id
)
core.symbol.export("qqpush.push_dying_homeworks", push_dying_homeworks)
