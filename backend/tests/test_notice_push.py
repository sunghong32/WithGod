import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from languages import SUPPORTED_LANGUAGES
from notifications.interpretation import find_problems
from notifications.models import DeviceRegistration, MobilePlatform

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "send_notice_push.py"
_spec = importlib.util.spec_from_file_location("send_notice_push", _SCRIPT)
notice = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(notice)


def _device(token: str, timezone: str = "Asia/Seoul", enabled: bool = True) -> DeviceRegistration:
    return DeviceRegistration(
        token=token, platform=MobilePlatform.IOS, timezone=timezone, enabled=enabled
    )


class NoticeMessageTest(unittest.TestCase):
    def test_every_supported_language_has_a_message(self):
        for lang in SUPPORTED_LANGUAGES:
            title, body = notice.NOTICE_MESSAGES[lang]
            self.assertTrue(title.strip() and body.strip(), lang)

    def test_korean_message_is_polite(self):
        title, body = notice.NOTICE_MESSAGES["ko"]
        self.assertEqual(find_problems(f"{title}. {body}"), [])

    def test_unknown_language_falls_back_to_korean(self):
        self.assertEqual(notice.build_payload("xx").title, notice.NOTICE_MESSAGES["ko"][0])


class SelectTargetsTest(unittest.TestCase):
    # 2026-11-03 12:00 KST = 같은 날 04:00 파리 = 전날 22:00 뉴욕
    NOW = datetime(2026, 11, 3, 12, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    def test_skips_disabled_sent_and_duplicate_tokens(self):
        devices = [
            _device("a"),
            _device("off", enabled=False),
            _device("done"),
            _device("a"),
        ]
        ready, deferred = notice.select_targets(devices, {"done"}, self.NOW, (9, 21))
        self.assertEqual([d.token for d in ready], ["a"])
        self.assertEqual(deferred, [])

    def test_defers_devices_outside_local_hours(self):
        devices = [
            _device("seoul"),
            _device("paris", "Europe/Paris"),
            _device("ny", "America/New_York"),
            _device("bad-tz", "Not/AZone"),
        ]
        ready, deferred = notice.select_targets(devices, set(), self.NOW, (9, 21))
        self.assertEqual({d.token for d in ready}, {"seoul", "bad-tz"})
        self.assertEqual({d.token for d in deferred}, {"paris", "ny"})


if __name__ == "__main__":
    unittest.main()
