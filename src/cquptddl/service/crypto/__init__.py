import base64
import hashlib

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from cquptddl import core
from cquptddl.core import config

_AES_KEY = hashlib.md5(config.SECRET_KEY.encode()).digest()[:16]


@core.symbol.crypto_aes_encrypt.register
def aes_encrypt(s: str) -> str:
    cipher = AES.new(_AES_KEY, AES.MODE_CBC)
    ciphertext = cipher.encrypt(pad(s.encode(), AES.block_size))
    return base64.b64encode(bytes(cipher.iv) + ciphertext).decode()


@core.symbol.crypto_aes_decrypt.register
def aes_decrypt(c: str) -> str:
    raw_data = base64.b64decode(c)
    iv = raw_data[: AES.block_size]
    ciphertext = raw_data[AES.block_size :]
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode()
