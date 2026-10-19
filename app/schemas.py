"""Input validation shared by the LinkPulse API."""

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class LinkCreate(BaseModel):
    long_url: str = Field(min_length=8, max_length=2048)
    custom_alias: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, max_length=256)
    expires_at: datetime | None = None
    click_limit: int | None = Field(default=None, ge=1, le=2_147_483_647)

    @field_validator("long_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Enter a complete http:// or https:// URL.")
        return value.strip()

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if value and not all(char.isalnum() or char in "-_" for char in value):
                raise ValueError("Aliases may contain letters, numbers, hyphens, and underscores.")
            if value and len(value) < 3:
                raise ValueError("Aliases must be at least 3 characters long.")
        return value or None


class PasswordVerify(BaseModel):
    password: str = Field(min_length=1, max_length=256)
