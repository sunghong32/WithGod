from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

# 지표의 "하루" 기준. 사용자별 로컬 날짜로 자르면 같은 사람이 이동만 해도
# 리텐션 코호트가 흔들리므로 서비스 타임존 하나로 고정한다.
SERVICE_TIMEZONE = "Asia/Seoul"


def connect(path: str) -> sqlite3.Connection:
    """분석 DB 커넥션.

    gunicorn 워커가 여러 개라 같은 파일에 동시 쓰기가 들어온다. WAL 이 아니면
    읽기 하나가 쓰기 전체를 막아 수집 API 가 밀린다.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    # 이벤트 한 건 유실보다 쓰기 지연이 더 아픈 데이터라 NORMAL 로 둔다.
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def session(path: str) -> Iterator[sqlite3.Connection]:
    """트랜잭션 + 커넥션 정리.

    `with sqlite3.connect(...)` 는 커밋만 하고 커넥션을 닫지 않는다. 수집
    엔드포인트는 요청마다 커넥션을 여니, 닫지 않으면 파일 핸들이 샌다.
    """
    conn = connect(path)
    try:
        with conn:  # 예외 시 롤백, 정상 종료 시 커밋
            yield conn
    finally:
        conn.close()


def init_db(path: str) -> None:
    with session(path) as conn:
        conn.executescript(
            """
            -- 원시 이벤트. 보관기간이 지나면 롤업 잡이 지운다.
            CREATE TABLE IF NOT EXISTS events (
                event_id    TEXT PRIMARY KEY,   -- 클라이언트가 만든 UUID = 재전송 멱등 키
                anon_id     TEXT NOT NULL,
                session_id  TEXT,
                name        TEXT NOT NULL,
                day         TEXT NOT NULL,      -- 서버 수신 시각의 KST 날짜
                ts_client   TEXT,               -- 기기 시계(조작·오차 가능, 참고용)
                ts_server   TEXT NOT NULL,      -- 수신 시각 UTC. 모든 집계의 기준
                platform    TEXT,
                app_version TEXT,
                os_version  TEXT,
                tz          TEXT,
                params_json TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_events_day ON events(day);
            CREATE INDEX IF NOT EXISTS ix_events_name_day ON events(name, day);
            CREATE INDEX IF NOT EXISTS ix_events_anon_day ON events(anon_id, day);

            -- 신규 사용자 판정의 유일한 근거. 원시 이벤트를 지워도 남긴다.
            CREATE TABLE IF NOT EXISTS device_profile (
                anon_id           TEXT PRIMARY KEY,
                first_day         TEXT NOT NULL,
                last_day          TEXT NOT NULL,
                platform          TEXT,
                first_app_version TEXT,
                last_app_version  TEXT,
                last_os_version   TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_device_first_day ON device_profile(first_day);

            -- 모든 활성 지표(DAU/WAU/MAU/리텐션)의 원천. 영구 보관.
            -- 행 크기가 작아 사용자 수 × 활동일수 만큼 쌓여도 부담이 없다.
            CREATE TABLE IF NOT EXISTS daily_active (
                day     TEXT NOT NULL,
                anon_id TEXT NOT NULL,
                PRIMARY KEY (day, anon_id)
            ) WITHOUT ROWID;
            CREATE INDEX IF NOT EXISTS ix_daily_active_anon ON daily_active(anon_id);

            -- 대시보드 응답 속도용 사전 계산치. 롤업 잡이 채운다.
            CREATE TABLE IF NOT EXISTS daily_metrics (
                day              TEXT PRIMARY KEY,
                dau              INTEGER NOT NULL DEFAULT 0,
                new_users        INTEGER NOT NULL DEFAULT 0,
                returning_users  INTEGER NOT NULL DEFAULT 0,
                wau              INTEGER NOT NULL DEFAULT 0,
                mau              INTEGER NOT NULL DEFAULT 0,
                sessions         INTEGER NOT NULL DEFAULT 0,
                events           INTEGER NOT NULL DEFAULT 0,
                computed_at      TEXT NOT NULL
            );

            -- 코호트 리텐션. 원시 이벤트를 지워도 유지되도록 미리 굳혀둔다.
            CREATE TABLE IF NOT EXISTS retention_cohort (
                cohort_day  TEXT NOT NULL,
                day_n       INTEGER NOT NULL,
                cohort_size INTEGER NOT NULL,
                retained    INTEGER NOT NULL,
                PRIMARY KEY (cohort_day, day_n)
            ) WITHOUT ROWID;

            -- 워커가 여러 개라 같은 잡이 중복 실행되는 것을 막는다.
            CREATE TABLE IF NOT EXISTS job_lock (
                job_name TEXT NOT NULL,
                day      TEXT NOT NULL,
                ran_at   TEXT NOT NULL,
                PRIMARY KEY (job_name, day)
            ) WITHOUT ROWID;

            -- 버전별 스토어 공개일(KST). 심사·테스트 기기를 가려내는 기준이다(review_device).
            -- source: seed = 지난 버전을 손으로 채운 값, auto = 기존 기기 2대 이상이
            -- 그 버전으로 올라온 날(ingest 가 기록).
            CREATE TABLE IF NOT EXISTS app_release (
                platform   TEXT NOT NULL,
                version    TEXT NOT NULL,
                public_day TEXT NOT NULL,
                source     TEXT NOT NULL,
                PRIMARY KEY (platform, version)
            ) WITHOUT ROWID;

            -- 기존 기기가 새 버전으로 올라온 기록. 공개일 자동 판정용.
            CREATE TABLE IF NOT EXISTS version_upgrade (
                platform TEXT NOT NULL,
                version  TEXT NOT NULL,
                anon_id  TEXT NOT NULL,
                day      TEXT NOT NULL,
                PRIMARY KEY (platform, version, anon_id)
            ) WITHOUT ROWID;
            """
        )
        _migrate_device_tz(conn)
        conn.executemany(
            "INSERT OR IGNORE INTO app_release (platform, version, public_day, source) "
            "VALUES (?, ?, ?, 'seed')",
            RELEASE_SEEDS,
        )
        conn.commit()
        _create_user_views(conn)


# 지표 수집(2026-07-24) 이전·직후 버전의 공개일. 기록이 없어 스토어 제출 기록과
# 실제 데이터(제출일에만 나타났다 사라진 기기 묶음)로 맞춘 값이다. 이후 버전은
# ingest 가 자동으로 채운다(app_release.source = 'auto').
# 안드로이드는 8/3 프로덕션 첫 출시 전까지 비공개 테스트뿐이었다.
RELEASE_SEEDS: tuple[tuple[str, str, str], ...] = (
    ("ios", "1.0.0", "2026-07-01"),
    ("ios", "1.1.0", "2026-07-01"),
    ("ios", "1.2.0", "2026-07-01"),
    ("ios", "1.2.4", "2026-07-25"),
    ("ios", "1.4.0", "2026-08-01"),
    ("ios", "1.4.1", "2026-08-04"),
    ("ios", "1.5.0", "2026-08-12"),
    ("ios", "1.6.0", "2026-11-10"),
    ("android", "1.2.1", "2026-08-03"),
    ("android", "1.2.2", "2026-08-03"),
    ("android", "1.2.3", "2026-08-03"),
    ("android", "1.2.4", "2026-08-03"),
    ("android", "1.3.0", "2026-08-03"),
    ("android", "1.4.0", "2026-08-03"),
    ("android", "1.4.1", "2026-08-04"),
    ("android", "1.5.0", "2026-08-11"),
    ("android", "1.6.0", "2026-11-10"),
)


def _create_user_views(conn: sqlite3.Connection) -> None:
    """심사·테스트 기기를 뺀 뷰. 사용자 수 지표는 전부 이 뷰로 센다.

    심사·테스트 기기 = 하루만 쓰고 사라졌고, 그날 쓰던 버전이 그 플랫폼에서
    아직 공개 전(공개 당일 포함)이었던 기기. 애플 심사·구글 출시 전 보고서
    (Test Lab) 기기가 새 버전을 낼 때마다 수십 대씩 '신규 사용자'로 잡혔다.
    두 번째 날 다시 오면 사람으로 본다(TestFlight·비공개 테스터).

    워커가 동시에 부팅하므로 DROP/CREATE 를 쓰기 잠금 하나로 묶는다.
    """
    conn.executescript(
        """
        BEGIN IMMEDIATE;
        DROP VIEW IF EXISTS user_events;
        DROP VIEW IF EXISTS user_profile;
        DROP VIEW IF EXISTS user_active;
        DROP VIEW IF EXISTS review_device;
        CREATE VIEW review_device AS
            SELECT p.anon_id, p.platform, p.first_day, p.first_app_version
            FROM device_profile p
            WHERE p.platform IN ('ios', 'android')
              AND COALESCE(p.first_app_version, '') <> ''
              AND p.last_day = p.first_day
              AND NOT EXISTS (
                  SELECT 1 FROM app_release r
                  WHERE r.platform = p.platform
                    AND r.version = p.first_app_version
                    AND r.public_day < p.first_day
              );
        CREATE VIEW user_active AS
            SELECT day, anon_id FROM daily_active
            WHERE anon_id NOT IN (SELECT anon_id FROM review_device);
        CREATE VIEW user_profile AS
            SELECT * FROM device_profile
            WHERE anon_id NOT IN (SELECT anon_id FROM review_device);
        CREATE VIEW user_events AS
            SELECT * FROM events
            WHERE anon_id NOT IN (SELECT anon_id FROM review_device);
        COMMIT;
        """
    )


def _migrate_device_tz(conn: sqlite3.Connection) -> None:
    """device_profile.last_tz 추가(국가 분포용).

    원시 이벤트는 보관기간이 지나면 지워지므로 tz 를 프로필에 굳혀 둬야
    오래된 사용자도 국가 집계에 남는다.

    워커 여러 개가 동시에 부팅하며 이 함수를 같이 실행한다. '컬럼 확인 후
    ALTER' 사이에 잠금이 없어 둘 다 ALTER 에 도달할 수 있으므로, 진 쪽의
    duplicate column 에러는 정상 경로로 취급한다(startup 에서 죽으면
    gunicorn 마스터 전체가 내려간다).
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(device_profile)")}
    if "last_tz" not in columns:
        try:
            conn.execute("ALTER TABLE device_profile ADD COLUMN last_tz TEXT")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise
    # 백필은 매 부팅 멱등 실행. ALTER 는 autocommit 이라 백필 커밋 전에
    # 프로세스가 죽을 수 있는데, '컬럼 존재'를 완료 마커로 쓰면 그 유실이
    # 영구가 된다. 비어 있는 행만 채우니 반복 실행해도 싸고 안전하다.
    conn.execute(
        """
        UPDATE device_profile SET last_tz = (
            SELECT e.tz FROM events e
            WHERE e.anon_id = device_profile.anon_id
              AND e.tz IS NOT NULL AND e.tz <> ''
            ORDER BY e.ts_server DESC LIMIT 1
        )
        WHERE last_tz IS NULL
          AND EXISTS (
            SELECT 1 FROM events e
            WHERE e.anon_id = device_profile.anon_id
              AND e.tz IS NOT NULL AND e.tz <> ''
          )
        """
    )


def utc_now() -> datetime:
    return datetime.now(dt_timezone.utc)


def service_day(moment: datetime | None = None) -> str:
    """UTC 시각 → 서비스 타임존(KST) 기준 날짜 문자열."""
    moment = moment or utc_now()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_timezone.utc)
    return moment.astimezone(ZoneInfo(SERVICE_TIMEZONE)).strftime("%Y-%m-%d")
