"""平台刷新冷却检查的单测。

`_check_platform_cooldown` 现在用**独立的短事务**读写 `last_refreshed_homework`：
判定通过时在退出时 commit（所以后续请求即使失败也照样占用冷却），判定不通过时抛
`RefreshCoolingDown` 并回滚。因此测试需要一个库，这里用一次性内存库替换
`core.factory.get_session`，语义与生产一致（yield 之后才 commit）。
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from cquptddl import core
from cquptddl.exc import RefreshCoolingDown
from cquptddl.model.db import PlatformInfo, User
from cquptddl.model.schema.platform import PlatformEnum
from cquptddl.service.platform import fetch
from cquptddl.service.platform.fetch import _check_platform_cooldown

USER_ID = "20230001"
PLATFORM = PlatformEnum.CHAOXING
COOLDOWN = timedelta(seconds=core.config.homework_cooldown_ttl)
SessionMaker = async_sessionmaker[AsyncSession]


@asynccontextmanager
async def _cooldown_db(last_refreshed: datetime) -> AsyncGenerator[SessionMaker]:
    """一次性内存库 + 一个已绑定平台的用户，并把冷却用的 session 指过来"""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            session.add(User(id=USER_ID, password=None, name="测试用户"))
            session.add(
                PlatformInfo(
                    user_id=USER_ID,
                    platform=PLATFORM,
                    credentials="",
                    cookies={},
                    last_refreshed_homework=last_refreshed,
                )
            )
            await session.commit()

        @asynccontextmanager
        async def _session() -> AsyncGenerator[AsyncSession]:
            # 与 core.factory.depends_session 同语义：yield 之后才 commit
            async with maker() as session:
                yield session
                await session.commit()

        with patch.object(core.factory, "get_session", _session):
            yield maker
    finally:
        await engine.dispose()


async def _read_last_refreshed(maker: SessionMaker) -> datetime:
    async with maker() as session:
        info = await session.get(PlatformInfo, (USER_ID, PLATFORM))
        assert info is not None
        return info.last_refreshed_homework


def test_cooldown_passes_after_threshold():
    """冷却期已过：放行，并把新的刷新时间提交进库"""

    async def case() -> datetime:
        last = datetime.now(UTC) - COOLDOWN - timedelta(minutes=1)
        async with _cooldown_db(last) as maker:
            await _check_platform_cooldown(USER_ID, PLATFORM)
            return await _read_last_refreshed(maker)

    stored = asyncio.run(case())
    assert stored.tzinfo is not None
    assert abs(stored - datetime.now().astimezone()) < timedelta(seconds=5)


def test_cooldown_raises_within_threshold():
    """仍在冷却期内：抛 RefreshCoolingDown，且不覆盖原刷新时间"""

    async def case() -> tuple[datetime, datetime]:
        last = datetime.now(UTC) - COOLDOWN + timedelta(minutes=1)
        async with _cooldown_db(last) as maker:
            with pytest.raises(RefreshCoolingDown):
                await _check_platform_cooldown(USER_ID, PLATFORM)
            return last, await _read_last_refreshed(maker)

    last, stored = asyncio.run(case())
    assert stored == last


class _FailingPlatform:
    """拉取必定失败的假平台"""

    @classmethod
    async def get_homework(cls, cookies: dict[str, str], user_id: str) -> None:
        raise RuntimeError("测试用：平台拉取失败")


def test_failed_fetch_still_consumes_cooldown(monkeypatch: pytest.MonkeyPatch):
    """刷新失败也要占用冷却：失败后立刻重试必须被拦下

    这是这次改动的核心语义：冷却时间戳由独立事务在请求发出前提交，
    所以拉取失败也不会让用户获得一次"免费"的立即重试。
    """

    async def case() -> None:
        async with _cooldown_db(datetime.fromtimestamp(0).astimezone()) as maker:
            monkeypatch.setattr(
                fetch.Platform, "get_platform_by_name", lambda name: _FailingPlatform
            )
            async with maker() as session:
                user = await session.get(User, USER_ID)
                assert user is not None
                with pytest.raises(RuntimeError):
                    await fetch.fetch_homework(session, user, PLATFORM)  # ty: ignore[missing-argument]
                assert (
                    await _read_last_refreshed(maker)
                    > datetime.fromtimestamp(0).astimezone()
                )
                with pytest.raises(RefreshCoolingDown):
                    await fetch.fetch_homework(session, user, PLATFORM)  # ty: ignore[missing-argument]

    asyncio.run(case())
