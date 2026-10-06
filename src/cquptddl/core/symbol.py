import enum
from collections.abc import Callable, Collection, Coroutine, Generator, Iterable
from contextlib import contextmanager
from datetime import datetime
from logging import INFO, getLogger
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl.model.db import Homework, IcsSubscription, User
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.schema.platform import AllAuthInputs, AuthMethod, PlatformEnum
from cquptddl.model.schema.qqpush import QQPushConfigSchema

from .config import config

_logger = getLogger(__name__)
_logger.setLevel(INFO)
_symbol_table = dict[str, Callable]()


class _Missing(enum.Enum):
    _ = enum.auto()


def export(name: str, func: Callable):
    if name in _symbol_table:
        raise NameError(f"符号{name}已存在")
    _symbol_table[name] = func


def call(name: str, *args, **kw) -> Any:
    return _symbol_table[name](*args, **kw)


@contextmanager
def mock(name: str, func: Callable) -> Generator[None]:
    """强制替换某个符号的实现，退出时恢复。

    仅供测试/调试使用
    未注册的名字也可 mock，退出时会被清掉而不是残留空壳。
    """
    if not config.DEBUG:
        raise RuntimeError(f"禁止在生产环境 mock 符号{name}")

    previous = _symbol_table.get(name, _Missing._)
    _symbol_table[name] = func
    _logger.warning("符号%s已被临时替换为%s", name, func)
    try:
        yield
    finally:
        if previous is _Missing._:
            _symbol_table.pop(name, None)
        else:
            _symbol_table[name] = previous


class _Declaration[**P, R]:
    name: str

    def __init__(self, name: str):
        self.name = name

    def register(self, f: Callable[P, R]) -> Callable[P, R]:
        export(self.name, f)
        return f

    def __repr__(self) -> str:
        return (
            f"<Symbol {self.name} ({'已注册' if self.name in _symbol_table else '空'})>"
        )


class Symbol[**P, R](_Declaration[P, R]):
    def __call__(self, *args: P.args, **kw: P.kwargs) -> R:
        return call(self.name, *args, **kw)


class AsyncSymbol[**P, R](_Declaration[P, Coroutine[Any, Any, R]]):
    def __call__(self, *args: P.args, **kw: P.kwargs) -> Coroutine[Any, Any, R]:
        return call(self.name, *args, **kw)


auth_password_login = AsyncSymbol[[AsyncSession, str, str], tuple[str, str, str]](
    "auth.password_login"
)
auth_get_login_qrcode = AsyncSymbol[[], tuple[str, UUID]]("auth.get_login_qrcode")
auth_qrcode_login = AsyncSymbol[[AsyncSession, UUID, bool], tuple[str, str, str]](
    "auth.qrcode_login"
)
auth_relogin = AsyncSymbol[[User], None]("auth.relogin")
auth_get_user_from_token = AsyncSymbol[[AsyncSession, str], User](
    "auth.get_user_from_token"
)
auth_refresh_token = AsyncSymbol[[AsyncSession, str], tuple[str, str]](
    "auth.refresh_token"
)
auth_logout = AsyncSymbol[[User], None]("auth.logout")
auth_delete_account = AsyncSymbol[[AsyncSession, User], None]("auth.delete_account")
crypto_aes_encrypt = Symbol[[str], str]("crypto.aes_encrypt")
crypto_aes_decrypt = Symbol[[str], str]("crypto.aes_decrypt")
homework_refresh_homework = AsyncSymbol[[AsyncSession, User, PlatformEnum], None](
    "homework.refresh_homework"
)
homework_complete = AsyncSymbol[[AsyncSession, str, UUID, bool], None](
    "homework.complete"
)
homework_get_cached_homework = AsyncSymbol[
    [AsyncSession, str, PlatformEnum | None, int, int], Iterable[Homework]
]("homework.get_cached_homework")
homework_get_cached_homework_count = AsyncSymbol[
    [AsyncSession, str, PlatformEnum | None], int
]("homework.get_cached_homework_count")
homework_get_last_refresh_time = AsyncSymbol[
    [AsyncSession, str, PlatformEnum | None], datetime
]("homework.get_last_refresh_time")
homework_get_user_dying_homeworks = AsyncSymbol[
    [AsyncSession, str, int | None], Collection[Homework]
]("homework.get_user_dying_homeworks")
homework_get_user_homeworks_with_deadline = AsyncSymbol[
    [AsyncSession, str], Collection[Homework]
]("homework.get_user_homeworks_with_deadline")
ics_list_subscriptions = AsyncSymbol[[AsyncSession, str], Collection[IcsSubscription]](
    "ics.list_subscriptions"
)
ics_create_subscription = AsyncSymbol[[AsyncSession, str], tuple[IcsSubscription, str]](
    "ics.create_subscription"
)
ics_delete_subscription = AsyncSymbol[[AsyncSession, str, UUID], None](
    "ics.delete_subscription"
)
ics_render_feed = AsyncSymbol[
    [AsyncSession, str, PlatformEnum | None], tuple[bytes, str]
]("ics.render_feed")
ics_get_url_count = AsyncSymbol[[AsyncSession, str], int]("ics.get_url_count")
meetschedule_bind = AsyncSymbol[[AsyncSession, str, str], None]("meetschedule.bind")
meetschedule_unbind = AsyncSymbol[[AsyncSession, str], None]("meetschedule.unbind")
meetschedule_is_bound = AsyncSymbol[[AsyncSession, str], bool]("meetschedule.is_bound")
platform_get_auth_method = Symbol[[PlatformEnum], AuthMethod](
    "platform.get_auth_method"
)
platform_bind = AsyncSymbol[[User, AsyncSession, PlatformEnum, AllAuthInputs], None](
    "platform.bind"
)
platform_valid_cookie = AsyncSymbol[[AsyncSession, str, PlatformEnum], bool | None](
    "platform.valid_cookie"
)
platform_unbind = AsyncSymbol[[AsyncSession, str, PlatformEnum], None](
    "platform.unbind"
)
platform_fetch_homework = AsyncSymbol[
    [AsyncSession, User, PlatformEnum, bool], set[Homework]
]("platform.fetch_homework")
qqpush_configure = AsyncSymbol[[AsyncSession, str, QQPushConfigSchema], None](
    "qqpush.configure"
)
qqpush_get_configure = AsyncSymbol[[AsyncSession, str], QQPushConfigSchema](
    "qqpush.get_configure"
)
qqpush_get_user_config_from_qqchan_id = AsyncSymbol[
    [AsyncSession, str], QQPushConfig | None
]("qqpush.get_user_config_from_qqchan_id")
qqpush_push_dying_homeworks = AsyncSymbol[[str, Collection[Homework]], None](
    "qqpush.push_dying_homeworks"
)
