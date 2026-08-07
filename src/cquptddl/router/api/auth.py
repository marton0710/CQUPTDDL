from typing import Annotated

from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.core.config import config
from cquptddl.middleware.auth import need_login
from cquptddl.model.db.user import User
from cquptddl.model.schema.auth import LoginInput, LoginOutput, Userinfo

router = APIRouter()


@router.post("/login", response_model=LoginOutput)
async def _(
    model: LoginInput,
    session: Annotated[AsyncSession, Depends(core.get_session)],
    token: Annotated[str, Cookie()] = "",
) -> JSONResponse:
    if token:
        user: User = await core.call("auth.get_user_from_token", session, token)
        return JSONResponse(LoginOutput(name=user.name).model_dump())

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
async def _(refresh_token: Annotated[str, Cookie()]):
    _result: tuple[str, str] = core.call("auth.refresh_token", refresh_token)
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


@router.get("/userinfo")
async def _(user: Annotated[User, Depends(need_login)]) -> Userinfo:
    return Userinfo(
        email=user.email,
        qqchan_id=user.qqchan_id,
        meetschedule_key=user.meetschedule_key,
    )


# @router.put("/userinfo", status_code=202)
# async def _(user: Annotated[User, Depends(need_login)], model: UserinfoInput):
#     pass


@router.patch("/userinfo", status_code=204)
async def _(user: Annotated[User, Depends(need_login)], model: Userinfo):
    for field in model.model_fields_set:
        setattr(user, field, getattr(model, field))
