from logging import INFO, getLogger

import fuckids

from cquptddl import core
from cquptddl.exc import LoginFailed
from cquptddl.model.db.user import User

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def login_from_platform_account(user: User, service: str) -> str:
    """使用当前账号登录
    自动获取当前账号的身份

    Args:
        service: 要登录的服务
    Returns:
        redirect_url: OAuth重定向地址
    """
    for _ in range(2):
        try:
            redirect_url, _ = await fuckids.cookie_login_async(service, user.ids_cookie)
        except fuckids.errors.CookieLoginFailed:
            _logger.debug(
                "用户%s尝试cookie登录平台%s失败，尝试relogin", user.id, service
            )
            await core.call("auth.relogin", user)
            _logger.debug("重新登录成功，正在重试")
            continue
            # raise LoginFailed("cookie登录失败，正在尝试密码登录") from e
        except fuckids.errors.LoginFailed as e:
            raise LoginFailed(str(e)) from e
        return redirect_url
    raise LoginFailed("尝试自动重新后使用cookie登录失败，请报告此问题")
