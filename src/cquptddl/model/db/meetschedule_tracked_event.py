from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


class MeetscheduleTrackedEvent(SQLModel, table=True):
    id: str = Field(primary_key=True, description="meet课程表事件id")
    user_id: str = Field(index=True, foreign_key="user.id", ondelete="CASCADE")
    homework_id: UUID = Field(
        unique=True, index=True, foreign_key="homework.id", ondelete="CASCADE"
    )
    updated_at: datetime = Field(default_factory=datetime.now)
