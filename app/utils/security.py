import jwt
from jwt import InvalidTokenError
from datetime import timedelta, datetime, timezone
from typing import Any
from pwdlib import PasswordHash

from app.core import settings
from app.utils import Error

password_hash = PasswordHash.recommended()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def hash_password(password: str) -> str:
    return password_hash.hash(password=password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password=password, hash=hashed_password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    创建jwt
    :param data: 加密的数据
    :param expires_delta: 存在时间
    :return:
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": now + expires_delta,
        "iat": now,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    解析jwt
    :param token: jwt token
    :return:
    """
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=ALGORITHM,
        options={"require": ["exp", "sub"]},
    )


def get_token_sub(token: str) -> str:
    """
    获取jwt里面的username
    :param token: jwt token
    :return:
    """
    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise Error(code=400, message="token 无效或已过期")

    sub = payload.get("sub")
    if not sub:
        raise Error(code=400, message="token 不合法")
    return str(sub)
