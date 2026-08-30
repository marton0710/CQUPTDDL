from sqlmodel import Field, SQLModel


class MeetscheduleConfig(SQLModel, table=True):
    user_id: str = Field(
        description="用户id",
        foreign_key="user.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    meetschedule_key: str = Field(unique=True)
    schedule_id: str = Field(description="要同步到的课程表id")
