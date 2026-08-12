import uuid
from logging import INFO, getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import InvalidPlatformCookie, PlatformNotBound, RefreshCoolingDown
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

REFRESH_HOMEWORK_PROMPT_TEMPLATE = "{platform}: {info}"
REFRESH_HOMEWORK_UNKNOW_ERROR_PROMPT_TEMPLATE = (
    "{platform}: 未知异常，请联系管理员，异常码：{errcode}"
)
router = APIRouter()
logger = getLogger(__name__)
logger.setLevel(INFO)


@router.get("")
async def _(
    user: Annotated[User, Depends(need_login)],
    session: Annotated[AsyncSession, Depends(core.factory.get_session)],
    num: Annotated[int, Query(ge=-1, le=30)] = -1,
    page: Annotated[int, Query(ge=1)] = 1,
    platform: Annotated[PlatformEnum | None, Query()] = None,
) -> HomeworkResponse:
    """
    Args:
        num: 一页的作业数量，-1为所有作业
    """
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


@router.post("/refresh")
async def refresh(
    session: Annotated[AsyncSession, Depends(core.factory.get_session)],
    user: Annotated[User, Depends(need_login)],
    platform: Annotated[PlatformEnum | None, Query()] = None,
) -> list[str]:
    if platform is not None:
        await core.call("homework.refresh_homework", session, user, platform)
        return []
    else:
        prompts = []
        for p in PlatformEnum:
            try:
                await core.call("homework.refresh_homework", session, user, p)
            except (PlatformNotBound, InvalidPlatformCookie, RefreshCoolingDown) as e:
                prompts.append(
                    REFRESH_HOMEWORK_PROMPT_TEMPLATE.format(platform=p, info=e)
                )
            except Exception as e:
                errcode = uuid.uuid4()
                logger.error("刷新作业时出现未知异常，异常码：%s", errcode, exc_info=e)
                prompts.append(
                    REFRESH_HOMEWORK_UNKNOW_ERROR_PROMPT_TEMPLATE.format(
                        platform=p, errcode=errcode
                    )
                )
        return prompts


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
) -> bool | None:
    return await core.call(
        "homework.platform.valid_cookie", session, user, platform_name
    )
