from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(str, Enum):
    PROFILE_VIEW = "profile_view"
    POST_VIEW = "post_view"
    POST_LIKE = "post_like"
    POST_COMMENT = "post_comment"
    CONNECTION_REQUEST = "connection_request"
    JOB_VIEW = "job_view"
    JOB_CLICK = "job_click"
    JOB_SAVE = "job_save"
    COMPANY_FOLLOW = "company_follow"


class EventMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str | None = None
    device: str | None = None


class ActivityEvent(BaseModel):
    event_id: UUID
    user_id: str = Field(min_length=1, max_length=100)
    event_type: EventType
    target_id: str = Field(min_length=1, max_length=100)
    timestamp: datetime
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone offset")
        return value
