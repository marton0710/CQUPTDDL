from sqlmodel import Field, SQLModel


class MeetscheduleConfig(SQLModel, table=True):
    user_id: str = Field(
        description="用户id",
        foreign_key="user.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    meetschedule_key: str | None = Field(None, unique=True)
