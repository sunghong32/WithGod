from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from analytics.db import service_day, session, utc_now
from analytics.rollup import RETENTION_DAYS
from analytics.tz_country import country_for_tz


def _shift(day: str, delta: int) -> str:
    return (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")


def _active_between(conn: sqlite3.Connection, start: str, end: str) -> int:
    return conn.execute(
        "SELECT COUNT(DISTINCT anon_id) FROM daily_active WHERE day BETWEEN ? AND ?",
        (start, end),
    ).fetchone()[0]


def get_overview(db_path: str, now: datetime | None = None) -> dict[str, Any]:
    """대시보드 상단 카드.

    오늘 값은 롤업 전이라 daily_metrics 를 믿을 수 없으므로 daily_active 에서
    직접 센다(그래서 실시간이다).
    """
    now = now or utc_now()
    today = service_day(now)
    yesterday = _shift(today, -1)

    with session(db_path) as conn:
        dau = _active_between(conn, today, today)
        dau_yesterday = _active_between(conn, yesterday, yesterday)
        wau = _active_between(conn, _shift(today, -6), today)
        mau = _active_between(conn, _shift(today, -29), today)

        new_today = conn.execute(
            "SELECT COUNT(*) FROM device_profile WHERE first_day = ?", (today,)
        ).fetchone()[0]
        new_yesterday = conn.execute(
            "SELECT COUNT(*) FROM device_profile WHERE first_day = ?", (yesterday,)
        ).fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM device_profile").fetchone()[0]
        events_today = conn.execute(
            "SELECT COUNT(*) FROM events WHERE day = ?", (today,)
        ).fetchone()[0]
        sessions_today = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM events WHERE day = ? AND session_id <> ''",
            (today,),
        ).fetchone()[0]
        last_event_at = conn.execute(
            "SELECT MAX(ts_server) FROM events"
        ).fetchone()[0]

    return {
        "day": today,
        "dau": dau,
        "dau_prev": dau_yesterday,
        "wau": wau,
        "mau": mau,
        "new_users": new_today,
        "new_users_prev": new_yesterday,
        "returning_users": max(0, dau - new_today),
        "total_users": total_users,
        "sessions": sessions_today,
        "events": events_today,
        # 고착도: 월간 사용자가 한 달에 며칠이나 들어오는지. 20%면 준수한 편.
        "stickiness": round(dau / mau, 4) if mau else 0.0,
        "last_event_at": last_event_at,
    }


def get_timeseries(db_path: str, days: int = 30, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or utc_now()
    today = service_day(now)
    start = _shift(today, -(days - 1))

    with session(db_path) as conn:
        rolled = {
            row["day"]: dict(row)
            for row in conn.execute(
                """
                SELECT day, dau, new_users, returning_users, wau, mau, sessions, events
                FROM daily_metrics WHERE day BETWEEN ? AND ? ORDER BY day
                """,
                (start, today),
            )
        }
        # 롤업이 아직 안 돈 날(주로 오늘)은 즉석에서 채운다.
        series: list[dict[str, Any]] = []
        for offset in range(days):
            day = _shift(start, offset)
            if day in rolled:
                series.append(rolled[day])
                continue
            dau = _active_between(conn, day, day)
            new_users = conn.execute(
                "SELECT COUNT(*) FROM device_profile WHERE first_day = ?", (day,)
            ).fetchone()[0]
            series.append(
                {
                    "day": day,
                    "dau": dau,
                    "new_users": new_users,
                    "returning_users": max(0, dau - new_users),
                    "wau": _active_between(conn, _shift(day, -6), day),
                    "mau": _active_between(conn, _shift(day, -29), day),
                    "sessions": 0,
                    "events": 0,
                }
            )
    return series


def get_retention(db_path: str, cohorts: int = 21, now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    today = service_day(now)
    start = _shift(today, -(cohorts - 1))

    with session(db_path) as conn:
        sizes = {
            row["first_day"]: row["size"]
            for row in conn.execute(
                """
                SELECT first_day, COUNT(*) AS size FROM device_profile
                WHERE first_day BETWEEN ? AND ? GROUP BY first_day
                """,
                (start, today),
            )
        }
        stored = {
            (row["cohort_day"], row["day_n"]): row
            for row in conn.execute(
                "SELECT * FROM retention_cohort WHERE cohort_day BETWEEN ? AND ?",
                (start, today),
            )
        }

    rows: list[dict[str, Any]] = []
    for offset in range(cohorts):
        cohort_day = _shift(start, offset)
        size = sizes.get(cohort_day, 0)
        cells: list[dict[str, Any]] = []
        for day_n in RETENTION_DAYS:
            target = _shift(cohort_day, day_n)
            if target > today or size == 0:
                # 아직 도래하지 않은 칸은 0%가 아니라 '없음'이다.
                cells.append({"day_n": day_n, "rate": None, "retained": None})
                continue
            record = stored.get((cohort_day, day_n))
            retained = record["retained"] if record else 0
            cells.append(
                {"day_n": day_n, "rate": round(retained / size, 4), "retained": retained}
            )
        rows.append({"cohort_day": cohort_day, "size": size, "cells": cells})

    return {"day_ns": list(RETENTION_DAYS), "rows": rows}


def get_event_counts(db_path: str, days: int = 7, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or utc_now()
    today = service_day(now)
    start = _shift(today, -(days - 1))

    with session(db_path) as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT name, COUNT(*) AS total, COUNT(DISTINCT anon_id) AS users
                FROM events WHERE day BETWEEN ? AND ?
                GROUP BY name ORDER BY total DESC
                """,
                (start, today),
            )
        ]


def get_breakdown(db_path: str, days: int = 30, now: datetime | None = None) -> dict[str, Any]:
    """최근 활동한 사용자의 플랫폼·앱 버전·국가 분포."""
    now = now or utc_now()
    today = service_day(now)
    start = _shift(today, -(days - 1))

    with session(db_path) as conn:
        platforms = [
            dict(row)
            for row in conn.execute(
                """
                SELECT COALESCE(NULLIF(p.platform, ''), 'unknown') AS key,
                       COUNT(DISTINCT p.anon_id) AS users
                FROM device_profile p
                JOIN daily_active a ON a.anon_id = p.anon_id
                WHERE a.day BETWEEN ? AND ?
                GROUP BY key ORDER BY users DESC
                """,
                (start, today),
            )
        ]
        versions = [
            dict(row)
            for row in conn.execute(
                """
                SELECT COALESCE(NULLIF(p.last_app_version, ''), 'unknown') AS key,
                       COUNT(DISTINCT p.anon_id) AS users
                FROM device_profile p
                JOIN daily_active a ON a.anon_id = p.anon_id
                WHERE a.day BETWEEN ? AND ?
                GROUP BY key ORDER BY users DESC LIMIT 12
                """,
                (start, today),
            )
        ]
        # 국가는 기기 타임존으로 추정한다. 서로 다른 tz 가 같은 국가로
        # 합쳐질 수 있어(예: America/*→US) 파이썬에서 다시 묶는다.
        country_users: dict[str, int] = {}
        for row in conn.execute(
            """
            SELECT p.last_tz AS tz, COUNT(DISTINCT p.anon_id) AS users
            FROM device_profile p
            JOIN daily_active a ON a.anon_id = p.anon_id
            WHERE a.day BETWEEN ? AND ?
            GROUP BY p.last_tz
            """,
            (start, today),
        ):
            country = country_for_tz(row["tz"]) or "unknown"
            country_users[country] = country_users.get(country, 0) + row["users"]
        countries = [
            {"key": country, "users": users}
            for country, users in sorted(
                country_users.items(), key=lambda item: (-item[1], item[0])
            )
        ]
    return {"platforms": platforms, "app_versions": versions, "countries": countries}
