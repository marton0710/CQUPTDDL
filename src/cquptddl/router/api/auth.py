from typing import Annotated

from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.core.config import config
from cquptddl.middleware.auth import need_login
from cquptddl.model.db.user import User
from cquptddl.model.schema.auth import LoginInput, LoginOutput, Userinfo, UserinfoPatch

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
async def _(user: Annotated[User, Depends(need_login)]) -> Userinfo:
    qqchan_id_to_show = (
        None if user.qqchan_id is None else "******" + user.qqchan_id[-4:]
    )
    meetkey_to_show = (
        None if user.meetschedule_key is None else "******" + user.meetschedule_key[-4:]
    )
    return Userinfo(
        name=user.name,
        email=user.email,
        qqchan_id=qqchan_id_to_show,
        meetschedule_key=meetkey_to_show,
    )


# @router.put("/userinfo", status_code=202)
# async def _(user: Annotated[User, Depends(need_login)], model: UserinfoInput):
#     pass


@router.patch("/userinfo", status_code=204)
async def _(user: Annotated[User, Depends(need_login)], model: UserinfoPatch):
    for field in model.model_fields_set:
        setattr(user, field, getattr(model, field))


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
