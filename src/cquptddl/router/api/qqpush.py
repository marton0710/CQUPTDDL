from typing import Annotated

from fastapi import APIRouter, Depends

from cquptddl import core
from cquptddl.middleware.auth import UserDep
from cquptddl.middleware.qqpush import verify_api_key
from cquptddl.middleware.session import SessionDep
from cquptddl.model.schema.qqpush import QQPushConfigSchema

router = APIRouter()


@router.post("/configure", status_code=204)
async def _(
    session: SessionDep,
    user: UserDep,
    model: QQPushConfigSchema,
):
    await core.symbol.qqpush_configure(session, user.id, model)


@router.post("/_/dying_homeworks")
async def _(
    session: SessionDep,
    _: Annotated[None, Depends(verify_api_key)],
    qqchan_id: str,
):
    config = await core.symbol.qqpush_get_user_config_from_qqchan_id(session, qqchan_id)
    if config is None:
        return "此ID没有绑定到平台，请先在个人中心完成绑定"

    homeworks = await core.symbol.homework_get_user_dying_homeworks(
        session,
        config.user_id,
        config.qq_push_scope,
    )
    await core.symbol.qqpush_push_dying_homeworks(config.user_id, homeworks)
