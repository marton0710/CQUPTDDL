from fastapi import APIRouter

from cquptddl import core
from cquptddl.middleware.auth import UserDep
from cquptddl.middleware.session import SessionDep
from cquptddl.model.schema.platform import AllAuthInputs, AuthMethod, PlatformEnum

router = APIRouter()


@router.get("/{platform_name}/auth_method")
async def _(platform_name: PlatformEnum) -> AuthMethod:
    return core.symbol.call("platform.get_auth_method", platform_name)


@router.post("/{platform_name}/bind", status_code=204)
async def _(
    user: UserDep,
    session: SessionDep,
    platform_name: PlatformEnum,
    credentials: AllAuthInputs,
):
    await core.symbol.call("platform.bind", user, session, platform_name, credentials)


@router.post("/{platform_name}/unbind", status_code=204)
async def _(
    user: UserDep,
    session: SessionDep,
    platform_name: PlatformEnum,
):
    return await core.symbol.call("platform.unbind", session, user.id, platform_name)


@router.get("/{platform_name}/valid_cookie")
async def _(
    user: UserDep,
    session: SessionDep,
    platform_name: PlatformEnum,
) -> bool | None:
    return await core.symbol.call(
        "platform.valid_cookie", session, user.id, platform_name
    )
