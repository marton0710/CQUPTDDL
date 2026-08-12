from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import UserReloginRequired
from cquptddl.model.db.user import User
from cquptddl.model.event import (
    UserLoginEvent,
    UserRegisterEvent,
    UserReloginRequiredEvent,
)

from . import crypto, ids


async def password_login(
    session: AsyncSession, username: str, password: str
) -> tuple[str, str, str]:
    """使用重邮统一认证账号登录系统
    Returns:
        access_token
        refresh_token
        name

    Raises:
        LoginFailed
    """
    uid, name, cookies = await ids.password_login(username, password)
    old_user = await session.get(User, uid)
    encrypted_password: str = core.symbol.call("crypto.aes_encrypt", password)
    if old_user is None:
        new_user = User(
            id=uid,
            password=encrypted_password,
            ids_cookie=cookies,
            name=name,
        )
        session.add(new_user)
        core.bus.emit(UserRegisterEvent(user=new_user))
    else:
        old_user.password = encrypted_password
        old_user.ids_cookie = cookies

    core.bus.emit(UserLoginEvent(user=old_user or new_user))
    return crypto.generate_token(uid, False), crypto.generate_token(uid, True), name


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
    uid = crypto.validate_token(token)
    user = await session.get(User, uid)
    assert user
    return user


def refresh_token(token: str) -> tuple[str, str]:
    """
    Returns:
        new_access_token
        new_refresh_token
    """
    uid = crypto.validate_token(token, True)
    return crypto.generate_token(uid, False), crypto.generate_token(uid, True)
