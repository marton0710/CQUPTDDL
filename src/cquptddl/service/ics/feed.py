from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from cquptddl.core import config
from cquptddl.model.db import Homework
from cquptddl.model.schema.platform import PlatformEnum

CALENDAR_NAME = "聚合截止线"
CALENDAR_DESCRIPTION = "重邮聚合截止线作业订阅"
PRODID = "-//CQUPTDDL//作业订阅//CN"
REFRESH_INTERVAL = timedelta(hours=1)
PUBLISHED_TTL = "PT1H"
UID_DOMAIN = "cquptddl"
# 固定VTIMEZONE的生成范围，保证相同输入渲染出相同字节
VTIMEZONE_FIRST_DATE = date(1970, 1, 1)
VTIMEZONE_LAST_DATE = date(2038, 1, 1)


def to_aware(dt: datetime, tz: ZoneInfo) -> datetime:
    """把数据库里naive的本地时间补上时区"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def feed_etag(body: bytes) -> str:
    return f'"{sha256(body).hexdigest()[:32]}"'


def build_calendar(
    homeworks: Iterable[Homework],
    *,
    tz: ZoneInfo,
    duration: timedelta,
    dtstamp: datetime,
) -> Calendar:
    """把作业渲染成日历。纯函数，相同输入输出逐字节一致"""
    calendar = Calendar()
    calendar.add("prodid", PRODID)
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.calendar_name = CALENDAR_NAME
    calendar.description = CALENDAR_DESCRIPTION
    calendar.add("X-WR-TIMEZONE", str(tz))
    calendar.refresh_interval = REFRESH_INTERVAL
    calendar.add("X-PUBLISHED-TTL", PUBLISHED_TTL)

    for homework in homeworks:
        if homework.deadline is None:
            continue

        deadline = to_aware(homework.deadline, tz)
        event = Event()
        event.add("uid", f"{homework.id}@{UID_DOMAIN}")
        event.add("summary", homework.title)
        event.add("dtstart", deadline - duration)
        event.add("dtend", deadline)
        event.add("dtstamp", dtstamp)
        event.categories = [str(homework.platform)]
        event.add("transp", "TRANSPARENT")
        event.add("status", "CONFIRMED")
        description = [f"课程：{homework.course_name}", f"平台：{homework.platform}"]
        if homework.url:
            event.add("url", homework.url)
            description.append(f"链接：{homework.url}")
        event.add("description", "\n".join(description))
        calendar.add_component(event)

    calendar.add_missing_timezones(
        first_date=VTIMEZONE_FIRST_DATE, last_date=VTIMEZONE_LAST_DATE
    )
    return calendar


def render_ics(
    homeworks: Iterable[Homework],
    *,
    tz: ZoneInfo,
    duration: timedelta,
    dtstamp: datetime,
) -> bytes:
    return build_calendar(
        homeworks, tz=tz, duration=duration, dtstamp=dtstamp
    ).to_ical()


async def get_feed_homeworks(
    session: AsyncSession,
    user_id: str,
    platform: PlatformEnum | None = None,
) -> Sequence[Homework]:
    """取要放进日历的作业：未完成、有截止时间、且还在保留期内"""
    cutoff = datetime.now().astimezone() - timedelta(days=config.ics_past_days)
    stmt = (
        select(Homework)
        .where(Homework.user_id == user_id)
        .where(Homework.done == False)
        .where(Homework.deadline.is_not(None))  # ty: ignore[unresolved-attribute]
        .where(Homework.deadline >= cutoff)  # ty: ignore[unsupported-operator]
        .order_by(Homework.deadline, Homework.id)  # ty: ignore[invalid-argument-type]
    )
    if platform is not None:
        stmt = stmt.where(Homework.platform == platform)
    resp = await session.execute(stmt)
    return resp.scalars().all()
