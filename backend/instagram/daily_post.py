"""Daily Verse 인스타 게시 실행기 — 운영 서버의 systemd 타이머가 매일 미국 동부 07:00 에 부른다 (이슈 #62).

    python -m instagram.daily_post                 # IG_MODE 대로(기본 dry-run)
    python -m instagram.daily_post --date 2026-11-26 --no-telegram   # 그날 몫 미리보기
    python -m instagram.daily_post --mark-posted psa-34-18,isa-41-10  # 손으로 올린 말씀 기록(겹침 방지)

흐름: 그날 말씀 고르기(앱 오늘의 말씀과 같게) → 매니페스트에서 캡션·이미지 키 → S3 presigned URL(1시간) →
URL 이 밖에서 받아지는지 확인 → [live] 컨테이너 생성 → 상태 확인 → media_publish → 퍼머링크 → 기록 → 텔레그램.
dry-run 은 API 호출 직전까지 가고(토큰이 있으면 /me 확인·갱신은 한다 — 토큰은 쓰지 않아도 60일 뒤 죽는다),
카드와 캡션을 텔레그램으로 보내 그날 무엇이 올라갈지 보여 준다.

설정(env, 운영은 systemd EnvironmentFile):
  IG_MODE=dry-run|live      IG_ACCESS_TOKEN  IG_USER_ID(비우면 /me 로)  IG_GRAPH_VERSION(기본 v27.0)
  IG_S3_BUCKET  IG_S3_REGION(기본 ap-northeast-2)  IG_STATE_DIR(기본 systemd STATE_DIRECTORY)
  IG_LATE_LIMIT_HOURS(기본 6 — 07:00 에서 이만큼 지나면 그날은 건너뛴다)
  TG_TOKEN  TG_CHAT_IDS(쉼표 구분) — 서버의 장애 알림과 같은 봇
"""
from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from instagram.caption import APP_LINE, build_caption, find_caption_problems
from instagram.graph import DEFAULT_VERSION, GraphError, InstagramClient, TokenStore
from instagram.posts import MANIFEST, load_daily_verses, load_manifest
from instagram.selection import pick_verse_id
from notifications.verse_provider import text_fingerprint

log = logging.getLogger("with-god.ig")

POST_TZ = ZoneInfo("America/New_York")
POST_TIME = time(7, 0)
# 앱 안내 줄을 붙이는 요일(월=0). 매일 붙이면 광고 계정처럼 보인다 — 수·일만.
APP_LINE_WEEKDAYS = frozenset({2, 6})
PRESIGN_SECONDS = 3600
# 게시가 끝난 뒤 이 코드로 나간다 — 실패를 텔레그램으로 이미 알렸으니 systemd OnFailure 알림을 또 보내지 않게
# 유닛의 SuccessExitStatus 에 넣는다. 알림까지 실패하면 1 로 나가 OnFailure 가 알린다.
EXIT_REPORTED_FAILURE = 3


@dataclass
class Config:
    mode: str = "dry-run"
    token: str = ""
    user_id: str = ""
    graph_version: str = DEFAULT_VERSION
    bucket: str = "with-god-ig-cards"
    region: str = "ap-northeast-2"
    state_dir: Path = Path("/var/lib/with-god-ig")
    late_limit: timedelta = timedelta(hours=6)
    tg_token: str = ""
    tg_chats: list[str] = field(default_factory=list)
    manifest: Path = MANIFEST

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Config":
        env = os.environ if env is None else env
        mode = (env.get("IG_MODE") or "dry-run").strip().lower()
        if mode not in ("dry-run", "live"):
            raise ValueError(f"IG_MODE 는 dry-run 또는 live: {mode!r}")
        state = env.get("IG_STATE_DIR") or env.get("STATE_DIRECTORY") or "/var/lib/with-god-ig"
        return cls(
            mode=mode,
            token=(env.get("IG_ACCESS_TOKEN") or "").strip(),
            user_id=(env.get("IG_USER_ID") or "").strip(),
            graph_version=env.get("IG_GRAPH_VERSION") or DEFAULT_VERSION,
            bucket=env.get("IG_S3_BUCKET") or "with-god-ig-cards",
            region=env.get("IG_S3_REGION") or "ap-northeast-2",
            state_dir=Path(state.split(":")[0]),
            late_limit=timedelta(hours=float(env.get("IG_LATE_LIMIT_HOURS") or 6)),
            tg_token=(env.get("TG_TOKEN") or "").strip(),
            tg_chats=[c.strip() for c in (env.get("TG_CHAT_IDS") or "").split(",") if c.strip()],
            manifest=Path(env.get("IG_MANIFEST") or MANIFEST),
        )


# ── 상태 파일 ─────────────────────────────────────────────────────

class State:
    """state_dir/posted.json — [{date, verse_id, media_id, permalink, posted_at, source}].
    pending.json — 컨테이너를 만든 뒤 게시 확인 전까지(재시작 중복 방지)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.posted_path = root / "posted.json"
        self.pending_path = root / "pending.json"

    def posted(self) -> list[dict]:
        try:
            return json.loads(self.posted_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []

    def last_posted_by_verse(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in self.posted():
            if row.get("verse_id") and row.get("date", "") > out.get(row["verse_id"], ""):
                out[row["verse_id"]] = row["date"]
        return out

    def posted_on(self, day: date) -> dict | None:
        return next((r for r in self.posted() if r.get("date") == day.isoformat()
                     and r.get("source") == "auto"), None)

    def append(self, row: dict) -> None:
        rows = self.posted() + [row]
        self._write(self.posted_path, rows)

    def pending(self) -> dict | None:
        try:
            return json.loads(self.pending_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def set_pending(self, row: dict | None) -> None:
        if row is None:
            self.pending_path.unlink(missing_ok=True)
        else:
            self._write(self.pending_path, row)

    def _write(self, path: Path, data) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)


# ── 바깥 의존(테스트에서 바꿔 끼운다) ─────────────────────────────

@dataclass
class Deps:
    presign: Callable[[str, str, str, int], str]
    probe: Callable[[str], tuple[int, str, int]]
    telegram: Callable[[Config, str, str], bool]
    client_factory: Callable[[Config, str], InstagramClient]
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


def s3_presign(bucket: str, region: str, key: str, seconds: int) -> str:
    import boto3
    from botocore.config import Config as BotoConfig

    # SigV4 + 리전 엔드포인트 — 서울 버킷은 SigV2·전역 엔드포인트로 서명하면 받는 쪽에서 리다이렉트·거절이 난다.
    s3 = boto3.client("s3", region_name=region, config=BotoConfig(signature_version="s3v4"),
                      endpoint_url=f"https://s3.{region}.amazonaws.com")
    return s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key},
                                     ExpiresIn=seconds)


def http_probe(url: str) -> tuple[int, str, int]:
    """(상태 코드, Content-Type, 전체 크기). 앞 1KB 만 받는다 — Meta 가 이 URL 을 받아 갈 수 있는지 미리 본다."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-1023"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        size = resp.headers.get("Content-Range", "").rsplit("/", 1)[-1]
        return resp.status, resp.headers.get("Content-Type", ""), int(size) if size.isdigit() else 0


def send_telegram(cfg: Config, text: str, photo_url: str = "") -> bool:
    """텔레그램 알림(best-effort). 사진이 있으면 sendPhoto(설명 1,024자 제한)로 먼저 보낸다."""
    if not cfg.tg_token or not cfg.tg_chats:
        log.warning("텔레그램 설정 없음 — 알림 생략")
        return False
    ok = True
    for chat in cfg.tg_chats:
        try:
            if photo_url:
                _tg(cfg.tg_token, "sendPhoto", {"chat_id": chat, "photo": photo_url,
                                                "caption": text[:1000]})
            else:
                _tg(cfg.tg_token, "sendMessage", {"chat_id": chat, "text": text[:4000],
                                                  "disable_web_page_preview": "true"})
        except Exception as exc:  # noqa: BLE001 — 알림 실패가 게시를 막지 않는다
            log.warning("텔레그램 실패(%s): %s", chat, type(exc).__name__)
            ok = False
    return ok


def _tg(token: str, method: str, params: dict) -> None:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp.read()


def default_deps() -> Deps:
    return Deps(
        presign=lambda bucket, region, key, seconds: s3_presign(bucket, region, key, seconds),
        probe=http_probe,
        telegram=send_telegram,
        client_factory=lambda cfg, token: InstagramClient(token, cfg.user_id, version=cfg.graph_version),
    )


# ── 실행 ──────────────────────────────────────────────────────────

class Skip(Exception):
    """그날은 올리지 않는다(이미 올림·너무 늦음). 실패가 아니다. notify 면 텔레그램으로 알린다."""

    def __init__(self, message: str, notify: bool = False) -> None:
        super().__init__(message)
        self.notify = notify


def app_line_for(day: date) -> str:
    return APP_LINE if day.weekday() in APP_LINE_WEEKDAYS else ""


def available_posts(manifest: dict) -> dict[str, dict]:
    """매니페스트 중 지금 목록과 본문이 같은 것만(목록·카드가 바뀌었는데 매니페스트가 낡으면 그 말씀은 뺀다)."""
    current = {v["verse_id"]: text_fingerprint(v["text"]) for v in load_daily_verses()}
    return {vid: e for vid, e in manifest.get("posts", {}).items() if current.get(vid) == e.get("ko_fp")}


def plan(cfg: Config, day: date, state: State) -> dict:
    """그날 올릴 것 — {day, verse_id, reason, entry, caption}."""
    posts = available_posts(load_manifest(cfg.manifest))
    verse_id, reason = pick_verse_id(day, state.last_posted_by_verse(), set(posts))
    e = posts[verse_id]
    caption = build_caption(hook=e["hook"], verse_text=e["text"], ref=e["display_ref"], note=e["note"],
                            cta=e["cta"], topic=e["topic"], app_line=app_line_for(day))
    problems = find_caption_problems(caption)
    if problems:
        raise RuntimeError(f"캡션 검사 실패({verse_id}): {'; '.join(problems)}")
    return {"day": day, "verse_id": verse_id, "reason": reason, "entry": e, "caption": caption}


def run(cfg: Config, deps: Deps, *, day: date | None = None, force: bool = False,
        notify: bool = True) -> dict:
    """한 번 실행. 결과 dict(status: posted|dry-run|skipped). 실패는 예외."""
    now = deps.now()
    local_now = now.astimezone(POST_TZ)
    explicit_day = day is not None
    day = day or local_now.date()
    state = State(cfg.state_dir)

    if cfg.mode == "live" and not force:
        done = state.posted_on(day)
        if done:
            raise Skip(f"{day} 몫은 이미 올렸다 — {done.get('permalink') or done.get('media_id')}")
    if not explicit_day and not force:
        due = datetime.combine(day, POST_TIME, tzinfo=POST_TZ)
        if local_now - due > cfg.late_limit:
            raise Skip(f"게시 시각({due:%H:%M} ET)에서 {cfg.late_limit} 넘게 지났다 — 그날은 건너뜀", notify=True)

    p = plan(cfg, day, state)
    e = p["entry"]
    url = deps.presign(cfg.bucket, cfg.region, e["image"], PRESIGN_SECONDS)
    status, ctype, size = deps.probe(url)
    if status not in (200, 206) or not ctype.startswith("image/jpeg"):
        raise RuntimeError(f"카드 이미지를 받을 수 없다: HTTP {status} {ctype} ({e['image']})")
    if size > 8 * 1024 * 1024:
        raise RuntimeError(f"카드 이미지가 8MB 를 넘는다: {size}")

    token_note, client = _token(cfg, deps, now)
    when = f"{day:%m/%d}({'월화수목금토일'[day.weekday()]}) 07:00 ET"
    why = "" if p["reason"] == "app" else f" · 앱 말씀 {p['reason'].split(':', 1)[1]} 대신({p['reason'].split(':')[0]})"
    head = f"{e['display_ref']} · {e['kicker']}{why}"

    if cfg.mode == "dry-run":
        result = {"status": "dry-run", "verse_id": p["verse_id"], "caption": p["caption"], "image_url": url}
        if notify:
            deps.telegram(cfg, f"🧪 [인스타 dry-run] {when} 게시 예정분\n{head}\n토큰: {token_note}", url)
            deps.telegram(cfg, p["caption"], "")
        return result

    if client is None:
        raise RuntimeError(f"live 인데 토큰을 쓸 수 없다 — {token_note}")

    # 컨테이너를 만들고 게시 확인 전에 죽었으면, 다시 돌 때 그 컨테이너가 이미 게시됐는지부터 본다.
    pending = state.pending()
    media_id = ""
    if pending and pending.get("date") == day.isoformat():
        if pending.get("media_id"):
            media_id = pending["media_id"]  # 게시까지 됐는데 기록 전에 끊겼다
        else:
            try:
                code = client.container_status(pending["container"]).get("status_code")
            except GraphError:
                code = ""
            if code == "PUBLISHED":
                media_id = "unknown"
                log.info("지난 실행의 컨테이너가 이미 게시됨 — 기록만 남긴다")
    if not media_id:
        container = client.create_image_container(url, p["caption"], e["alt_text"])
        state.set_pending({"date": day.isoformat(), "verse_id": p["verse_id"], "container": container})
        client.wait_until_finished(container)
        media_id = client.publish(container)
        state.set_pending({"date": day.isoformat(), "verse_id": p["verse_id"], "container": container,
                           "media_id": media_id})
    permalink = ""
    if media_id != "unknown":
        try:
            permalink = client.permalink(media_id)
        except GraphError as exc:
            log.warning("퍼머링크 조회 실패: %s", exc)
    state.append({"date": day.isoformat(), "verse_id": p["verse_id"], "media_id": media_id,
                  "permalink": permalink, "posted_at": deps.now().isoformat(timespec="seconds"),
                  "source": "auto"})
    state.set_pending(None)
    if notify:
        deps.telegram(cfg, f"✅ 인스타 게시 완료 — {head}\n{permalink or media_id}\n토큰: {token_note}", "")
    return {"status": "posted", "verse_id": p["verse_id"], "media_id": media_id, "permalink": permalink}


def _token(cfg: Config, deps: Deps, now: datetime) -> tuple[str, InstagramClient | None]:
    """(사람이 읽을 토큰 상태, 클라이언트). 토큰이 없으면 (설명, None). 갱신은 dry-run 에서도 한다."""
    store = TokenStore(cfg.state_dir / "token.json", cfg.token, now=deps.now)
    state = store.load()
    if state is None:
        return "없음(IG_ACCESS_TOKEN 을 넣으면 확인한다)", None
    client = deps.client_factory(cfg, state.access_token)
    notes = []
    if store.needs_refresh(state):
        try:
            state = store.refresh(state, client)
            notes.append("갱신함")
        except GraphError as exc:
            notes.append(f"갱신 실패({exc})")
    try:
        me = client.me()
        client.user_id = cfg.user_id or me["user_id"]
        notes.insert(0, f"정상 @{me.get('username', '?')}")
    except GraphError as exc:
        return f"확인 실패({exc})", None
    if state.expires_at:
        left = datetime.fromisoformat(state.expires_at) - now
        notes.append(f"만료까지 {left.days}일")
        if left < timedelta(days=10):
            notes.append("⚠️ 곧 만료 — 갱신이 계속 실패하면 새 토큰을 넣을 것")
    return " · ".join(notes), client


def mark_posted(cfg: Config, verse_ids: list[str], day: date) -> None:
    """손으로 올린 말씀을 기록한다(자동 게시가 90일 안에 같은 말씀을 다시 올리지 않게)."""
    state = State(cfg.state_dir)
    for vid in verse_ids:
        state.append({"date": day.isoformat(), "verse_id": vid, "media_id": "", "permalink": "",
                      "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "source": "manual"})


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Daily Verse 인스타 게시 (이슈 #62)")
    ap.add_argument("--date", type=date.fromisoformat, help="이 날짜(미국 동부) 몫. 늦음 검사를 건너뛴다")
    ap.add_argument("--mode", choices=("dry-run", "live"), help="IG_MODE 대신")
    ap.add_argument("--force", action="store_true", help="이미 올린 날·늦음 검사를 무시")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--print", action="store_true", help="캡션을 표준 출력으로")
    ap.add_argument("--mark-posted", metavar="IDS", help="쉼표로 구분한 verse_id 를 손으로 올린 것으로 기록")
    args = ap.parse_args(argv)

    cfg = Config.from_env()
    if args.mode:
        cfg.mode = args.mode
    cfg.state_dir.mkdir(parents=True, exist_ok=True)

    if args.mark_posted:
        ids = [v.strip() for v in args.mark_posted.split(",") if v.strip()]
        mark_posted(cfg, ids, args.date or datetime.now(POST_TZ).date())
        print(f"{len(ids)}개 기록 → {cfg.state_dir / 'posted.json'}")
        return 0

    deps = default_deps()
    lock = open(cfg.state_dir / "lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error("다른 실행이 진행 중이다")
        return 1
    try:
        result = run(cfg, deps, day=args.date, force=args.force, notify=not args.no_telegram)
    except Skip as exc:
        log.info("건너뜀: %s", exc)
        if exc.notify and not args.no_telegram:
            deps.telegram(cfg, f"⏭ 인스타 게시 건너뜀 — {exc}", "")
        return 0
    except Exception as exc:  # noqa: BLE001 — 무엇이든 알리고 끝낸다
        log.exception("인스타 게시 실패")
        if args.no_telegram:
            return 1
        reported = deps.telegram(cfg, f"🚨 인스타 게시 실패({cfg.mode}): {type(exc).__name__}: {exc}", "")
        return EXIT_REPORTED_FAILURE if reported else 1
    log.info("%s %s", result["status"], result["verse_id"])
    if args.print and "caption" in result:
        print(result["caption"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
