from collections.abc import Iterable
from datetime import datetime, timedelta

from sqlmodel import select

from cquptddl import core
from cquptddl.model.db import Homework


async def get_dying_homeworks(user_id: str, scope: int) -> Iterable[Homework]:
    now = datetime.now().astimezone()
    sql = (
        select(Homework)
        .where(Homework.user_id == user_id)
        .where(Homework.done == False)
        .where(Homework.deadline > now)  # ty: ignore[unsupported-operator]
        .where(Homework.deadline < now + timedelta(hours=scope))  # ty: ignore[unsupported-operator]
    )
    async with core.factory.get_session() as session:
        resp = await session.execute(sql)
        return resp.scalars().all()


async def get_homeworks_with_deadline(user_id: str) -> Iterable[Homework]:
    sql = (
        select(Homework)
        .where(Homework.user_id == user_id)
        .where(Homework.done == False)
        .where(Homework.deadline != None)
    )
    async with core.factory.get_session() as session:
        resp = await session.execute(sql)
        return resp.scalars().all()
