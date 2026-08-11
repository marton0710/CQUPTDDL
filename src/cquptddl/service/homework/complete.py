from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl.model.db import Homework, User


async def complete_homework(
    session: AsyncSession, user: User, homework_id: int, is_complete: bool
):
    homework = await session.get(Homework, homework_id)
    if homework is None:
        raise  # TODO:
    if homework.user_id != user.id:
        raise  # TODO:
    homework.done = is_complete
