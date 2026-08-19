from __future__ import annotations

import os
import secrets
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from analytics import queries
from analytics.db import init_db, service_day
from analytics.ingest import ingest_batch
from analytics.ratelimit import SlidingWindowLimiter
from analytics.rollup import run_rollup
from analytics.schema import MAX_EVENTS_PER_BATCH

router = APIRouter()

# 기기 하나가 정상적으로 만들 수 있는 배치는 분당 몇 건 수준이다.
_device_limiter = SlidingWindowLimiter(limit=30, window_seconds=60.0)
_ip_limiter = SlidingWindowLimiter(limit=300, window_seconds=60.0)


def _db_path() -> str:
    from settings import AppSettings

    return AppSettings.from_env().analytics_db_path


def require_analytics_admin(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    """대시보드 API 보호.

    전용 키(ANALYTICS_ADMIN_API_KEY)가 없으면 기존 푸시 관리 키로 대체한다.
    둘 다 비어 있으면 잠긴 상태로 둔다(무조건 401).
    """
    expected = os.getenv("ANALYTICS_ADMIN_API_KEY", "") or os.getenv("PUSH_ADMIN_API_KEY", "")
    if not expected or x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


class TelemetryEventIn(BaseModel):
    """이벤트 한 건.

    길이 제한을 느슨하게 둔 것은 의도적이다. 여기서 엄격하게 막으면 이벤트
    하나가 잘못됐을 때 배치 전체가 422 로 튕기고, 앱은 같은 배치를 영원히
    재전송한다. 실제 판별은 ingest 에서 건별로 하고 잘못된 것만 버린다.
    """

    event_id: str = Field(..., max_length=200, examples=["8f0b...-uuid"])
    name: str = Field(..., max_length=200, examples=["verse_save"])
    ts: Optional[str] = Field(default=None, description="기기 시각(ISO). 참고용")
    session_id: Optional[str] = Field(default=None, max_length=200)
    # 값은 서버에서 화이트리스트로 다시 거른다. 개인 내용은 애초에 키가 없다.
    params: Optional[dict[str, Any]] = None


class TelemetryBatchIn(BaseModel):
    anon_id: str = Field(..., max_length=64, description="앱의 withgod.deviceId")
    platform: Optional[str] = Field(default=None, max_length=32)
    app_version: Optional[str] = Field(default=None, max_length=32)
    os_version: Optional[str] = Field(default=None, max_length=32)
    tz: Optional[str] = Field(default=None, max_length=64)
    events: List[TelemetryEventIn] = Field(default_factory=list, max_length=MAX_EVENTS_PER_BATCH)


@router.post("/telemetry/events", status_code=202, tags=["analytics"])
def collect_events(payload: TelemetryBatchIn, request: Request) -> dict[str, Any]:
    """앱이 모아 보낸 이벤트 배치를 저장한다(인증 없음, 레이트리밋으로 보호)."""
    client_ip = request.client.host if request.client else "unknown"
    if not _ip_limiter.allow(client_ip) or not _device_limiter.allow(payload.anon_id):
        raise HTTPException(status_code=429, detail="Too many requests")

    result = ingest_batch(_db_path(), payload.model_dump())
    return result


@router.get("/admin/analytics/overview", dependencies=[Depends(require_analytics_admin)], tags=["analytics"])
def overview() -> dict[str, Any]:
    return queries.get_overview(_db_path())


@router.get("/admin/analytics/timeseries", dependencies=[Depends(require_analytics_admin)], tags=["analytics"])
def timeseries(days: int = Query(default=30, ge=1, le=180)) -> dict[str, Any]:
    return {"days": days, "series": queries.get_timeseries(_db_path(), days=days)}


@router.get("/admin/analytics/retention", dependencies=[Depends(require_analytics_admin)], tags=["analytics"])
def retention(cohorts: int = Query(default=21, ge=1, le=90)) -> dict[str, Any]:
    return queries.get_retention(_db_path(), cohorts=cohorts)


@router.get("/admin/analytics/events", dependencies=[Depends(require_analytics_admin)], tags=["analytics"])
def event_counts(days: int = Query(default=7, ge=1, le=90)) -> dict[str, Any]:
    return {"days": days, "events": queries.get_event_counts(_db_path(), days=days)}


@router.get("/admin/analytics/breakdown", dependencies=[Depends(require_analytics_admin)], tags=["analytics"])
def breakdown(days: int = Query(default=30, ge=1, le=180)) -> dict[str, Any]:
    return queries.get_breakdown(_db_path(), days=days)


@router.get("/admin/analytics/languages", dependencies=[Depends(require_analytics_admin)], tags=["analytics"])
def languages_by_country(days: int = Query(default=30, ge=1, le=180)) -> dict[str, Any]:
    """국가별 **앱 언어 설정** 분포.

    지표(events)에는 언어가 없다 — 개인정보 최소 수집 원칙으로 tz·플랫폼·버전만
    받기 때문이다. 대신 푸시 등록 기기에는 발송 언어가 저장돼 있어 그걸 집계한다.

    **국가 분포 카드와 같은 모집단(최근 N일 활동 사용자)으로 맞춘다.** 기기 목록은
    누적이라 그대로 세면 앱을 몇 달째 안 여는 사람까지 들어가 옆 카드와 숫자가
    어긋난다. device_store.device_id 와 지표의 anon_id 는 앱에서 같은
    getOrCreateDeviceId() 값을 쓰므로 조인할 수 있다.

    (device_store 의 updated_at 은 **푸시를 보낼 때마다** 갱신되므로 활동 여부의
    근거가 못 된다 — 그래서 daily_active 로 거른다.)

    여전히 **알림을 켠 사용자만** 집계된다는 한계는 남는다.
    """
    from analytics.tz_country import country_for_tz

    try:
        # 지연 임포트 — analytics 가 app 을 임포트하면 순환이 된다.
        from app import _notification_manager

        devices = _notification_manager().list_devices()
    except Exception:
        return {"countries": [], "source": "push_devices", "note": "기기 목록을 읽을 수 없음"}

    active = queries.active_anon_ids(_db_path(), days=days)

    agg: dict[str, dict[str, int]] = {}
    skipped = 0
    for d in devices:
        if d.get("device_id") not in active:
            skipped += 1
            continue
        country = country_for_tz(d.get("timezone")) or "unknown"
        lang = (d.get("language") or "unknown").lower()
        agg.setdefault(country, {})
        agg[country][lang] = agg[country].get(lang, 0) + 1
    countries = [
        {
            "key": c,
            "devices": sum(langs.values()),
            "languages": [
                {"key": l, "devices": n}
                for l, n in sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
        }
        for c, langs in sorted(agg.items(), key=lambda kv: -sum(kv[1].values()))
    ]
    return {
        "countries": countries,
        "source": "push_devices",
        "days": days,
        # 최근 N일에 앱을 열지 않아 제외된 등록 기기 수(누적과의 차이).
        "inactive_devices": skipped,
    }


@router.post("/admin/analytics/rollup", dependencies=[Depends(require_analytics_admin)], tags=["analytics"])
def trigger_rollup() -> dict[str, Any]:
    """수동 롤업. 스케줄러가 도는 중에도 안전하다(같은 값을 다시 굳힐 뿐)."""
    from settings import AppSettings

    settings = AppSettings.from_env()
    return run_rollup(
        settings.analytics_db_path,
        raw_retention_days=settings.analytics_raw_retention_days,
    )


def ensure_schema(db_path: str) -> None:
    init_db(db_path)


__all__ = ["router", "ensure_schema", "service_day"]
