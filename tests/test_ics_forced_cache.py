"""ICS 服务端强制缓存（不可绕过的 304）的行为规格。

背景：有个日历客户端几天拉近 1000 次，且**不发 If-None-Match**，所以 ETag 那套 304
对它无效，正文流量压不住。要定的契约是服务端说了算：

- 只要作业数据源（``PlatformInfo.last_refreshed_homework``）没晚于本订阅上次拉取的时间，
  一律回空的 304，客户端发不发 ETag 都一样；
- 新订阅（``last_fetched_at`` 还是 NULL）第一次拉取必须给正文，否则客户端什么都没有；
- 304 也算一次拉取（``fetch_count`` / ``last_fetched_at`` 照常前移），口径与 ETag 命中一致；
- 想拿新内容：等平台刷新，或新建一条订阅（新 token 没有拉取记录）。

全部用 HTTP 状态码 + 数据库统计断言，不绑内部异常类型，实现怎么写都行。
用例里标了「现状不满足」的，就是这次要修的规格。
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from uuid import UUID

import httpx2
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from cquptddl import core
from cquptddl.model.db import Homework, IcsSubscription, PlatformInfo, User
from cquptddl.model.schema.platform import PlatformEnum
from cquptddl.router.api import ics as ics_api
from cquptddl.service.ics.subscription import create_subscription

UID = "20230001"
PLATFORM = PlatformEnum.CHAOXING
HOMEWORK_TITLE = "作业A"
NEW_HOMEWORK_TITLE = "新作业B"
SessionMaker = async_sessionmaker[AsyncSession]


@asynccontextmanager
async def _memory_db() -> AsyncGenerator[SessionMaker]:
    """用完即弃的内存库"""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _seed(
    maker: SessionMaker,
    *,
    last_refreshed: datetime | None,
    last_fetched: datetime = datetime.fromtimestamp(0).astimezone(),  # noqa: B008
    fetch_count: int = 0,
) -> tuple[str, UUID]:
    """建 用户 + 一条作业 + 一条订阅，返回 (明文token, 订阅id)。

    ``last_refreshed=None`` 表示用户压根没有 PlatformInfo 行（没绑定或没刷新过）；
    ``last_fetched=None`` 表示这条订阅还没被拉取过。
    """
    async with maker() as session:
        session.add(User(id=UID, password=None, name="测试用户"))
        if last_refreshed is not None:
            session.add(
                PlatformInfo(
                    user_id=UID,
                    platform=PLATFORM,
                    credentials="",
                    cookies={},
                    last_refreshed_homework=last_refreshed,
                )
            )
        session.add(
            Homework(
                id=Homework.generate_id(UID, str(PLATFORM), "a"),
                user_id=UID,
                title=HOMEWORK_TITLE,
                deadline=datetime.now().astimezone() + timedelta(days=1),
                url=None,
                platform=PLATFORM,
            )
        )
        subscription, token = await create_subscription(session, UID)
        subscription.last_fetched_at = last_fetched
        subscription.fetch_count = fetch_count
        await session.commit()
        return token, subscription.id


async def _add_homework(maker: SessionMaker, title: str, key: str):
    """平台刷新时多出来一条作业"""
    async with maker() as session:
        session.add(
            Homework(
                id=Homework.generate_id(UID, str(PLATFORM), key),
                user_id=UID,
                title=title,
                deadline=datetime.now().astimezone() + timedelta(days=2),
                url=None,
                platform=PLATFORM,
            )
        )
        await session.commit()


async def _platform_refresh(maker: SessionMaker, when: datetime):
    """模拟刷新任务把 ``last_refreshed_homework`` 推到 ``when``"""
    async with maker() as session:
        info = await session.get(PlatformInfo, (UID, PLATFORM))
        assert info is not None
        info.last_refreshed_homework = when
        await session.commit()


async def _read_stats(
    maker: SessionMaker, subscription_id: UUID
) -> tuple[int, datetime | None]:
    """从库里读拉取统计（绕开任何缓存层）"""
    async with maker() as session:
        subscription = await session.get(IcsSubscription, subscription_id)
        assert subscription is not None, "订阅不该被删掉"
        return subscription.fetch_count, subscription.last_fetched_at


def _app(maker: SessionMaker) -> FastAPI:
    """只挂 ics 路由的迷你app，session 依赖指到内存库（不起 lifespan、不碰生产库）"""
    app = FastAPI()
    app.include_router(ics_api.router, prefix="/api/ics")

    async def _session() -> AsyncGenerator[AsyncSession]:
        # 与 core.factory.depends_session 同语义：yield 之后才 commit
        async with maker() as session:
            yield session
            await session.commit()

    app.dependency_overrides[core.factory.depends_session] = _session
    return app


async def _fetch(
    app: FastAPI, token: str, headers: dict[str, str] | None = None
) -> httpx2.Response:
    """按日历客户端的方式拉 feed：默认一个缓存相关的请求头都不带"""
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.get(f"/api/ics/feed/{token}.ics", headers=headers)


def run[T](func: Callable[[], Awaitable[T]]) -> T:
    return asyncio.run(func())


@pytest.mark.parametrize(
    "last_refreshed",
    [
        pytest.param(
            datetime.fromtimestamp(0).astimezone(), id="平台刷新时间是很久以前"
        ),
        pytest.param(None, id="没有PlatformInfo行"),
    ],
)
def test_new_subscription_first_fetch_gets_body(last_refreshed: datetime | None):
    """新订阅第一次拉取必须给正文。

    客户端此时没有任何缓存，回 304 就是空日历；更不该 500。
    现状不满足：``last_fetched_at`` 是 NULL，拿 None 去比时间会 TypeError。
    """

    async def case() -> tuple[httpx2.Response, tuple[int, datetime | None]]:
        async with _memory_db() as maker:
            token, subscription_id = await _seed(maker, last_refreshed=last_refreshed)
            response = await _fetch(_app(maker), token)
            return response, await _read_stats(maker, subscription_id)

    response, (fetch_count, last_fetched_at) = run(case)
    assert response.status_code == 200
    assert HOMEWORK_TITLE.encode() in response.content
    assert fetch_count == 1
    assert last_fetched_at is not None


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param(None, id="客户端不发If-None-Match"),
        pytest.param({"If-None-Match": '"whatever"'}, id="客户端发的ETag是编的"),
    ],
)
def test_no_new_data_returns_empty_304(headers: dict[str, str] | None):
    """数据源自上次拉取以来没前进过：一律回空 304，客户端怎么发都绕不过去。

    这就是省流量的关键：没有正文，也没有条件请求可谈。
    现状不满足：命中的 304 没记拉取统计（问题6）。
    """
    before = datetime.now().astimezone()

    async def case() -> tuple[httpx2.Response, tuple[int, datetime | None]]:
        async with _memory_db() as maker:
            token, subscription_id = await _seed(
                maker,
                last_refreshed=before - timedelta(hours=2),
                last_fetched=before - timedelta(hours=1),
                fetch_count=3,
            )
            response = await _fetch(_app(maker), token, headers)
            return response, await _read_stats(maker, subscription_id)

    response, (fetch_count, last_fetched_at) = run(case)
    assert response.status_code == 304
    assert response.content == b""
    # 问题6：304 也算一次拉取
    assert fetch_count == 4
    assert last_fetched_at is not None
    assert last_fetched_at.tzinfo is not None
    assert last_fetched_at >= before


def test_repeated_fetch_never_bypasses_the_cache():
    """反复拉也不漏正文，而且每次都要计数（客户端越频繁，服务端越要顶住）"""

    async def case() -> tuple[list[int], tuple[int, datetime | None]]:
        async with _memory_db() as maker:
            now = datetime.now().astimezone()
            token, subscription_id = await _seed(
                maker,
                last_refreshed=now - timedelta(hours=2),
                last_fetched=now - timedelta(hours=1),
            )
            app = _app(maker)
            statuses = [(await _fetch(app, token)).status_code for _ in range(5)]
            return statuses, await _read_stats(maker, subscription_id)

    statuses, (fetch_count, _) = run(case)
    assert statuses == [304] * 5
    assert fetch_count == 5


def test_platform_refresh_lets_the_cache_expire():
    """平台刷新后缓存自然放行：新作业出现在 feed 里，然后立刻又回到 304"""

    async def case() -> tuple[httpx2.Response, httpx2.Response, httpx2.Response]:
        async with _memory_db() as maker:
            now = datetime.now().astimezone()
            token, _ = await _seed(
                maker,
                last_refreshed=now - timedelta(hours=2),
                last_fetched=now - timedelta(hours=1),
            )
            app = _app(maker)
            cached = await _fetch(app, token)
            # 平台在两次拉取之间刷新完：比刚才那次拉取晚，但不是未来时间
            await _platform_refresh(maker, datetime.now().astimezone())
            await _add_homework(maker, NEW_HOMEWORK_TITLE, "b")
            fresh = await _fetch(app, token)
            again = await _fetch(app, token)
            return cached, fresh, again

    cached, fresh, again = run(case)
    assert cached.status_code == 304
    assert fresh.status_code == 200
    assert NEW_HOMEWORK_TITLE.encode() in fresh.content
    assert again.status_code == 304


def test_etag_hit_still_counts_as_a_fetch():
    """强制缓存不拦时（数据源时间戳在前方）照常渲染；客户端拿相同 ETag 再来还是 304，照样计数"""

    async def case() -> tuple[httpx2.Response, httpx2.Response, int]:
        async with _memory_db() as maker:
            token, subscription_id = await _seed(
                maker,
                # 刷新时间放到前方，专门让强制缓存让路，好走到渲染+ETag 这条老路径上
                last_refreshed=datetime.now().astimezone() + timedelta(hours=1),
                last_fetched=datetime.fromtimestamp(0).astimezone(),
            )
            app = _app(maker)
            first = await _fetch(app, token)
            second = await _fetch(app, token, {"If-None-Match": first.headers["etag"]})
            fetch_count, _ = await _read_stats(maker, subscription_id)
            return first, second, fetch_count

    first, second, fetch_count = run(case)
    assert first.status_code == 200
    assert second.status_code == 304
    assert fetch_count == 2


def test_new_subscription_bypasses_the_cache():
    """要新内容就新建一条订阅：新 token 没有拉取记录，第一次一定给正文"""

    async def case() -> tuple[httpx2.Response, httpx2.Response]:
        async with _memory_db() as maker:
            now = datetime.now().astimezone()
            token_old, _ = await _seed(
                maker,
                last_refreshed=now - timedelta(hours=2),
                last_fetched=now - timedelta(hours=1),
            )
            app = _app(maker)
            old = await _fetch(app, token_old)
            async with maker() as session:
                _, token_new = await create_subscription(session, UID)
                await session.commit()
            new = await _fetch(app, token_new)
            return old, new

    old, new = run(case)
    assert old.status_code == 304
    # 现状不满足：新 token 的 last_fetched_at 是 NULL，会 TypeError→500
    assert new.status_code == 200
    assert HOMEWORK_TITLE.encode() in new.content
