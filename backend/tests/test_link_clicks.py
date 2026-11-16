import tempfile
import unittest
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from analytics.db import init_db
from analytics.link_clicks import InvalidLinkClick, get_link_clicks, record_click

KST = ZoneInfo("Asia/Seoul")


def kst(month, day, hour=12, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=KST).astimezone(dt_timezone.utc)


class LinkClickTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self._tmp.name) / "analytics.sqlite3")
        init_db(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def test_counts_by_source_and_platform(self):
        record_click(self.db, "ig-dm", "ios", "aaaa1111", now=kst(11, 16, 10))
        record_click(self.db, "ig-dm", "android", "bbbb2222", now=kst(11, 16, 11))
        record_click(self.db, "instagram", "other", "cccc3333", now=kst(11, 16, 12))

        result = get_link_clicks(self.db, days=7, now=kst(11, 16, 13))

        by_source = {row["source"]: row for row in result["sources"]}
        self.assertEqual(by_source["ig-dm"]["clicks"], 2)
        self.assertEqual(by_source["ig-dm"]["ios"], 1)
        self.assertEqual(by_source["ig-dm"]["android"], 1)
        self.assertEqual(by_source["ig-dm"]["other"], 0)
        self.assertEqual(by_source["instagram"]["other"], 1)
        # 클릭이 많은 출처가 먼저
        self.assertEqual(result["sources"][0]["source"], "ig-dm")

    def test_same_visitor_same_day_counts_once(self):
        for minute in (0, 1, 2):
            record_click(self.db, "ig-dm", "ios", "aaaa1111", now=kst(11, 16, 10, minute))
        # 해시는 하루마다 바뀌므로 다음 날은 다른 방문으로 센다
        record_click(self.db, "ig-dm", "ios", "aaaa1111", now=kst(11, 17, 10))

        row = get_link_clicks(self.db, days=7, now=kst(11, 17, 12))["sources"][0]
        self.assertEqual(row["clicks"], 4)
        self.assertEqual(row["visitors"], 2)

    def test_missing_visitor_counts_each_click(self):
        record_click(self.db, "direct", "other", None, now=kst(11, 16, 10))
        record_click(self.db, "direct", "other", None, now=kst(11, 16, 11))

        row = get_link_clicks(self.db, days=1, now=kst(11, 16, 12))["sources"][0]
        self.assertEqual(row["visitors"], 2)

    def test_range_uses_kst_days(self):
        # 11/9 23:30 KST 는 기간 밖, 11/10 00:30 KST 는 7일 기간(11/10~11/16) 안
        record_click(self.db, "ig-dm", "ios", "aaaa1111", now=kst(11, 9, 23, 30))
        record_click(self.db, "ig-dm", "ios", "bbbb2222", now=kst(11, 10, 0, 30))

        result = get_link_clicks(self.db, days=7, now=kst(11, 16, 12))
        self.assertEqual(result["sources"][0]["clicks"], 1)
        self.assertEqual(len(result["recent"]), 1)

    def test_recent_is_newest_first(self):
        record_click(self.db, "ig-dm", "ios", "aaaa1111", now=kst(11, 16, 9))
        record_click(self.db, "instagram", "android", "bbbb2222", now=kst(11, 16, 10))

        recent = get_link_clicks(self.db, days=7, now=kst(11, 16, 12))["recent"]
        self.assertEqual([r["source"] for r in recent], ["instagram", "ig-dm"])
        self.assertEqual(recent[0]["platform"], "android")

    def test_rejects_invalid_values(self):
        with self.assertRaises(InvalidLinkClick):
            record_click(self.db, "IG DM", "ios")
        with self.assertRaises(InvalidLinkClick):
            record_click(self.db, "ig-dm", "windows")
        with self.assertRaises(InvalidLinkClick):
            record_click(self.db, "ig-dm", "ios", "203.0.113.7")
        self.assertEqual(get_link_clicks(self.db, days=7)["sources"], [])

    def test_init_db_twice_keeps_rows(self):
        record_click(self.db, "ig-dm", "ios", "aaaa1111", now=kst(11, 16, 10))
        init_db(self.db)
        self.assertEqual(
            get_link_clicks(self.db, days=1, now=kst(11, 16, 12))["sources"][0]["clicks"], 1
        )


if __name__ == "__main__":
    unittest.main()
