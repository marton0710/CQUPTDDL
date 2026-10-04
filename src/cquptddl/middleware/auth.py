from typing import Annotated

from fastapi import Cookie, Depends

from cquptddl import core
from cquptddl.exc import InvalidToken
from cquptddl.middleware.session import SessionDep
from cquptddl.model.db import User


async def need_login(
    session: SessionDep,
    token: Annotated[str, Cookie()],
) -> User:
    if not token:
        raise InvalidToken
    return await core.symbol.auth_get_user_from_token(session, token)


UserDep = Annotated[User, Depends(need_login)]
