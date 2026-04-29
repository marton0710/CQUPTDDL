from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad
import base64
import random


class LoginAES:
    def __init__(self, password = "", salt = ""):
        self.password = password if password else ""
        self.key = salt if salt else ""
        self.aes_chars = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"

    def random_string(self, length):
        """生成随机字符串"""
        return ''.join(random.choice(self.aes_chars) for _ in range(length))

    def get_aes_string(self, text, iv):
        """执行 AES 加密"""
        key_bytes = self.key.strip().encode('utf-8')
        iv_bytes = iv.encode('utf-8')
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        padded_text = pad(text.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded_text)
        return base64.b64encode(encrypted).decode('utf-8')

    def encrypt_aes(self):
        """AES 加密封装"""
        if self.key:
            return self.get_aes_string(self.random_string(64) + self.password, self.random_string(16))
        return self.password

    def encrypt_password(self):
        """加密密码"""
        try:
            return self.encrypt_aes()
        except Exception:
            return self.password
