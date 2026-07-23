from __future__ import annotations

import re
from typing import Any

# 이벤트 이름 규칙. 화이트리스트에 없어도 이 형태면 받는다 — 앱이 새 이벤트를
# 붙였는데 백엔드 배포가 늦어서 조용히 유실되는 상황이 더 위험하다.
EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

# 파라미터는 반대로 엄격하게 잠근다. 여기가 개인정보가 새는 유일한 경로다.
# 사용자가 입력한 마음(mood) 원문처럼 내용이 담긴 값은 절대 키를 열지 않는다.
GLOBAL_ALLOWED_PARAMS: frozenset[str] = frozenset(
    {
        "screen_name",
        "source",
        "reference",
        "from",
        "length",
        "index",
        "count",
        "duration_ms",
        "style",
        "result",
        "enabled",
        "reason",
    }
)

# 알려진 이벤트는 필요한 키만 남긴다.
EVENT_SPECS: dict[str, frozenset[str]] = {
    "app_open": frozenset(),
    "session_start": frozenset(),
    "screen_view": frozenset({"screen_name"}),
    "mood_submit": frozenset({"length"}),
    "verse_save": frozenset({"source", "reference", "from"}),
    "verse_unsave": frozenset({"source", "reference", "from"}),
    "verse_copy": frozenset({"source", "reference"}),
    "verse_share": frozenset({"source", "reference"}),
}

MAX_EVENTS_PER_BATCH = 50
MAX_PARAMS_PER_EVENT = 8
MAX_PARAM_VALUE_LEN = 100
MAX_ID_LEN = 64
MAX_META_LEN = 32


def is_valid_event_name(name: Any) -> bool:
    return isinstance(name, str) and bool(EVENT_NAME_RE.match(name))


def sanitize_params(event_name: str, params: Any) -> dict[str, Any]:
    """허용된 키만 남기고 값 타입·길이를 자른다.

    알려진 이벤트면 그 이벤트의 키만, 모르는 이벤트면 전역 허용 키만 통과시킨다.
    """
    if not isinstance(params, dict):
        return {}

    allowed = EVENT_SPECS.get(event_name)
    if allowed is None:
        allowed = GLOBAL_ALLOWED_PARAMS

    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if len(cleaned) >= MAX_PARAMS_PER_EVENT:
            break
        if not isinstance(key, str) or key not in allowed:
            continue
        if isinstance(value, bool) or isinstance(value, int):
            cleaned[key] = value
        elif isinstance(value, float):
            cleaned[key] = value
        elif isinstance(value, str):
            cleaned[key] = value[:MAX_PARAM_VALUE_LEN]
        # 그 외(dict/list/None)는 버린다 — 중첩 구조로 원문이 새는 걸 막는다.
    return cleaned


def clip(value: Any, limit: int = MAX_META_LEN) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]
