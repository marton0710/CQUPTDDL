from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils import Error
from app.db.session import get_session
from app.service import ChaoXingService, XueZaiService, YuKeTangService

router = APIRouter(prefix="/api")


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
    try:
        await chaoxingservice.get_chaoxing_cookie()
        homework = await chaoxingservice.get_chaoxing_activities()
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
    xuezaiservice = await XueZaiService.create(username=username, password=password)
    try:
        await xuezaiservice.get_xuezai_cookie()
        homework = await xuezaiservice.get_xuezai_todo()
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


@router.get("/yuketang")
async def yuketang(
        session: AsyncSession = Depends(get_session)
):
    """
    雨课堂
    :param session: 服务器session
    :return: 状态
    """
    yuketangservice = await YuKeTangService.create(session=session)
    try:
        homework = await yuketangservice.get_yuketang_homework()
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
