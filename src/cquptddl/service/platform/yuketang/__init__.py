import json
import random
from logging import INFO, getLogger

from httpx import AsyncClient, HTTPStatusError

from cquptddl import core
from cquptddl.exc import InvalidPlatformCookie
from cquptddl.model.db.homework import Homework
from cquptddl.model.db.user import User
from cquptddl.model.schema.platform import AuthMethod, IDSLoginInput, PlatformEnum
from cquptddl.service.platform.base import Platform as BasePlatform
from cquptddl.service.platform.base.utils import login_with_ddl_account

from .fetch import (
    GET_COURSES_URL,
    IDSLOGIN_SERVICE_URL,
    get_course,
    get_course_homeworks,
)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
_logger = getLogger(__name__)
_logger.setLevel(INFO)


class Yuketang(BasePlatform):
    name = PlatformEnum.YUKETANG
    auth_method = AuthMethod.CQUPT_IDS

    @classmethod
    async def login(
        cls, client: AsyncClient, user: User, credentials: IDSLoginInput
    ) -> dict[str, str]:  # ty:ignore[invalid-method-override]
        redirect_url = await login_with_ddl_account(user, IDSLOGIN_SERVICE_URL)
        await client.get(redirect_url, follow_redirects=True)

        # 下面3句是为了让 cqupt.yuketang.com 和 changjiang.yuketang.com 共享 cookie
        sessionid = client.cookies["sessionid"]
        del client.cookies["sessionid"]
        client.cookies["sessionid"] = sessionid

        # 获取初始courses缓存
        courses = await get_course(client)

        return {
            "sessionid": sessionid,
            "courses": json.dumps(courses),
            "courses_ttl": str(random.randint(1, 14)),
        }

    @classmethod
    async def get_homework(
        cls, cookies: dict[str, str], user_id: str
    ) -> list[Homework]:
        async with core.factory.get_client(
            cookies={"sessionid": cookies["sessionid"]}
        ) as client:
            try:
                courses = await _try_courses_cache_and_fallback(client, cookies)
                homeworks: list[Homework] = []
                for cn, cid in courses.items():
                    homeworks.extend(
                        await get_course_homeworks(client, user_id, cn, cid)
                    )
            except HTTPStatusError as e:
                exc = InvalidPlatformCookie()
                _logger.error("雨课堂cookie无效", exc_info=exc)
                raise exc from e
        return homeworks

    @classmethod
    async def valid_cookie(cls, cookies: dict[str, str]) -> bool:
        """
        验证cookie的合理性
        """
        url = GET_COURSES_URL
        async with core.factory.get_client(
            # headers={"User-Agent": UA},
            cookies={"sessionid": cookies["sessionid"]},
            timeout=10,
        ) as client:
            return (await client.get(url=url)).status_code == 200


async def _try_courses_cache_and_fallback(
    client: AsyncClient, cookies: dict[str, str]
) -> dict[str, int]:
    """
    尝试使用缓存的课程
    如果缓存ttl耗尽则回退到联网获取，并重新缓存
    Returns:
        courses: {课程名称: 班级id}
    """
    courses_str = cookies.get("courses")
    ttl = int(cookies.get("courses_ttl", "0"))
    if courses_str is None:
        courses_str = "{}"
    courses: dict[str, int] = json.loads(courses_str)

    # 上方写法为过渡期间数据库自动迁移的写法，成熟后直接替换为下面的写法：
    # courses_str: dict[str, int] = json.loads(cookies['courses'])
    # ttl = int(cookies['courses_ttl'])
    if ttl:
        cookies["courses_ttl"] = str(ttl - 1)
        return courses
    courses = await get_course(client)
    cookies["courses"] = json.dumps(courses)
    cookies["courses_ttl"] = "13"
    return courses
