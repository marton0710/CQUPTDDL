import fuckids

from cquptddl import core
from cquptddl.exc import LoginFailed
from cquptddl.model.db.user import User


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
            await core.call("auth.relogin", user)
            continue
            # raise LoginFailed("cookie登录失败，正在尝试密码登录") from e
        except fuckids.errors.LoginFailed as e:
            raise LoginFailed(str(e)) from e
        return redirect_url
    raise LoginFailed("尝试自动重新后使用cookie登录失败，请报告此问题")
