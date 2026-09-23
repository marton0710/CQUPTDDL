"""平台刷新冷却检查的单测。

库内 `last_refreshed_homework` 经 SQLModel 的 UTCDateTime 读出后一律是 aware(UTC)，
所以冷却计算两边都是 aware，不涉及 naive / aware 混算。
"""

from datetime import UTC, datetime, timedelta

import pytest

from cquptddl import core
from cquptddl.exc import RefreshCoolingDown
from cquptddl.model.db import PlatformInfo
from cquptddl.model.schema.platform import PlatformEnum
from cquptddl.service.platform.fetch import _check_platform_cooldown

COOLDOWN = timedelta(seconds=core.config.homework_cooldown_ttl)


def _make_info(last_refreshed: datetime) -> PlatformInfo:
    return PlatformInfo(
        user_id="20230001",
        platform=PlatformEnum.CHAOXING,
        credentials="",
        cookies={},
        last_refreshed_homework=last_refreshed,
    )


def test_cooldown_passes_after_threshold():
    """冷却期已过：不抛异常，并把刷新时间写回为带时区的当前时间"""
    info = _make_info(datetime.now(UTC) - COOLDOWN - timedelta(minutes=1))
    _check_platform_cooldown(info)
    assert info.last_refreshed_homework.tzinfo is not None
    assert abs(info.last_refreshed_homework - datetime.now().astimezone()) < timedelta(
        seconds=5
    )


def test_cooldown_raises_within_threshold():
    """仍在冷却期内：抛 RefreshCoolingDown，且不写回刷新时间"""
    last = datetime.now(UTC) - COOLDOWN + timedelta(minutes=1)
    info = _make_info(last)
    with pytest.raises(RefreshCoolingDown):
        _check_platform_cooldown(info)
    assert info.last_refreshed_homework == last
