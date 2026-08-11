import traceback
from typing import Any

import fuckids
from httpx import AsyncClient

from cquptddl.exc import LoginFailed

from .const import IDS_GET_USERINFO_SERVICE


async def password_login(
    username: str, password: str
) -> tuple[str, str, dict[str, str]]:
    """使用重邮统一认证账号登录系统
    **必须获取真实统一认证码，防止用户使用别名登录导致的账号多开**

    Returns:
        uid: 统一认证码
        name: 姓名
        cookies: 登录时下发的cookies

    Raises:
        LoginFailed
    """
    try:
        _, ctx = await fuckids.password_login_async(
            IDS_GET_USERINFO_SERVICE, username, password
        )
    except fuckids.errors.WrongPassword as e:
        raise LoginFailed("用户名或密码错误") from e
    except fuckids.errors.DataRequired as e:
        if "captcha" in e.keys:
            raise LoginFailed("请手动登录一次统一认证平台以去除验证码")
    except Exception as e:
        raise LoginFailed("无法登录你的账号") from e

    try:
        uid, name = await _get_userinfo(ctx.client)
    except Exception as e:
        traceback.print_exc()
        raise LoginFailed("获取用户信息失败") from e

    return uid, name, _get_ids_cookies(ctx.client)


async def _get_userinfo(client: AsyncClient) -> tuple[str, str]:
    """从ids获取用户信息
    警告：慢速接口"""
    userinfo_resp = await client.post(
        IDS_GET_USERINFO_SERVICE, follow_redirects=True, timeout=10
    )
    userinfo_json: dict[str, Any] = userinfo_resp.raise_for_status().json()
    assert userinfo_json["code"] == "0"
    return userinfo_json["datas"]["uid"], userinfo_json["datas"]["cn"]


def _get_ids_cookies(client: AsyncClient) -> dict[str, str]:
    return {
        item.name: item.value
        for item in client.cookies.jar
        if item.domain == "ids.cqupt.edu.cn" and item.value
    }
