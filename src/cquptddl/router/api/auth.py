from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.core.config import config
from cquptddl.middleware.auth import need_login
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.db.user import User
from cquptddl.model.schema.auth import (
    GetLoginQRCodeOutput,
    LoginInput,
    LoginOutput,
    QRCodeLoginInput,
    Userinfo,
)

router = APIRouter()


@router.post("/login", response_model=LoginOutput)
async def _(
    model: LoginInput,
    session: Annotated[AsyncSession, Depends(core.depends_session)],
) -> JSONResponse:
    _result: tuple[str, str, str] = await core.call(
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
    session: Annotated[AsyncSession, Depends(core.depends_session)],
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
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    refresh_token: Annotated[str, Cookie()],
):
    _result: tuple[str, str] = await core.call(
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
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    user: Annotated[User, Depends(need_login)],
) -> Userinfo:
    qqpush_config = await session.get(QQPushConfig, user.id)
    meetschedule_config = await session.get(MeetscheduleConfig, user.id)
    assert qqpush_config is not None

    qqpush_config_data = qqpush_config.model_dump()
    del qqpush_config_data["user_id"]

    if meetschedule_config is None:
        meetschedule_config_data = None
    else:
        meetschedule_config_data = meetschedule_config.model_dump()
        del meetschedule_config_data["user_id"]
        del meetschedule_config_data["schedule_id"]
        meetschedule_config_data["meetschedule_key"] = (
            None
            if meetschedule_config_data["api_key"] is None
            else "******" + meetschedule_config_data["api_key"][-4:]
        )
        del meetschedule_config_data["api_key"]

    return Userinfo(
        name=user.name,
        qqpush_config=qqpush_config_data,
        meetschedule_config=meetschedule_config_data,
    )


@router.post("/logout", status_code=204)
async def _(user: Annotated[User, Depends(need_login)]):
    await core.call("auth.logout", user)
    resp = Response(status_code=204)
    resp.delete_cookie("token")
    resp.delete_cookie("refresh_token", "/api/auth/refresh")
    return resp


@router.delete("/me", status_code=204)
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    user: Annotated[User, Depends(need_login)],
):
    await core.symbol.call("auth.delete_account", session, user)
    resp = Response(status_code=204)
    resp.delete_cookie("token")
    resp.delete_cookie("refresh_token", "/api/auth/refresh")
    return resp
