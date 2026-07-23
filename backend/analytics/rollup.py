from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from analytics.db import service_day, session, utc_now

# 리텐션으로 볼 경과일. 앱 특성상 1일차/7일차가 가장 중요하다.
RETENTION_DAYS = (1, 3, 7, 14, 30)

# 롤업할 때 거슬러 올라가는 일수. 배치 전송이라 어제 이벤트가 오늘 새벽에
# 도착할 수 있고, WAU/MAU 도 뒤늦게 바뀌므로 넉넉히 다시 계산한다.
DEFAULT_LOOKBACK_DAYS = 35


def _shift(day: str, delta: int) -> str:
    return (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")


def run_rollup(
    db_path: str,
    now: datetime | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    raw_retention_days: int = 90,
) -> dict[str, Any]:
    """일별 지표·리텐션을 다시 계산하고 오래된 원시 이벤트를 정리한다.

    daily_active / device_profile 은 수집 시점에 이미 채워져 있으므로 여기서는
    파생 지표만 굳힌다. 그래서 원시 이벤트를 지워도 지표는 남는다.
    """
    now = now or utc_now()
    today = service_day(now)

    with session(db_path) as conn:
        days = [_shift(today, -offset) for offset in range(lookback_days)]
        for day in days:
            _rollup_day(conn, day, now)

        cohorts = _recompute_retention(conn, today)
        pruned = _prune_raw_events(conn, today, raw_retention_days)
        conn.commit()

    return {
        "computed_days": len(days),
        "cohorts": cohorts,
        "pruned_events": pruned,
        "today": today,
    }


def _rollup_day(conn: sqlite3.Connection, day: str, now: datetime) -> None:
    dau = conn.execute(
        "SELECT COUNT(*) FROM daily_active WHERE day = ?", (day,)
    ).fetchone()[0]
    new_users = conn.execute(
        "SELECT COUNT(*) FROM device_profile WHERE first_day = ?", (day,)
    ).fetchone()[0]
    wau = conn.execute(
        "SELECT COUNT(DISTINCT anon_id) FROM daily_active WHERE day BETWEEN ? AND ?",
        (_shift(day, -6), day),
    ).fetchone()[0]
    mau = conn.execute(
        "SELECT COUNT(DISTINCT anon_id) FROM daily_active WHERE day BETWEEN ? AND ?",
        (_shift(day, -29), day),
    ).fetchone()[0]

    row = conn.execute(
        """
        SELECT COUNT(*) AS events, COUNT(DISTINCT session_id) AS sessions
        FROM events WHERE day = ?
        """,
        (day,),
    ).fetchone()
    events, sessions = row["events"], row["sessions"]

    # 보관기간이 지나 원시 이벤트가 지워진 날은 예전에 굳혀둔 값을 지킨다.
    if events == 0:
        previous = conn.execute(
            "SELECT events, sessions FROM daily_metrics WHERE day = ?", (day,)
        ).fetchone()
        if previous:
            events, sessions = previous["events"], previous["sessions"]

    conn.execute(
        """
        INSERT INTO daily_metrics (
            day, dau, new_users, returning_users, wau, mau, sessions, events, computed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(day) DO UPDATE SET
            dau = excluded.dau,
            new_users = excluded.new_users,
            returning_users = excluded.returning_users,
            wau = excluded.wau,
            mau = excluded.mau,
            sessions = excluded.sessions,
            events = excluded.events,
            computed_at = excluded.computed_at
        """,
        (
            day,
            dau,
            new_users,
            max(0, dau - new_users),
            wau,
            mau,
            sessions,
            events,
            now.isoformat(),
        ),
    )


def _recompute_retention(conn: sqlite3.Connection, today: str) -> int:
    """최근 코호트의 N일차 유지율을 다시 계산한다.

    가장 긴 경과일(30일)보다 오래된 코호트는 더 이상 값이 바뀌지 않으므로
    건드리지 않는다.
    """
    oldest = _shift(today, -(max(RETENTION_DAYS) + 1))
    cohorts = [
        row["first_day"]
        for row in conn.execute(
            "SELECT DISTINCT first_day FROM device_profile WHERE first_day >= ?",
            (oldest,),
        )
    ]

    for cohort_day in cohorts:
        size = conn.execute(
            "SELECT COUNT(*) FROM device_profile WHERE first_day = ?", (cohort_day,)
        ).fetchone()[0]
        if size == 0:
            continue

        for day_n in RETENTION_DAYS:
            target_day = _shift(cohort_day, day_n)
            if target_day > today:
                # 아직 오지 않은 날짜는 0%로 굳히면 안 된다.
                continue
            retained = conn.execute(
                """
                SELECT COUNT(*)
                FROM device_profile p
                JOIN daily_active a ON a.anon_id = p.anon_id AND a.day = ?
                WHERE p.first_day = ?
                """,
                (target_day, cohort_day),
            ).fetchone()[0]

            conn.execute(
                """
                INSERT INTO retention_cohort (cohort_day, day_n, cohort_size, retained)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cohort_day, day_n) DO UPDATE SET
                    cohort_size = excluded.cohort_size,
                    retained = excluded.retained
                """,
                (cohort_day, day_n, size, retained),
            )

    return len(cohorts)


def _prune_raw_events(conn: sqlite3.Connection, today: str, retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    cutoff = _shift(today, -retention_days)
    cursor = conn.execute("DELETE FROM events WHERE day < ?", (cutoff,))
    return cursor.rowcount if cursor.rowcount > 0 else 0


def claim_job(db_path: str, job_name: str, day: str) -> bool:
    """워커가 여러 개일 때 하루 한 번만 실행되도록 잡을 선점한다."""
    with session(db_path) as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO job_lock (job_name, day, ran_at) VALUES (?, ?, ?)",
            (job_name, day, utc_now().isoformat()),
        )
        conn.commit()
        return cursor.rowcount > 0
