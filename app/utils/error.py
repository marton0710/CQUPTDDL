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
