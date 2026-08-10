from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from analytics.db import service_day, session, utc_now
from analytics.schema import (
    MAX_EVENTS_PER_BATCH,
    MAX_ID_LEN,
    clip,
    is_valid_event_name,
    sanitize_params,
)


def ingest_batch(
    db_path: str,
    payload: dict[str, Any],
    received_at: datetime | None = None,
) -> dict[str, int]:
    """앱이 보낸 이벤트 배치를 저장한다.

    - 집계 기준 시각은 항상 서버 수신 시각이다. 기기 시계는 참고용으로만 남긴다.
    - event_id 가 PK 라 재전송이 그대로 들어와도 중복 집계되지 않는다.
    - device_profile / daily_active 를 수집 시점에 같이 갱신해, 롤업 전이라도
      '오늘' 수치를 실시간으로 볼 수 있게 한다.
    """
    received_at = received_at or utc_now()
    ts_server = received_at.isoformat()
    day = service_day(received_at)

    anon_id = clip(payload.get("anon_id"), MAX_ID_LEN)
    if not anon_id:
        return {"accepted": 0, "dropped": 0, "duplicates": 0}

    platform = clip(payload.get("platform"))
    app_version = clip(payload.get("app_version"))
    os_version = clip(payload.get("os_version"))
    tz = clip(payload.get("tz"), 64)

    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raw_events = []
    over_limit = max(0, len(raw_events) - MAX_EVENTS_PER_BATCH)
    raw_events = raw_events[:MAX_EVENTS_PER_BATCH]

    accepted = 0
    duplicates = 0
    dropped = over_limit

    with session(db_path) as conn:
        for raw in raw_events:
            if not isinstance(raw, dict):
                dropped += 1
                continue

            name = raw.get("name")
            if not is_valid_event_name(name):
                dropped += 1
                continue

            event_id = clip(raw.get("event_id"), MAX_ID_LEN)
            if not event_id:
                dropped += 1
                continue

            params = sanitize_params(name, raw.get("params"))
            session_id = clip(raw.get("session_id"), MAX_ID_LEN)
            ts_client = clip(raw.get("ts"), 40)

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO events (
                    event_id, anon_id, session_id, name, day,
                    ts_client, ts_server, platform, app_version, os_version,
                    tz, params_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    anon_id,
                    session_id,
                    name,
                    day,
                    ts_client,
                    ts_server,
                    platform,
                    app_version,
                    os_version,
                    tz,
                    json.dumps(params, ensure_ascii=False) if params else None,
                ),
            )
            if cursor.rowcount == 0:
                duplicates += 1
            else:
                accepted += 1

        if accepted or duplicates:
            _touch_device(conn, anon_id, day, platform, app_version, os_version, tz)
            conn.execute(
                "INSERT OR IGNORE INTO daily_active (day, anon_id) VALUES (?, ?)",
                (day, anon_id),
            )
        conn.commit()

    return {"accepted": accepted, "dropped": dropped, "duplicates": duplicates}


def _touch_device(
    conn: sqlite3.Connection,
    anon_id: str,
    day: str,
    platform: str,
    app_version: str,
    os_version: str,
    tz: str,
) -> None:
    # first_day 는 한 번 정해지면 절대 덮어쓰지 않는다 — 신규 사용자 판정과
    # 리텐션 코호트가 전부 이 값에 걸려 있다.
    conn.execute(
        """
        INSERT INTO device_profile (
            anon_id, first_day, last_day, platform,
            first_app_version, last_app_version, last_os_version, last_tz
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(anon_id) DO UPDATE SET
            last_day = MAX(device_profile.last_day, excluded.last_day),
            platform = COALESCE(NULLIF(excluded.platform, ''), device_profile.platform),
            last_app_version = COALESCE(
                NULLIF(excluded.last_app_version, ''), device_profile.last_app_version
            ),
            last_os_version = COALESCE(
                NULLIF(excluded.last_os_version, ''), device_profile.last_os_version
            ),
            last_tz = COALESCE(NULLIF(excluded.last_tz, ''), device_profile.last_tz)
        """,
        (anon_id, day, day, platform, app_version, app_version, os_version, tz),
    )
