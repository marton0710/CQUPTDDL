class Error(Exception):
    def __init__(self, code, message):
        """
        自定义错误
        :param code: 错误码
        :param message: 错误消息
        """
        self.code = code
        self.message = message
        super().__init__(message)


class LoginFailed(Error):
    def __init__(self, message: str = "登录失败"):
        super().__init__(code=400, message=message)
