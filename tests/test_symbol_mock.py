"""用 ``core.symbol.mock`` 替换平台拉取，单测 ``refresh_homework`` 的"只增不删 + 去重"。

``platform.fetch_homework`` 正常要连平台网络；符号表允许在 DEBUG 下临时换掉实现，
于是这里注入假数据，只观察落库数量与 ``homework.after_refresh`` 钩子的入参。
"""

import asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from cquptddl import core
from cquptddl.model.db import Homework, User
from cquptddl.model.schema.platform import PlatformEnum
from cquptddl.service.homework.refresh_homework import refresh_homework

USER_ID = "20230001"
PLATFORM = PlatformEnum.CHAOXING


def _homework(custom: str, title: str) -> Homework:
    return Homework(
        id=Homework.generate_id(USER_ID, PLATFORM, custom),
        user_id=USER_ID,
        title=title,
        deadline=None,
        url=None,
        platform=PLATFORM,
    )


def test_refresh_homework_dedups_with_mocked_fetch():
    """同一批作业刷两次只落库一次，钩子每次只收到新增的 id"""

    first_batch = [_homework("a", "作业A"), _homework("b", "作业B")]
    second_batch = [*first_batch, _homework("c", "作业C")]

    async def case() -> tuple[int, set, set]:
        engine = create_async_engine("sqlite+aiosqlite://")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
            maker = async_sessionmaker(engine, expire_on_commit=False)

            async with maker() as session:
                session.add(User(id=USER_ID, password=None, name="测试用户"))
                await session.commit()

            batches = [first_batch, second_batch]

            async def fake_fetch(session, user, platform_name, check_cooldown=True):
                """假的 platform.fetch_homework：不联网，按批次返回"""
                return list(batches.pop(0))

            trigger = AsyncMock()
            with (
                core.symbol.mock("platform.fetch_homework", fake_fetch),
                patch.object(core.hook, "trigger", trigger),
            ):
                for _ in range(2):
                    async with maker() as session:
                        user = await session.get_one(User, USER_ID)
                        await refresh_homework(session, user, PLATFORM)

            async with maker() as session:
                resp = await session.execute(select(Homework))
                rows = resp.scalars().all()

            new_ids = [c.kwargs["new_homework_ids"] for c in trigger.await_args_list]
            return len(rows), new_ids[0], new_ids[1]
        finally:
            await engine.dispose()

    count, first_new, second_new = asyncio.run(case())
    assert count == 3  # 第二批里的 a/b 没有重复插入
    assert first_new == {h.id for h in first_batch}
    assert second_new == {second_batch[-1].id}
