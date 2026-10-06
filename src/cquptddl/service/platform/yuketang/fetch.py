from datetime import datetime

from httpx import AsyncClient

from cquptddl.model.db import Homework
from cquptddl.model.schema.platform import PlatformEnum

IDSLOGIN_SERVICE_URL = "http://cqupt.yuketang.cn/edu_admin/university_cas_login/3042/"
GET_COURSES_URL = "https://changjiang.yuketang.cn/v2/api/web/courses/list?identity=2"
GET_COURSE_HOMEWORK_URL = "https://changjiang.yuketang.cn/v2/api/web/logs/learn/{classroom_id}?actype=5&page=0&offset=20&sort=-1"
HOMEWORK_DETAIL_URL = (
    "https://changjiang.yuketang.cn/v2/web/exam/{classroom_id}/{hmw_id}"
)


async def get_course(client: AsyncClient) -> dict[str, int]:
    """
    获取课程列表
    Returns:
        courses: {课程名称: 班级id}
    """
    dist_url = GET_COURSES_URL
    class_info: dict[str, int] = {}
    payload = (await client.get(url=dist_url)).raise_for_status().json()

    course_list = payload.get("data", {}).get("list", [])
    for item in course_list:
        name = item.get("name")
        classroom_id = item.get("classroom_id")
        if name and classroom_id is not None:
            class_info[str(name)] = int(classroom_id)
    return class_info


async def get_course_homeworks(
    client: AsyncClient, user_id: str, course_name: str, classroom_id: int
) -> list[Homework]:
    payload = (
        (await client.get(GET_COURSE_HOMEWORK_URL.format(classroom_id=classroom_id)))
        .raise_for_status()
        .json()
    )
    homeworks: list[Homework] = []
    for item in payload.get("data", {}).get("activities", []):
        if item.get("type") == 5:
            ddl_timestamp = item["deadline"] // 1000
            homeworks.append(
                Homework(
                    id=Homework.generate_id(
                        user_id, PlatformEnum.YUKETANG, str(item["id"])
                    ),
                    user_id=user_id,
                    course_name=course_name,
                    title=item["title"],
                    deadline=datetime.fromtimestamp(ddl_timestamp).astimezone()
                    if ddl_timestamp != 0
                    else None,
                    url=HOMEWORK_DETAIL_URL.format(
                        classroom_id=classroom_id, hmw_id=item["courseware_id"]
                    ),
                    platform=PlatformEnum.YUKETANG,
                )
            )
        elif item.get("type") == 20:
            ddl_timestamp = item["content"]["score_d"] // 1000
            homeworks.append(
                Homework(
                    id=Homework.generate_id(
                        user_id, PlatformEnum.YUKETANG, str(item["id"])
                    ),
                    user_id=user_id,
                    course_name=course_name,
                    title=item["title"],
                    deadline=datetime.fromtimestamp(ddl_timestamp).astimezone()
                    if ddl_timestamp != 0
                    else None,
                    url=HOMEWORK_DETAIL_URL.format(
                        classroom_id=classroom_id,
                        hmw_id=item["content"]["leaf_type_id"],
                    ),
                    platform=PlatformEnum.YUKETANG,
                )
            )

    return homeworks
