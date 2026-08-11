from logging import INFO, getLogger

from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl.exc import NoSuchHomework
from cquptddl.model.db import Homework, User

_logger = getLogger(__name__)
_logger.setLevel(INFO)


async def complete_homework(
    session: AsyncSession, user: User, homework_id: int, is_complete: bool
):
    homework = await session.get(Homework, homework_id)
    if homework is None:
        raise NoSuchHomework
    if homework.user_id != user.id:
        _logger.warning("用户%s试图修改他人作业状态", user.id)
        raise NoSuchHomework
    homework.done = is_complete
