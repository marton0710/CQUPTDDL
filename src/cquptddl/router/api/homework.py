from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.middleware.auth import need_login
from cquptddl.model.db import User
from cquptddl.model.schema.homework import (
    Homework as HomeworkSchema,
)
from cquptddl.model.schema.homework import (
    HomeworkCompleteInput,
    HomeworkResponse,
)
from cquptddl.model.schema.platform_auth import (
    AllAuthInputs,
    PlatformEnum,
)
from cquptddl.service.homework.platform.base import AuthMethod

router = APIRouter()


@router.get("")
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.factory.get_session)],
    num: Annotated[int, Query(ge=1, le=30)] = 10,
    page: Annotated[int, Query(ge=1)] = 1,
    platform: Annotated[PlatformEnum | None, Query()] = None,
) -> HomeworkResponse:
    homeworks = await core.call(
        "homework.get_cached_homework", session, user, platform, num, page
    )
    resp = HomeworkResponse(
        homeworks=[HomeworkSchema.model_validate(i.model_dump()) for i in homeworks],
        count=await core.call(
            "homework.get_cached_homework_count", session, user, platform
        ),
        last_refresh_time=await core.call(
            "homework.get_last_refresh_time", session, user, platform
        ),
    )
    # await refresh(user, platform)
    return resp


@router.post("/refresh", status_code=202)
async def refresh(
    user: Annotated[User, Depends(need_login)],
    platform: Annotated[PlatformEnum | None, Query()] = None,
):
    if platform is not None:
        core.task.background(
            core.call("homework.refresh_homework", user, platform),
            f"user_{user.id}_refresh_homework",
        )
    else:
        for p in PlatformEnum:
            core.task.background(
                core.call("homework.refresh_homework", user, p),
                f"user_{user.id}_refresh_homework",
            )


@router.post("/{id}/complete", status_code=204)
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.factory.get_session)],
    id: UUID,
    model: HomeworkCompleteInput,
):
    await core.call("homework.complete", session, user, id, model.is_complete)


@router.get("/platform/{platform_name}/auth_method")
async def _(platform_name: PlatformEnum) -> AuthMethod:
    return core.call("homework.platform.get_auth_method", platform_name)


@router.post("/platform/{platform_name}/bind", status_code=204)
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.get_session)],
    platform_name: PlatformEnum,
    credentials: AllAuthInputs,
):
    await core.call("homework.platform.bind", user, session, platform_name, credentials)


@router.post("/platform/{platform_name}/unbind", status_code=204)
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.get_session)],
    platform_name: PlatformEnum,
):
    return await core.call("homework.platform.unbind", session, user, platform_name)


@router.get("/platform/{platform_name}/valid_cookie")
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.get_session)],
    platform_name: PlatformEnum,
) -> bool:
    return await core.call(
        "homework.platform.valid_cookie", session, user, platform_name
    )
