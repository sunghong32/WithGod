import tempfile
import unittest
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from analytics import queries
from analytics.db import init_db, service_day, session
from analytics.ingest import ingest_batch
from analytics.ratelimit import SlidingWindowLimiter
from analytics.rollup import claim_job, run_rollup
from analytics.schema import sanitize_params

KST = ZoneInfo("Asia/Seoul")


def kst(year, month, day, hour=12):
    return datetime(year, month, day, hour, tzinfo=KST).astimezone(dt_timezone.utc)


def batch(anon_id, events, **meta):
    payload = {
        "anon_id": anon_id,
        "platform": meta.get("platform", "ios"),
        "app_version": meta.get("app_version", "1.2.0"),
        "os_version": meta.get("os_version", "18.2"),
        "tz": "Asia/Seoul",
        "events": events,
    }
    return payload


def event(event_id, name="app_open", params=None, session_id="s1"):
    return {
        "event_id": event_id,
        "name": name,
        "ts": "2026-07-23T12:00:00+09:00",
        "session_id": session_id,
        "params": params,
    }


class AnalyticsTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self._tmp.name) / "analytics.sqlite3")
        init_db(self.db)

    def tearDown(self):
        self._tmp.cleanup()


class IngestTest(AnalyticsTestBase):
    def test_stores_events_and_marks_device_active(self):
        result = ingest_batch(
            self.db,
            batch("device-a", [event("e1"), event("e2", "verse_save")]),
            received_at=kst(2026, 7, 23),
        )
        self.assertEqual(result["accepted"], 2)

        with session(self.db) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 2
            )
            active = conn.execute("SELECT day, anon_id FROM daily_active").fetchall()
            self.assertEqual([tuple(row) for row in active], [("2026-07-23", "device-a")])
            profile = conn.execute("SELECT * FROM device_profile").fetchone()
            self.assertEqual(profile["first_day"], "2026-07-23")
            self.assertEqual(profile["platform"], "ios")

    def test_resent_batch_is_not_double_counted(self):
        payload = batch("device-a", [event("e1")])
        ingest_batch(self.db, payload, received_at=kst(2026, 7, 23))
        again = ingest_batch(self.db, payload, received_at=kst(2026, 7, 23))

        self.assertEqual(again["accepted"], 0)
        self.assertEqual(again["duplicates"], 1)
        with session(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)

    def test_first_day_never_moves_forward(self):
        ingest_batch(self.db, batch("device-a", [event("e1")]), received_at=kst(2026, 7, 20))
        ingest_batch(self.db, batch("device-a", [event("e2")]), received_at=kst(2026, 7, 23))

        with session(self.db) as conn:
            profile = conn.execute("SELECT * FROM device_profile").fetchone()
            self.assertEqual(profile["first_day"], "2026-07-20")
            self.assertEqual(profile["last_day"], "2026-07-23")

    def test_unknown_event_name_shape_is_dropped(self):
        result = ingest_batch(
            self.db,
            batch("device-a", [event("e1", "Verse Save!"), event("e2", "")]),
            received_at=kst(2026, 7, 23),
        )
        self.assertEqual(result["accepted"], 0)
        self.assertEqual(result["dropped"], 2)

    def test_bad_event_does_not_take_down_the_whole_batch(self):
        # 배치 전체를 거부하면 앱이 같은 배치를 영원히 재전송하게 된다.
        result = ingest_batch(
            self.db,
            batch("device-a", [event("e1", "Verse Save!"), event("e2", "verse_save")]),
            received_at=kst(2026, 7, 23),
        )
        self.assertEqual(result, {"accepted": 1, "dropped": 1, "duplicates": 0})

    def test_new_event_name_is_accepted_without_backend_deploy(self):
        # 앱이 먼저 새 이벤트를 붙여도 유실되지 않아야 한다.
        result = ingest_batch(
            self.db,
            batch("device-a", [event("e1", "widget_tap")]),
            received_at=kst(2026, 7, 23),
        )
        self.assertEqual(result["accepted"], 1)

    def test_service_day_uses_kst_not_utc(self):
        # UTC 로는 22일 23시지만 KST 로는 23일 08시다.
        moment = datetime(2026, 7, 22, 23, 0, tzinfo=dt_timezone.utc)
        ingest_batch(self.db, batch("device-a", [event("e1")]), received_at=moment)
        with session(self.db) as conn:
            self.assertEqual(
                conn.execute("SELECT day FROM events").fetchone()[0], "2026-07-23"
            )


class ParamSanitizeTest(unittest.TestCase):
    def test_drops_keys_outside_whitelist(self):
        cleaned = sanitize_params("mood_submit", {"length": 12, "mood": "요즘 너무 힘들어요"})
        self.assertEqual(cleaned, {"length": 12})

    def test_drops_nested_structures(self):
        cleaned = sanitize_params("verse_save", {"reference": "이사야 41:10", "source": {"a": 1}})
        self.assertEqual(cleaned, {"reference": "이사야 41:10"})

    def test_truncates_long_values(self):
        cleaned = sanitize_params("verse_save", {"reference": "가" * 500})
        self.assertEqual(len(cleaned["reference"]), 100)

    def test_unknown_event_falls_back_to_global_whitelist(self):
        cleaned = sanitize_params("widget_tap", {"source": "home", "note": "비밀"})
        self.assertEqual(cleaned, {"source": "home"})


class RollupTest(AnalyticsTestBase):
    def seed(self, anon_id, day_offsets, base=kst(2026, 7, 23)):
        for offset in day_offsets:
            moment = base - timedelta(days=offset)
            ingest_batch(
                self.db,
                batch(anon_id, [event(f"{anon_id}-{offset}")]),
                received_at=moment,
            )

    def test_daily_metrics_split_new_and_returning(self):
        now = kst(2026, 7, 23)
        self.seed("old-user", [5, 0])   # 5일 전 첫 방문, 오늘 재방문
        self.seed("new-user", [0])      # 오늘 첫 방문
        run_rollup(self.db, now=now)

        with session(self.db) as conn:
            row = conn.execute(
                "SELECT * FROM daily_metrics WHERE day = ?", ("2026-07-23",)
            ).fetchone()
        self.assertEqual(row["dau"], 2)
        self.assertEqual(row["new_users"], 1)
        self.assertEqual(row["returning_users"], 1)

    def test_wau_mau_count_distinct_users_over_window(self):
        now = kst(2026, 7, 23)
        self.seed("a", [0])
        self.seed("b", [3])    # 주간 창 안
        self.seed("c", [10])   # 주간 창 밖, 월간 창 안
        self.seed("d", [45])   # 둘 다 밖
        run_rollup(self.db, now=now)

        overview = queries.get_overview(self.db, now=now)
        self.assertEqual(overview["dau"], 1)
        self.assertEqual(overview["wau"], 2)
        self.assertEqual(overview["mau"], 3)
        self.assertEqual(overview["total_users"], 4)

    def test_retention_counts_only_returning_cohort_members(self):
        now = kst(2026, 7, 23)
        # 7/16 에 둘 다 첫 방문, 하루 뒤엔 한 명만 돌아옴
        self.seed("stayer", [7, 6])
        self.seed("leaver", [7])
        run_rollup(self.db, now=now)

        with session(self.db) as conn:
            row = conn.execute(
                "SELECT * FROM retention_cohort WHERE cohort_day = ? AND day_n = 1",
                ("2026-07-16",),
            ).fetchone()
        self.assertEqual(row["cohort_size"], 2)
        self.assertEqual(row["retained"], 1)

    def test_future_retention_cells_are_null_not_zero(self):
        now = kst(2026, 7, 23)
        self.seed("today-user", [0])
        run_rollup(self.db, now=now)

        result = queries.get_retention(self.db, cohorts=3, now=now)
        today_row = [r for r in result["rows"] if r["cohort_day"] == "2026-07-23"][0]
        self.assertTrue(all(cell["rate"] is None for cell in today_row["cells"]))

    def test_pruning_keeps_rolled_up_metrics(self):
        now = kst(2026, 7, 23)
        self.seed("a", [100])
        # 100일 전 지표를 먼저 굳혀둔다(보관기간보다 길게 잡아 원시 데이터 유지).
        run_rollup(self.db, now=now, lookback_days=120, raw_retention_days=365)
        run_rollup(self.db, now=now, lookback_days=120, raw_retention_days=90)

        old_day = service_day(now - timedelta(days=100))
        with session(self.db) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM events WHERE day = ?", (old_day,)).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM daily_active WHERE day = ?", (old_day,)).fetchone()[0],
                1,
            )
            metrics = conn.execute(
                "SELECT * FROM daily_metrics WHERE day = ?", (old_day,)
            ).fetchone()
        self.assertEqual(metrics["dau"], 1)
        self.assertEqual(metrics["events"], 1)

    def test_job_lock_lets_only_one_worker_run(self):
        self.assertTrue(claim_job(self.db, "daily_rollup", "2026-07-23"))
        self.assertFalse(claim_job(self.db, "daily_rollup", "2026-07-23"))
        self.assertTrue(claim_job(self.db, "daily_rollup", "2026-07-24"))


class QueriesTest(AnalyticsTestBase):
    def test_today_is_live_without_rollup(self):
        now = kst(2026, 7, 23)
        ingest_batch(self.db, batch("device-a", [event("e1")]), received_at=now)

        overview = queries.get_overview(self.db, now=now)
        self.assertEqual(overview["dau"], 1)
        self.assertEqual(overview["new_users"], 1)

    def test_event_counts_group_by_name(self):
        now = kst(2026, 7, 23)
        ingest_batch(
            self.db,
            batch("device-a", [event("e1", "verse_save"), event("e2", "verse_save")]),
            received_at=now,
        )
        ingest_batch(self.db, batch("device-b", [event("e3", "verse_save")]), received_at=now)

        counts = {row["name"]: row for row in queries.get_event_counts(self.db, now=now)}
        self.assertEqual(counts["verse_save"]["total"], 3)
        self.assertEqual(counts["verse_save"]["users"], 2)

    def test_breakdown_counts_recently_active_only(self):
        now = kst(2026, 7, 23)
        ingest_batch(self.db, batch("ios-user", [event("e1")], platform="ios"), received_at=now)
        ingest_batch(
            self.db,
            batch("old-android", [event("e2")], platform="android"),
            received_at=now - timedelta(days=60),
        )

        breakdown = queries.get_breakdown(self.db, days=30, now=now)
        self.assertEqual(breakdown["platforms"], [{"key": "ios", "users": 1}])


class RateLimitTest(unittest.TestCase):
    def test_blocks_after_limit_within_window(self):
        limiter = SlidingWindowLimiter(limit=2, window_seconds=60.0)
        self.assertTrue(limiter.allow("a", now=0.0))
        self.assertTrue(limiter.allow("a", now=1.0))
        self.assertFalse(limiter.allow("a", now=2.0))
        # 창이 지나면 다시 허용
        self.assertTrue(limiter.allow("a", now=62.0))

    def test_keys_are_independent(self):
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60.0)
        self.assertTrue(limiter.allow("a", now=0.0))
        self.assertTrue(limiter.allow("b", now=0.0))


if __name__ == "__main__":
    unittest.main()
