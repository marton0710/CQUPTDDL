import asyncio
from collections.abc import Awaitable, Callable
from hashlib import sha256

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from cquptddl.exc import IcsSubscriptionNotFound
from cquptddl.service.ics.subscription import (
    create_subscription,
    delete_subscription,
    list_subscriptions,
    render_feed,
)


async def _with_session[T](func: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """用完即弃的内存库，跑一个session的用例"""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            result = await func(session)
            await session.commit()
            return result
    finally:
        await engine.dispose()


def run[T](func: Callable[[AsyncSession], Awaitable[T]]) -> T:
    return asyncio.run(_with_session(func))


def test_user_can_hold_multiple_subscriptions():
    async def case(session: AsyncSession):
        first, first_token = await create_subscription(session, "20230001")
        second, second_token = await create_subscription(session, "20230001")
        await create_subscription(session, "20230002")
        return (
            (first, first_token),
            (second, second_token),
            await list_subscriptions(session, "20230001"),
        )

    (first, first_token), (second, second_token), mine = run(case)
    assert first.id != second.id
    assert first_token != second_token
    assert {i.id for i in mine} == {first.id, second.id}


def test_token_is_stored_hashed():
    async def case(session: AsyncSession):
        subscription, token = await create_subscription(session, "20230001")
        return subscription, token

    subscription, token = run(case)
    assert subscription.token_hash == sha256(token.encode()).hexdigest()
    # 明文不能出现在任何一列里
    assert all(token not in str(v) for v in subscription.model_dump().values())


def test_render_feed_records_fetch_and_keeps_etag_stable():
    async def case(session: AsyncSession):
        subscription, token = await create_subscription(session, "20230001")
        _, first_etag = await render_feed(session, token)
        _, second_etag = await render_feed(session, token)
        await session.refresh(subscription)
        return first_etag, second_etag, subscription

    first_etag, second_etag, subscription = run(case)
    assert subscription.fetch_count == 2
    assert subscription.last_fetched_at is not None
    # 统计字段不参与渲染，否则ETag会抖动、304失效
    assert first_etag == second_etag


def test_render_feed_unknown_token():
    async def case(session: AsyncSession):
        await create_subscription(session, "20230001")
        await render_feed(session, "not-a-token")

    with pytest.raises(IcsSubscriptionNotFound):
        run(case)


def test_delete_subscription_rejects_other_user():
    async def case(session: AsyncSession):
        subscription, _ = await create_subscription(session, "20230001")
        with pytest.raises(IcsSubscriptionNotFound):
            await delete_subscription(session, "20230002", subscription.id)
        await delete_subscription(session, "20230001", subscription.id)
        return await list_subscriptions(session, "20230001")

    assert run(case) == []
