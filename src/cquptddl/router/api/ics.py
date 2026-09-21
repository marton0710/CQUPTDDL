import uuid
from logging import INFO, getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import CquptddlException
from cquptddl.middleware.auth import need_login
from cquptddl.model.db import User
from cquptddl.model.schema.ics import (
    IcsSubscriptionCreatedSchema,
    IcsSubscriptionSchema,
)
from cquptddl.model.schema.platform import PlatformEnum

ICS_MEDIA_TYPE = "text/calendar"
ICS_FILENAME = "cquptddl.ics"
ICS_ETAG_HEADER = "ETag"
ICS_CACHE_CONTROL = "private, no-cache"

router = APIRouter()
_logger = getLogger(__name__)
_logger.setLevel(INFO)


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    for part in if_none_match.split(","):
        part = part.strip()
        if part == "*":
            return True
        if part.startswith("W/"):
            part = part.removeprefix("W/").strip()
        if part == etag:
            return True
    return False


@router.get("/subscription")
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    user: Annotated[User, Depends(need_login)],
) -> list[IcsSubscriptionSchema]:
    subscriptions = await core.symbol.call("ics.list_subscriptions", session, user.id)
    return [IcsSubscriptionSchema.model_validate(i.model_dump()) for i in subscriptions]


@router.post("/subscription")
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    user: Annotated[User, Depends(need_login)],
) -> IcsSubscriptionCreatedSchema:
    subscription, token = await core.symbol.call(
        "ics.create_subscription", session, user.id
    )
    # 明文token只在这一次响应里出现，之后库里只有sha256
    return IcsSubscriptionCreatedSchema.model_validate(
        subscription.model_dump() | {"token": token}
    )


@router.delete("/subscription/{subscription_id}", status_code=204)
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    user: Annotated[User, Depends(need_login)],
    subscription_id: UUID,
):
    await core.symbol.call("ics.delete_subscription", session, user.id, subscription_id)


@router.get("/feed/{token}.ics", response_class=Response)
async def _(
    session: Annotated[AsyncSession, Depends(core.factory.depends_session)],
    request: Request,
    token: str,
    platform: Annotated[PlatformEnum | None, Query()] = None,
) -> Response:
    try:
        body, etag = await core.symbol.call("ics.render_feed", session, token, platform)
    except CquptddlException:
        raise
    except Exception as e:
        errcode = uuid.uuid4()
        _logger.error("渲染ICS订阅时发生未知异常，异常码：%s", errcode, exc_info=e)
        raise CquptddlException(
            f"生成ICS订阅时发生异常，错误码：{errcode}，请联系管理员"
        ) from e

    headers = {
        ICS_ETAG_HEADER: etag,
        "Cache-Control": ICS_CACHE_CONTROL,
        "X-Robots-Tag": "noindex",
        "Content-Disposition": f'inline; filename="{ICS_FILENAME}"',
    }
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type=ICS_MEDIA_TYPE, headers=headers)
