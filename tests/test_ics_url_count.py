"""验证 ICS 订阅数量在三个来源之间保持一致：

1. 本地数据库直接读取的行数（``get_url_count`` / ``list_subscriptions``）
2. 写入函数 ``create_subscription`` 每次返回的行
3. ``GET /api/auth/me`` 接口返回的 ``ics_url_count``

不需要真的起 uvicorn：``httpx.ASGITransport`` 会在进程内驱动真实的 FastAPI 应用，
数据库换成一次性内存库，并通过依赖覆盖注入。
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from cquptddl import app, core
from cquptddl.middleware.auth import need_login
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.db.user import User
from cquptddl.service.ics.subscription import (
    create_subscription,
    delete_subscription,
    get_url_count,
    list_subscriptions,
)

USER_ID = "20230001"
OTHER_USER_ID = "20230002"

SessionMaker = async_sessionmaker[AsyncSession]


async def _new_database() -> tuple[AsyncEngine, SessionMaker]:
    """一次性内存库，用完即弃"""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def _api_client(maker: SessionMaker) -> AsyncGenerator[AsyncClient]:
    """把 FastAPI 的 session 依赖换成测试库，把登录依赖换成假用户。

    真实登录要走统一认证，测试里直接覆盖 ``need_login`` 即可。
    """
    fake_user = User(id=USER_ID, password=None, name="测试用户")

    async def override_session() -> AsyncGenerator[AsyncSession]:
        async with maker() as session:
            yield session
            await session.commit()

    async def override_need_login() -> User:
        return fake_user

    app.dependency_overrides[core.depends_session] = override_session
    app.dependency_overrides[need_login] = override_need_login
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test/"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def _seed_user(maker: SessionMaker, user_id: str) -> None:
    """/api/auth/me 会读 QQPushConfig，先给测试用户建好"""
    async with maker() as session:
        session.add(User(id=user_id, password=None, name="测试用户"))
        session.add(QQPushConfig(user_id=user_id))
        await session.commit()


def run[T](func: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """跑一个只依赖本地数据库的用例"""

    async def _main() -> T:
        engine, maker = await _new_database()
        try:
            async with maker() as session:
                return await func(session)
        finally:
            await engine.dispose()

    return asyncio.run(_main())


# ---------------------------------------------------------------------------
# 第一阶段：本地数据库读取的行数 == 写入函数返回的行数
# ---------------------------------------------------------------------------


def test_write_return_matches_local_row_count():
    """create_subscription 每次返回一行，本地读取的行数应与之完全一致"""

    async def case(session: AsyncSession) -> tuple[int, int, bool]:
        created = []
        for _ in range(4):
            subscription, _token = await create_subscription(session, USER_ID)
            created.append(subscription)
        await session.commit()

        listed = await list_subscriptions(session, USER_ID)
        # 写入函数返回的行就是库里能读到的行
        same_rows = {s.id for s in created} == {s.id for s in listed}
        return len(created), await get_url_count(session, USER_ID), same_rows

    written, counted, same_rows = run(case)
    assert written == counted == 4
    assert same_rows


def test_count_is_scoped_per_user():
    """计数只统计目标用户，不会把别人的订阅算进来"""

    async def case(session: AsyncSession) -> tuple[int, int]:
        for _ in range(3):
            await create_subscription(session, USER_ID)
        for _ in range(2):
            await create_subscription(session, OTHER_USER_ID)
        await session.commit()
        return await get_url_count(session, USER_ID), await get_url_count(
            session, OTHER_USER_ID
        )

    assert run(case) == (3, 2)


def test_local_count_follows_delete():
    """删除一条订阅后，本地读取的行数应同步减一"""

    async def case(session: AsyncSession) -> tuple[int, int]:
        first, _ = await create_subscription(session, USER_ID)
        await create_subscription(session, USER_ID)
        await session.commit()
        before = await get_url_count(session, USER_ID)

        await delete_subscription(session, USER_ID, first.id)
        await session.commit()
        return before, await get_url_count(session, USER_ID)

    assert run(case) == (2, 1)


def test_local_count_is_zero_without_subscriptions():
    assert run(lambda session: get_url_count(session, USER_ID)) == 0


# ---------------------------------------------------------------------------
# 第二阶段：API 接口获取的行数 == 数据库/写入的行数
# ---------------------------------------------------------------------------


def test_api_count_matches_database_row_count():
    """通过 API 写入 3 条后，/api/auth/me 的数量、列表长度、库里行数三者一致"""

    async def case() -> tuple[int, int, int]:
        engine, maker = await _new_database()
        try:
            await _seed_user(maker, USER_ID)

            async with _api_client(maker) as client:
                for _ in range(3):
                    resp = await client.post("/api/ics/subscription")
                    assert resp.status_code == 200

                me = await client.get("/api/auth/me")
                assert me.status_code == 200
                listed = await client.get("/api/ics/subscription")
                assert listed.status_code == 200

            async with maker() as session:
                db_count = await get_url_count(session, USER_ID)

            return me.json()["ics_url_count"], db_count, len(listed.json())
        finally:
            await engine.dispose()

    api_count, db_count, listed_count = asyncio.run(case())
    assert api_count == db_count == listed_count == 3


def test_api_count_drops_after_delete():
    """API 删除订阅后，接口数量与库里行数同步减一"""

    async def case() -> tuple[int, int, int]:
        engine, maker = await _new_database()
        try:
            await _seed_user(maker, USER_ID)

            async with _api_client(maker) as client:
                first = (await client.post("/api/ics/subscription")).json()
                await client.post("/api/ics/subscription")
                before = (await client.get("/api/auth/me")).json()["ics_url_count"]

                deleted = await client.delete(f"/api/ics/subscription/{first['id']}")
                assert deleted.status_code == 204
                after = (await client.get("/api/auth/me")).json()["ics_url_count"]

            async with maker() as session:
                db_after = await get_url_count(session, USER_ID)

            return before, after, db_after
        finally:
            await engine.dispose()

    before, after, db_after = asyncio.run(case())
    assert before == 2
    assert after == db_after == 1


def test_api_count_only_counts_current_user():
    """别人库里的订阅不会出现在当前用户的 ics_url_count 里"""

    async def case() -> int:
        engine, maker = await _new_database()
        try:
            await _seed_user(maker, USER_ID)

            async with maker() as session:
                await create_subscription(session, OTHER_USER_ID)
                await create_subscription(session, OTHER_USER_ID)
                await session.commit()

            async with _api_client(maker) as client:
                resp = await client.post("/api/ics/subscription")
                assert resp.status_code == 200
                me = await client.get("/api/auth/me")
                assert me.status_code == 200

            return me.json()["ics_url_count"]
        finally:
            await engine.dispose()

    assert asyncio.run(case()) == 1
