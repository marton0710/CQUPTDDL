import uuid
from datetime import datetime, timedelta
from logging import INFO, getLogger
from typing import Any

import fuckids
from httpx import AsyncClient

from cquptddl import core
from cquptddl.exc import LoginFailed, QRCodeNotScanned, QRLoginSessionNotFound

from .const import IDS_GET_USERINFO_SERVICE

_qrcode_login_sessions = dict[
    uuid.UUID, tuple[fuckids.AsyncContext, datetime]
]()  # {会话ID: (会话, 会话创建时间)}
_logger = getLogger(__name__)
_logger.setLevel(INFO)


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
    async with core.factory.get_client() as client:
        try:
            _, ctx = await fuckids.password_login_async(
                IDS_GET_USERINFO_SERVICE, username, password, client=client
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
            _logger.error("获取用户信息失败", exc_info=e)
            raise LoginFailed("获取用户信息失败") from e

    return uid, name, _get_ids_cookies(ctx.client)


async def get_login_qrcode() -> tuple[str, uuid.UUID]:
    """获取登录二维码
    Returns:
        qrcode_url: 二维码内容
        session_id: 登录会话id
    """
    _clear_expired_qrlogin_session()
    session_id = uuid.uuid4()
    async with core.factory.get_client() as client:
        qrcode_url, ctx = await fuckids.get_qrcode_async(
            IDS_GET_USERINFO_SERVICE, client=client
        )
    _qrcode_login_sessions[session_id] = (ctx, datetime.now().astimezone())
    return qrcode_url, session_id


async def qrcode_login(session_id: uuid.UUID) -> tuple[str, str, dict[str, str]]:
    """
    进行二维码登录
    Returns:
        uid: 统一认证码
        name: 姓名
        cookies: 登录时下发的cookies
    Raises:
        QRLoginSessionNotFound:
        QRCodeNotScanned:
        LoginFailed:
    """
    try:
        ctx = _qrcode_login_sessions[session_id][0]
    except KeyError as e:
        raise QRLoginSessionNotFound from e

    cookies = ctx.client.cookies
    async with core.factory.get_client(cookies=cookies) as client:
        ctx.client = client
        try:
            await fuckids.qrcode_login_async(ctx)
        except fuckids.errors.DataRequired as e:
            if e.keys != ["qrcode_scanned"]:
                _logger.error("二位码登录失败", exc_info=e)
                raise LoginFailed("无法登录你的账号") from e
            raise QRCodeNotScanned(ctx.qrcode_status)
        except fuckids.errors.QRCodeExpired as e:
            del _qrcode_login_sessions[session_id]
            raise QRCodeNotScanned(fuckids.context.QRCodeStatus.EXPIRED) from e
        except Exception as e:
            _logger.error("二位码登录失败", exc_info=e)
            del _qrcode_login_sessions[session_id]
            raise LoginFailed("无法登录你的账号") from e
        else:
            del _qrcode_login_sessions[session_id]

        try:
            uid, name = await _get_userinfo(ctx.client)
        except Exception as e:
            _logger.error("获取用户信息失败", exc_info=e)
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


def _clear_expired_qrlogin_session():
    now = datetime.now().astimezone()
    expired_session_ids = {
        id
        for id, (_, created_at) in _qrcode_login_sessions.items()
        if now - created_at >= timedelta(seconds=core.config.qr_login_session_ttl)
    }
    for i in expired_session_ids:
        _qrcode_login_sessions.pop(i, None)
