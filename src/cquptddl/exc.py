from fastapi import HTTPException


class CquptddlException(HTTPException):
    status: int = 500
    detail: str = "重邮聚合截止线异常"

    def __init__(self, detail: str | None = None, status: int | None = None):
        super().__init__(status or self.status, detail or self.detail)


class LoginFailed(CquptddlException):
    status = 500
    detail = "登录失败"


class WrongPassword(LoginFailed):
    status = 400
    detail = "用户名或密码错误"


class InvalidToken(CquptddlException):
    status = 401
    detail = "无效的token"


class ExpiredToken(InvalidToken):
    detail = "token已过期"
