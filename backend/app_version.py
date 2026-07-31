"""앱 버전 게이팅 — 클라이언트가 최신/최소지원 버전을 물어보는 엔드포인트.

latest(최신 버전)는 **App Store 라이브 버전을 자동 추적**한다: iTunes Lookup 을
TTL 캐시로 조회해 스토어 버전이 저장값보다 높으면 자동으로 올린다(수동 갱신 누락
방지 — 1.3.0/1.4.0 릴리즈 때 latest 가 1.2.4 로 방치됐던 사고의 재발 방지).
자동 반영은 '올리기'만 한다 — 스토어 심사 중(미공개) 버전으로 안내하는 일이 없고,
어드민이 수동으로 더 높게 올리는 것도 그대로 존중된다.

min_supported(강제 업데이트)는 계속 어드민 수동 전용. 값은 data/app_version.json
에 저장하며 요청마다 읽으므로 서버 재시작 없이 반영된다. 파일이 없으면 DEFAULTS.

이 파일은 gitignore 로 두어(서버가 관리) git pull 과 충돌하지 않게 한다. 수동 변경은
어드민 대시보드(POST /admin/app-version) 로 한다.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import re
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from analytics.routes import require_analytics_admin

logger = logging.getLogger(__name__)

router = APIRouter()

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "data" / "app_version.json"

# App Store 라이브 버전 자동 추적 (iTunes Lookup — 공개 API, 인증 불필요).
# Play 는 공개 조회 API 가 없어 iOS 를 기준으로 삼는다(두 스토어 동시 릴리즈 관례).
APPSTORE_ID = "6757704775"
STORE_LOOKUP_URL = (
    f"https://itunes.apple.com/lookup?id={APPSTORE_ID}&country=kr"
)
# 캐시 TTL(기본 6시간) — 0 이면 자동 추적 비활성(수동 전용으로 롤백).
STORE_TTL_SECONDS = int(os.getenv("APP_VERSION_STORE_TTL", "21600"))
STORE_TIMEOUT_SECONDS = 5

# 파일이 없을 때의 안전한 기본값. min_supported=1.0.0 이라 강제 업데이트는 걸리지
# 않고, latest 가 낮으면 팝업이 안 뜬다(오작동보다 조용한 실패가 안전).
DEFAULTS: dict[str, str] = {
    "latest": "1.2.4",
    "min_supported": "1.0.0",
    "ios_url": "https://apps.apple.com/app/id6757704775",
    "android_url": "https://play.google.com/store/apps/details?id=kr.co.mincha.withgod",
}

# 1.2.4 / 1.10.0 같은 점 구분 정수. 사람이 입력하므로 형식을 검증한다.
VERSION_RE = re.compile(r"^\d+(\.\d+){1,3}$")


def _read_config() -> dict[str, str]:
    config = dict(DEFAULTS)
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for key in DEFAULTS:
                value = data.get(key)
                if isinstance(value, str) and value:
                    config[key] = value
    except Exception:
        pass
    return config


def _write_config(config: dict[str, str]) -> None:
    """임시 파일에 쓴 뒤 원자적으로 교체한다.

    제자리 쓰기는 중간에 프로세스가 죽으면(워커 타임아웃 SIGKILL·배포 재시작)
    잘린 JSON 을 남기고, _read_config 가 그걸 조용히 DEFAULTS 로 후퇴시킨다 —
    min_supported 가 1.0.0 으로 돌아가 강제 업데이트 게이트가 풀린다.
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 워커/스레드가 동시에 써도 임시 파일이 겹치지 않게 한다.
    temp_path = CONFIG_PATH.with_name(
        f".{CONFIG_PATH.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        temp_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temp_path, CONFIG_PATH)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


@contextmanager
def _config_write_lock():
    """설정 파일의 read-modify-write 를 직렬화한다(gunicorn 워커 간 + 스레드 간).

    자동 반영(GET)과 어드민 저장(POST) 이 둘 다 '전체 읽기 → 수정 → 전체 쓰기'라,
    락이 없으면 낡은 스냅샷이 뒤늦게 덮어써서 방금 저장한 min_supported 가 조용히
    롤백된다. 설정 파일은 os.replace 로 inode 가 바뀌므로 락은 별도 파일에 건다.
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = CONFIG_PATH.with_name(CONFIG_PATH.name + ".lock")
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _version_key(version: str) -> tuple[int, ...]:
    """'1.10.0' > '1.2.4' 처럼 숫자 단위 비교용 키. 형식은 VERSION_RE 로 선검증."""
    return tuple(int(part) for part in version.split("."))


def _is_newer(candidate: str, baseline: str) -> bool:
    try:
        return _version_key(candidate) > _version_key(baseline)
    except (ValueError, AttributeError):
        return False


def _fetch_store_version() -> str | None:
    """iTunes Lookup 으로 App Store 라이브 버전을 조회한다. 실패 시 None(fail-open)."""
    try:
        request = urllib.request.Request(
            STORE_LOOKUP_URL, headers={"User-Agent": "withgod-backend/app-version"}
        )
        with urllib.request.urlopen(request, timeout=STORE_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results") or []
        version = results[0].get("version") if results else None
        if isinstance(version, str) and VERSION_RE.match(version):
            return version
    except Exception as exc:  # 스토어 조회 실패가 앱 버전 응답을 막으면 안 된다
        logger.warning("app-version: App Store lookup failed: %s", exc)
    return None


# 스토어 버전 캐시 — 요청 경로를 블로킹하지 않도록 백그라운드 스레드로 갱신한다.
_store_cache: dict[str, object] = {"version": None, "fetched_at": 0.0}
_store_lock = threading.Lock()
_refresh_in_flight = False


def _refresh_store_cache() -> None:
    global _refresh_in_flight
    try:
        version = _fetch_store_version()
        with _store_lock:
            _store_cache["fetched_at"] = time.time()
            if version:
                _store_cache["version"] = version
    finally:
        with _store_lock:
            _refresh_in_flight = False


def _maybe_refresh_store_cache_async() -> None:
    """TTL 이 지났으면 백그라운드 갱신을 시작한다(요청은 기다리지 않는다)."""
    global _refresh_in_flight
    if STORE_TTL_SECONDS <= 0:
        return
    with _store_lock:
        fresh = time.time() - float(_store_cache["fetched_at"]) < STORE_TTL_SECONDS
        if fresh or _refresh_in_flight:
            return
        _refresh_in_flight = True
    try:
        threading.Thread(target=_refresh_store_cache, daemon=True).start()
    except RuntimeError as exc:
        # 스레드 생성 실패(1GB 인스턴스의 메모리 압박 등). 플래그를 되돌리지 않으면
        # 이 워커의 자동 추적이 재시작 때까지 조용히 죽는다 — 이 모듈이 막으려던
        # 'latest 방치'가 그대로 재발한다. 예외는 삼켜 GET 은 저장값을 계속 서빙한다.
        with _store_lock:
            _refresh_in_flight = False
        logger.warning("app-version: store refresh thread start failed: %s", exc)


def _apply_store_latest(config: dict[str, str]) -> dict[str, str]:
    """스토어 라이브 버전이 저장된 latest 보다 높으면 자동으로 올리고 영속화한다.

    '올리기'만 한다: 스토어보다 높게 잡아둔 수동 값은 유지되고, 심사 중(스토어
    미공개) 버전으로 먼저 안내하는 일도 구조적으로 없다.
    """
    with _store_lock:
        store_version = _store_cache["version"]
    if not isinstance(store_version, str) or not _is_newer(store_version, config["latest"]):
        return config
    try:
        with _config_write_lock():
            # 락 안에서 다시 읽는다 — 락 밖에서 뜬 스냅샷을 그대로 쓰면 그 사이
            # 어드민이 저장한 min_supported 를 덮어써 되돌리게 된다.
            config = _read_config()
            if _is_newer(store_version, config["latest"]):
                config["latest"] = store_version
                _write_config(config)
                logger.info(
                    "app-version: latest auto-bumped to %s (App Store live)",
                    store_version,
                )
    except Exception as exc:
        # 영속화 실패가 응답을 막지 않는다 — 이번 응답만 저장값으로 나간다.
        logger.warning("app-version: failed to persist auto-bump: %s", exc)
    return config


@router.get("/app-version", tags=["app"])
def get_app_version() -> dict[str, str]:
    _maybe_refresh_store_cache_async()
    config = _apply_store_latest(_read_config())
    # 대시보드 표시용 — 앱은 latest/min_supported 만 읽으므로 추가 키는 무해하다.
    with _store_lock:
        store_version = _store_cache["version"]
    if isinstance(store_version, str):
        config["store_latest"] = store_version
    return config


class AppVersionUpdate(BaseModel):
    latest: str = Field(..., examples=["1.3.0"])
    min_supported: str = Field(..., examples=["1.0.0"])


@router.post(
    "/admin/app-version",
    dependencies=[Depends(require_analytics_admin)],
    tags=["app"],
)
def update_app_version(payload: AppVersionUpdate) -> dict[str, str]:
    """어드민 대시보드에서 최신/최소지원 버전을 갱신한다(스토어 URL 은 유지)."""
    if not VERSION_RE.match(payload.latest):
        raise HTTPException(status_code=422, detail="latest 형식이 올바르지 않습니다 (예: 1.3.0)")
    if not VERSION_RE.match(payload.min_supported):
        raise HTTPException(status_code=422, detail="min_supported 형식이 올바르지 않습니다 (예: 1.0.0)")

    with _config_write_lock():
        config = _read_config()
        config["latest"] = payload.latest
        config["min_supported"] = payload.min_supported
        _write_config(config)
    return config
