#!/usr/bin/env python3
"""인스타 릴스 월·수·금 예약 게시 — 이 맥 launchd 가 10분마다 부른다.

릴스는 이 맥에서 한 편씩 만든다(그림은 로컬 모델, 영상은 render.py, 음악은 music.swift). 다 만든 편을
큐에 넣어 두면 정해진 시각에 공식 Graph API 로 올리고 텔레그램으로 링크를 보낸다.

자동 제작(사용자 결정 2026-11-26 "예정된 릴스는 다 일정으로 잡아 그 시간에 시작, 놓쳐서 못 올리는 일 없게"):
데스크 앱 예약 작업이 매일 13:00(KST)에 `next --claim` 으로 72시간 안의 빈 슬롯 하나를 맡아 AUTO.md 대로 만들고 큐에 넣는다
(미리보기가 텔레그램으로 가고, 사용자가 답장으로 고칠 점을 주면 고쳐 `add --replace`).
**승인해야 올라간다(사용자 11/26 "막 올리긴 싫다")** — 텔레그램 「올려」 → `approve`. 승인 전이면 게시 24·6시간 전에 승인을 청하고,
게시 시각까지 승인이 없으면 올리지 않고 알린 뒤 기다린다(승인이 늦게 오면 그때 바로 올린다).
앱이 꺼져 있어 게시 30시간 전에도 비어 있으면 이 launchd 가 `claude -p` 로 직접 제작을 띄우고, 24시간 전에도 비어 있으면 알린다.

주기(사용자 결정 2026-11-13): 월 성경 인물 이야기 · 수 앱 시연 · 금 번갈아(그 시절 생활 → 성화 읽기 →
찬송가 이야기 → 오래된 기도), 11/29~12/24 는 대림절 특집을 끼워 넣는다. 오늘의 말씀 재탕은 하지 않는다.
게시 시각은 미국 동부 19:00 — 동부 7시·서부 4시, 미국 저녁(사용자 결정 11/17: 20:00 안을 보고 19:00 유지.
아침 7시는 서부가 새벽 4시라 뺐다). 한국 시간으로는 다음 날 09:00, 미국 서머타임
(3월 둘째 일요일~11월 첫째 일요일) 동안은 08:00 이다 — zoneinfo 가 맞춘다. 오늘의 말씀(07:00 ET)과 12시간 떨어진다.

무엇을 언제 올릴지는 편성표 lineup.json(ET 날짜 → 형식·주제)에 둔다. 편성표에 없는 날은 월 인물·수 시연·
금 번갈아 기본 규칙을 따른다. 만드는 법과 사용자 피드백 규칙은 README.md.

큐 폴더: ~/.local/share/withgod-ig-reels/queue/<ET 날짜>-<slug>/
    reel.mp4 · cover.jpg · caption.txt · job.json — 올린 편은 queue/done/ 으로 옮긴다.

    python3 reel_queue.py add <폴더> --title "한나" [--format hymn] [--slot 2026-11-18 | --at 2026-11-17T12:30+09:00 | --now]
    python3 reel_queue.py status          # 앞으로의 슬롯·편성표 주제·큐
    python3 reel_queue.py preview <폴더>   # 텔레그램으로 영상 미리보기(add 도 넣을 때 자동으로 보낸다)
    python3 reel_queue.py run             # launchd 가 부름(손으로 불러도 안전 — 같은 편을 두 번 올리지 않는다)
    python3 reel_queue.py install         # bin/ 에 복사하고 launchd 등록(코드·편성표를 고친 뒤 다시 부른다)

영상은 S3(with-god-ig-cards/reels/)에 올려 7일짜리 서명 주소로 넘긴다(버킷은 공개가 아니다). 컨테이너는
게시 3시간 전에 미리 만들어 FINISHED 를 확인해 둔다(24시간 뒤 만료). S3 는 aws CLI 를, 인스타는
backend/instagram/graph.py 를 쓴다 — 표준 라이브러리 밖의 파이썬 패키지는 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]  # bin/ 에 복사한 graph.py, 아니면 backend/instagram/graph.py
from graph import GraphError, InstagramClient  # noqa: E402

REPO = Path(os.environ.get("WITHGOD_REPO", Path.home() / "WithGod"))
SECRET = REPO / "backend/secrets/instagram.json"
ROOT = Path(os.environ.get("WITHGOD_REELS_ROOT", Path.home() / ".local/share/withgod-ig-reels"))
QUEUE, DONE, STATE = ROOT / "queue", ROOT / "queue/done", ROOT / "state.json"
LABEL = "com.minsunghong.withgod-ig-reels"
PLIST = Path.home() / f"Library/LaunchAgents/{LABEL}.plist"
LOG = Path.home() / "Library/Logs/withgod-ig-reel.log"
AWS = shutil.which("aws") or "/opt/homebrew/bin/aws"
# launchd 는 버전이 박힌 경로(python3.14) 대신 업그레이드에도 남는 링크로 부른다
PYTHON = "/opt/homebrew/bin/python3" if Path("/opt/homebrew/bin/python3").exists() else sys.executable
BUCKET, REGION = "with-god-ig-cards", "ap-northeast-2"

ET, KST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
POST_HOUR = 19
KINDS = {0: "성경 인물 이야기", 2: "앱 시연", 4: "금요일 번갈아"}
# 형식(job.json 의 format). 금요일은 FRIDAY_ROTATION 순서로 돌고, 다음 차례는 지난 금요일 게시 기록으로 정한다.
FORMATS = {"character": "성경 인물 이야기", "demo": "앱 시연", "life": "그 시절 생활", "painting": "성화 읽기",
           "hymn": "찬송가 이야기", "prayer": "오래된 기도문", "advent": "대림절 특집", "other": "기타"}
WEEKDAY_FORMAT = {0: "character", 2: "demo"}
FRIDAY_ROTATION = ("life", "painting", "hymn", "prayer")
WEEKDAY_KO = "월화수목금토일"
PREPARE_LEAD = timedelta(hours=3)
CONTAINER_TTL = timedelta(hours=20)   # 만료(24시간) 전에 다시 만든다
URL_TTL = timedelta(days=6)           # 서명 주소는 7일 — 하루 여유
REMIND_AT = (timedelta(hours=24),)
APPROVE_REMIND_AT = (timedelta(hours=24), timedelta(hours=6))   # 승인 전이면 이때 승인을 청한다(+ 게시 시각에 한 번)   # 자동 제작이 72→30시간 전에 돌므로, 24시간 전에도 비면 문제다(11/26)
AUTO_WINDOW = 72        # 시간 — 데스크 예약 실행(매일 13:00 KST)이 이 안의 빈 슬롯을 맡는다
CLAIM_TTL = timedelta(hours=4)        # 「제작 중」 표시가 이보다 오래됐는데 큐가 비었으면 그 실행은 죽은 것
FALLBACK_AT = timedelta(hours=30)     # 이때도 비어 있고 아무도 안 만들고 있으면 launchd 가 직접 제작을 띄운다
FALLBACK_MIN = timedelta(hours=3)     # 이보다 촉박하면 만들 시간이 없다 — 알림만
AUTO_DIR = Path(os.environ.get("WITHGOD_REELS_WT", ROOT / "repo"))   # 자동 제작 전용 git 워크트리(앱이 정리하지 않는 곳)
AUTO_DOC = "backend/instagram/reels/AUTO.md"
CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or str(Path.home() / ".local/bin/claude")
MAKE_LOG = Path.home() / "Library/Logs/withgod-ig-reel-make.log"
FAIL_NOTIFY_EVERY = timedelta(hours=1)
REQUIRED = ("reel.mp4", "cover.jpg", "caption.txt")
# 메시지 한 줄 + 한국어 줄거리 + 대본(REVIEW.md 틀). 새 서브에이전트 검토를 통과해야 「검토: 통과 …」 줄을 적고 큐에 넣는다.
# 텔레그램 미리보기 뒤에 「## 대본」 앞까지를 보낸다 — 사용자가 스토리를 알고 보도록(11/20).
STORY = "story.md"
HASHTAG_MAX = 5
MAKE_HINT = "자동 제작이 결과를 못 냈습니다(로그 ~/Library/Logs/withgod-ig-reel-make.log). 답장으로 「다음 릴스 만들어줘」라고 하면 backend/instagram/reels/AUTO.md 대로 만듭니다."


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def log(msg: str) -> None:
    print(datetime.now().astimezone().isoformat(timespec="seconds"), msg, flush=True)


def notify(text: str) -> bool:
    """텔레그램 sendMessage — 보냈으면 True. 알림 실패가 게시를 막지 않는다.
    tg-notify.sh 는 실패해도 0 으로 끝나서 빈 슬롯 알림이 못 갔는데도 '보냄'으로 적혔다(11/25) — 응답을 직접 본다."""
    try:
        token, chats = tg_env()
        if not token or not chats:
            return False
        ok = True
        for chat in chats:
            cfg = f'url = "https://api.telegram.org/bot{token}/sendMessage"\n'
            r = subprocess.run(["curl", "-sS", "-K", "-", "--data-urlencode", f"chat_id={chat}",
                                "--data-urlencode", f"text={text[:4000]}"],
                               input=cfg, capture_output=True, text=True, timeout=30)
            ok = ok and '"ok":true' in r.stdout
        if not ok:
            log("notify failed: telegram not ok")
        return ok
    except Exception as exc:
        log(f"notify failed: {type(exc).__name__}")
        return False


def tg_env() -> tuple[str, list[str]]:
    env = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    ids = env.get("TELEGRAM_ALLOWED_CHAT_IDS") or env.get("TELEGRAM_CHAT_ID", "")
    return env.get("TELEGRAM_BOT_TOKEN", ""), [i.strip() for i in ids.split(",") if i.strip()]


TG_VIDEO_MAX = 49 * 1024 * 1024  # 텔레그램 봇 sendVideo 상한 50MB


def send_video(video: Path, caption: str) -> bool:
    """텔레그램 sendVideo(50MB 까지). 토큰이 프로세스 목록에 보이지 않게 curl 설정을 표준 입력으로 준다.
    더 크면(성화 편은 캔버스 결 때문에 100MB 안팎) 720p 미리보기로 줄여 보낸다 — 게시하는 원본은 그대로."""
    try:
        token, chats = tg_env()
        if not token or not chats:
            return False
        with tempfile.TemporaryDirectory() as tmp:
            if video.stat().st_size > TG_VIDEO_MAX:
                small = Path(tmp) / "preview.mp4"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "scale=720:-2",
                                "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
                                "-movflags", "+faststart", str(small)], check=True, timeout=600)
                video = small
            ok = True
            for chat in chats:
                cfg = f'url = "https://api.telegram.org/bot{token}/sendVideo"\n'
                r = subprocess.run(["curl", "-sS", "-K", "-", "-F", f"chat_id={chat}", "-F", f"video=@{video}",
                                    "-F", "supports_streaming=true", "-F", f"caption={caption[:1000]}"],
                                   input=cfg, capture_output=True, text=True, timeout=300)
                ok = ok and '"ok":true' in r.stdout
        return ok
    except Exception as exc:
        log(f"send_video failed: {type(exc).__name__}")
        return False


def story_summary(src: Path) -> str:
    """story.md 의 「## 대본」 앞까지(메시지 한 줄 + 한국어 줄거리) — 텔레그램 한 통(4,096자)에 들어가게."""
    p = src / STORY
    if not p.exists():
        return ""
    head = p.read_text().split("\n## 대본", 1)[0].replace("## 한국어 줄거리\n", "").strip()
    return head[:3900]


def send_story(src: Path) -> None:
    text = story_summary(src)
    if text:
        notify("📖 " + text.removeprefix("# "))


def kst(dt: datetime) -> str:
    k = dt.astimezone(KST)
    return f"{k.month}/{k.day}({WEEKDAY_KO[k.weekday()]}) {k:%H:%M}"


def et(dt: datetime) -> str:
    e = dt.astimezone(ET)
    return f"{e.month}/{e.day}({WEEKDAY_KO[e.weekday()]}) {e:%H:%M} ET"


# ── 슬롯 ──────────────────────────────────────────────────────────────

def slot_at(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, POST_HOUR, tzinfo=ET).astimezone(timezone.utc)


def upcoming_slots(after: datetime, n: int) -> list[datetime]:
    out, d = [], after.astimezone(ET).date()
    while len(out) < n:
        if d.weekday() in KINDS and slot_at(d) > after:
            out.append(slot_at(d))
        d += timedelta(days=1)
    return out


def next_friday_format() -> str:
    """지난 금요일 편(게시했거나 큐에 있는 것) 중 가장 최근 형식의 다음 차례."""
    rows = []
    for base in (DONE, QUEUE):
        if base.exists():
            for d in base.iterdir():
                if (d / "job.json").exists():
                    j = load_job(d)
                    if j.get("format") in FRIDAY_ROTATION:
                        rows.append((j["due"], j["format"]))
    if not rows:
        return FRIDAY_ROTATION[0]
    last = max(rows)[1]
    return FRIDAY_ROTATION[(FRIDAY_ROTATION.index(last) + 1) % len(FRIDAY_ROTATION)]


def lineup() -> dict:
    for p in (HERE / "lineup.json", REPO / "backend/instagram/reels/lineup.json"):
        if p.exists():
            return {k: v for k, v in json.loads(p.read_text()).items() if not k.startswith("_")}
    return {}


def planned(slot: datetime) -> dict:
    return lineup().get(f"{slot.astimezone(ET):%Y-%m-%d}", {})


def expected_format(slot: datetime) -> str:
    plan = planned(slot)
    if plan.get("format") in FORMATS:
        return plan["format"]
    wd = slot.astimezone(ET).weekday()
    return WEEKDAY_FORMAT.get(wd) or next_friday_format()


def plan_text(slot: datetime) -> str:
    topic = planned(slot).get("topic")
    return f"{FORMATS[expected_format(slot)]}" + (f" — {topic}" if topic else "")


# ── 상태(알림 기록 · 제작 중 표시) ───────────────────────────────────

def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    tmp.replace(STATE)


def state_lock():
    """state.json 을 읽고 고치는 동안 잡는 잠금(launchd run · 데스크 예약 실행 · 손 실행이 겹쳐도 같은 슬롯을 두 번 맡지 않게)."""
    ROOT.mkdir(parents=True, exist_ok=True)
    f = open(ROOT / "state.lock", "w")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


def active_claim(state: dict, slot: datetime) -> dict | None:
    c = state.get("making", {}).get(slot.isoformat())
    if c and now_utc() - datetime.fromisoformat(c["at"]) < CLAIM_TTL:
        return c
    return None


def empty_slots(within: timedelta) -> list[datetime]:
    have = {datetime.fromisoformat(j["due"]) for _, j in queued()}
    return [s for s in upcoming_slots(now_utc(), 8) if s not in have and s - now_utc() <= within]


# ── 큐 ────────────────────────────────────────────────────────────────

def load_job(d: Path) -> dict:
    return json.loads((d / "job.json").read_text())


def save_job(d: Path, job: dict) -> None:
    tmp = d / "job.json.tmp"
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1))
    tmp.replace(d / "job.json")


def queued() -> list[tuple[Path, dict]]:
    if not QUEUE.exists():
        return []
    jobs = [(d, load_job(d)) for d in QUEUE.iterdir() if d.is_dir() and (d / "job.json").exists()]
    return sorted(jobs, key=lambda x: x[1]["due"])


def check_folder(src: Path) -> list[str]:
    problems = [f"{n} 없음" for n in REQUIRED if not (src / n).exists()]
    if problems:
        return problems
    cap = (src / "caption.txt").read_text().strip()
    if len(cap) > 2200:
        problems.append(f"캡션 {len(cap)}자(최대 2200)")
    tags = [t.lower() for t in re.findall(r"(?<!\w)#\w+", cap)]
    if len(tags) > HASHTAG_MAX:  # 2025-12 부터 인스타 상한 5개(예전 30) — 넘으면 게시가 막힐 수 있다
        problems.append(f"해시태그 {len(tags)}개(최대 {HASHTAG_MAX})")
    if "#bibleverse" not in tags:
        problems.append("#bibleverse 없음(README 「캡션」)")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:"
                            "format=duration,size", "-of", "json", str(src / "reel.mp4")],
                           capture_output=True, text=True)
    info = json.loads(probe.stdout or "{}")
    v = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    a = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    dur = float(info.get("format", {}).get("duration", 0))
    size = int(info.get("format", {}).get("size", 0))
    if not v or (v[0].get("width"), v[0].get("height")) != (1080, 1920) or v[0].get("codec_name") != "h264":
        problems.append(f"영상은 1080×1920 H.264 여야 함: {v[:1]}")
    if not a:
        problems.append("오디오 트랙 없음(무음이라도 트랙은 있어야 함)")
    story = src / STORY
    if not story.exists():
        problems.append("story.md 없음 — 메시지 한 줄·한국어 줄거리·대본을 쓰고 검토를 거친다(REVIEW.md)")
    elif not re.search(r"^검토: 통과", story.read_text(), re.M):
        problems.append("story.md 에 「검토: 통과 …」 줄이 없다 — 새 서브에이전트 검토(REVIEW.md)를 통과한 뒤 적는다")
    if not 3 <= dur <= 90:
        problems.append(f"길이 {dur:.1f}초(3~90초)")
    if size > 300 * 1024 * 1024:
        problems.append(f"용량 {size / 1e6:.0f}MB(300MB 이하)")
    return problems


def cmd_add(args) -> int:
    src = Path(args.folder).expanduser().resolve()
    problems = check_folder(src)
    if problems:
        print("큐에 넣지 못함:\n- " + "\n- ".join(problems))
        return 1
    taken = {datetime.fromisoformat(j["due"]) for _, j in queued()}
    if args.now:
        due = now_utc()
    elif args.at:
        due = datetime.fromisoformat(args.at).astimezone(timezone.utc)
    elif args.slot:
        day = date.fromisoformat(args.slot)
        if day.weekday() not in KINDS:
            print(f"{day} 은 월·수·금이 아니다(--at 으로 시각을 직접 주면 된다)")
            return 1
        due = slot_at(day)
    else:
        due = next(s for s in upcoming_slots(now_utc(), 60) if s not in taken)
    replaced = False
    if due in taken:
        if not args.replace:
            print(f"{et(due)} 슬롯에 이미 다른 편이 있다(고친 편으로 바꾸려면 --replace)")
            return 1
        for d, j in queued():
            if datetime.fromisoformat(j["due"]) != due:
                continue
            if j.get("media_id"):
                print(f"{d.name} 은 이미 올라갔다 — 바꿀 수 없다")
                return 1
            old = QUEUE / "replaced" / f"{d.name}-{now_utc().astimezone(KST):%m%d%H%M}"
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(old))
            print(f"앞 편을 치움: {old}")
            replaced = True
    slug = args.slug or src.name
    dst = QUEUE / f"{due.astimezone(ET):%Y-%m-%d}-{slug}"
    if dst.exists():
        print(f"이미 있음: {dst}")
        return 1
    dst.mkdir(parents=True)
    for n in REQUIRED + (STORY,):
        shutil.copy2(src / n, dst / n)
    fmt = args.format or (expected_format(due) if due.astimezone(ET).weekday() in KINDS else "other")
    if args.format and due.astimezone(ET).weekday() in KINDS and args.format != expected_format(due):
        print(f"참고: 편성표·차례는 {plan_text(due)} 인데 {FORMATS[args.format]} 로 넣는다")
    kind = FORMATS[fmt]
    save_job(dst, {"slug": slug, "title": args.title or slug, "kind": kind, "format": fmt,
                   "due": due.isoformat(timespec="seconds"), "added_at": now_utc().isoformat(timespec="seconds")})
    print(f"큐에 넣음: {dst.name} — {et(due)} = 한국 {kst(due)} [{kind}]")
    with state_lock():
        state = load_state()
        if state.get("making", {}).pop(due.isoformat(), None) is not None:
            save_state(state)
    if not args.no_preview:
        head = "📼 고친 편으로 바꿔 넣음" if replaced else "📼 릴스 큐에 들어감"
        sent = send_video(dst / "reel.mp4", f"{head}: {args.title or slug} ({kind})\n"
                                            f"게시 {et(due)} = 한국 {kst(due)}\n"
                                            "올려도 되면 이 대화에 「올려」라고 답장 주세요. 고칠 점이 있으면 그 내용을 답장으로 — "
                                            "고쳐서 다시 보내 드립니다. 승인 전에는 올라가지 않습니다.")
        print("텔레그램 미리보기 " + ("보냄" if sent else "못 보냄"))
        send_story(dst)
    return 0


def cmd_preview(args) -> int:
    src = Path(args.folder).expanduser().resolve()
    ok = send_video(src / "reel.mp4", args.caption or f"📼 릴스 미리보기: {src.name}")
    if ok:
        send_story(src)
    print("보냄" if ok else "못 보냄")
    return 0 if ok else 1


def cmd_status(_args) -> int:
    jobs = queued()
    state = load_state()
    by_due = {datetime.fromisoformat(j["due"]): (d, j) for d, j in jobs}
    print(f"지금 {kst(now_utc())} KST / {et(now_utc())}")
    print("\n앞으로의 슬롯:")
    for s in upcoming_slots(now_utc() - timedelta(hours=1), 8):
        d, j = by_due.get(s, (None, None))
        c = None if j else active_claim(state, s)
        mark = (f"✅ {j['title']} ({'승인됨' if j.get('approved_at') else '승인 대기'}"
                f"{', 컨테이너 준비됨' if j.get('container_id') else ''})" if j else
                f"🛠 제작 중({kst(datetime.fromisoformat(c['at']))}~, {c.get('by', '')})" if c else "⬜ 비어 있음")
        fmt = FORMATS[j["format"]] if j else plan_text(s)
        print(f"  {et(s):<20} 한국 {kst(s):<16} {mark:<24} {fmt}")
    extra = [(d, j) for d, j in jobs if datetime.fromisoformat(j["due"]) not in
             set(upcoming_slots(now_utc() - timedelta(hours=1), 8))]
    if extra:
        print("\n그 밖의 큐:")
        for d, j in extra:
            print(f"  {d.name}: {kst(datetime.fromisoformat(j['due']))} KST {j['title']}")
    if DONE.exists():
        done = sorted(DONE.iterdir(), key=lambda p: p.name)[-5:]
        if done:
            print("\n최근 게시:")
            for d in done:
                j = load_job(d)
                print(f"  {kst(datetime.fromisoformat(j['published_at']))} KST {j['title']} {j.get('permalink', '')}")
    return 0


# ── 게시 ──────────────────────────────────────────────────────────────

def client() -> InstagramClient:
    sec = json.loads(SECRET.read_text())
    return InstagramClient(sec["access_token"], sec["ig_user_id"])


def upload(d: Path, job: dict) -> None:
    """S3 에 올리고 7일 서명 주소를 job 에 넣는다(내용 해시로 이름을 지어 같은 파일은 덮어써도 같다)."""
    for name, ctype, key_name in (("reel.mp4", "video/mp4", "video_url"), ("cover.jpg", "image/jpeg", "cover_url")):
        data = (d / name).read_bytes()
        key = f"reels/{job['slug']}-{hashlib.sha256(data).hexdigest()[:10]}{Path(name).suffix}"
        subprocess.run([AWS, "s3", "cp", str(d / name), f"s3://{BUCKET}/{key}", "--content-type", ctype,
                        "--region", REGION, "--only-show-errors"], check=True, timeout=600)
        url = subprocess.run([AWS, "s3", "presign", f"s3://{BUCKET}/{key}", "--expires-in", str(7 * 24 * 3600),
                              "--region", REGION], check=True, capture_output=True, text=True, timeout=60).stdout.strip()
        job[key_name] = url
    job["urls_at"] = now_utc().isoformat(timespec="seconds")
    log(f"{d.name}: uploaded")


def make_container(c: InstagramClient, d: Path, job: dict) -> None:
    urls_at = job.get("urls_at")
    if not urls_at or now_utc() - datetime.fromisoformat(urls_at) > URL_TTL:
        upload(d, job)
    out = c._request("POST", f"{c.user_id}/media", {
        "media_type": "REELS", "video_url": job["video_url"], "cover_url": job["cover_url"],
        "caption": (d / "caption.txt").read_text().strip(), "share_to_feed": "true"})
    cid = str(out["id"])
    code = ""
    for _ in range(60):  # 영상 처리는 보통 1~2분
        time.sleep(10)
        st = c.container_status(cid)
        code = st.get("status_code", "")
        if code in ("FINISHED", "ERROR", "EXPIRED"):
            break
    if code != "FINISHED":
        raise GraphError(f"REELS 컨테이너 {code or '시간 초과'}: {st.get('status', '')}")
    job.update(container_id=cid, container_at=now_utc().isoformat(timespec="seconds"))
    log(f"{d.name}: container {cid} FINISHED")


def container_ok(c: InstagramClient, job: dict) -> bool:
    cid, at = job.get("container_id"), job.get("container_at")
    if not cid or not at or now_utc() - datetime.fromisoformat(at) > CONTAINER_TTL:
        return False
    try:
        return c.container_status(cid).get("status_code") == "FINISHED"
    except GraphError:
        return False


def fail(d: Path, job: dict, stage: str, exc: Exception) -> None:
    msg = f"{type(exc).__name__}: {str(exc)[:300]}"
    log(f"{d.name}: {stage} FAILED {msg}")
    last = job.get("fail_notified_at")
    if not last or now_utc() - datetime.fromisoformat(last) >= FAIL_NOTIFY_EVERY:
        notify(f"🚨 릴스 「{job['title']}」 {stage} 실패 — {msg}\n10분마다 다시 시도합니다(알림은 1시간에 한 번).")
        job["fail_notified_at"] = now_utc().isoformat(timespec="seconds")
    job["last_error"] = msg
    save_job(d, job)


def process(c: InstagramClient, d: Path, job: dict) -> None:
    due = datetime.fromisoformat(job["due"])
    if job.get("media_id"):
        DONE.mkdir(parents=True, exist_ok=True)
        d.rename(DONE / d.name)
        return
    if now_utc() < due - PREPARE_LEAD:
        return
    if not container_ok(c, job):
        try:
            make_container(c, d, job)
            save_job(d, job)
        except Exception as exc:
            fail(d, job, "준비(업로드·컨테이너)", exc)
            return
    if now_utc() < due:
        return
    if not job.get("approved_at"):  # 사용자가 텔레그램으로 승인해야 올린다(11/26) — 컨테이너는 위에서 미리 준비해 둔다
        return
    try:
        mid = c.publish(job["container_id"])
    except Exception as exc:
        fail(d, job, "게시", exc)
        return
    job.update(media_id=mid, published_at=now_utc().isoformat(timespec="seconds"))
    save_job(d, job)  # 링크를 못 받아도 두 번 올리지 않게 먼저 적는다
    try:
        job["permalink"] = c.permalink(mid)
    except GraphError:
        job["permalink"] = ""
    save_job(d, job)
    late = now_utc() - due
    late_why = ("승인이 게시 시각 뒤에 와서" if datetime.fromisoformat(job["approved_at"]) > due
                else "이 맥이 꺼져 있었을 수 있음")
    late_note = f"\n(예정보다 {int(late.total_seconds() // 60)}분 늦게 올라감 — {late_why})" \
        if late > timedelta(minutes=30) else ""
    log(f"{d.name}: published {mid} {job['permalink']}")
    notify(f"🎬 릴스 게시 완료: {job['title']} ({job['kind']})\n{job['permalink']}{late_note}\n"
           f"앱에서 스토리 공유·댓글 확인해 주세요.")
    DONE.mkdir(parents=True, exist_ok=True)
    d.rename(DONE / d.name)


def remind_empty(jobs: list[tuple[Path, dict]]) -> None:
    with state_lock():
        state = load_state()
        sent = state.setdefault("reminded", {})
        have = {datetime.fromisoformat(j["due"]) for _, j in jobs}
        changed = False
        for s in upcoming_slots(now_utc(), 2):
            if s in have or active_claim(state, s):
                continue
            left = s - now_utc()
            for i, lead in enumerate(REMIND_AT):
                key = f"{s.isoformat()}#{i}"
                if left <= lead and key not in sent and (i + 1 == len(REMIND_AT) or left > REMIND_AT[i + 1]):
                    hours = int(left.total_seconds() // 3600)
                    if notify(f"📭 다음 릴스가 아직 없습니다\n{plan_text(s)}\n"
                              f"게시 {et(s)} = 한국 {kst(s)} (약 {hours}시간 남음)\n{MAKE_HINT}"):
                        sent[key] = now_utc().isoformat(timespec="seconds")  # 보냈을 때만 — 못 보냈으면 다음 run 에서 다시
                        changed = True
        cutoff = now_utc() - timedelta(days=14)
        for k in [k for k in sent if datetime.fromisoformat(k.split("#")[0]) < cutoff]:
            del sent[k]
            changed = True
        if changed:
            save_state(state)


def remind_approval(jobs: list[tuple[Path, dict]]) -> None:
    """승인 전인 편: 게시 24·6시간 전에 승인을 청하고, 게시 시각이 지나도 승인이 없으면 한 번 알린다(보냈을 때만 기록)."""
    with state_lock():
        state = load_state()
        sent = state.setdefault("approval_reminded", {})
        changed = False
        for d, j in jobs:
            if j.get("approved_at") or j.get("media_id"):
                continue
            due = datetime.fromisoformat(j["due"])
            left = due - now_utc()
            hours = int(left.total_seconds() // 3600)
            msgs = []
            for i, lead in enumerate(APPROVE_REMIND_AT):
                if left <= lead and (i + 1 == len(APPROVE_REMIND_AT) or left > APPROVE_REMIND_AT[i + 1]) and left > timedelta(0):
                    msgs.append((f"{d.name}#{i}", f"✋ 승인 기다리는 릴스: {j['title']} ({j['kind']})\n"
                                 f"게시 {et(due)} = 한국 {kst(due)} (약 {hours}시간 남음)\n"
                                 "올려도 되면 이 대화에 「올려」라고 답장 주세요(미리보기는 앞서 보낸 영상). "
                                 "승인 전에는 올라가지 않습니다."))
            if left <= timedelta(0):
                msgs.append((f"{d.name}#due", f"⏸ 승인이 없어 {j['title']} 을(를) 올리지 않았습니다(예정 한국 {kst(due)}).\n"
                             "「올려」라고 답장 주시면 바로 올립니다. 올리지 않으려면 「취소」."))
            for key, text in msgs[-1:]:  # 여러 단계가 한꺼번에 걸리면(맥이 꺼져 있었다 등) 가장 최근 것만
                if key not in sent and notify(text):
                    sent[key] = now_utc().isoformat(timespec="seconds")
                    changed = True
        live = {d.name for d, _ in jobs}
        for k in [k for k in sent if k.split("#")[0] not in live]:
            del sent[k]
            changed = True
        if changed:
            save_state(state)


def find_job(slot: str | None, unapproved: bool = False) -> tuple[Path, dict] | None:
    """ET 날짜(YYYY-MM-DD)로 큐의 편을, 날짜가 없으면 가장 이른(승인 전) 편을."""
    for d, j in queued():
        if j.get("media_id"):
            continue
        if slot and f"{datetime.fromisoformat(j['due']).astimezone(ET):%Y-%m-%d}" != slot:
            continue
        if not slot and unapproved and j.get("approved_at"):
            continue
        return d, j
    return None


def cmd_approve(args) -> int:
    """사용자가 텔레그램 등으로 「올려」라고 했을 때 — 그 편을 승인해 예정 시각(지났으면 다음 run)에 올리게 한다."""
    hit = find_job(args.slot, unapproved=True)
    if not hit:
        print("승인할 편이 없다")
        return 1
    d, j = hit
    j.update(approved_at=now_utc().isoformat(timespec="seconds"), approved_note=args.note or "")
    save_job(d, j)
    due = datetime.fromisoformat(j["due"])
    when = "다음 run(10분 안)에 바로" if due <= now_utc() else f"{et(due)} = 한국 {kst(due)} 에"
    print(f"승인: {d.name} — {when} 올라간다")
    return 0


def cmd_cancel(args) -> int:
    """「올리지 마」 — 아직 안 올라간 편을 queue/replaced/ 로 치운다(지우지 않는다)."""
    hit = find_job(args.slot)
    if not hit:
        print("그 날짜의 큐가 없다")
        return 1
    d, _ = hit
    old = QUEUE / "replaced" / f"{d.name}-cancel-{now_utc().astimezone(KST):%m%d%H%M}"
    old.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), str(old))
    print(f"취소: {old}")
    return 0


def auto_start(dry: bool = False) -> None:
    """데스크 예약 실행이 돌지 않았을 때(앱이 꺼져 있었다 등)의 대비 — 게시 30시간 전에도 비어 있고 아무도 만들고 있지 않으면
    자동 제작 워크트리에서 `claude -p` 로 AUTO.md 를 직접 실행한다. 슬롯마다 한 번만."""
    with state_lock():
        state = load_state()
        for s in empty_slots(FALLBACK_AT):
            left, key = s - now_utc(), s.isoformat()
            if left < FALLBACK_MIN or active_claim(state, s) or key in state.get("fallback", {}):
                continue
            day = f"{s.astimezone(ET):%Y-%m-%d}"
            if dry:
                print(f"(dry) {day} 자동 제작을 띄울 차례 — {plan_text(s)}")
                continue
            if not (AUTO_DIR / AUTO_DOC).exists() or not Path(CLAUDE).exists():
                state.setdefault("fallback", {})[key] = now_utc().isoformat(timespec="seconds")
                notify(f"⚠️ 릴스 자동 제작을 띄우지 못했습니다(워크트리 {AUTO_DIR} 또는 claude 없음)\n{plan_text(s)}\n"
                       f"게시 {et(s)} = 한국 {kst(s)}")
                continue
            env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}  # 구독(OAuth)으로
            env["PATH"] = f"{Path(CLAUDE).parent}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
            prompt = (f"{AUTO_DOC} 를 처음부터 끝까지 읽고 그대로 해라. 대상 슬롯은 {day}(ET) 이다 — "
                      "launchd 가 이미 「제작 중」으로 표시해 두었으니 `next --claim` 대신 이 슬롯으로 만든다.")
            MAKE_LOG.parent.mkdir(parents=True, exist_ok=True)
            out = open(MAKE_LOG, "a")
            out.write(f"\n=== {datetime.now().astimezone().isoformat(timespec='seconds')} launchd 대비 실행 {day}\n")
            out.flush()
            subprocess.Popen([CLAUDE, "-p", "--permission-mode", "bypassPermissions", prompt], cwd=str(AUTO_DIR),
                             stdout=out, stderr=out, env=env, start_new_session=True)
            now = now_utc().isoformat(timespec="seconds")
            state.setdefault("making", {})[key] = {"at": now, "by": "launchd 대비"}
            state.setdefault("fallback", {})[key] = now
            log(f"auto_start {day}")
            notify(f"⚠️ 릴스가 게시 {int(left.total_seconds() // 3600)}시간 전인데 아직 없어 직접 만들기 시작했습니다"
                   f"(데스크 예약 실행이 돌지 않았습니다 — 앱이 꺼져 있었을 수 있음).\n{plan_text(s)}\n"
                   f"게시 {et(s)} = 한국 {kst(s)}. 다 되면 미리보기를 보냅니다.")
        cutoff = now_utc() - timedelta(days=14)
        for bucket in ("making", "fallback"):
            for k in [k for k in state.get(bucket, {}) if datetime.fromisoformat(k) < cutoff]:
                del state[bucket][k]
        save_state(state)


def cmd_next(args) -> int:
    """자동 제작의 첫 단계 — 앞으로 within 시간 안의 빈 슬롯 중 아무도 만들고 있지 않은 첫 슬롯을 JSON 한 줄로.
    --claim 이면 그 슬롯을 「제작 중」으로 표시한다(4시간 뒤 풀림, add 하면 지워짐). 없으면 {"slot": null}."""
    with state_lock():
        state = load_state()
        for s in empty_slots(timedelta(hours=args.within)):
            if s - now_utc() < timedelta(hours=1) or active_claim(state, s):
                continue
            plan = planned(s)
            out = {"slot": f"{s.astimezone(ET):%Y-%m-%d}", "due_et": et(s), "due_kst": kst(s),
                   "hours_left": int((s - now_utc()).total_seconds() // 3600), "format": expected_format(s),
                   "kind": FORMATS[expected_format(s)], "topic": plan.get("topic"), "note": plan.get("note")}
            if args.claim:
                state.setdefault("making", {})[s.isoformat()] = {"at": now_utc().isoformat(timespec="seconds"),
                                                                 "by": args.by}
                save_state(state)
            print(json.dumps(out, ensure_ascii=False))
            return 0
    print(json.dumps({"slot": None}))
    return 0


def cmd_release(args) -> int:
    """제작을 그만둘 때(실패 등) 「제작 중」 표시를 지운다 — 다음 예약 실행·대비 실행이 다시 맡을 수 있게."""
    s = slot_at(date.fromisoformat(args.slot))
    with state_lock():
        state = load_state()
        gone = state.get("making", {}).pop(s.isoformat(), None)
        save_state(state)
    print("지움" if gone else "표시가 없었다")
    return 0


def cmd_run(_args) -> int:
    QUEUE.mkdir(parents=True, exist_ok=True)
    lock = open(ROOT / "run.lock", "w")
    try:  # launchd 와 손으로 부른 run 이 겹쳐 같은 편을 두 번 올리지 않게
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another run is in progress")
        return 0
    jobs = queued()
    if any(now_utc() >= datetime.fromisoformat(j["due"]) - PREPARE_LEAD for _, j in jobs):
        c = client()
        for d, job in jobs:
            process(c, d, job)
    try:
        auto_start()
    except Exception as exc:  # 대비 실행이 게시·알림을 막지 않게
        log(f"auto_start failed: {type(exc).__name__}: {exc}")
    remind_empty(queued())
    remind_approval(queued())
    return 0


def cmd_install(_args) -> int:
    bin_dir = ROOT / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), bin_dir / "reel_queue.py")
    graph = next(p for p in (HERE / "graph.py", HERE.parent / "graph.py") if p.exists())
    if graph.resolve() != (bin_dir / "graph.py").resolve():
        shutil.copy2(graph, bin_dir / "graph.py")
    if (HERE / "lineup.json").resolve() != (bin_dir / "lineup.json").resolve():
        shutil.copy2(HERE / "lineup.json", bin_dir / "lineup.json")
    PLIST.write_bytes(plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [PYTHON, str(bin_dir / "reel_queue.py"), "run"],
        "StartInterval": 600, "RunAtLoad": True,
        "StandardOutPath": str(LOG), "StandardErrorPath": str(LOG),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", "LANG": "en_US.UTF-8"},
    }))
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)], check=True)
    print(f"설치: {bin_dir}/reel_queue.py · launchd {LABEL}(10분마다) · 로그 {LOG}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="다 만든 릴스 폴더를 큐에 넣는다(복사)")
    a.add_argument("folder")
    a.add_argument("--title", help="알림에 쓸 이름(예: 한나)")
    a.add_argument("--slug", help="큐 폴더·S3 이름(기본: 폴더 이름)")
    a.add_argument("--format", choices=sorted(FORMATS), help="형식(기본: 그 슬롯의 차례)")
    g = a.add_mutually_exclusive_group()
    g.add_argument("--slot", help="ET 날짜 YYYY-MM-DD(월·수·금). 안 주면 다음 빈 슬롯")
    g.add_argument("--at", help="시각을 직접(ISO, 시간대 포함)")
    g.add_argument("--now", action="store_true", help="지금 바로(다음 run 에서 게시)")
    a.add_argument("--no-preview", action="store_true", help="텔레그램 미리보기를 보내지 않는다")
    a.add_argument("--replace", action="store_true", help="그 슬롯의 아직 안 올라간 편을 고친 편으로 바꾼다(피드백 반영)")
    pv = sub.add_parser("preview", help="텔레그램으로 영상 미리보기")
    pv.add_argument("folder")
    pv.add_argument("--caption")
    sub.add_parser("status")
    nx = sub.add_parser("next", help="자동 제작: 앞으로 N시간 안의 아직 아무도 안 만드는 빈 슬롯(JSON)")
    nx.add_argument("--within", type=int, default=AUTO_WINDOW)
    nx.add_argument("--claim", action="store_true", help="그 슬롯을 「제작 중」으로 표시")
    nx.add_argument("--by", default="손 실행", help="누가 맡았는지(상태 표시용)")
    rl = sub.add_parser("release", help="「제작 중」 표시 지우기")
    rl.add_argument("slot", help="ET 날짜 YYYY-MM-DD")
    sub.add_parser("auto-check", help="대비 실행이 지금 무엇을 띄울지(dry)")
    ap_ = sub.add_parser("approve", help="사용자 승인(「올려」) — 그 편을 예정 시각에 올린다")
    ap_.add_argument("slot", nargs="?", help="ET 날짜 YYYY-MM-DD(없으면 가장 이른 승인 전 편)")
    ap_.add_argument("--note", help="누가·어디서 승인했는지")
    cn = sub.add_parser("cancel", help="「올리지 마」 — 큐에서 치운다(queue/replaced/)")
    cn.add_argument("slot", help="ET 날짜 YYYY-MM-DD")
    sub.add_parser("run")
    sub.add_parser("install")
    args = ap.parse_args()
    return {"add": cmd_add, "status": cmd_status, "preview": cmd_preview, "run": cmd_run, "install": cmd_install,
            "next": cmd_next, "release": cmd_release, "approve": cmd_approve, "cancel": cmd_cancel,
            "auto-check": lambda _a: auto_start(dry=True) or 0}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
