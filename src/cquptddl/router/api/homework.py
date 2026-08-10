from asyncio import TaskGroup
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.middleware.auth import need_login
from cquptddl.model.db.user import User
from cquptddl.model.schema.homework import (
    Homework,
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
    num: Annotated[int, Query(ge=1, le=30)] = 10,
    page: Annotated[int, Query(ge=1)] = 1,
    platform: Annotated[PlatformEnum | None, Query()] = None,
) -> HomeworkResponse:
    pass


@router.post("/refresh")
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.get_session)],
    platform: Annotated[PlatformEnum | None, Query()] = None,
) -> list[Homework]:
    if platform is None:
        homeworks: list[Homework] = []
        async with TaskGroup() as tg:
            tasks = [
                tg.create_task(
                    core.call("homework.platform.fetch_homework", session, user, p)
                )  # XXX: 现在只是fetch，还没有落库
                for p in PlatformEnum
            ]
        for task in tasks:
            homeworks.extend(task.result())
        return homeworks
    return await core.call("homework.platform.fetch_homework", session, user, platform)


@router.post("/{id}/complete", status_code=204)
async def _(
    user: Annotated[User, Depends(need_login)], id: UUID, model: HomeworkCompleteInput
):
    pass


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
    return await core.call("homework.platform.unbind", user, session, platform_name)


@router.get("/platform/{platform_name}/valid_cookie")
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.get_session)],
    platform_name: PlatformEnum,
) -> bool:
    return await core.call(
        "homework.platform.valid_cookie", session, user, platform_name
    )
