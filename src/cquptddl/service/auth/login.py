import uuid
from logging import INFO, getLogger

from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import UserReloginRequired
from cquptddl.model.db.user import User
from cquptddl.model.event import (
    AccountDeletedEvent,
    UserLoginEvent,
    UserRegisterEvent,
    UserReloginRequiredEvent,
)

from . import crypto, ids

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def password_login(
    session: AsyncSession, username: str, password: str
) -> tuple[str, str, str]:
    """使用重邮统一认证账号登录系统
    Returns:
        access_token
        refresh_token
        name

    Raises:
        LoginFailed:
    """
    uid, name, cookies = await ids.password_login(username, password)
    old_user = await session.get(User, uid)
    encrypted_password: str = core.symbol.call("crypto.aes_encrypt", password)
    if old_user is None:
        user = User(
            id=uid,
            password=encrypted_password,
            ids_cookie=cookies,
            name=name,
            token_version=uuid.uuid7(),
        )
        session.add(user)
        core.bus.emit(UserRegisterEvent(uid=uid))
    else:
        user = old_user
        user.password = encrypted_password
        user.ids_cookie = cookies

    core.bus.emit(UserLoginEvent(uid=uid))
    _logger.info("用户%s已登录", uid)
    return (
        crypto.generate_token(uid, user.token_version, False),
        crypto.generate_token(uid, user.token_version, True),
        name,
    )


async def relogin(user: User):
    """
    Raises:
        UserReloginRequired: 使用扫码登录时，无法自动重新登录，需要用户手动登录
    """
    if user.password is None:
        core.bus.emit(UserReloginRequiredEvent(uid=user.id))
        raise UserReloginRequired
    password: str = core.symbol.call("crypto.aes_decrypt", user.password)
    _, _, user.ids_cookie = await ids.password_login(user.id, password)


async def get_user_from_token(session: AsyncSession, token: str) -> User:
    return await crypto.validate_token(session, token)


async def refresh_token(session: AsyncSession, token: str) -> tuple[str, str]:
    """
    Returns:
        new_access_token
        new_refresh_token
    """
    user = await crypto.validate_token(session, token, True)
    return crypto.generate_token(
        user.id, user.token_version, False
    ), crypto.generate_token(user.id, user.token_version, True)


async def logout(user: User):
    user.token_version = uuid.uuid7()


async def delete_account(session: AsyncSession, user: User):
    await session.delete(user)
    core.bus.emit(AccountDeletedEvent(uid=user.id))
    _logger.info("用户%s已删除账户", user.id)
