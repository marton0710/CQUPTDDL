from enum import StrEnum
from uuid import UUID

from sqlmodel import Field, SQLModel


class MeetscheduleEntryStatus(StrEnum):
    PENDING = "pending"
    PENDING_UPDATE = "pending-update"
    PENDING_DELETE = "pending-delete"
    SUCCESS = "success"


class MeetscheduleEntry(SQLModel, table=True):
    id: UUID = Field(primary_key=True, foreign_key="homework.id")
    meet_event_id: str | None = Field(
        unique=True, index=True, description="meet课程表事件id"
    )
    user_id: str = Field(index=True, foreign_key="user.id", ondelete="CASCADE")
    status: MeetscheduleEntryStatus = Field(index=True)

    def __hash__(self):
        return hash(self.id)
