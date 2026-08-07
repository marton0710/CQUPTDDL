import fuckids

from cquptddl import core
from cquptddl.exc import LoginFailed


async def login_from_platform_account(service: str) -> str:
    """使用当前账号登录
    自动获取当前账号的身份

    Args:
        service: 要登录的服务
    Returns:
        redirect_url: OAuth重定向地址
    """
    for _ in range(2):
        cookies: dict[str, str] = core.call("auth.get_current_user_cookie")
        try:
            redirect_url, _ = await fuckids.cookie_login_async(service, cookies)
        except fuckids.errors.CookieLoginFailed:
            # core.call("auth.relogin")     # FIXME: 接口未对齐
            continue
            # raise LoginFailed("cookie登录失败，正在尝试密码登录") from e
        except fuckids.errors.LoginFailed as e:
            raise LoginFailed(str(e)) from e
        return redirect_url
    raise LoginFailed("尝试自动重新后使用cookie登录失败，请报告此问题")
