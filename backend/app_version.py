"""앱 버전 게이팅 — 클라이언트가 최신/최소지원 버전을 물어보는 엔드포인트.

새 버전을 스토어에 올린 뒤 data/app_version.json 의 latest 를 올리면, 구버전
앱에서 업데이트 안내 팝업이 뜬다(앱 재배포 불필요). 파일이 없으면 DEFAULTS 를
쓴다. 요청마다 파일을 읽으므로 서버 재시작 없이 값 변경이 반영된다.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "data" / "app_version.json"

# 파일이 없을 때의 기본값. 릴리스마다 이 값을 최신으로 유지한다.
DEFAULTS: dict[str, str] = {
    # 스토어에 올라간 최신 버전. 이보다 낮으면 '선택 업데이트' 안내.
    "latest": "1.2.4",
    # 이보다 낮으면 '강제 업데이트'(계속 쓰려면 업데이트 필수).
    "min_supported": "1.0.0",
    "ios_url": "https://apps.apple.com/app/id6757704775",
    "android_url": "https://play.google.com/store/apps/details?id=kr.co.mincha.withgod",
}


@router.get("/app-version", tags=["app"])
def get_app_version() -> dict[str, str]:
    config = dict(DEFAULTS)
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            # 알려진 키만 덮어써서 예상치 못한 값이 섞이지 않게 한다.
            for key in DEFAULTS:
                value = data.get(key)
                if isinstance(value, str) and value:
                    config[key] = value
    except Exception:
        # 설정 파일이 깨졌어도 기본값으로 응답한다(앱을 막지 않는다).
        pass
    return config
