"""기기 재등록 시 부분 병합 (이슈 #23).

이미 등록된 기기에는 요청에 온 필드만 반영하고, 안 보낸 필드는 기존 값을 둔다.
language 를 안 보내는 구버전 앱(1.3.0 미만)의 등록 한 번에 외국어 사용자가 ko 로,
개인 알림 시각이 전역 기본으로 되돌아가던 문제를 막는다.
"""

import tempfile
import unittest
from pathlib import Path

from notifications.device_store import DeviceStore
from notifications.manager import DailyVerseNotificationManager
from notifications.models import PushDispatchResult
from notifications.push_service import PushGateway
from notifications.verse_provider import DailyVerseProvider
from settings import AppSettings


class _NoopPushGateway(PushGateway):
    def send(self, devices, payload):
        return PushDispatchResult(success_count=len(devices), failure_count=0)


# 현재 앱(1.3.0+)이 보내는 전체 필드
CURRENT_APP_PAYLOAD = dict(
    token="tok-1",
    platform="ios",
    timezone="Europe/Berlin",
    device_id="install-1",
    app_version="1.5.0",
    os_version="18.1",
    language="de",
    enabled=True,
    schedule_hour=7,
    schedule_minute=30,
)


class DeviceUpsertMergeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        verse_store_path = (
            Path(__file__).resolve().parent.parent / "notifications" / "daily_verses.json"
        )
        settings = AppSettings(
            firebase_service_account_path="",
            device_store_path=str(temp_path / "devices.json"),
            daily_verse_store_path=str(verse_store_path),
            verse_interpretation_store_path=str(temp_path / "verse_interpretations.json"),
            push_schedule_hour=9,
            push_schedule_minute=0,
            push_default_timezone="Asia/Seoul",
            scheduler_poll_seconds=30,
        )
        self.store = DeviceStore(settings.device_store_path)
        self.manager = DailyVerseNotificationManager(
            settings=settings,
            device_store=self.store,
            verse_provider=DailyVerseProvider(str(verse_store_path)),
            push_gateway=_NoopPushGateway(),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _only_device(self):
        devices = self.store.list_devices()
        self.assertEqual(len(devices), 1)
        return devices[0]

    def test_omitted_fields_keep_existing_values(self) -> None:
        self.manager.register_device(**CURRENT_APP_PAYLOAD)
        result = self.manager.register_device(
            token="tok-1", platform="ios", timezone="Europe/Berlin"
        )

        self.assertTrue(result["updated"])
        device = self._only_device()
        self.assertEqual(device.language, "de")
        self.assertEqual((device.schedule_hour, device.schedule_minute), (7, 30))
        self.assertEqual(device.device_id, "install-1")
        self.assertEqual(device.app_version, "1.5.0")
        self.assertEqual(device.os_version, "18.1")
        self.assertTrue(device.enabled)

    def test_empty_language_counts_as_not_sent(self) -> None:
        self.manager.register_device(**CURRENT_APP_PAYLOAD)
        self.manager.register_device(**{**CURRENT_APP_PAYLOAD, "language": ""})
        self.assertEqual(self._only_device().language, "de")

    def test_sent_fields_overwrite_existing_values(self) -> None:
        self.manager.register_device(**CURRENT_APP_PAYLOAD)
        self.manager.register_device(
            **{
                **CURRENT_APP_PAYLOAD,
                "timezone": "America/New_York",
                "language": "EN",
                "app_version": "1.6.0",
                "os_version": "18.2",
                "enabled": False,
                "schedule_hour": 6,
                "schedule_minute": 15,
            }
        )

        device = self._only_device()
        self.assertEqual(device.timezone, "America/New_York")
        self.assertEqual(device.language, "en")  # 보낸 값은 정규화해 반영
        self.assertEqual(device.app_version, "1.6.0")
        self.assertEqual(device.os_version, "18.2")
        self.assertFalse(device.enabled)
        self.assertEqual((device.schedule_hour, device.schedule_minute), (6, 15))

    def test_falsy_values_are_applied_and_then_kept(self) -> None:
        # 0시 0분·꺼짐(False)은 '안 보냄'이 아니다.
        self.manager.register_device(**CURRENT_APP_PAYLOAD)
        self.manager.register_device(
            token="tok-1",
            platform="ios",
            timezone="Europe/Berlin",
            enabled=False,
            schedule_hour=0,
            schedule_minute=0,
        )
        device = self._only_device()
        self.assertFalse(device.enabled)
        self.assertEqual((device.schedule_hour, device.schedule_minute), (0, 0))

        # 다음 등록에서 안 보내면 그대로 남는다.
        self.manager.register_device(token="tok-1", platform="ios", timezone="Europe/Berlin")
        device = self._only_device()
        self.assertFalse(device.enabled)
        self.assertEqual((device.schedule_hour, device.schedule_minute), (0, 0))

    def test_new_device_gets_defaults(self) -> None:
        result = self.manager.register_device(token="tok-new", platform="android")

        self.assertTrue(result["created"])
        device = self._only_device()
        self.assertEqual(device.language, "ko")
        self.assertTrue(device.enabled)
        self.assertIsNone(device.schedule_hour)
        self.assertIsNone(device.schedule_minute)
        self.assertEqual(device.timezone, "Asia/Seoul")
        self.assertEqual(device.device_id, "")

    def test_token_rotation_by_device_id_keeps_settings(self) -> None:
        self.manager.register_device(**CURRENT_APP_PAYLOAD)
        self.store.mark_sent("tok-1", "2026-11-05")

        # 같은 설치(device_id)에서 FCM 토큰만 바뀌어 다시 등록
        result = self.manager.register_device(
            token="tok-2", platform="ios", timezone="Europe/Berlin", device_id="install-1"
        )

        self.assertTrue(result["updated"])
        device = self._only_device()
        self.assertEqual(device.token, "tok-2")
        self.assertEqual(device.language, "de")
        self.assertEqual((device.schedule_hour, device.schedule_minute), (7, 30))
        self.assertEqual(device.last_daily_sent_on, "2026-11-05")

    def test_disabled_token_is_reenabled_by_registration(self) -> None:
        # 앱은 등록 때마다 enabled 를 보낸다 — 무효 토큰으로 꺼진 행도 다시 켜진다.
        self.manager.register_device(**CURRENT_APP_PAYLOAD)
        self.store.disable_tokens(["tok-1"])
        self.manager.register_device(**CURRENT_APP_PAYLOAD)
        self.assertTrue(self._only_device().enabled)

    def test_legacy_app_payloads(self) -> None:
        self.manager.register_device(**CURRENT_APP_PAYLOAD)

        # 1.2.x(알림 설정 화면 도입 ~ 다국어 이전): language 를 안 보낸다.
        self.manager.register_device(
            token="tok-1",
            platform="ios",
            timezone="Europe/Berlin",
            device_id="install-1",
            app_version="1.2.0",
            os_version="17.4",
            enabled=True,
            schedule_hour=8,
            schedule_minute=0,
        )
        device = self._only_device()
        self.assertEqual(device.language, "de")
        self.assertEqual((device.schedule_hour, device.schedule_minute), (8, 0))
        self.assertEqual(device.app_version, "1.2.0")

        # 1.0.x(FCM 전환 직후): schedule_*·language·os_version·device_id 없이 온다.
        self.manager.register_device(
            token="tok-1",
            platform="ios",
            timezone="Europe/Berlin",
            app_version="1.0.3",
            enabled=True,
        )
        device = self._only_device()
        self.assertEqual(device.language, "de")
        self.assertEqual((device.schedule_hour, device.schedule_minute), (8, 0))
        self.assertEqual(device.os_version, "17.4")
        self.assertEqual(device.device_id, "install-1")
        self.assertEqual(device.app_version, "1.0.3")


if __name__ == "__main__":
    unittest.main()
