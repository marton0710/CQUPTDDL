from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl.model.db.user import User

from . import crypto, ids


async def password_login(
    session: AsyncSession, username: str, password: str
) -> tuple[str, str, str]:
    """使用重邮统一认证账号登录系统
    Returns:
        access_token
        refresh_token
        name
    """
    uid, name, cookies = await ids.password_login(username, password)
    await session.merge(
        User(
            id=uid, password=crypto.aes_encrypt(password), ids_cookie=cookies, name=name
        )
    )

    return crypto.generate_token(uid, False), crypto.generate_token(uid, True), name


async def relogin(user: User):
    if user.password is None:
        raise  # TODO:
    password = crypto.aes_decrypt(user.password)
    await ids.password_login(user.id, password)


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
