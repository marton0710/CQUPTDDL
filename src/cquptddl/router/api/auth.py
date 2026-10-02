from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie
from fastapi.responses import JSONResponse, Response

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


@router.post("/login", response_model=LoginOutput)
async def _(
    model: LoginInput,
    session: SessionDep,
) -> JSONResponse:
    _result: tuple[str, str, str] = await core.symbol.call(
        "auth.password_login", session, model.username, model.password
    )
    access_token, refresh_token, name = _result

    resp = JSONResponse(LoginOutput(name=name).model_dump())
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
    return resp


@router.get("/qrcode_login")
async def _() -> GetLoginQRCodeOutput:
    """获取登录二维码"""
    r: tuple[str, UUID] = await core.symbol.call("auth.get_login_qrcode")
    qrcode_url, session_id = r
    return GetLoginQRCodeOutput(qrcode_url=qrcode_url, session_id=session_id)


@router.post("/qrcode_login", response_model=LoginOutput)
async def _(
    session: SessionDep,
    model: QRCodeLoginInput,
) -> JSONResponse:
    _result: tuple[str, str, str] = await core.symbol.call(
        "auth.qrcode_login", session, model.qrlogin_session_id, model.clear_password
    )
    access_token, refresh_token, name = _result

    resp = JSONResponse(LoginOutput(name=name).model_dump())
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
    return resp


@router.post("/refresh")
async def _(
    session: SessionDep,
    refresh_token: Annotated[str, Cookie()],
):
    _result: tuple[str, str] = await core.symbol.call(
        "auth.refresh_token", session, refresh_token
    )
    new_access_token, new_refresh_token = _result
    resp = Response(status_code=204)
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
    return resp


@router.get("/me")
async def _(
    session: SessionDep,
    user: UserDep,
) -> Userinfo:
    qqpush_config: QQPushConfigSchema = await core.symbol.call(
        "qqpush.get_configure", session, user.id
    )
    is_bound_meetschedule: bool = await core.symbol.call(
        "meetschedule.is_bound", session, user.id
    )
    ics_url_count: int = await core.symbol.call("ics.get_url_count", session, user.id)

    return Userinfo(
        name=user.name,
        qqpush_config=qqpush_config,
        is_bound_meetschedule=is_bound_meetschedule,
        ics_url_count=ics_url_count,
    )


@router.post("/logout", status_code=204)
async def _(user: UserDep):
    await core.symbol.call("auth.logout", user)
    resp = Response(status_code=204)
    resp.delete_cookie("token")
    resp.delete_cookie("refresh_token", "/api/auth/refresh")
    return resp


@router.delete("/me", status_code=204)
async def _(
    session: SessionDep,
    user: UserDep,
):
    await core.symbol.call("auth.delete_account", session, user)
    resp = Response(status_code=204)
    resp.delete_cookie("token")
    resp.delete_cookie("refresh_token", "/api/auth/refresh")
    return resp
