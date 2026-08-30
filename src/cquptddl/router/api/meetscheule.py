from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import MeetscheduleNotBound
from cquptddl.middleware.auth import need_login
from cquptddl.model.db import User
from cquptddl.model.db.meetschedule_config import MeetscheduleConfig
from cquptddl.model.schema.meetschedule import MeetscheduleConfigSchema

router = APIRouter()


@router.post("/bind", status_code=204)
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    user: Annotated[User, Depends(need_login)],
    model: MeetscheduleConfigSchema,
):
    await core.symbol.call("meetschedule.bind", session, user, model)


@router.delete("/bind", status_code=202)
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    user: Annotated[User, Depends(need_login)],
):
    if await session.get(MeetscheduleConfig, user.id) is None:
        raise MeetscheduleNotBound
    core.task.background(
        core.symbol.call("meetschedule.unbind", user.id),
        f"unbind_meet_for_{user.id}",
    )
