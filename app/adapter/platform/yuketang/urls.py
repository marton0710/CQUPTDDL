from furl import furl

BASE_URL = "https://changjiang.yuketang.cn"
GET_COURSES_URL = "https://changjiang.yuketang.cn/v2/api/web/courses/list?identity=2"
GET_COURSE_HOMEWORK_URL = furl(
    "https://changjiang.yuketang.cn/v2/api/web/logs/learn/"
).add(args={"actype": -1, "page": 0, "offset": 20, "sort": -1})
