import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


def encryptByAES(message, key="u2oh6Vu^HWe4_AES") -> str:
    # 密钥和 IV 都使用 key（和 JS 代码完全一致）
    key_bytes = key.encode("utf-8")
    iv_bytes = key.encode("utf-8")

    # 初始化 AES-CBC
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)

    # 明文编码 + PKCS7 填充
    message_bytes = message.encode("utf-8")
    padded_data = pad(message_bytes, AES.block_size)

    # 加密
    encrypted_bytes = cipher.encrypt(padded_data)

    # 返回 base64
    return base64.b64encode(encrypted_bytes).decode("utf-8")
