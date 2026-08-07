from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from cquptddl.middleware.auth import need_login
from cquptddl.model.db.homework import PlatformEnum
from cquptddl.model.db.user import User
from cquptddl.model.schema.homework import Homework, HomeworkResponse
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
    platform: Annotated[PlatformEnum | None, Query()] = None,
) -> list[Homework]:
    pass


@router.post("/{id}/complete", status_code=204)
async def _(user: Annotated[User, Depends(need_login)], id: UUID):
    pass


@router.get("/platform/{platform_name}/auth_method")
async def _(
    user: Annotated[User, Depends(need_login)], platform_name: PlatformEnum
) -> AuthMethod:
    pass


@router.post("/platform/{platform_name}/bind")
async def _(user: Annotated[User, Depends(need_login)], platform_name: PlatformEnum):
    pass


@router.post("/platform/{platform_name}/unbind")
async def _(user: Annotated[User, Depends(need_login)], platform_name: PlatformEnum):
    pass
