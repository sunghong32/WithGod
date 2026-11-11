"""Instagram API(인스타그램 로그인) 게시 클라이언트와 장기 토큰 보관 (이슈 #62).

공식 문서(2026-11 확인, API v27.0):
- 컨테이너 생성 `POST /{ig-user-id}/media` (image_url·caption·alt_text) → 상태 `GET /{container}?fields=status_code`
  (EXPIRED·ERROR·FINISHED·IN_PROGRESS·PUBLISHED, 1분에 한 번·5분까지 권장) → `POST /{ig-user-id}/media_publish`
  (creation_id) → `GET /{media}?fields=permalink`.
- 이미지는 JPEG 만, 8MB·가로 320~1440·비율 4:5~1.91:1. image_url 은 게시 시점에 공개로 받을 수 있어야 한다.
- 24시간에 게시 50건(`content_publishing_limit`), 컨테이너는 24시간 뒤 만료.
- 장기 토큰은 60일. `GET /refresh_access_token?grant_type=ig_refresh_token` 으로 갱신하며, 받은 지
  24시간이 지나고 만료 전이어야 한다.

외부 라이브러리 없이 표준 라이브러리로 부른다(운영 venv 를 늘리지 않는다). 토큰은 로그·예외 메시지에
남기지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

GRAPH_HOST = "https://graph.instagram.com"
DEFAULT_VERSION = "v27.0"
HTTP_TIMEOUT = 30

# 상태 확인 간격(초). 이미지 컨테이너는 보통 몇 초면 FINISHED 다. 문서 권장(1분 간격·5분까지) 안에서
# 처음엔 짧게 본다 — 합계 300초.
POLL_SCHEDULE = (5, 10, 15, 30, 60, 60, 60, 60)

# 갱신 시점 — 마지막 갱신 뒤 7일이 지났거나 만료가 30일 안으로 들어오면 갱신한다(받은 지 24시간 뒤부터).
REFRESH_EVERY = timedelta(days=7)
REFRESH_BEFORE_EXPIRY = timedelta(days=30)
MIN_TOKEN_AGE = timedelta(hours=24)


class GraphError(RuntimeError):
    """Graph API 오류. message 는 토큰을 지운 것만 담는다."""

    def __init__(self, message: str, *, status: int = 0, code: int | None = None,
                 subcode: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.subcode = subcode


Opener = Callable[..., object]


def _scrub(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


class InstagramClient:
    def __init__(self, token: str, user_id: str = "", *, version: str = DEFAULT_VERSION,
                 opener: Opener = urllib.request.urlopen,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.token = token
        self.user_id = user_id
        self.version = version
        self._open = opener
        self._sleep = sleep

    # ── 저수준 ──
    def _request(self, method: str, path: str, params: dict | None = None,
                 *, versioned: bool = True) -> dict:
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        params["access_token"] = self.token
        base = f"{GRAPH_HOST}/{self.version}" if versioned else GRAPH_HOST
        url = f"{base}/{path.lstrip('/')}"
        body = None
        if method == "GET":
            url += "?" + urllib.parse.urlencode(params)
        else:
            body = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=body, method=method)
        try:
            with self._open(req, timeout=HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                err = json.loads(raw).get("error", {})
            except json.JSONDecodeError:
                err = {"message": raw[:300]}
            raise GraphError(
                _scrub(f"{method} {path}: HTTP {exc.code} {err.get('message', '')}".strip(), self.token),
                status=exc.code, code=err.get("code"), subcode=err.get("error_subcode"),
            ) from None
        except urllib.error.URLError as exc:
            raise GraphError(_scrub(f"{method} {path}: {exc.reason}", self.token)) from None

    # ── 계정 ──
    def me(self) -> dict:
        """{"user_id": 게시용 IG id, "username": …}. 응답이 data 배열로 올 때도 있다(문서 예시)."""
        out = self._request("GET", "me", {"fields": "user_id,username"})
        if isinstance(out.get("data"), list) and out["data"]:
            out = out["data"][0]
        return {"user_id": str(out.get("user_id") or out.get("id") or ""), "username": out.get("username", "")}

    def ensure_user_id(self) -> str:
        if not self.user_id:
            self.user_id = self.me()["user_id"]
        if not self.user_id:
            raise GraphError("IG user_id 를 알 수 없다(/me 응답에 user_id 없음)")
        return self.user_id

    def publishing_quota(self) -> dict:
        out = self._request("GET", f"{self.ensure_user_id()}/content_publishing_limit",
                            {"fields": "quota_usage,config"})
        data = out.get("data") or [{}]
        return data[0]

    # ── 게시 ──
    def create_image_container(self, image_url: str, caption: str, alt_text: str = "") -> str:
        out = self._request("POST", f"{self.ensure_user_id()}/media",
                            {"image_url": image_url, "caption": caption, "alt_text": alt_text})
        if not out.get("id"):
            raise GraphError(f"컨테이너 id 없음: {out}")
        return str(out["id"])

    def container_status(self, container_id: str) -> dict:
        return self._request("GET", container_id, {"fields": "status_code,status"})

    def wait_until_finished(self, container_id: str) -> str:
        """FINISHED 가 되면 돌아온다. ERROR·EXPIRED·시간 초과는 GraphError."""
        status = {}
        for delay in (0, *POLL_SCHEDULE):
            if delay:
                self._sleep(delay)
            status = self.container_status(container_id)
            code = status.get("status_code")
            if code in ("FINISHED", "PUBLISHED"):
                return code
            if code in ("ERROR", "EXPIRED"):
                raise GraphError(f"컨테이너 {code}: {status.get('status', '')}")
        raise GraphError(f"컨테이너가 {sum(POLL_SCHEDULE)}초 안에 준비되지 않음: {status}")

    def publish(self, container_id: str) -> str:
        out = self._request("POST", f"{self.ensure_user_id()}/media_publish", {"creation_id": container_id})
        if not out.get("id"):
            raise GraphError(f"게시 응답에 media id 없음: {out}")
        return str(out["id"])

    def permalink(self, media_id: str) -> str:
        return str(self._request("GET", media_id, {"fields": "permalink"}).get("permalink", ""))

    # ── 토큰 ──
    def refresh_token(self) -> tuple[str, int]:
        """(새 장기 토큰, 남은 초). 버전 없는 경로다."""
        out = self._request("GET", "refresh_access_token", {"grant_type": "ig_refresh_token"},
                            versioned=False)
        token = out.get("access_token")
        if not token:
            raise GraphError("갱신 응답에 access_token 없음")
        return str(token), int(out.get("expires_in") or 0)


# ── 토큰 보관 ─────────────────────────────────────────────────────

def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]


@dataclass
class TokenState:
    access_token: str
    seed: str                # 처음 넣은(env) 토큰의 지문 — env 토큰을 바꾸면 새로 시작한다
    obtained_at: str         # 이 토큰을 받은 시각(ISO, UTC)
    expires_at: str = ""     # 갱신 응답으로 안 만료 시각. env 로 넣은 첫 토큰은 모른다
    refreshed_at: str = ""


class TokenStore:
    """장기 토큰을 상태 디렉터리(token.json, 600)에 두고 갱신한다.

    처음 토큰은 env(IG_ACCESS_TOKEN)로 넣는다. 갱신한 토큰은 env 파일(root 소유)을 고칠 수 없어
    상태 파일에 쓴다. env 토큰을 새로 바꿔 넣으면(지문이 달라지면) 상태 파일을 버리고 새로 시작한다.
    """

    def __init__(self, path: Path, env_token: str, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.env_token = (env_token or "").strip()
        self._now = now or (lambda: datetime.now(timezone.utc))

    def load(self) -> TokenState | None:
        state = None
        if self.path.exists():
            try:
                state = TokenState(**json.loads(self.path.read_text(encoding="utf-8")))
            except (OSError, TypeError, json.JSONDecodeError):
                state = None
        if self.env_token and (state is None or state.seed != _fingerprint(self.env_token)):
            state = TokenState(
                access_token=self.env_token, seed=_fingerprint(self.env_token),
                obtained_at=self._now().isoformat(timespec="seconds"),
            )
            self.save(state)
        return state

    def save(self, state: TokenState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state.__dict__, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def needs_refresh(self, state: TokenState) -> bool:
        now = self._now()
        if now - datetime.fromisoformat(state.obtained_at) < MIN_TOKEN_AGE:
            return False  # Meta: 받은 지 24시간이 지나야 갱신된다
        if not state.refreshed_at or not state.expires_at:
            return True
        if now - datetime.fromisoformat(state.refreshed_at) >= REFRESH_EVERY:
            return True
        return datetime.fromisoformat(state.expires_at) - now <= REFRESH_BEFORE_EXPIRY

    def refresh(self, state: TokenState, client: InstagramClient) -> TokenState:
        token, expires_in = client.refresh_token()
        now = self._now()
        new = TokenState(
            access_token=token, seed=state.seed,
            obtained_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(seconds=expires_in)).isoformat(timespec="seconds") if expires_in else "",
            refreshed_at=now.isoformat(timespec="seconds"),
        )
        self.save(new)
        client.token = token
        return new
