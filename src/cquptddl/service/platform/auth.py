from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import InvalidPlatformCredentialFormat
from cquptddl.model.db import PlatformInfo, User
from cquptddl.model.schema.platform_auth import AllAuthInputs, AuthMethod, PlatformEnum

from .base import Platform


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

    async with core.factory.get_client() as client:
        cookies = await platform.login(client, user, credentials)

    credentials_to_save = core.symbol.call(
        "crypto.aes_encrypt", credentials.model_dump_json()
    )
    await session.merge(
        PlatformInfo(
            user_id=user.id,
            platform=platform_name,
            credentials=credentials_to_save,
            cookies=cookies,
            last_refreshed_homework=datetime.fromtimestamp(0),  # noqa: DTZ006
        )
    )


async def unbind(session: AsyncSession, user: User, platform_name: PlatformEnum):
    platform_info = await session.get(PlatformInfo, (user.id, platform_name))
    if platform_info is not None:
        await session.delete(platform_info)
    await core.call("homework.delete_platform_homework", session, user, platform_name)


async def relogin(
    session: AsyncSession, user: User, platform_name: PlatformEnum
) -> dict[str, str]:
    """
    Returns:
        new_cookies
    """
    platform_info = await session.get(PlatformInfo, (user.id, platform_name))
    assert platform_info is not None
    platform = Platform.get_platform_by_name(platform_name)
    credentials = AuthMethod(platform.auth_method).model_class.model_validate_json(
        core.symbol.call("crypto.aes_decrypt", platform_info.credentials)
    )
    async with core.factory.get_client() as client:
        new_cookies = await platform.login(client, user, credentials)
    platform_info.cookies = new_cookies
    return new_cookies


async def valid_cookie(
    session: AsyncSession, user: User, platform_name: PlatformEnum
) -> bool | None:
    platform_info = await session.get(PlatformInfo, (user.id, platform_name))
    if platform_info is None:
        return None
    platform = Platform.get_platform_by_name(platform_name)
    return await platform.valid_cookie(platform_info.cookies)
