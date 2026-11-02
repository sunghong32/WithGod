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
    # "풀이"(3~4문장 묵상). 한국어는 사람이 검토한 것(daily_interpretations.json)을 쓰고,
    # 외국어는 LLM 이 만들어 파일 캐시에 둔다(말씀·언어당 1회). 실패 시 reflection 으로 폴백.
    # 자세한 건 notifications/interpretation.py.
    interpretation: str = ""


@dataclass(slots=True)
class DeviceRegistration:
    token: str
    platform: MobilePlatform
    timezone: str
    device_id: str = ""
    app_version: str = ""
    os_version: str = ""
    # 앱 표시 언어(ko/en/es/pt/de/fr/it/pl) — 푸시 본문·제목 현지화용.
    # 발송 시점에 resolve_lang 으로 활성 여부를 거른다(비활성이면 ko).
    language: str = "ko"
    enabled: bool = True
    schedule_hour: int | None = None
    schedule_minute: int | None = None
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
