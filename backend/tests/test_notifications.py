import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from notifications.device_store import DeviceStore
from notifications.manager import DailyVerseNotificationManager
from notifications.models import MobilePlatform, PushDispatchResult
from notifications.push_service import PushGateway
from notifications.scheduler import DailyVerseScheduler
from notifications.models import DailyVerse
from notifications.verse_provider import (
    DailyVerseProvider,
    VerseInterpretationStore,
    VerseInterpreter,
    fixed_verse_id,
)
from settings import AppSettings


class FakePushGateway(PushGateway):
    def __init__(self) -> None:
        self.sent_batches: list[list[str]] = []
        # (devices, payload) 원본 — 언어별 그룹 발송 검증용
        self.calls: list[tuple[list, object]] = []

    def send(self, devices, payload):
        self.sent_batches.append([device.token for device in devices])
        self.calls.append((list(devices), payload))
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

    # --- #25: 알림 시각이 지난 뒤 새로 등록된 기기에 즉시 푸시가 가던 문제 ---

    def test_new_device_registered_after_target_waits_until_next_day(self) -> None:
        # 15:00 에 처음 등록(전역 9:00)하면 캐치업으로 곧바로 보내지 않고 다음 날 9:00 부터 받는다.
        result = self.manager.register_device(
            token="late-token",
            platform="android",
            timezone="Asia/Seoul",
            device_id="install-late",
            now=datetime(2026, 4, 21, 15, 0),
        )
        self.assertTrue(result["created"])
        self.assertEqual(result["device"]["last_daily_sent_on"], "2026-04-21")
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)

        right_after = scheduler.run_once(now=datetime(2026, 4, 21, 15, 0, 30))
        self.assertEqual(right_after["scheduled_count"], 0)
        self.assertEqual(self.gateway.sent_batches, [])

        next_day_early = scheduler.run_once(now=datetime(2026, 4, 22, 8, 59))
        self.assertEqual(next_day_early["scheduled_count"], 0)

        next_day_sent = scheduler.run_once(now=datetime(2026, 4, 22, 9, 0))
        self.assertEqual(next_day_sent["result"]["success_count"], 1)
        self.assertEqual(self.store.list_devices()[0].last_daily_sent_on, "2026-04-22")

    def test_new_device_registered_before_target_gets_push_same_day(self) -> None:
        result = self.manager.register_device(
            token="early-token",
            platform="ios",
            timezone="Asia/Seoul",
            device_id="install-early",
            now=datetime(2026, 4, 21, 8, 0),
        )
        self.assertEqual(result["device"]["last_daily_sent_on"], "")
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)

        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 21, 8, 59))["scheduled_count"], 0)
        sent = scheduler.run_once(now=datetime(2026, 4, 21, 9, 0))
        self.assertEqual(sent["result"]["success_count"], 1)

    def test_new_device_uses_personal_schedule_for_initial_sent_date(self) -> None:
        # 개인 시각 기준으로 판정한다: 15:00 등록 시 7:30 은 이미 지났고 20:30 은 아직이다.
        passed = self.manager.register_device(
            token="morning-token",
            platform="ios",
            timezone="Asia/Seoul",
            device_id="install-morning",
            schedule_hour=7,
            schedule_minute=30,
            now=datetime(2026, 4, 21, 15, 0),
        )
        upcoming = self.manager.register_device(
            token="evening-token",
            platform="ios",
            timezone="Asia/Seoul",
            device_id="install-evening",
            schedule_hour=20,
            schedule_minute=30,
            now=datetime(2026, 4, 21, 15, 0),
        )
        self.assertEqual(passed["device"]["last_daily_sent_on"], "2026-04-21")
        self.assertEqual(upcoming["device"]["last_daily_sent_on"], "")
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)

        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 21, 15, 1))["scheduled_count"], 0)
        evening = scheduler.run_once(now=datetime(2026, 4, 21, 20, 30))
        self.assertEqual(self.gateway.sent_batches, [["evening-token"]])
        self.assertEqual(evening["result"]["success_count"], 1)

        next_morning = scheduler.run_once(now=datetime(2026, 4, 22, 7, 30))
        self.assertEqual(next_morning["result"]["success_count"], 1)
        self.assertEqual(self.gateway.sent_batches[-1], ["morning-token"])

    def test_new_device_initial_sent_date_uses_device_local_date(self) -> None:
        # 서버 기본은 Asia/Seoul. KST 4/21 15:00 = LA 4/20 23:00 → LA 기준 4/20 몫만 보낸 것으로 친다.
        la = self.manager.register_device(
            token="la-token",
            platform="android",
            timezone="America/Los_Angeles",
            device_id="install-la",
            now=datetime(2026, 4, 21, 15, 0),
        )
        self.assertEqual(la["device"]["last_daily_sent_on"], "2026-04-20")
        # KST 4/21 23:00 = LA 4/21 07:00 → 아직 9:00 전이라 비워 둔다.
        la_morning = self.manager.register_device(
            token="la-morning-token",
            platform="android",
            timezone="America/Los_Angeles",
            device_id="install-la-morning",
            now=datetime(2026, 4, 21, 23, 0),
        )
        self.assertEqual(la_morning["device"]["last_daily_sent_on"], "")
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)

        # LA 4/21 08:59 (KST 4/22 00:59) 에는 둘 다 아직.
        early = scheduler.run_once(now=datetime(2026, 4, 22, 0, 59))
        self.assertEqual(early["scheduled_count"], 0)
        # LA 4/21 09:00 (KST 4/22 01:00) 에 둘 다 받는다 — 서버 날짜(4/21)를 썼다면 la-token 이 빠진다.
        sent = scheduler.run_once(now=datetime(2026, 4, 22, 1, 0))
        self.assertEqual(sorted(self.gateway.sent_batches[-1]), ["la-morning-token", "la-token"])
        self.assertEqual(sent["result"]["success_count"], 2)

    def test_token_rotation_keeps_sent_date_so_no_second_push(self) -> None:
        # 같은 설치(device_id)에서 토큰만 바뀌면 기존 행 갱신 — 이미 받은 날 다시 보내지 않는다.
        self.manager.register_device(
            token="old-token",
            platform="ios",
            timezone="Asia/Seoul",
            device_id="install-rotate",
            now=datetime(2026, 4, 21, 8, 0),
        )
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)
        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 21, 9, 0))["scheduled_count"], 1)

        rotated = self.manager.register_device(
            token="new-token",
            platform="ios",
            timezone="Asia/Seoul",
            device_id="install-rotate",
            now=datetime(2026, 4, 21, 15, 0),
        )
        self.assertFalse(rotated["created"])
        self.assertEqual(rotated["device"]["token"], "new-token")
        self.assertEqual(rotated["device"]["last_daily_sent_on"], "2026-04-21")
        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 21, 15, 1))["scheduled_count"], 0)

    def test_existing_device_moving_schedule_later_still_gets_today(self) -> None:
        # 기존 사용자가 알림 시각을 '지금 이후'로 바꾸면 그날 바뀐 시각에 그대로 받는다.
        self.manager.register_device(
            token="move-token",
            platform="android",
            timezone="Asia/Seoul",
            device_id="install-move",
            schedule_hour=21,
            schedule_minute=0,
            now=datetime(2026, 4, 20, 8, 0),
        )
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)
        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 20, 21, 0))["scheduled_count"], 1)

        moved = self.manager.register_device(
            token="move-token",
            platform="android",
            timezone="Asia/Seoul",
            device_id="install-move",
            schedule_hour=18,
            schedule_minute=0,
            now=datetime(2026, 4, 21, 15, 0),
        )
        self.assertFalse(moved["created"])
        self.assertEqual(moved["device"]["last_daily_sent_on"], "2026-04-20")
        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 21, 17, 59))["scheduled_count"], 0)
        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 21, 18, 0))["scheduled_count"], 1)

    def test_existing_device_reregistered_after_target_keeps_catch_up(self) -> None:
        # 초기화는 새 행에만 한다: 오늘 아직 못 받은 기존 행이 시각이 지난 뒤 재등록돼도
        # (앱 실행 시 재등록 등) 캐치업 발송은 그대로 나간다.
        self.manager.register_device(
            token="kept-token",
            platform="ios",
            timezone="Asia/Seoul",
            device_id="install-kept",
            now=datetime(2026, 4, 21, 8, 0),
        )
        again = self.manager.register_device(
            token="kept-token",
            platform="ios",
            timezone="Asia/Seoul",
            device_id="install-kept",
            now=datetime(2026, 4, 21, 15, 0),
        )
        self.assertFalse(again["created"])
        self.assertEqual(again["device"]["last_daily_sent_on"], "")
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)
        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 21, 15, 0, 30))["scheduled_count"], 1)

    def test_new_device_registered_disabled_then_enabled_same_day(self) -> None:
        # 알림을 끈 채 시각 이후에 처음 등록했다가 그날 켜도 곧바로 보내지 않는다.
        self.manager.register_device(
            token="off-token",
            platform="android",
            timezone="Asia/Seoul",
            device_id="install-off",
            enabled=False,
            now=datetime(2026, 4, 21, 15, 0),
        )
        enabled = self.manager.register_device(
            token="off-token",
            platform="android",
            timezone="Asia/Seoul",
            device_id="install-off",
            enabled=True,
            now=datetime(2026, 4, 21, 16, 0),
        )
        self.assertTrue(enabled["device"]["enabled"])
        self.assertEqual(enabled["device"]["last_daily_sent_on"], "2026-04-21")
        scheduler = DailyVerseScheduler(self.manager, poll_seconds=30)
        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 21, 16, 1))["scheduled_count"], 0)
        self.assertEqual(scheduler.run_once(now=datetime(2026, 4, 22, 9, 0))["scheduled_count"], 1)

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
        generate.assert_called_once_with(verse["reference"], verse["text"], "ko", "")
        self.assertEqual(verse["interpretation"], "풀이 첫 문장이에요. 두 번째 문장이에요.")
        # 풀이가 파일 캐시에 영속되어야 한다. 키는 verse_id 에 본문 지문을 붙인 것이다
        # (같은 verse_id 라도 본문이 바뀌면 예전 풀이를 쓰지 않기 위해 — 아래 테스트 참고).
        cached = json.loads(self.interpretation_store_path.read_text(encoding="utf-8"))
        keys = [k for k, v in cached.items() if v == verse["interpretation"]]
        self.assertEqual(len(keys), 1)
        self.assertTrue(keys[0].startswith(verse["verse_id"] + ":"))

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

    def test_interpretation_cache_invalidated_when_verse_text_changes(self) -> None:
        # 같은 verse_id 라도 본문이 바뀌면 예전 풀이를 붙여 내보내면 안 된다.
        # 실제로 목록 교체 때 num-6-24 가 민수기 6:24 → 6:24-26(아론의 축복 전체)으로 바뀌었다.
        store = VerseInterpretationStore(str(self.interpretation_store_path))
        old = DailyVerse(verse_id="num-6-24", reference="민수기 6:24",
                         text="여호와는 네게 복을 주시고 너를 지키시기를 원하며", reflection="r")
        new = DailyVerse(verse_id="num-6-24", reference="민수기 6:24-26",
                         text="여호와는 네게 복을 주시고 … 평강주시기를 원하노라", reflection="r")

        VerseInterpreter(store=store, generate_fn=Mock(return_value="예전 본문 풀이")).interpret(old)
        regenerate = Mock(return_value="새 본문 풀이")
        result = VerseInterpreter(store=store, generate_fn=regenerate).interpret(new)

        regenerate.assert_called_once()
        self.assertEqual(result, "새 본문 풀이")
        # 본문이 같으면 다시 부르지 않는다
        again = Mock(return_value="불리면 안 됨")
        self.assertEqual(VerseInterpreter(store=store, generate_fn=again).interpret(new), "새 본문 풀이")
        again.assert_not_called()

    def test_fixed_verses_on_holidays(self) -> None:
        # 회전 주기가 365일이 아니라서 절기에는 정해진 말씀을 고정한다.
        expected = {
            date(2026, 1, 1): "jer-29-11",    # 새해
            date(2026, 4, 5): "jhn-16-22",    # 부활절(계산)
            date(2027, 3, 28): "jhn-16-22",   # 부활절은 해마다 옮겨 다닌다
            date(2026, 12, 24): "isa-9-2",    # 성탄 전야
            date(2026, 12, 25): "luk-2-14",   # 성탄절
            date(2026, 2, 17): "num-6-24",    # 설날(음력 1/1)
            date(2026, 9, 25): "psa-128-2",   # 추석(음력 8/15)
            date(2027, 2, 7): "num-6-24",     # 2027 설날 — 한국 음력 기준
        }
        for day, verse_id in expected.items():
            with self.subTest(day=day):
                self.assertEqual(fixed_verse_id(day), verse_id)
                served = self.provider.get_daily_verse(now=datetime(day.year, day.month, day.day, 9, 0))
                self.assertEqual(served.verse_id, verse_id)

        # 성탄절 말씀은 성탄절에만 나온다 — 평소 회전에서는 빠진다.
        verses = json.loads(self.verse_store_path.read_text(encoding="utf-8"))
        day = date(2027, 1, 2)
        for offset in range(len(verses) + 1):
            current = date.fromordinal(day.toordinal() + offset)
            if fixed_verse_id(current):
                continue
            served = self.provider.get_daily_verse(now=datetime(current.year, current.month, current.day, 9, 0))
            self.assertNotEqual(served.verse_id, "luk-2-14", current)

        # 중국 음력으로 계산하면 2027 설날이 2/6 이 된다. 그날은 고정하지 않아야 한다.
        self.assertIsNone(fixed_verse_id(date(2027, 2, 6)))
        # 평범한 날은 고정 없음
        self.assertIsNone(fixed_verse_id(date(2026, 3, 3)))


class LanguageFeatureTest(NotificationFeatureTest):
    """기기 언어 필드 + 언어별 푸시 발송 (이슈 #12)."""

    def test_register_device_persists_language(self) -> None:
        self.manager.register_device(
            token="tok-lang", platform="ios", language="EN"
        )
        stored = self.store.list_devices()[-1]
        self.assertEqual(stored.language, "en")  # 정규화되어 저장

    def test_register_device_defaults_language_to_ko(self) -> None:
        self.manager.register_device(token="tok-nolang", platform="ios")
        stored = self.store.list_devices()[-1]
        self.assertEqual(stored.language, "ko")

    def test_legacy_store_record_defaults_language_to_ko(self) -> None:
        # language 필드가 없던 기존 저장 파일도 ko 로 읽혀야 한다.
        self.manager.register_device(token="tok-legacy", platform="ios")
        raw = json.loads(self.store.path.read_text(encoding="utf-8"))
        for item in raw:
            item.pop("language", None)
        self.store.path.write_text(json.dumps(raw), encoding="utf-8")
        stored = self.store.list_devices()[-1]
        self.assertEqual(stored.language, "ko")

    def test_send_groups_devices_by_language(self) -> None:
        from unittest.mock import patch

        self.manager.register_device(token="tok-ko", platform="ios", language="ko")
        self.manager.register_device(token="tok-en", platform="android", language="en")

        localized = {"ref": "Psalms 23:1", "text": "The LORD is my shepherd."}
        with patch("notifications.manager.resolve_lang", side_effect=lambda l: l or "ko"), \
             patch("notifications.manager.localize_ko_ref", return_value=localized):
            self.manager.send_daily_verse_now(now=datetime(2026, 4, 21, 9, 0))

        # 언어 그룹별로 별도 페이로드가 발송된다.
        self.assertEqual(len(self.gateway.calls), 2)
        by_title = {payload.title.split(" | ")[0]: devices
                    for devices, payload in self.gateway.calls}
        self.assertIn("오늘의 말씀", by_title)
        self.assertIn("Today's Verse", by_title)
        en_devices, en_payload = next(
            (d, p) for d, p in self.gateway.calls if p.title.startswith("Today's Verse")
        )
        self.assertEqual([d.token for d in en_devices], ["tok-en"])
        self.assertEqual(en_payload.body, "The LORD is my shepherd.")
        self.assertEqual(en_payload.data["ref"], "Psalms 23:1")

    def test_send_falls_back_to_korean_when_localization_fails(self) -> None:
        from unittest.mock import patch

        self.manager.register_device(token="tok-en2", platform="ios", language="en")
        with patch("notifications.manager.resolve_lang", side_effect=lambda l: l or "ko"), \
             patch("notifications.manager.localize_ko_ref", return_value=None):
            self.manager.send_daily_verse_now(now=datetime(2026, 4, 21, 9, 0))
        # 정렬 실패 시 한국어 본문이라도 발송된다(제목은 해당 언어).
        devices, payload = self.gateway.calls[-1]
        self.assertTrue(payload.title.startswith("Today's Verse"))
        self.assertNotEqual(payload.body, "")
