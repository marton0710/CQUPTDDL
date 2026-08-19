from pydantic import BaseModel, ConfigDict


class MeetscheduleConfigSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meetschedule_key: str | None = None
