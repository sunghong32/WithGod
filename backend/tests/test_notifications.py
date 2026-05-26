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
        )
        registered = result["device"]
        self.assertTrue(result["created"])
        self.assertEqual(registered["token"], "abc123")
        self.assertEqual(registered["device_id"], "device-1")
        self.assertEqual(len(self.store.list_devices()), 1)
        self.assertEqual(self.store.list_devices()[0].platform, MobilePlatform.IOS)

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
