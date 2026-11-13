from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from languages import DAILY_VERSE_TITLES, localize_ko_ref, normalize_lang, resolve_lang
from notifications.device_store import DeviceStore
from notifications.models import DailyVerse, DeviceRegistration, MobilePlatform, PushDispatchResult, PushPayload
from notifications.push_service import PushGateway, RetryBackoff
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
        retry_backoff: RetryBackoff | None = None,
    ) -> None:
        self.settings = settings
        self.device_store = device_store
        self.verse_provider = verse_provider
        self.push_gateway = push_gateway
        # None 이면 interpretation 은 빈 문자열로 남는다(푸시 배치 경로 등 풀이가 필요 없는 경우).
        self.verse_interpreter = verse_interpreter
        self.retry_backoff = retry_backoff or RetryBackoff()

    def get_daily_verse(
        self, now: datetime | None = None, lang: str = "ko", day: date | None = None
    ) -> dict[str, str]:
        """오늘의 말씀. day 는 기기 현지 날짜(#69, `accept_local_date` 로 거른 값).

        day 가 없으면(구버전 앱·위젯) 지금처럼 push_default_timezone 의 오늘. naive now(또는 None)가
        그대로 흘러가면 서버 OS 타임존(UTC 등) 기준 날짜가 되므로 항상 normalize 해서 넘긴다.
        """
        if day is not None:
            source = self.verse_provider.verse_for_date(day)
        else:
            source = self.verse_provider.get_daily_verse(now=self._normalize_now(now))
        verse = self._localize_verse(source, lang)
        if self.verse_interpreter is not None:
            verse.interpretation = self.verse_interpreter.interpret(verse, lang, source=source)
        return asdict(verse)

    @staticmethod
    def accept_local_date(day: date | None, now: datetime | None = None) -> date | None:
        """앱이 보낸 기기 현지 날짜를 받아도 되면 그대로, 아니면 None(→ 기본 시간대의 오늘).

        지금 이 순간 지구 어딘가의 날짜일 수 있는 것(UTC−12 ~ UTC+14, 곧 UTC 날짜 ±1일)만 받는다.
        시계가 크게 틀린 기기나 손으로 만든 요청이 먼 날의 말씀을 받아 가지 않게 한다.
        """
        if day is None:
            return None
        utc_today = (now or datetime.now(dt_timezone.utc)).astimezone(dt_timezone.utc).date()
        return day if abs((day - utc_today).days) <= 1 else None

    def _device_local_date(self, device: DeviceRegistration, now: datetime) -> date:
        """기기 시간대의 날짜. 시간대가 깨져 있으면 기본 시간대(등록 때 검사하므로 드묾)."""
        try:
            tz = self._resolve_timezone(device.timezone or self.settings.push_default_timezone)
        except ValueError:
            tz = self._resolve_timezone(self.settings.push_default_timezone)
        return now.astimezone(tz).date()

    @staticmethod
    def _localize_verse(verse: DailyVerse, lang: str) -> DailyVerse:
        """큐레이션된 한국어 오늘의 말씀을 해당 언어의 같은 구절로 바꾼다.

        reflection 은 한국어 큐레이션이라 비한국어에서는 비운다(풀이는
        VerseInterpreter 가 언어별로 생성·캐시). 정렬 실패 시 한국어 그대로.
        """
        if lang == "ko":
            return verse
        found = localize_ko_ref(lang, verse.reference, verse.text)
        if not found:
            return verse
        return DailyVerse(
            verse_id=verse.verse_id,
            reference=found["ref"],
            text=found["text"],
            reflection="",
        )

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
        language: str | None = None,
        enabled: bool | None = None,
        schedule_hour: int | None = None,
        schedule_minute: int | None = None,
        now: datetime | None = None,
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
        # 그날 알림 시각이 지난 뒤 처음 등록된 기기는 캐치업 판정에 걸려 다음 폴링에 곧바로
        # 푸시가 나간다(#25). 새 행이면 오늘 몫은 보낸 것으로 쳐 두고 다음 날부터 받게 한다.
        # 기존 행은 upsert 가 last_daily_sent_on 을 보존하므로 시각을 바꿔도 그날 그대로 받는다.
        sent_on_if_created = (
            self._passed_target_on(
                self._normalize_now(now), tz_name, schedule_hour, schedule_minute
            )
            or ""
        )
        device, created = self.device_store.upsert(
            token=clean_token,
            platform=mobile_platform,
            timezone=tz_name,
            device_id=device_id.strip(),
            app_version=app_version.strip(),
            os_version=os_version.strip(),
            # 안 보낸 language 는 None 그대로 넘겨 기존 값을 지킨다(이슈 #23) —
            # normalize_lang(None) 은 'ko' 라 여기서 정규화하면 외국어 사용자가 ko 로 돌아간다.
            language=normalize_lang(language) if language else None,
            enabled=enabled,
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            last_daily_sent_on_if_created=sent_on_if_created,
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
        days = {device.token: self._device_local_date(device, current) for device in devices}
        return self._send(devices, now=current, mark_sent=False, days=days)

    def send_due_notifications(self, now: datetime | None = None) -> dict[str, object]:
        current = self._normalize_now(now)
        due_devices: list[DeviceRegistration] = []
        sent_dates: dict[str, str] = {}
        for device in self.device_store.list_enabled_devices():
            # 캐치업 발송: '현재 분 == 목표 분' 정확 일치 대신, 목표 시각을 지났고
            # 오늘 아직 안 보냈으면 발송한다.
            # 프로세스 재시작/스톨로 해당 분을 넘겨도 그날 발송이 누락되지 않는다.
            local_date = self._passed_target_on(
                current, device.timezone, device.schedule_hour, device.schedule_minute
            )
            if local_date is None or device.last_daily_sent_on == local_date:
                continue
            # 실패가 이어진 기기는 30초마다가 아니라 간격을 늘려 다시 보낸다(RetryBackoff).
            if not self.retry_backoff.ready(device.token, local_date, current):
                continue
            due_devices.append(device)
            sent_dates[device.token] = local_date

        outcome = self._send(
            due_devices,
            now=current,
            mark_sent=False,
            days={token: date.fromisoformat(day) for token, day in sent_dates.items()},
        )
        result = outcome["result"]
        self.device_store.disable_tokens(result["invalid_tokens"])
        for device in due_devices:
            failed = device.token in result["failed_tokens"]
            self.retry_backoff.record(device.token, sent_dates[device.token], current, failed)
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
        days: dict[str, date] | None = None,
    ) -> dict[str, object]:
        """발송. days 는 {토큰: 기기 현지 날짜} — 기기마다 그 날짜의 말씀을 보낸다(#69).

        days 에 없는 기기는 now 의 날짜(기본 시간대). 응답의 verse 는 기본 시간대 오늘의 말씀
        (관리 화면·로그 호환), verses 는 실제로 보낸 {날짜: verse_id}.
        """
        verse = self.verse_provider.get_daily_verse(now=now)
        if not devices:
            return {
                "verse": asdict(verse),
                "verses": {},
                "result": asdict(PushDispatchResult(success_count=0, failure_count=0)),
            }

        # (현지 날짜, 기기 언어)로 묶어 그날 말씀을 그 언어로 현지화해 발송한다. 발송 시점에
        # resolve_lang 으로 거르므로 비활성 언어 기기는 ko 그룹으로 온다.
        day_of = {device.token: (days or {}).get(device.token, now.date()) for device in devices}
        groups: dict[tuple[date, str], list[DeviceRegistration]] = {}
        for device in devices:
            groups.setdefault((day_of[device.token], resolve_lang(device.language)), []).append(device)

        verses: dict[date, DailyVerse] = {}
        dispatch = PushDispatchResult(success_count=0, failure_count=0)
        for (day, lang), group_devices in groups.items():
            if day not in verses:
                verses[day] = self.verse_provider.verse_for_date(day)
            localized = self._localize_verse(verses[day], lang)
            title_word = DAILY_VERSE_TITLES.get(lang, DAILY_VERSE_TITLES["ko"])
            title = f"{title_word} | {localized.reference}"
            payload = PushPayload(
                title=title,
                body=localized.text,
                data={
                    "type": "daily_verse",
                    "verseId": localized.verse_id,
                    "ref": localized.reference,
                    "text": localized.text,
                    "comment": localized.reflection,
                    "tag": title_word,
                    "title": title,
                    "body": localized.text,
                },
            )
            part = self.push_gateway.send(group_devices, payload)
            dispatch.success_count += part.success_count
            dispatch.failure_count += part.failure_count
            dispatch.invalid_tokens.extend(part.invalid_tokens)
            dispatch.failed_tokens.extend(part.failed_tokens)

        if mark_sent:
            for device in devices:
                if device.token not in dispatch.failed_tokens:
                    self.device_store.mark_sent(device.token, day_of[device.token].isoformat())
        return {
            "verse": asdict(verse),
            "verses": {day.isoformat(): v.verse_id for day, v in sorted(verses.items())},
            "result": asdict(dispatch),
        }

    def _passed_target_on(
        self,
        now: datetime,
        timezone: str,
        schedule_hour: int | None,
        schedule_minute: int | None,
    ) -> str | None:
        """기기 현지 시각으로 그날 알림 시각을 지났으면 현지 날짜(ISO), 아직이면 None."""
        local_now = now.astimezone(self._resolve_timezone(timezone))
        # 기기별 개인 알림 시각이 있으면 사용, 없으면 전역 기본값으로 폴백.
        target_hour = (
            schedule_hour if schedule_hour is not None else self.settings.push_schedule_hour
        )
        target_minute = (
            schedule_minute if schedule_minute is not None else self.settings.push_schedule_minute
        )
        if (local_now.hour, local_now.minute) < (target_hour, target_minute):
            return None
        return local_now.date().isoformat()

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
