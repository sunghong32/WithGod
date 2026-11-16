"""웹 앱 받기 링크(/get) 클릭 기록·집계.

스토어 쪽 유입 집계(App Store 캠페인·Play UTM)는 하루 넘게 늦고, 숫자가 작으면
아예 보여 주지 않는다. DM 한 통에 붙인 링크를 눌렀는지 같은 작은 신호는 여기서 본다.

기록은 웹 서버(withgod-web)가 관리 키를 붙여 보낸다 — 브라우저가 직접 부르지 않으니
누구나 숫자를 부풀릴 수 있는 공개 수집 경로가 아니다. IP 는 받지 않는다. 웹이
IP·User-Agent·날짜를 해시한 하루짜리 방문자 값만 보내고, 같은 사람이 같은 날 여러 번
눌러도 방문자는 한 번으로 센다.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from analytics.db import service_day, session, utc_now

# 웹의 normalizeSource 와 같은 규칙. 스토어 파라미터에 그대로 실리는 값이다.
SOURCE_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
PLATFORMS = ("ios", "android", "other")
VISITOR_RE = re.compile(r"^[0-9a-f]{8,64}$")

RECENT_LIMIT = 20


class InvalidLinkClick(ValueError):
    pass


def record_click(
    db_path: str,
    source: str,
    platform: str,
    visitor: str | None = None,
    now: datetime | None = None,
) -> None:
    if not isinstance(source, str) or not SOURCE_RE.match(source):
        raise InvalidLinkClick("source")
    if platform not in PLATFORMS:
        raise InvalidLinkClick("platform")
    if visitor is not None and not VISITOR_RE.match(visitor):
        raise InvalidLinkClick("visitor")

    now = now or utc_now()
    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO link_click (ts_server, day, source, platform, visitor) "
            "VALUES (?, ?, ?, ?, ?)",
            (now.isoformat(), service_day(now), source, platform, visitor),
        )


def get_link_clicks(db_path: str, days: int, now: datetime | None = None) -> dict[str, Any]:
    """최근 N일(오늘 포함, KST) 출처별 클릭 수와 최근 클릭 목록."""
    now = now or utc_now()
    today = service_day(now)
    start_day = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days - 1)).strftime(
        "%Y-%m-%d"
    )

    with session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT source,
                   COUNT(*) AS clicks,
                   -- 방문자 해시는 하루마다 바뀐다. 해시가 없는 행(구버전 웹)은 클릭마다 한 명.
                   COUNT(DISTINCT day || ':' || COALESCE(visitor, 'row' || id)) AS visitors,
                   SUM(platform = 'ios') AS ios,
                   SUM(platform = 'android') AS android,
                   SUM(platform = 'other') AS other,
                   MAX(ts_server) AS last_at
            FROM link_click
            WHERE day BETWEEN ? AND ?
            GROUP BY source
            ORDER BY clicks DESC, source
            """,
            (start_day, today),
        ).fetchall()
        recent = conn.execute(
            """
            SELECT ts_server, source, platform
            FROM link_click
            WHERE day BETWEEN ? AND ?
            ORDER BY ts_server DESC, id DESC
            LIMIT ?
            """,
            (start_day, today, RECENT_LIMIT),
        ).fetchall()

    return {
        "days": days,
        "sources": [
            {
                "source": row["source"],
                "clicks": row["clicks"],
                "visitors": row["visitors"],
                "ios": row["ios"],
                "android": row["android"],
                "other": row["other"],
                "last_at": row["last_at"],
            }
            for row in rows
        ],
        "recent": [
            {"at": row["ts_server"], "source": row["source"], "platform": row["platform"]}
            for row in recent
        ],
    }
