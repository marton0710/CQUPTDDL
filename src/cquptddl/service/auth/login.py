import uuid
from logging import INFO, getLogger

from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import UserReloginRequired
from cquptddl.model.db.user import User
from cquptddl.model.event import (
    UserReloginRequiredEvent,
)

from . import crypto, ids

_logger = getLogger(__name__)
_logger.setLevel(INFO)


@core.symbol.auth_password_login.register
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
    encrypted_password = core.symbol.crypto_aes_encrypt(password)
    if old_user is None:
        user = User(
            id=uid,
            password=encrypted_password,
            ids_cookie=cookies,
            name=name,
            token_version=uuid.uuid7(),
        )
        session.add(user)
        await core.hook.trigger("auth.after_register", uid)
    else:
        user = old_user
        user.password = encrypted_password
        user.ids_cookie = cookies

    await core.hook.trigger("auth.after_login", uid)
    _logger.info("用户%s已通过密码登录", uid)
    return (
        crypto.generate_token(uid, user.token_version, False),
        crypto.generate_token(uid, user.token_version, True),
        name,
    )


@core.symbol.auth_get_login_qrcode.register
async def get_login_qrcode() -> tuple[str, uuid.UUID]:
    """获取登录二维码内容
    Returns:
        qrcode_url: 二维码内容（ids链接）
        session_id: 二位码登录会话id
    """
    return await ids.get_login_qrcode()


@core.symbol.auth_qrcode_login.register
async def qrcode_login(
    session: AsyncSession, qrlogin_session_id: uuid.UUID, clear_password: bool
) -> tuple[str, str, str]:
    """扫码登录系统
    Returns:
        access_token
        refresh_token
        name

    Raises:
        LoginFailed:
    """
    uid, name, cookies = await ids.qrcode_login(qrlogin_session_id)
    old_user = await session.get(User, uid)
    if old_user is None:
        user = User(
            id=uid,
            password=None,
            ids_cookie=cookies,
            name=name,
            token_version=uuid.uuid7(),
        )
        session.add(user)
        await core.hook.trigger("auth.after_register", uid)
    else:
        user = old_user
        if clear_password:
            user.password = None
        user.ids_cookie = cookies

    await core.hook.trigger("auth.after_login", uid)
    _logger.info("用户%s已通过二维码登录", uid)
    return (
        crypto.generate_token(uid, user.token_version, False),
        crypto.generate_token(uid, user.token_version, True),
        name,
    )


@core.symbol.auth_relogin.register
async def relogin(user: User):
    """
    Raises:
        UserReloginRequired: 使用扫码登录时，无法自动重新登录，需要用户手动登录
    """
    if user.password is None:
        core.bus.emit(UserReloginRequiredEvent(uid=user.id))
        raise UserReloginRequired
    password = core.symbol.crypto_aes_decrypt(user.password)
    _, _, user.ids_cookie = await ids.password_login(user.id, password)


@core.symbol.auth_get_user_from_token.register
async def get_user_from_token(session: AsyncSession, token: str) -> User:
    return await crypto.validate_token(session, token)


@core.symbol.auth_refresh_token.register
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


@core.symbol.auth_logout.register
async def logout(user: User):
    user.token_version = uuid.uuid7()


@core.symbol.auth_delete_account.register
async def delete_account(session: AsyncSession, user: User):
    await core.hook.trigger("auth.before_delete_user", session, user)
    await session.delete(user)
    await core.hook.trigger("auth.after_delete_user", user_id=user.id)
    _logger.info("用户%s已删除账户", user.id)
