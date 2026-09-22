import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from cquptddl.core import config
from cquptddl.exc import IcsSubscriptionNotFound
from cquptddl.model.db.ics_subscription import IcsSubscription
from cquptddl.model.schema.platform import PlatformEnum

from .feed import feed_etag, get_feed_homeworks, render_ics, to_aware


def hash_token(token: str) -> str:
    """token是256位随机串，不存在被爆破的可能，用sha256即可。
    不要换成bcrypt/argon2：那是为了抗低熵口令，只会拖慢每次feed请求"""
    return sha256(token.encode()).hexdigest()


async def list_subscriptions(
    session: AsyncSession, user_id: str
) -> list[IcsSubscription]:
    stmt = (
        select(IcsSubscription)
        .where(IcsSubscription.user_id == user_id)
        .order_by(IcsSubscription.created_at, IcsSubscription.id)  # ty: ignore[invalid-argument-type]
    )
    resp = await session.execute(stmt)
    return list(resp.scalars().all())


async def get_url_count(session: AsyncSession, user_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(IcsSubscription)
        .where(IcsSubscription.user_id == user_id)
    )
    resp = await session.execute(stmt)
    return resp.scalar_one()


async def create_subscription(
    session: AsyncSession, user_id: str
) -> tuple[IcsSubscription, str]:
    """新建一条订阅，返回订阅行和**只此一次**的明文token。
    允许同一用户存在多条，不做去重
    """
    token = secrets.token_urlsafe(32)
    subscription = IcsSubscription(user_id=user_id, token_hash=hash_token(token))
    session.add(subscription)
    await session.flush()
    return subscription, token


async def delete_subscription(
    session: AsyncSession, user_id: str, subscription_id: UUID
):
    """撤销自己的某条订阅，不存在或不属于自己时抛404"""
    stmt = (
        select(IcsSubscription)
        .where(IcsSubscription.id == subscription_id)
        .where(IcsSubscription.user_id == user_id)
    )
    resp = await session.execute(stmt)
    subscription = resp.scalars().first()
    if subscription is None:
        raise IcsSubscriptionNotFound
    await session.delete(subscription)


async def _record_fetch(session: AsyncSession, subscription_id: UUID):
    """累加拉取统计。用原子自增避免并发丢更新，且不参与渲染、不影响ETag"""
    stmt = (
        update(IcsSubscription)
        .where(IcsSubscription.id == subscription_id)  # ty: ignore[invalid-argument-type]
        .values(
            fetch_count=IcsSubscription.fetch_count + 1,
            last_fetched_at=datetime.now().astimezone(),
        )
    )
    await session.execute(stmt)


async def render_feed(
    session: AsyncSession,
    token: str,
    platform: PlatformEnum | None = None,
) -> tuple[bytes, str]:
    """按订阅token渲染日历，并记录一次拉取
    Returns:
        ics内容
        ETag

    Raises:
        IcsSubscriptionNotFound:
    """
    stmt = select(IcsSubscription).where(
        IcsSubscription.token_hash == hash_token(token)
    )
    resp = await session.execute(stmt)
    subscription = resp.scalars().first()
    if subscription is None:
        raise IcsSubscriptionNotFound

    homeworks = await get_feed_homeworks(session, subscription.user_id, platform)
    tz = ZoneInfo(config.ics_timezone)
    body = render_ics(
        homeworks,
        tz=tz,
        duration=timedelta(minutes=config.ics_event_duration_minutes),
        dtstamp=to_aware(subscription.created_at, tz).astimezone(UTC),
    )
    await _record_fetch(session, subscription.id)
    return body, feed_etag(body)
