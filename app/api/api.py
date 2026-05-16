from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils import Error
from app.api.auth import get_current_user
from app.schemas import Login, Register, Request as PlatFormRequest
from app.db.session import get_session
from app.service import ChaoXingService, XueZaiService, YuKeTangService, UserService, AllHomeworkService

router = APIRouter(prefix="/api")


@router.post("/ddl/login")
async def login(
        resp: Login,
        session: AsyncSession = Depends(get_session),
):
    """
    登录
    :param resp: 请求
    :param session: 数据库会话
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


@router.post("/ddl/register")
async def register(
        user: Register,
        session: AsyncSession = Depends(get_session),
):
    """
    注册
    :param user: 注册校验
    :param session: 数据库会话
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
        chaoxingrequest: PlatFormRequest,
        session: AsyncSession = Depends(get_session),
        current_user=Depends(get_current_user),
):
    """
    超星
    :param chaoxingrequest: 超星请求体
    :param current_user: 当前用户
    :param session: 数据库会话
    :return: 状态
    """
    chaoxingservice = ChaoXingService(
        username=chaoxingrequest.username,
        password=chaoxingrequest.password,
        owner=current_user.username,
        session=session,
    )
    try:
        return await chaoxingservice.refresh_homework()
    except Error as e:
        raise HTTPException(
            status_code=e.code,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )


@router.post("/xuezai")
async def xuezai(
        xuezairequest: PlatFormRequest,
        session: AsyncSession = Depends(get_session),
        current_user=Depends(get_current_user),
):
    """
    学在重邮
    :param xuezairequest: 学在重邮请求体
    :param current_user: 当前用户
    :param session: 数据库会话
    :return: 状态
    """
    xuezaiservice = XueZaiService(
        username=xuezairequest.username,
        password=xuezairequest.password,
        owner=current_user.username,
        session=session,
    )
    try:
        return await xuezaiservice.refresh_homework()
    except Error as e:
        raise HTTPException(
            status_code=e.code,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )


@router.post("/yuketang")
async def yuketang(
        yuketangrequest: PlatFormRequest,
        session: AsyncSession = Depends(get_session),
        current_user = Depends(get_current_user),
):
    """
    雨课堂
    :param yuketangrequest: 雨课堂请求体
    :param current_user: 当前用户
    :param session: 数据库会话
    :return: 状态
    """
    yuketangservice = YuKeTangService(
        username=yuketangrequest.username,
        password=yuketangrequest.password,
        owner=current_user.username,
        session=session,
    )
    try:
        return await yuketangservice.refresh_homework()
    except Error as e:
        raise HTTPException(
            status_code=e.code,
            detail={
                "code": e.code,
                "message": e.message,
            }
        )


@router.get("/ddl/all_homework")
async def allhomework(
        session: AsyncSession = Depends(get_session),
        current_user = Depends(get_current_user),
):
    """
    获取全部作业
    :param session: 数据库会话
    :param current_user: 当前用户
    :return:
    """
    allhomeworkservice = AllHomeworkService(
        session=session,
        current_user=current_user,
    )
    return await allhomeworkservice.get_all_homework()
