from datetime import UTC, datetime, timedelta
from logging import INFO, getLogger
from uuid import UUID

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.core import config
from cquptddl.exc import ExpiredToken, InvalidToken
from cquptddl.model.db import User

_logger = getLogger(__name__)
_logger.setLevel(INFO)


def generate_token(uid: str, version: UUID, isrefresh: bool = False) -> str:
    uidenc: str = core.symbol.call("crypto.aes_encrypt", uid)
    exp = datetime.now().astimezone(UTC) + timedelta(
        seconds=config.REFRESH_TOKEN_EXPIRE_SECONDS
        if isrefresh
        else config.ACCESS_TOKEN_EXPIRE_SECONDS
    )
    payload = {
        "uid": uidenc,
        "ver": str(version),
        "exp": exp.timestamp(),
        "isrefresh": isrefresh,
    }
    return jwt.encode(payload, config.SECRET_KEY, config.ALGORITHM)


async def validate_token(
    session: AsyncSession, token: str, isrefresh: bool = False
) -> User:
    """
    Returns:
        uid
    """
    try:
        decoded_payload = jwt.decode(token, config.SECRET_KEY, [config.ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise ExpiredToken from e
    except jwt.InvalidTokenError as e:
        raise InvalidToken from e
    if decoded_payload["isrefresh"] != isrefresh:
        raise InvalidToken
    encrypted_uid = decoded_payload["uid"]
    uid = core.symbol.call("crypto.aes_decrypt", encrypted_uid)
    user = await session.get(User, uid)
    if user is None:
        _logger.critical("警告：发现无对应用户的token")
        raise InvalidToken
    if decoded_payload["ver"] != str(user.token_version):
        _logger.warning("警告：用户%s试图使用version不匹配的token认证", user.id)
        raise InvalidToken
    return user
