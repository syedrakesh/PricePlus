"""
Pydantic schemas for user settings endpoints.
"""

from pydantic import BaseModel, Field, field_validator


class UserSettingsResponse(BaseModel):
    user_id: str
    discovery_concurrency: int
    discovery_min_delay: float
    discovery_max_delay: float
    tracking_concurrency: int
    tracking_min_delay: float
    tracking_max_delay: float
    updated_at: str

    model_config = {"from_attributes": True}


class UpdateUserSettingsRequest(BaseModel):
    discovery_concurrency: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Parallel worker count for discovery data fetching (1 to 10)",
    )
    discovery_min_delay: float | None = Field(
        default=None,
        ge=0.1,
        le=10.0,
        description="Minimum delay between requests in seconds",
    )
    discovery_max_delay: float | None = Field(
        default=None,
        ge=0.2,
        le=15.0,
        description="Maximum delay between requests in seconds",
    )
    tracking_concurrency: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Parallel worker count for product monitoring check requests (1 to 10)",
    )
    tracking_min_delay: float | None = Field(
        default=None,
        ge=0.05,
        le=10.0,
        description="Minimum delay between product monitoring check requests in seconds",
    )
    tracking_max_delay: float | None = Field(
        default=None,
        ge=0.05,
        le=15.0,
        description="Maximum delay between product monitoring check requests in seconds",
    )

    @field_validator("discovery_max_delay")
    @classmethod
    def validate_max_delay(cls, max_delay: float | None, info) -> float | None:
        min_delay = info.data.get("discovery_min_delay")
        if min_delay is not None and max_delay is not None:
            if max_delay < min_delay:
                raise ValueError("max_delay must be greater than or equal to min_delay")
        return max_delay

    @field_validator("tracking_max_delay")
    @classmethod
    def validate_tracking_max_delay(cls, max_delay: float | None, info) -> float | None:
        min_delay = info.data.get("tracking_min_delay")
        if min_delay is not None and max_delay is not None:
            if max_delay < min_delay:
                raise ValueError("tracking_max_delay must be greater than or equal to tracking_min_delay")
        return max_delay
