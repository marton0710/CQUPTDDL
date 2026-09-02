from contextlib import asynccontextmanager
from logging import INFO, getLogger
from math import inf

import meetschedule_sdk
from meetschedule_sdk import AsyncMeetSchedule
from throttled.asyncio import RateLimiterType, Throttled, rate_limiter, store

from cquptddl.exc import RaceLimitExceed

_logger = getLogger(__name__)
_logger.setLevel(INFO)
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
    try:
        yield
    except meetschedule_sdk.exceptions.TooManyRequestsError as e:
        _logger.error("限流失败", exc_info=e)
        raise
