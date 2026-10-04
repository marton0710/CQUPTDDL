from typing import Annotated

from fastapi import APIRouter, Cookie
from fastapi.responses import Response

from cquptddl import core
from cquptddl.core.config import config
from cquptddl.middleware.auth import UserDep
from cquptddl.middleware.session import SessionDep
from cquptddl.model.schema.auth import (
    GetLoginQRCodeOutput,
    LoginInput,
    LoginOutput,
    QRCodeLoginInput,
    Userinfo,
)
from cquptddl.model.schema.qqpush import QQPushConfigSchema

router = APIRouter()


@router.post("/login")
async def _(model: LoginInput, session: SessionDep, resp: Response) -> LoginOutput:
    access_token, refresh_token, name = await core.symbol.auth_password_login(
        session, model.username, model.password
    )

    resp.set_cookie(
        "token",
        access_token,
        config.ACCESS_TOKEN_EXPIRE_SECONDS,
        secure=not config.DEBUG,
        httponly=True,
    )
    resp.set_cookie(
        "refresh_token",
        refresh_token,
        config.REFRESH_TOKEN_EXPIRE_SECONDS,
        path="/api/auth/refresh",
        secure=not config.DEBUG,
        httponly=True,
    )
    return LoginOutput(name=name)


@router.get("/qrcode_login")
async def _() -> GetLoginQRCodeOutput:
    """获取登录二维码"""
    qrcode_url, session_id = await core.symbol.auth_get_login_qrcode()
    return GetLoginQRCodeOutput(qrcode_url=qrcode_url, session_id=session_id)


@router.post("/qrcode_login")
async def _(
    session: SessionDep, model: QRCodeLoginInput, resp: Response
) -> LoginOutput:
    access_token, refresh_token, name = await core.symbol.auth_qrcode_login(
        session, model.qrlogin_session_id, model.clear_password
    )

    resp.set_cookie(
        "token",
        access_token,
        config.ACCESS_TOKEN_EXPIRE_SECONDS,
        secure=not config.DEBUG,
        httponly=True,
    )
    resp.set_cookie(
        "refresh_token",
        refresh_token,
        config.REFRESH_TOKEN_EXPIRE_SECONDS,
        path="/api/auth/refresh",
        secure=not config.DEBUG,
        httponly=True,
    )
    return LoginOutput(name=name)


@router.post("/refresh", status_code=204)
async def _(
    session: SessionDep, refresh_token: Annotated[str, Cookie()], resp: Response
):
    new_access_token, new_refresh_token = await core.symbol.auth_refresh_token(
        session, refresh_token
    )
    resp.set_cookie(
        "token",
        new_access_token,
        config.ACCESS_TOKEN_EXPIRE_SECONDS,
        secure=not config.DEBUG,
        httponly=True,
    )
    resp.set_cookie(
        "refresh_token",
        new_refresh_token,
        config.REFRESH_TOKEN_EXPIRE_SECONDS,
        path="/api/auth/refresh",
        secure=not config.DEBUG,
        httponly=True,
    )


@router.get("/me")
async def _(
    session: SessionDep,
    user: UserDep,
) -> Userinfo:
    qqpush_config: QQPushConfigSchema = await core.symbol.qqpush_get_configure(
        session, user.id
    )
    is_bound_meetschedule: bool = await core.symbol.meetschedule_is_bound(
        session, user.id
    )
    ics_url_count: int = await core.symbol.ics_get_url_count(session, user.id)

    return Userinfo(
        name=user.name,
        qqpush_config=qqpush_config,
        is_bound_meetschedule=is_bound_meetschedule,
        ics_url_count=ics_url_count,
    )


@router.post("/logout", status_code=204)
async def _(user: UserDep, resp: Response):
    await core.symbol.auth_logout(user)
    resp.delete_cookie("token")
    resp.delete_cookie("refresh_token", "/api/auth/refresh")


@router.delete("/me", status_code=204)
async def _(session: SessionDep, user: UserDep, resp: Response):
    await core.symbol.auth_delete_account(session, user)
    resp.delete_cookie("token")
    resp.delete_cookie("refresh_token", "/api/auth/refresh")
