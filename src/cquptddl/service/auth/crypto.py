from datetime import UTC, datetime, timedelta

import jwt

from cquptddl import core
from cquptddl.core import config
from cquptddl.exc import ExpiredToken, InvalidToken


def generate_token(uid: str, isrefresh: bool = False) -> str:
    uidenc: str = core.symbol.call("crypto.aes_encrypt", uid)
    exp = datetime.now().astimezone(UTC) + timedelta(
        seconds=config.REFRESH_TOKEN_EXPIRE_SECONDS
        if isrefresh
        else config.ACCESS_TOKEN_EXPIRE_SECONDS
    )
    payload = {
        "uid": uidenc,
        "exp": exp.timestamp(),
        "isrefresh": isrefresh,
    }
    return jwt.encode(payload, config.SECRET_KEY, config.ALGORITHM)


def validate_token(token: str, isrefresh: bool = False) -> str:
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
        raise InvalidToken("")
    encrypted_uid = decoded_payload["uid"]
    return core.symbol.call("crypto.aes_decrypt", encrypted_uid)
