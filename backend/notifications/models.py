from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MobilePlatform(StrEnum):
    ANDROID = "android"
    IOS = "ios"


@dataclass(slots=True)
class DailyVerse:
    verse_id: str
    reference: str
    text: str
    reflection: str = ""


@dataclass(slots=True)
class DeviceRegistration:
    token: str
    platform: MobilePlatform
    timezone: str
    device_id: str = ""
    app_version: str = ""
    os_version: str = ""
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
    last_daily_sent_on: str = ""


@dataclass(slots=True)
class PushPayload:
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PushDispatchResult:
    success_count: int
    failure_count: int
    invalid_tokens: list[str] = field(default_factory=list)
    failed_tokens: list[str] = field(default_factory=list)
