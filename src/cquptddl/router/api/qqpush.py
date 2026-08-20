from collections.abc import Iterable
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.middleware.auth import need_login
from cquptddl.middleware.qqpush import verify_api_key
from cquptddl.model.db import Homework, User
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.schema.qqpush import QQPushConfigSchema

router = APIRouter()


@router.post("/configure", status_code=204)
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    user: Annotated[User, Depends(need_login)],
    model: QQPushConfigSchema,
):
    await core.symbol.call("qqpush.configure", session, user, model)


@router.post("/_/dying_homeworks")
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    _: Annotated[None, Depends(verify_api_key)],
    qqchan_id: str,
):
    config: QQPushConfig = await core.symbol.call(
        "qqpush.get_user_config_from_qqchan_id", session, qqchan_id
    )
    homeworks: Iterable[Homework] = await core.symbol.call(
        "homework.get_user_dying_homeworks",
        session,
        config.user_id,
        config.qq_push_scope,
    )
    await core.symbol.call("qqpush.push_dying_homeworks", config.user_id, homeworks)
