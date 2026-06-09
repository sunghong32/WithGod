import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from notifications.device_store import DeviceStore
from notifications.manager import DailyVerseNotificationManager
from notifications.models import MobilePlatform, PushDispatchResult
from notifications.push_service import PushGateway
from notifications.scheduler import DailyVerseScheduler
from notifications.verse_provider import DailyVerseProvider
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
        self.verse_store_path = (
            Path(__file__).resolve().parent.parent / "notifications" / "daily_verses.json"
        )
        self.settings = AppSettings(
            firebase_service_account_path="",
            device_store_path=str(self.device_store_path),
            daily_verse_store_path=str(self.verse_store_path),
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

        # 전역 기본 9:00 에는 발송되지 않는다.
        skipped = scheduler.run_once(now=datetime(2026, 4, 21, 9, 0))
        self.assertEqual(skipped["result"]["success_count"], 0)

        # 개인 설정 7:30 에 발송된다.
        sent = scheduler.run_once(now=datetime(2026, 4, 21, 7, 30))
        self.assertEqual(sent["result"]["success_count"], 1)
        self.assertEqual(self.store.list_devices()[0].last_daily_sent_on, "2026-04-21")

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

    def test_daily_verse_is_deterministic_for_same_day(self) -> None:
        verse_a = self.provider.get_daily_verse(now=datetime(2026, 4, 21, 9, 0))
        verse_b = self.provider.get_daily_verse(now=datetime(2026, 4, 21, 23, 59))
        self.assertEqual(verse_a.verse_id, verse_b.verse_id)
