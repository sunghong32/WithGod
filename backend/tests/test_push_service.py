"""FCM 발송 실패 처리(#24) — 무효 토큰만 끄고, 일시 오류·페이로드 오류는 남기고, 재시도 간격을 늘린다.

예외는 firebase-admin 이 send() 안에서 하는 것과 똑같이 FCM HTTP 오류 응답으로부터 만든다.
응답 본문은 2026-11-05 운영 서버(firebase-admin 7.4.0)에서 dry_run 으로 받은 것 그대로다
(SENDER_ID_MISMATCH·UNAVAILABLE·INTERNAL·QUOTA_EXCEEDED·THIRD_PARTY_AUTH_ERROR 는 같은 모양으로 지었다).
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from notifications.device_store import DeviceStore
from notifications.manager import DailyVerseNotificationManager
from notifications.models import MobilePlatform
from notifications.push_service import FirebasePushGateway, RetryBackoff, is_invalid_token_error
from notifications.scheduler import DailyVerseScheduler
from notifications.verse_provider import DailyVerseProvider
from settings import AppSettings

try:
    import requests
    from firebase_admin import _utils, messaging
    from firebase_admin import exceptions as firebase_exceptions
except ImportError:  # firebase-admin 이 없는 환경에서는 건너뛴다
    messaging = None

FCM_ERROR = "type.googleapis.com/google.firebase.fcm.v1.FcmError"
BAD_REQUEST = "type.googleapis.com/google.rpc.BadRequest"


def _fcm_body(code: int, status: str, message: str, fcm_code: str, field: str | None = None) -> dict:
    details = [{"@type": FCM_ERROR, "errorCode": fcm_code}]
    if field:
        details.insert(0, {"@type": BAD_REQUEST, "fieldViolations": [{"field": field, "description": message}]})
    return {"code": code, "message": message, "status": status, "details": details}


UNREGISTERED = _fcm_body(404, "NOT_FOUND", "NotRegistered", "UNREGISTERED")
INVALID_TOKEN = _fcm_body(
    400,
    "INVALID_ARGUMENT",
    "The registration token is not a valid FCM registration token",
    "INVALID_ARGUMENT",
    field="message.token",
)
PAYLOAD_DATA = _fcm_body(
    400, "INVALID_ARGUMENT", "Invalid data payload key: from", "INVALID_ARGUMENT", field="message.data"
)
PAYLOAD_APNS = _fcm_body(
    400,
    "INVALID_ARGUMENT",
    "Invalid expiration set for apns platform",
    "INVALID_ARGUMENT",
    field="message.apns.headers.apns-expiration",
)
SENDER_ID_MISMATCH = _fcm_body(403, "PERMISSION_DENIED", "SenderId mismatch", "SENDER_ID_MISMATCH")
UNAVAILABLE = _fcm_body(503, "UNAVAILABLE", "The service is currently unavailable.", "UNAVAILABLE")
INTERNAL = _fcm_body(500, "INTERNAL", "Internal error encountered.", "INTERNAL")
QUOTA_EXCEEDED = _fcm_body(429, "RESOURCE_EXHAUSTED", "Quota exceeded.", "QUOTA_EXCEEDED")
APNS_AUTH = _fcm_body(401, "UNAUTHENTICATED", "Auth error from APNS or Web Push Service", "THIRD_PARTY_AUTH_ERROR")


def fcm_error(body: dict) -> Exception:
    """FCM 오류 응답을 firebase-admin 이 send() 에서 하는 그대로 예외로 바꾼다."""
    response = requests.Response()
    response.status_code = body["code"]
    response._content = json.dumps({"error": body}).encode()
    error = requests.exceptions.HTTPError(response=response)
    return _utils.handle_platform_error_from_requests(
        error, messaging._MessagingService._build_fcm_error_requests
    )


@unittest.skipIf(messaging is None, "firebase-admin 이 설치되지 않음")
class InvalidTokenClassificationTest(unittest.TestCase):
    def test_sdk_maps_fcm_error_codes_to_typed_exceptions(self) -> None:
        # 판별이 예외 타입에 기대므로, SDK 가 응답을 이 타입들로 바꾸는지부터 고정해 둔다.
        self.assertIsInstance(fcm_error(UNREGISTERED), messaging.UnregisteredError)
        self.assertIsInstance(fcm_error(SENDER_ID_MISMATCH), messaging.SenderIdMismatchError)
        self.assertIsInstance(fcm_error(QUOTA_EXCEEDED), messaging.QuotaExceededError)
        self.assertIsInstance(fcm_error(APNS_AUTH), messaging.ThirdPartyAuthError)
        self.assertIsInstance(fcm_error(INVALID_TOKEN), firebase_exceptions.InvalidArgumentError)
        self.assertIsInstance(fcm_error(UNAVAILABLE), firebase_exceptions.UnavailableError)
        # 옛 판별이 왜 안 걸렸는지: 메시지에 에러 코드 문자열이 없다.
        self.assertEqual(str(fcm_error(UNREGISTERED)), "NotRegistered")

    def test_dead_or_foreign_or_malformed_tokens_are_invalid(self) -> None:
        for body in (UNREGISTERED, SENDER_ID_MISMATCH, INVALID_TOKEN):
            with self.subTest(body["details"][-1]["errorCode"], message=body["message"]):
                self.assertTrue(is_invalid_token_error(fcm_error(body)))

    def test_payload_and_transient_errors_keep_the_token(self) -> None:
        for body in (PAYLOAD_DATA, PAYLOAD_APNS, UNAVAILABLE, INTERNAL, QUOTA_EXCEEDED, APNS_AUTH):
            with self.subTest(body["status"], message=body["message"]):
                self.assertFalse(is_invalid_token_error(fcm_error(body)))

    def test_invalid_argument_without_response_body_falls_back_to_message(self) -> None:
        self.assertTrue(
            is_invalid_token_error(
                firebase_exceptions.InvalidArgumentError(
                    "The registration token is not a valid FCM registration token"
                )
            )
        )
        self.assertFalse(
            is_invalid_token_error(firebase_exceptions.InvalidArgumentError("Request contains an invalid argument."))
        )

    def test_unparseable_response_body_is_not_invalid(self) -> None:
        response = requests.Response()
        response.status_code = 400
        response._content = b"<html>Bad Request</html>"
        exc = firebase_exceptions.InvalidArgumentError("Bad Request", http_response=response)
        self.assertFalse(is_invalid_token_error(exc))


@unittest.skipIf(messaging is None, "firebase-admin 이 설치되지 않음")
class FirebaseFailureHandlingTest(unittest.TestCase):
    """실제 FirebasePushGateway·DeviceStore·manager 를 거쳐 끝까지 확인한다(messaging.send 만 가짜)."""

    SEOUL = ZoneInfo("Asia/Seoul")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        verse_store_path = Path(__file__).resolve().parent.parent / "notifications" / "daily_verses.json"
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
        # 서비스 계정 없이 만든다 — messaging.send 를 가짜로 바꾸므로 앱 초기화가 필요 없다.
        self.gateway = FirebasePushGateway.__new__(FirebasePushGateway)
        self.gateway._app = None
        self.manager = DailyVerseNotificationManager(
            settings=settings,
            device_store=self.store,
            verse_provider=DailyVerseProvider(str(verse_store_path)),
            push_gateway=self.gateway,
        )
        # token → 그 토큰으로 보낼 때 던질 FCM 오류 본문(없으면 성공)
        self.failures: dict[str, dict] = {}
        self.sent: list[str] = []

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _fake_send(self, message, dry_run=False, app=None):
        self.sent.append(message.token)
        body = self.failures.get(message.token)
        if body is not None:
            raise fcm_error(body)
        return "projects/test/messages/1"

    def _register(self, *tokens: str) -> None:
        for token in tokens:
            self.store.upsert(token=token, platform=MobilePlatform.ANDROID, timezone="Asia/Seoul")

    def _poll(self, now: datetime) -> dict[str, object]:
        self.sent = []
        with patch.object(messaging, "send", side_effect=self._fake_send):
            return self.manager.send_due_notifications(now=now)

    def _devices(self) -> dict[str, object]:
        return {device.token: device for device in self.store.list_devices()}

    def test_only_invalid_tokens_are_disabled(self) -> None:
        self.failures = {
            "dead": UNREGISTERED,
            "malformed": INVALID_TOKEN,
            "other-project": SENDER_ID_MISMATCH,
            "flaky": UNAVAILABLE,
            "fcm-internal": INTERNAL,
            "quota": QUOTA_EXCEEDED,
            "bad-payload": PAYLOAD_DATA,
            "apns-auth": APNS_AUTH,
        }
        self._register("ok", *self.failures)

        with self.assertLogs("with-god.push", level="WARNING") as logs:
            outcome = self._poll(datetime(2026, 11, 5, 9, 0, tzinfo=self.SEOUL))

        result = outcome["result"]
        self.assertEqual(sorted(result["invalid_tokens"]), ["dead", "malformed", "other-project"])
        devices = self._devices()
        for token in ("dead", "malformed", "other-project"):
            self.assertFalse(devices[token].enabled, token)
        for token in ("ok", "flaky", "fcm-internal", "quota", "bad-payload", "apns-auth"):
            self.assertTrue(devices[token].enabled, token)
        # 실패한 기기는 오늘 받은 것으로 치지 않는다(나중에 다시 시도).
        self.assertEqual(devices["ok"].last_daily_sent_on, "2026-11-05")
        self.assertEqual(devices["flaky"].last_daily_sent_on, "")
        # 실패 원인이 로그에 남는다.
        joined = "\n".join(logs.output)
        self.assertIn("UnregisteredError code=NOT_FOUND http=404 invalid=True: NotRegistered", joined)
        self.assertIn("UnavailableError code=UNAVAILABLE http=503 invalid=False", joined)
        self.assertIn("sent=1 failed=8 invalid_tokens=3", joined)

        # 다음 폴링: 꺼진 기기는 대상에서 빠진다.
        self.failures = {}
        self._poll(datetime(2026, 11, 5, 9, 2, tzinfo=self.SEOUL))
        self.assertNotIn("dead", self.sent)
        self.assertNotIn("malformed", self.sent)
        self.assertIn("flaky", self.sent)
        self.assertEqual(self._devices()["flaky"].last_daily_sent_on, "2026-11-05")

    def test_transient_failure_backs_off_instead_of_retrying_every_poll(self) -> None:
        self.failures = {"flaky": UNAVAILABLE}
        self._register("flaky")
        start = datetime(2026, 11, 5, 9, 0, tzinfo=self.SEOUL)

        with self.assertLogs("with-god.push", level="WARNING"):
            self._poll(start)  # 실패 1 → 1분 뒤
        self.assertEqual(self.sent, ["flaky"])
        self._poll(start + timedelta(seconds=30))
        self.assertEqual(self.sent, [])  # 예전엔 30초마다 다시 보냈다
        with self.assertLogs("with-god.push", level="WARNING"):
            self._poll(start + timedelta(minutes=1))  # 실패 2 → 2분 뒤
        self.assertEqual(self.sent, ["flaky"])
        self._poll(start + timedelta(minutes=2))
        self.assertEqual(self.sent, [])

        self.failures = {}  # 장애가 풀리면 다음 차례에 보내고 오늘 받은 것으로 기록한다.
        self._poll(start + timedelta(minutes=3))
        self.assertEqual(self.sent, ["flaky"])
        self.assertEqual(self._devices()["flaky"].last_daily_sent_on, "2026-11-05")

    def test_backoff_resets_on_next_local_day(self) -> None:
        self.failures = {"flaky": UNAVAILABLE}
        self._register("flaky")
        with self.assertLogs("with-god.push", level="WARNING"):
            self._poll(datetime(2026, 11, 5, 23, 59, tzinfo=self.SEOUL))
        self.failures = {}
        self._poll(datetime(2026, 11, 6, 9, 0, 30, tzinfo=self.SEOUL))
        self.assertEqual(self.sent, ["flaky"])
        self.assertEqual(self._devices()["flaky"].last_daily_sent_on, "2026-11-06")


class RetryBackoffTest(unittest.TestCase):
    def test_delay_doubles_up_to_max_and_success_resets(self) -> None:
        backoff = RetryBackoff(first_delay=timedelta(minutes=1), max_delay=timedelta(hours=1))
        now = datetime(2026, 11, 5, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        expected_minutes = [1, 2, 4, 8, 16, 32, 60, 60, 60]
        for minutes in expected_minutes:
            backoff.record("t", "2026-11-05", now, failed=True)
            self.assertFalse(backoff.ready("t", "2026-11-05", now + timedelta(minutes=minutes) - timedelta(seconds=1)))
            now += timedelta(minutes=minutes)
            self.assertTrue(backoff.ready("t", "2026-11-05", now))
        backoff.record("t", "2026-11-05", now, failed=False)
        backoff.record("t", "2026-11-05", now, failed=True)
        self.assertTrue(backoff.ready("t", "2026-11-05", now + timedelta(minutes=1)))

    def test_many_failures_do_not_overflow(self) -> None:
        backoff = RetryBackoff()
        now = datetime(2026, 11, 5, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        for _ in range(500):
            backoff.record("t", "2026-11-05", now, failed=True)
        self.assertTrue(backoff.ready("t", "2026-11-05", now + timedelta(hours=1)))


class SchedulerErrorLoggingTest(unittest.TestCase):
    def test_repeated_identical_error_is_logged_once(self) -> None:
        manager = Mock()
        scheduler = DailyVerseScheduler(manager=manager, poll_seconds=0)

        def fail() -> None:
            if manager.send_due_notifications.call_count >= 3:
                scheduler._stop_event.set()
            raise RuntimeError("Missing FIREBASE_SERVICE_ACCOUNT_PATH")

        manager.send_due_notifications.side_effect = fail
        with self.assertLogs("with-god.push", level="ERROR") as logs:
            scheduler._run()
        self.assertEqual(manager.send_due_notifications.call_count, 3)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("Missing FIREBASE_SERVICE_ACCOUNT_PATH", logs.output[0])


if __name__ == "__main__":
    unittest.main()
