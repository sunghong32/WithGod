import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from notifications.device_store import DeviceStore
from notifications.manager import DailyVerseNotificationManager
from notifications.models import MobilePlatform, PushDispatchResult
from notifications.push_service import PushGateway
from notifications.scheduler import DailyVerseScheduler
from notifications.verse_provider import (
    DailyVerseProvider,
    VerseInterpretationStore,
    VerseInterpreter,
)
from settings import AppSettings


class FakePushGateway(PushGateway):
    def __init__(self) -> None:
        self.sent_batches: list[list[str]] = []

    def send(self, devices, payload):
        self.sent_batches.append([device.token for device in devices])
        return PushDispatchResult(
            success_count=len(devices),
            failure_count=0,
            invalid_tokens=[],
            failed_tokens=[],
        )


class NotificationFeatureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.device_store_path = temp_path / "devices.json"
        self.interpretation_store_path = temp_path / "verse_interpretations.json"
        self.verse_store_path = (
            Path(__file__).resolve().parent.parent / "notifications" / "daily_verses.json"
        )
        self.settings = AppSettings(
            firebase_service_account_path="",
            device_store_path=str(self.device_store_path),
            daily_verse_store_path=str(self.verse_store_path),
            verse_interpretation_store_path=str(self.interpretation_store_path),
            push_schedule_hour=9,
            push_schedule_minute=0,
            push_default_timezone="Asia/Seoul",
            scheduler_poll_seconds=30,
        )
        self.store = DeviceStore(str(self.device_store_path))
        self.provider = DailyVerseProvider(str(self.verse_store_path))
        self.gateway = FakePushGateway()
        self.manager = DailyVerseNotificationManager(
            settings=self.settings,
            device_store=self.store,
            verse_provider=self.provider,
            push_gateway=self.gateway,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_register_device_persists(self) -> None:
        result = self.manager.register_device(
            token="abc123",
            platform="ios",
            timezone="Asia/Seoul",
            device_id="device-1",
            app_version="1.0.0",
            os_version="17.4",
            schedule_hour=7,
            schedule_minute=30,
        )
        registered = result["device"]
        self.assertTrue(result["created"])
        self.assertEqual(registered["token"], "abc123")
        self.assertEqual(registered["device_id"], "device-1")
        self.assertEqual(registered["schedule_hour"], 7)
        self.assertEqual(registered["schedule_minute"], 30)
        self.assertEqual(len(self.store.list_devices()), 1)
        self.assertEqual(self.store.list_devices()[0].platform, MobilePlatform.IOS)
        # 저장 후 다시 읽어도 신규 필드가 유지되어야 한다(직렬화/역직렬화 라운드트립).
        reloaded = DeviceStore(str(self.device_store_path)).list_devices()[0]
        self.assertEqual(reloaded.schedule_hour, 7)
        self.assertEqual(reloaded.schedule_minute, 30)

    def test_register_device_defaults_schedule_to_none(self) -> None:
        result = self.manager.register_device(
            token="no-schedule",
            platform="android",
            timezone="Asia/Seoul",
        )
        registered = result["device"]
        self.assertIsNone(registered["schedule_hour"])
        self.assertIsNone(registered["schedule_minute"])

    def test_register_device_rejects_invalid_schedule(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.register_device(
                token="bad-hour",
                platform="ios",
                timezone="Asia/Seoul",
                schedule_hour=24,
            )
        with self.assertRaises(ValueError):
            self.manager.register_device(
                token="bad-minute",
                platform="ios",
                timezone="Asia/Seoul",
                schedule_minute=60,
            )

    def test_upsert_matches_by_device_id_across_token_change(self) -> None:
        # 같은 설치(device_id)에서 FCM 토큰이 갱신되어도 한 항목으로 합쳐져야 한다.
        self.store.upsert(
            token="old-token",
            platform=MobilePlatform.IOS,
            timezone="Asia/Seoul",
            device_id="install-1",
        )
        self.store.upsert(
            token="new-token",
            platform=MobilePlatform.IOS,
            timezone="Asia/Seoul",
            device_id="install-1",
        )
        devices = self.store.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].token, "new-token")
        self.assertEqual(devices[0].device_id, "install-1")

    def test_backward_compatible_legacy_store_uses_global_default(self) -> None:
        # schedule_* 가 없는 (구버전) device_store.json 도 전역 기본(9:00)으로 동작.
        self.device_store_path.write_text(
            '[{"token": "legacy", "platform": "android", "timezone": "Asia/Seoul", '
            '"enabled": true}]',
            encoding="utf-8",
        )
        device = self.store.list_devices()[0]
        self.assertIsNone(device.schedule_hour)
        self.assertIsNone(device.schedule_minute)

        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)
        # 전역 기본 9:00 에 발송되어야 한다.
        sent = scheduler.run_once(now=datetime(2026, 4, 21, 9, 0))
        self.assertEqual(sent["result"]["success_count"], 1)

    def test_scheduler_respects_per_device_schedule(self) -> None:
        self.store.upsert(
            token="custom-token",
            platform=MobilePlatform.IOS,
            timezone="Asia/Seoul",
            device_id="install-custom",
            schedule_hour=7,
            schedule_minute=30,
        )
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)

        # 개인 설정 7:30 이전(7:29)에는 발송되지 않는다.
        skipped = scheduler.run_once(now=datetime(2026, 4, 21, 7, 29))
        self.assertEqual(skipped["result"]["success_count"], 0)

        # 전역 기본 9:00 이 아니라 개인 설정 7:30 에 발송된다.
        sent = scheduler.run_once(now=datetime(2026, 4, 21, 7, 30))
        self.assertEqual(sent["result"]["success_count"], 1)
        self.assertEqual(self.store.list_devices()[0].last_daily_sent_on, "2026-04-21")

        # 이미 발송된 날에는 전역 기본 9:00 이 되어도 중복 발송하지 않는다.
        duplicate = scheduler.run_once(now=datetime(2026, 4, 21, 9, 0))
        self.assertEqual(duplicate["result"]["success_count"], 0)

    def test_register_device_upserts_same_token(self) -> None:
        first = self.manager.register_device(
            token="same-token",
            platform="android",
            timezone="Asia/Seoul",
            app_version="1.0.0",
        )
        second = self.manager.register_device(
            token="same-token",
            platform="android",
            timezone="Asia/Seoul",
            app_version="1.0.1",
        )
        self.assertTrue(first["created"])
        self.assertTrue(second["updated"])
        self.assertEqual(len(self.store.list_devices()), 1)
        self.assertEqual(self.store.list_devices()[0].app_version, "1.0.1")

    def test_scheduler_sends_only_when_due(self) -> None:
        self.store.upsert(
            token="android-token",
            platform=MobilePlatform.ANDROID,
            timezone="Asia/Seoul",
        )
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)

        skipped = scheduler.run_once(now=datetime(2026, 4, 21, 8, 59))
        self.assertEqual(skipped["result"]["success_count"], 0)

        sent = scheduler.run_once(now=datetime(2026, 4, 21, 9, 0))
        self.assertEqual(sent["result"]["success_count"], 1)
        self.assertEqual(self.store.list_devices()[0].last_daily_sent_on, "2026-04-21")

        duplicate = scheduler.run_once(now=datetime(2026, 4, 21, 9, 0))
        self.assertEqual(duplicate["result"]["success_count"], 0)

        # 캐치업 도입 후에도 같은 날 늦은 시각 재실행이 중복 발송으로 이어지면 안 된다.
        later_same_day = scheduler.run_once(now=datetime(2026, 4, 21, 15, 0))
        self.assertEqual(later_same_day["result"]["success_count"], 0)

    def test_scheduler_catches_up_when_target_minute_was_missed(self) -> None:
        # 프로세스 재시작/스톨로 목표 시각(9:00)의 '그 분'을 넘겨도,
        # 오늘 아직 안 보냈으면 그날 안에 캐치업 발송해야 한다.
        self.store.upsert(
            token="catchup-token",
            platform=MobilePlatform.ANDROID,
            timezone="Asia/Seoul",
        )
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)

        sent = scheduler.run_once(now=datetime(2026, 4, 21, 13, 47))
        self.assertEqual(sent["result"]["success_count"], 1)
        self.assertEqual(self.store.list_devices()[0].last_daily_sent_on, "2026-04-21")

        # 같은 날 재실행은 멱등(중복 발송 없음).
        duplicate = scheduler.run_once(now=datetime(2026, 4, 21, 13, 48))
        self.assertEqual(duplicate["result"]["success_count"], 0)

        # 다음 날 목표 시각 이전에는 발송하지 않는다.
        next_day_early = scheduler.run_once(now=datetime(2026, 4, 22, 8, 59))
        self.assertEqual(next_day_early["result"]["success_count"], 0)

        # 다음 날 목표 시각을 지나면 다시 발송한다.
        next_day_sent = scheduler.run_once(now=datetime(2026, 4, 22, 9, 30))
        self.assertEqual(next_day_sent["result"]["success_count"], 1)
        self.assertEqual(self.store.list_devices()[0].last_daily_sent_on, "2026-04-22")

    def test_daily_verse_is_deterministic_for_same_day(self) -> None:
        verse_a = self.provider.get_daily_verse(now=datetime(2026, 4, 21, 9, 0))
        verse_b = self.provider.get_daily_verse(now=datetime(2026, 4, 21, 23, 59))
        self.assertEqual(verse_a.verse_id, verse_b.verse_id)

    def test_daily_verse_uses_default_timezone_for_aware_now(self) -> None:
        # UTC 2026-04-21 16:00 은 Asia/Seoul 기준 2026-04-22 01:00 이다.
        # manager 는 push_default_timezone(Asia/Seoul) 벽시계로 normalize 해서
        # verse_provider 에 넘기므로 4/22 의 말씀이 나와야 한다.
        utc_now = datetime(2026, 4, 21, 16, 0, tzinfo=ZoneInfo("UTC"))
        verse_via_manager = self.manager.get_daily_verse(now=utc_now)
        seoul_next_day = self.provider.get_daily_verse(now=datetime(2026, 4, 22, 1, 0))
        seoul_same_day = self.provider.get_daily_verse(now=datetime(2026, 4, 21, 16, 0))
        self.assertEqual(verse_via_manager["verse_id"], seoul_next_day.verse_id)
        self.assertNotEqual(verse_via_manager["verse_id"], seoul_same_day.verse_id)

    def _manager_with_interpreter(
        self, generate_fn: Mock
    ) -> DailyVerseNotificationManager:
        # generate_fn(reference, text) 은 운영에서 OpenAI 백엔드 함수가 주입되는 자리로,
        # 테스트에서는 mock 을 주입해 실제 LLM 호출 없이 캐시/폴백 동작을 검증한다.
        interpreter = VerseInterpreter(
            store=VerseInterpretationStore(str(self.interpretation_store_path)),
            generate_fn=generate_fn,
        )
        return DailyVerseNotificationManager(
            settings=self.settings,
            device_store=self.store,
            verse_provider=self.provider,
            push_gateway=self.gateway,
            verse_interpreter=interpreter,
        )

    def test_interpretation_generated_and_cached_on_first_call(self) -> None:
        now = datetime(2026, 4, 21, 9, 0)
        generate = Mock(return_value="풀이 첫 문장이에요. 두 번째 문장이에요.")
        manager = self._manager_with_interpreter(generate)

        verse = manager.get_daily_verse(now=now)

        # (a) 첫 호출 시 LLM 이 1회 호출되어 풀이가 생성된다.
        generate.assert_called_once_with(verse["reference"], verse["text"])
        self.assertEqual(verse["interpretation"], "풀이 첫 문장이에요. 두 번째 문장이에요.")
        # verse_id -> interpretation 이 파일 캐시에 영속되어야 한다.
        cached = json.loads(self.interpretation_store_path.read_text(encoding="utf-8"))
        self.assertEqual(cached[verse["verse_id"]], verse["interpretation"])

    def test_interpretation_reused_from_cache_without_second_llm_call(self) -> None:
        now = datetime(2026, 4, 21, 9, 0)
        first_generate = Mock(return_value="캐시에 저장될 풀이예요.")
        first = self._manager_with_interpreter(first_generate).get_daily_verse(now=now)
        first_generate.assert_called_once()

        # (b) 별도 매니저(같은 캐시 파일)로 다시 호출해도 LLM 은 호출되지 않고 캐시를 재사용한다.
        second_generate = Mock(return_value="새로 생성되면 안 되는 풀이")
        second = self._manager_with_interpreter(second_generate).get_daily_verse(now=now)

        second_generate.assert_not_called()
        self.assertEqual(second["interpretation"], first["interpretation"])
        self.assertEqual(second["interpretation"], "캐시에 저장될 풀이예요.")

    def test_interpretation_falls_back_to_reflection_on_llm_error(self) -> None:
        now = datetime(2026, 4, 21, 9, 0)
        generate = Mock(side_effect=RuntimeError("LLM 호출 실패"))
        manager = self._manager_with_interpreter(generate)

        verse = manager.get_daily_verse(now=now)

        # (c) LLM 예외 시 reflection 으로 폴백하며, 말씀 자체는 그대로 반환한다(500 없음).
        generate.assert_called_once()
        self.assertNotEqual(verse["reflection"], "")
        self.assertEqual(verse["interpretation"], verse["reflection"])
        # 폴백 값은 캐시에 저장하지 않는다(다음 요청에서 LLM 재시도).
        self.assertFalse(self.interpretation_store_path.exists())
