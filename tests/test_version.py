import asyncio
from importlib.metadata import version

from httpx import ASGITransport, AsyncClient

from cquptddl import app

transport = ASGITransport(app)


def test_version():
    async def case() -> tuple[str, str]:
        ver = version("cquptddl")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/version")
            got_ver = resp.text
        return ver, got_ver

    ver, got_ver = asyncio.run(case())
    assert ver == got_ver
    assert not got_ver.startswith("v")
