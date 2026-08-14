from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.exc import InvalidToken


async def need_login(
    session: Annotated[AsyncSession, Depends(core.depends_session)],
    token: Annotated[str, Cookie()] = "",
):
    if not token:
        raise InvalidToken
    return await core.call("auth.get_user_from_token", session, token)
