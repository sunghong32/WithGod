from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from notifications.device_store import DeviceStore
from notifications.models import DeviceRegistration, MobilePlatform, PushDispatchResult, PushPayload
from notifications.push_service import PushGateway
from notifications.verse_provider import DailyVerseProvider, VerseInterpreter
from settings import AppSettings


class DailyVerseNotificationManager:
    def __init__(
        self,
        settings: AppSettings,
        device_store: DeviceStore,
        verse_provider: DailyVerseProvider,
        push_gateway: PushGateway,
        verse_interpreter: VerseInterpreter | None = None,
    ) -> None:
        self.settings = settings
        self.device_store = device_store
        self.verse_provider = verse_provider
        self.push_gateway = push_gateway
        # None 이면 interpretation 은 빈 문자열로 남는다(푸시 배치 경로 등 풀이가 필요 없는 경우).
        self.verse_interpreter = verse_interpreter

    def get_daily_verse(self, now: datetime | None = None) -> dict[str, str]:
        # naive now(또는 None)가 그대로 흘러가면 서버 OS 타임존(UTC 등) 기준 날짜가
        # 되므로, 항상 push_default_timezone 기준으로 normalize 해서 넘긴다.
        verse = self.verse_provider.get_daily_verse(now=self._normalize_now(now))
        if self.verse_interpreter is not None:
            verse.interpretation = self.verse_interpreter.interpret(verse)
        return asdict(verse)

    def list_devices(self) -> list[dict[str, str | bool]]:
        return [asdict(device) for device in self.device_store.list_devices()]

    def register_device(
        self,
        token: str,
        platform: str,
        timezone: str | None = None,
        device_id: str = "",
        app_version: str = "",
        os_version: str = "",
        enabled: bool = True,
        schedule_hour: int | None = None,
        schedule_minute: int | None = None,
    ) -> dict[str, object]:
        clean_token = token.strip()
        if not clean_token:
            raise ValueError("token is required")
        try:
            mobile_platform = MobilePlatform(platform.strip().lower())
        except ValueError as exc:
            raise ValueError("platform must be android or ios") from exc

        if schedule_hour is not None and not 0 <= schedule_hour <= 23:
            raise ValueError("schedule_hour must be between 0 and 23")
        if schedule_minute is not None and not 0 <= schedule_minute <= 59:
            raise ValueError("schedule_minute must be between 0 and 59")

        tz_name = (timezone or self.settings.push_default_timezone).strip()
        self._resolve_timezone(tz_name)
        device, created = self.device_store.upsert(
            token=clean_token,
            platform=mobile_platform,
            timezone=tz_name,
            device_id=device_id.strip(),
            app_version=app_version.strip(),
            os_version=os_version.strip(),
            enabled=enabled,
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
        )
        return {
            "device": asdict(device),
            "created": created,
            "updated": not created,
        }

    def delete_device(self, token: str) -> bool:
        return self.device_store.delete(token.strip())

    def send_daily_verse_now(
        self,
        now: datetime | None = None,
        tokens: list[str] | None = None,
    ) -> dict[str, object]:
        current = self._normalize_now(now)
        devices = self.device_store.list_enabled_devices()
        if tokens:
            allowed = set(tokens)
            devices = [device for device in devices if device.token in allowed]
        return self._send(devices, now=current, mark_sent=False)

    def send_due_notifications(self, now: datetime | None = None) -> dict[str, object]:
        current = self._normalize_now(now)
        due_devices: list[DeviceRegistration] = []
        sent_dates: dict[str, str] = {}
        for device in self.device_store.list_enabled_devices():
            local_now = current.astimezone(self._resolve_timezone(device.timezone))
            local_date = local_now.date().isoformat()
            if device.last_daily_sent_on == local_date:
                continue
            # 기기별 개인 알림 시각이 있으면 사용, 없으면 전역 기본값으로 폴백.
            target_hour = (
                device.schedule_hour
                if device.schedule_hour is not None
                else self.settings.push_schedule_hour
            )
            target_minute = (
                device.schedule_minute
                if device.schedule_minute is not None
                else self.settings.push_schedule_minute
            )
            # 캐치업 발송: '현재 분 == 목표 분' 정확 일치 대신, 오늘 아직 안 보냈고
            # (위 last_daily_sent_on 검사) 목표 시각을 지났으면 발송한다.
            # 프로세스 재시작/스톨로 해당 분을 넘겨도 그날 발송이 누락되지 않는다.
            if (local_now.hour, local_now.minute) < (target_hour, target_minute):
                continue
            due_devices.append(device)
            sent_dates[device.token] = local_date

        outcome = self._send(due_devices, now=current, mark_sent=False)
        result = outcome["result"]
        self.device_store.disable_tokens(result["invalid_tokens"])
        successful_tokens = [
            device.token for device in due_devices if device.token not in result["failed_tokens"]
        ]
        for token in successful_tokens:
            self.device_store.mark_sent(token, sent_dates[token])
        outcome["scheduled_count"] = len(due_devices)
        return outcome

    def _send(
        self,
        devices: list[DeviceRegistration],
        now: datetime,
        mark_sent: bool,
    ) -> dict[str, object]:
        verse = self.verse_provider.get_daily_verse(now=now)
        if not devices:
            return {
                "verse": asdict(verse),
                "result": asdict(PushDispatchResult(success_count=0, failure_count=0)),
            }

        payload = PushPayload(
            title=f"오늘의 말씀 | {verse.reference}",
            body=verse.text,
            data={
                "type": "daily_verse",
                "verseId": verse.verse_id,
                "ref": verse.reference,
                "text": verse.text,
                "comment": verse.reflection,
                "tag": "오늘의 말씀",
                "title": f"오늘의 말씀 | {verse.reference}",
                "body": verse.text,
            },
        )
        dispatch = self.push_gateway.send(devices, payload)
        if mark_sent:
            local_date = now.date().isoformat()
            for device in devices:
                if device.token not in dispatch.failed_tokens:
                    self.device_store.mark_sent(device.token, local_date)
        return {
            "verse": asdict(verse),
            "result": asdict(dispatch),
        }

    def _resolve_timezone(self, name: str) -> ZoneInfo:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {name}") from exc

    def _normalize_now(self, now: datetime | None) -> datetime:
        tz = self._resolve_timezone(self.settings.push_default_timezone)
        if now is None:
            return datetime.now(tz)
        if now.tzinfo is not None:
            # aware 면 기본 타임존의 벽시계로 변환한다(일자 계산이 항상 기본 타임존 기준이 되도록).
            return now.astimezone(tz)
        return now.replace(tzinfo=tz)
