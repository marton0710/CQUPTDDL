from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils import Error
from app.api.auth import get_current_user
from app.schemas import Login, Register, ChaoXingRequest, YuKeTangRequest, XueZaiRequest
from app.db.session import get_session
from app.service import ChaoXingService, XueZaiService, YuKeTangService, UserService, CacheService

router = APIRouter(prefix="/api")


@router.post("/login")
async def login(
        resp: Login,
        session: AsyncSession = Depends(get_session),
):
    """
    登录
    :param resp: 请求
    :param session: 数据库服务
    :return:
    """
    username = resp.username
    password = resp.password
    email = resp.email
    userservice = UserService(
        session=session,
        username=username,
        password=password,
        email=email,
    )
    try:
        access_token = await userservice.login()
        return {
            "errcode": 0,
            "username": username,
            "token": access_token,
        }
    except Error as e:
        raise HTTPException(
            status_code=e.code,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )


@router.post("/register")
async def register(
        user: Register,
        session: AsyncSession = Depends(get_session),
):
    """
    注册
    :param user: 注册校验
    :param session: 数据库session
    :return:
    """
    username = user.username
    password = user.password
    confirm_password = user.confirm_password
    email = user.email
    userservice = UserService(
        session=session,
        username=username,
        password=password,
        confirm_password=confirm_password,
        email=email,
    )
    try:
        um = await userservice.add_new_user()
        return {
            "errcode": 0,
            "username": um,
        }
    except Error as e:
        raise HTTPException(
            status_code=e.code,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )


@router.post("/chaoxing")
async def chaoxing(
        chaoxingrequest: ChaoXingRequest,
        current_user = Depends(get_current_user),
):
    """
    超星
    :param chaoxingrequest: 超星请求体
    :param current_user: 当前用户
    :return: 状态
    """
    um = chaoxingrequest.username
    password = chaoxingrequest.password
    chaoxingservice = ChaoXingService(username=um, password=password)
    cacheservice = CacheService()
    try:
        homework = await cacheservice.get_or_refresh_homework(
            username=um,
            platform=chaoxingservice.platform,
            fetcher=chaoxingservice.get_chaoxing_homework,
        )
        return {
            "errcode": 0,
            "username": um,
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


@router.post("/xuezai")
async def xuezai(
        xuezairequest: XueZaiRequest,
        current_user = Depends(get_current_user)
):
    """
    学在重邮
    :param xuezairequest: 学在重邮请求体
    :param current_user: 当前用户
    :return: 状态
    """
    um = xuezairequest.username
    password = xuezairequest.password
    xuezaiservice = XueZaiService(username=um, password=password)
    cacheservice = CacheService()
    try:
        homework = await cacheservice.get_or_refresh_homework(
            username=um,
            platform=xuezaiservice.platform,
            fetcher=xuezaiservice.get_xuezai_homework,
        )
        return {
            "errcode": 0,
            "username": um,
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


@router.post("/yuketang")
async def yuketang(
        yuketangrequest: YuKeTangRequest,
        current_user = Depends(get_current_user),
):
    """
    雨课堂
    :param yuketangrequest: 雨课堂请求体
    :param current_user: 当前用户
    :return: 状态
    """
    cookies = yuketangrequest.cookies
    um = yuketangrequest.username
    cacheservice = CacheService()
    try:
        yuketangservice = await YuKeTangService.create(cookies=cookies)
        homework = await cacheservice.get_or_refresh_homework(
            username=um,
            platform=yuketangservice.platform,
            fetcher=yuketangservice.get_yuketang_homework,
        )
        await yuketangservice.close()
        return {
            "errcode": 0,
            "username": um,
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
