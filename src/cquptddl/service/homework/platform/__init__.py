from collections.abc import Iterable
from logging import INFO, getLogger

from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import (
    InvalidPlatformCookie,
    InvalidPlatformCredentialFormat,
    PlatformNotBound,
)
from cquptddl.model.db import Homework, PlatformCookies
from cquptddl.model.db.user import User
from cquptddl.model.schema.platform_auth import (
    AllAuthInputs,
    AuthMethod,
    PlatformEnum,
)

from .base import Platform
from .chaoxing import Chaoxing
from .xzcy import Xzcy
from .yuketang import Yuketang

__all__ = ["Chaoxing", "Xzcy", "Yuketang"]
_logger = getLogger(__name__)
_logger.setLevel(INFO)


def get_auth_method(platform_name: PlatformEnum) -> AuthMethod:
    return Platform.get_platform_by_name(platform_name).auth_method


async def bind(
    user: User,
    session: AsyncSession,
    platform_name: PlatformEnum,
    credentials: AllAuthInputs,
):
    platform = Platform.get_platform_by_name(platform_name)
    if not isinstance(credentials, platform.auth_method.model_class):
        raise InvalidPlatformCredentialFormat
    async for client in core.factory.get_client():
        cookies = await platform.login(client, user, credentials)
    credentials_to_save = core.symbol.call(
        "crypto.aes_encrypt", credentials.model_dump_json()
    )
    await session.merge(
        PlatformCookies(
            user_id=user.id,
            platform=platform_name,
            credentials=credentials_to_save,
            cookies=cookies,
        )
    )


async def relogin(
    session: AsyncSession, user: User, platform_name: PlatformEnum
) -> dict[str, str]:
    cookies_obj = await session.get(PlatformCookies, (user.id, platform_name))
    assert cookies_obj is not None
    platform = Platform.get_platform_by_name(platform_name)
    credentials = AuthMethod(platform.auth_method).model_class.model_validate_json(
        core.symbol.call("crypto.aes_decrypt", cookies_obj.credentials)
    )
    async for client in core.factory.get_client():
        new_cookies = await platform.login(client, user, credentials)
    cookies_obj.cookies = new_cookies
    return new_cookies


async def valid_cookie(
    session: AsyncSession, user: User, platform_name: PlatformEnum
) -> bool | None:
    cookies = await session.get(PlatformCookies, (user.id, platform_name))
    if cookies is None:
        return None
    platform = Platform.get_platform_by_name(platform_name)
    return await platform.valid_cookie(cookies.cookies)


async def fetch_homework(
    session: AsyncSession, user: User, platform_name: PlatformEnum
) -> Iterable[Homework]:
    """
    Raises:
        PlatformNotBound: 用户没有绑定该平台
        InvalidPlatformCookie: 平台cookie无效

    """
    cookies_model = await session.get(PlatformCookies, (user.id, platform_name))
    if cookies_model is None:
        raise PlatformNotBound
    platform = Platform.get_platform_by_name(platform_name)
    try:
        homeworks = await platform.get_homework(cookies_model.cookies, user)
    except InvalidPlatformCookie:
        _logger.debug(
            "用户%s在平台%s的token已过期，正在重新登录", user.id, platform_name
        )
        cookies = await relogin(session, user, platform_name)
        homeworks = await platform.get_homework(cookies, user)
    return homeworks


async def unbind(session: AsyncSession, user: User, platform_name: PlatformEnum):
    cookies_obj = await session.get(PlatformCookies, (user.id, platform_name))
    if cookies_obj is not None:
        await session.delete(cookies_obj)
    await core.call("homework.delete_platform_homework", session, user, platform_name)


core.export("homework.platform.get_auth_method", get_auth_method)
core.export("homework.platform.bind", bind)
core.export("homework.platform.valid_cookie", valid_cookie)
core.export("homework.platform.unbind", unbind)
