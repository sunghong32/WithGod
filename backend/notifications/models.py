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
    # LLM(gpt-4o-mini)이 생성한 "풀이"(구절을 일상어로 부드럽게 2문장 이내).
    # verse_id 기준 파일 캐시라 말씀당 최대 1회만 생성한다. 생성 실패 시 reflection 으로 폴백.
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
