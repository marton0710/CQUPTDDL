from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import User
from app.db.repositories import UserRepositories
from app.utils import Error, get_token_sub

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        session: AsyncSession = Depends(get_session),
) -> User:
    """
    获取当前登录用户，路由守卫
    :param token: jwt token
    :param session: 数据库会话
    :return:
    """
    try:
        sub = get_token_sub(token)
    except Error as e:
        raise HTTPException(
            status_code=401,
            detail={"code": e.code, "message": e.message},
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo = UserRepositories(session=session)
    row = await repo.get_user_by_username(username=sub)
    if row is None:
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "message": "未登录"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return row
