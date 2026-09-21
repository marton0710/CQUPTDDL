from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from icalendar import Calendar

from cquptddl.model.db import Homework
from cquptddl.model.schema.platform import PlatformEnum
from cquptddl.service.ics.feed import feed_etag, render_ics

TZ = ZoneInfo("Asia/Shanghai")
DTSTAMP = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
DURATION = timedelta(minutes=30)


def make_homework(
    *,
    id: str = "0195c3a0-0000-7000-8000-000000000001",
    course_name: str = "高等数学",
    title: str = "第一章作业",
    deadline: datetime | None = datetime(2026, 3, 1, 23, 59),  # noqa: DTZ001
    url: str | None = "https://example.com/hmw/1",
    platform: PlatformEnum = PlatformEnum.CHAOXING,
) -> Homework:
    return Homework(
        id=UUID(id),
        user_id="20230001",
        course_name=course_name,
        title=title,
        deadline=deadline,
        url=url,
        platform=platform,
    )


def render(*homeworks: Homework) -> bytes:
    return render_ics(homeworks, tz=TZ, duration=DURATION, dtstamp=DTSTAMP)


def test_naive_deadline_rendered_in_configured_timezone():
    data = render(make_homework())

    assert b"DTSTART;TZID=Asia/Shanghai:20260301T232900" in data
    assert b"DTEND;TZID=Asia/Shanghai:20260301T235900" in data

    event = Calendar.from_ical(data).events[0]
    assert event.start == datetime(2026, 3, 1, 23, 29, tzinfo=TZ)
    assert event.end == datetime(2026, 3, 1, 23, 59, tzinfo=TZ)


def test_aware_deadline_converted_to_configured_timezone():
    data = render(make_homework(deadline=datetime(2026, 3, 1, 15, 59, tzinfo=UTC)))

    event = Calendar.from_ical(data).events[0]
    assert event.end == datetime(2026, 3, 1, 23, 59, tzinfo=TZ)


def test_special_chars_and_long_title_roundtrip():
    title = "作业，含,逗号;分号\\反斜杠\n换行" + "很长很长" * 40
    data = render(make_homework(title=title))

    event = Calendar.from_ical(data).events[0]
    assert str(event["SUMMARY"]) == title


def test_empty_homeworks_still_valid_calendar():
    data = render()
    calendar = Calendar.from_ical(data)

    assert calendar.events == []
    assert str(calendar["VERSION"]) == "2.0"
    assert calendar.calendar_name == "聚合截止线"
    assert b"BEGIN:VTIMEZONE" not in data


def test_homework_without_deadline_is_skipped():
    assert Calendar.from_ical(render(make_homework(deadline=None))).events == []


def test_completed_homework_state_does_not_affect_rendering():
    # 是否已完成由查询层过滤，渲染层只负责把给定作业画出来
    homework = make_homework()
    homework.done = True
    assert len(Calendar.from_ical(render(homework)).events) == 1


def test_uid_is_stable_and_unique():
    first = make_homework(id="0195c3a0-0000-7000-8000-000000000001")
    second = make_homework(
        id="0195c3a0-0000-7000-8000-000000000002", title="第一章作业"
    )
    data = render(first, second)

    uids = [str(event["UID"]) for event in Calendar.from_ical(data).events]
    assert uids == [
        f"{first.id}@cquptddl",
        f"{second.id}@cquptddl",
    ]
    assert render(first, second) == data


def test_vtimezone_is_added():
    data = render(make_homework())

    assert b"BEGIN:VTIMEZONE" in data
    assert Calendar.from_ical(data).get_missing_tzids() == set()


def test_etag_depends_on_content():
    original = render(make_homework())
    changed = render(make_homework(title="改名了"))

    assert feed_etag(original) == feed_etag(original)
    assert feed_etag(original) != feed_etag(changed)
    assert feed_etag(original).startswith('"')
    assert feed_etag(original).endswith('"')
