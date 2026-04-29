from datetime import datetime


def shifttime(time: int) -> str:
    """
    将时间戳转为正确格式
    :param time: 时间戳
    :return: %Y-%m-%d %H:%M:%S格式的时间
    """
    return datetime.fromtimestamp(time / 1000).strftime("%Y-%m-%d %H:%M:%S")
