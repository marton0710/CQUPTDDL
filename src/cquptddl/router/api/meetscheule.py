from fastapi import APIRouter

from cquptddl import core
from cquptddl.middleware.auth import UserDep
from cquptddl.middleware.session import SessionDep
from cquptddl.model.schema.meetschedule import MeetscheduleConfigSchema

router = APIRouter()


@router.post("/bind", status_code=204)
async def _(
    session: SessionDep,
    user: UserDep,
    model: MeetscheduleConfigSchema,
):
    await core.symbol.meetschedule_bind(session, user.id, model.meetschedule_key)


@router.delete("/bind", status_code=202)
async def _(
    session: SessionDep,
    user: UserDep,
):
    await core.symbol.meetschedule_unbind(session, user.id)
