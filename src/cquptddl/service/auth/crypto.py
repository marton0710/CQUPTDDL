import base64
import hashlib
from datetime import UTC, datetime, timedelta

import jwt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from cquptddl.core import config
from cquptddl.exc import ExpiredToken, InvalidToken

_AES_KEY = hashlib.md5(config.SECRET_KEY.encode()).digest()[:16]


def generate_token(uid: str, isrefresh: bool = False) -> str:
    uidenc = aes_encrypt(uid)
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
    return aes_decrypt(encrypted_uid)


def aes_encrypt(s: str) -> str:
    cipher = AES.new(_AES_KEY, AES.MODE_CBC)
    ciphertext = cipher.encrypt(pad(s.encode(), AES.block_size))
    return base64.b64encode(bytes(cipher.iv) + ciphertext).decode()


def aes_decrypt(c: str) -> str:
    raw_data = base64.b64decode(c)
    iv = raw_data[: AES.block_size]
    ciphertext = raw_data[AES.block_size :]
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode()
