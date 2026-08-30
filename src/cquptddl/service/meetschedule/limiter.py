from contextlib import asynccontextmanager
from math import inf

from meetschedule_sdk import AsyncMeetSchedule
from throttled.asyncio import RateLimiterType, Throttled, rate_limiter, store

from cquptddl.exc import RaceLimitExceed

throttle = Throttled(
    using=RateLimiterType.FIXED_WINDOW.value,
    quota=rate_limiter.per_min(60),
    store=store.MemoryStore(),
)


@asynccontextmanager
async def acquire(meet: AsyncMeetSchedule, block: bool = True):
    api_key = meet._client.headers["X-API-Key"]
    if block:
        await throttle.limit(api_key, timeout=inf)
    else:
        result = await throttle.limit(api_key)
        if result.limited:
            raise RaceLimitExceed
    yield
