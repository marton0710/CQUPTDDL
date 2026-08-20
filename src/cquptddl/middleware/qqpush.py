from typing import Annotated

from fastapi import Depends
from fastapi.security import APIKeyHeader

from cquptddl import core
from cquptddl.exc import WrongQQPushAPIKey

need_api_key = APIKeyHeader(name="X-API-Key")


async def verify_api_key(api_key: Annotated[str, Depends(need_api_key)]):
    if api_key != core.config.QQBOT_SEND_API_KEY:
        raise WrongQQPushAPIKey
