from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.middleware.auth import need_login
from cquptddl.model.db import User
from cquptddl.model.schema.platform_auth import AllAuthInputs, AuthMethod, PlatformEnum

router = APIRouter()


@router.get("/{platform_name}/auth_method")
async def _(platform_name: PlatformEnum) -> AuthMethod:
    return core.call("platform.get_auth_method", platform_name)


@router.post("/{platform_name}/bind", status_code=204)
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.depends_session)],
    platform_name: PlatformEnum,
    credentials: AllAuthInputs,
):
    await core.call("platform.bind", user, session, platform_name, credentials)


@router.post("/{platform_name}/unbind", status_code=204)
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.depends_session)],
    platform_name: PlatformEnum,
):
    return await core.call("platform.unbind", session, user, platform_name)


@router.get("/{platform_name}/valid_cookie")
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.depends_session)],
    platform_name: PlatformEnum,
) -> bool | None:
    return await core.call("platform.valid_cookie", session, user, platform_name)
