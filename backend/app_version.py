"""앱 버전 게이팅 — 클라이언트가 최신/최소지원 버전을 물어보는 엔드포인트.

새 버전을 스토어에 올린 뒤 latest 를 올리면, 구버전 앱에서 업데이트 안내 팝업이
뜬다(앱 재배포 불필요). 값은 data/app_version.json 에 저장하며 요청마다 읽으므로
서버 재시작 없이 반영된다. 파일이 없으면 DEFAULTS 를 쓴다.

이 파일은 gitignore 로 두어(서버가 관리) git pull 과 충돌하지 않게 한다. 값 변경은
어드민 대시보드(POST /admin/app-version) 로 한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from analytics.routes import require_analytics_admin

router = APIRouter()

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "data" / "app_version.json"

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
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


@router.get("/app-version", tags=["app"])
def get_app_version() -> dict[str, str]:
    return _read_config()


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

    config = _read_config()
    config["latest"] = payload.latest
    config["min_supported"] = payload.min_supported
    _write_config(config)
    return config
