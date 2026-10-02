from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core

SessionDep = Annotated[AsyncSession, Depends(core.factory.depends_session)]
