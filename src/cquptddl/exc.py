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


class QRLoginSessionNotFound(LoginFailed):
    status = 404
    detail = "找不到此会话"


class InvalidToken(CquptddlException):
    status = 401
    detail = "无效的token"


class ExpiredToken(InvalidToken):
    detail = "token已过期"


class UserReloginRequired(CquptddlException):
    status = 510
    detail = "需要手动重新登录"


class NoSuchHomework(CquptddlException):
    status = 404
    detail = "你没有此id的作业"


class RefreshCoolingDown(CquptddlException):
    status = 429
    detail = "刷新作业还在冷却中，请稍后再试"


class InvalidPlatformCredentialFormat(CquptddlException):
    status = 422
    detail = "平台凭据格式不正确"


class PlatformNotBound(CquptddlException):
    status = 428
    detail = "请先绑定该平台"


class InvalidPlatformCookie(CquptddlException):
    status = 510
    detail = "平台cookie无效，请检查是否已过期"


class WrongQQPushAPIKey(CquptddlException):
    status = 403
    detail = "你不能调用此接口"


class MeetscheduleBindingExisted(CquptddlException):
    status = 409
    detail = "你已经绑定过Meet课程表了，如需重新绑定，请先解绑"


class InvalidMeetScheduleKey(CquptddlException):
    status = 400
    detail = "Meet课程表key无效"


class MeetscheduleNotBound(CquptddlException):
    status = 428
    detail = "未绑定Meet课程表"


class MeetscheduleKeyPermissionDenied(CquptddlException):
    status = 403
    detail = "Meet课程表key权限不足。至少需要：读取课表、读取事件、写入事件"


class RaceLimitExceed(CquptddlException):
    status = 429
    detail = "服务器忙，请稍后重试"
