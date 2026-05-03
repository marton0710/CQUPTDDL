from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils import Error
from app.schemas import Register
from app.db.session import get_session
from app.service import ChaoXingService, XueZaiService, YuKeTangService, UserService, CacheService

router = APIRouter(prefix="/api")


@router.get("/register")
async def register(
        user: Register,
        session: AsyncSession = Depends(get_session)
):
    """
    注册
    :param user: 注册校验
    :param session: 数据库session
    :return:
    """
    userservice = UserService(session=session, username=user.username)
    await userservice.add_new_user()


@router.get("/chaoxing/{username}/{password}")
async def chaoxing(
        username: str,
        password: str,
):
    """
    超星
    :param username: 用户名
    :param password: 密码
    :return: 状态
    """
    chaoxingservice = ChaoXingService(username=username, password=password)
    cacheservice = CacheService()
    try:
        homework = await cacheservice.get_or_refresh_homework(
            user_id=int(username),
            platform=chaoxingservice.platform,
            fetcher=chaoxingservice.get_chaoxing_homework,
        )
        return {
            "errcode": 0,
            "homework": homework,
        }
    except Error as e:
        raise HTTPException(
            status_code=e.code,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )
    finally:
        await chaoxingservice.close()


@router.get("/xuezai/{username}/{password}")
async def xuezai(
        username: str,
        password: str,
):
    """
    学在重邮
    :param username: 用户名
    :param password: 密码
    :return: 状态
    """
    xuezaiservice = XueZaiService(username=username, password=password)
    cacheservice = CacheService()
    try:
        homework = await cacheservice.get_or_refresh_homework(
            user_id=int(username),
            platform=xuezaiservice.platform,
            fetcher=xuezaiservice.get_xuezai_homework,
        )
        return {
            "errcode": 0,
            "homework": homework,
        }
    except Error as e:
        raise HTTPException(
            status_code=e.code,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )
    finally:
        await xuezaiservice.close()


@router.get("/yuketang/{user_id}")
async def yuketang(
        user_id: int,
        session: AsyncSession = Depends(get_session)
):
    """
    雨课堂
    :param user_id: 用户id
    :param session: 数据库session
    :return: 状态
    """
    yuketangservice = await YuKeTangService.create(session=session, user_id=user_id)
    cacheservice = CacheService()
    try:
        homework = await cacheservice.get_or_refresh_homework(
            user_id=user_id,
            platform=yuketangservice.platform,
            fetcher=yuketangservice.get_yuketang_homework,
        )
        return {
            "errcode": 0,
            "homework": homework,
        }
    except Error as e:
        raise HTTPException(
            status_code=e.code,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )
    finally:
        await yuketangservice.close()
