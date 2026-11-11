"""런칭 게시물을 인스타 공식 Content Publishing API 로 올린다.

  python3 docs/instagram/tools/post_launch.py prepare <slug>...   # 컨테이너만 만들고 FINISHED 확인(공개 안 됨)
  python3 docs/instagram/tools/post_launch.py publish <slug>...   # 적은 순서대로 공개
  python3 docs/instagram/tools/post_launch.py schedule 2026-11-12T22:00 <slug>...   # 예약 묶음 추가(캡션·이미지 주소를 미리 굳혀 둔다)
  python3 docs/instagram/tools/post_launch.py due [--dry] [--now 2026-11-12T22:05]   # 시간이 된 묶음 하나를 올리고 텔레그램 알림

`due` 는 launchd(~/Library/LaunchAgents/com.minsunghong.withgod-ig-launch.plist)가 예약 시각에 부른다.
이미지는 공개 레포 raw URL 로 넘긴다(PNG 도 받음). 컨테이너는 24시간 뒤 만료.
"""
import json, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCH = ROOT / "docs/instagram/launch"
STATE = LAUNCH / "posted.json"        # 컨테이너·게시 id(공개 정보)
SCHEDULE = LAUNCH / "schedule.json"   # 예약 묶음
NOTIFY = ROOT / "scripts/tg-notify.sh"
LOG = Path.home() / "Library/Logs/withgod-ig-launch.log"
SHA = "eb25c85"  # 이미지가 들어 있는 푸시된 커밋 — 이미지를 다시 만들면 커밋·푸시 후 바꾼다
RAW = f"https://raw.githubusercontent.com/sunghong32/WithGod/{SHA}/docs/instagram/launch"
BASE = "https://graph.facebook.com/v23.0"

CFG = json.load(open(ROOT / "backend/secrets/instagram.json"))  # gitignore — 토큰은 출력하지 않는다
TOKEN = CFG["access_token"]
IG = CFG["ig_user_id"]

state = json.loads(STATE.read_text()) if STATE.exists() else {}


def save():
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False))


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{BASE}/{path}"
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "body": e.read().decode().replace(TOKEN, "***")}
    except urllib.error.URLError as e:
        return {"_url_error": str(e.reason)}


def build_item(slug):
    """생성기에서 캡션·대체 텍스트·이미지 주소를 뽑는다(PIL 이 필요해서 필요할 때만 import)."""
    import make_launch_posts as m
    p = next(p for p in m.build_posts() if p["slug"] == slug)
    n = len(p["slides"])
    return {"slug": slug, "title": p["title"], "caption": p["caption"],
            "images": [f"{RAW}/{slug}/{i:02d}.png" for i in range(1, n + 1)],
            "alts": [m.alt_text(s) for s in p["slides"]]}


def wait(cid):
    r = {}
    for _ in range(40):
        r = call("GET", cid, fields="status_code,status")
        if r.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"):
            return r
        time.sleep(3)
    return r


def media(**kw):
    r = call("POST", f"{IG}/media", **kw)
    if "_http_error" in r and "alt_text" in kw:          # alt_text 를 안 받으면 빼고 다시
        print("  alt_text 거절 → 빼고 다시:", r["body"][:200])
        kw.pop("alt_text")
        r = call("POST", f"{IG}/media", **kw)
    return r


def prepare(it):
    slug = it["slug"]
    if "media_id" in state.get(slug, {}):
        print(slug, "이미 게시됨 — 건너뜀")
        return True
    if len(it["images"]) == 1:
        r = media(image_url=it["images"][0], caption=it["caption"], alt_text=it["alts"][0])
    else:
        kids = []
        for u, a in zip(it["images"], it["alts"]):
            k = media(image_url=u, is_carousel_item="true", alt_text=a)
            if "id" not in k:
                print(slug, "자식 실패", k)
                return False
            w = wait(k["id"])
            if w.get("status_code") != "FINISHED":
                print(slug, "자식 처리 실패", u, w)
                return False
            kids.append(k["id"])
        r = call("POST", f"{IG}/media", media_type="CAROUSEL", children=",".join(kids), caption=it["caption"])
    if "id" not in r:
        print(slug, "컨테이너 실패", r)
        return False
    w = wait(r["id"])
    print(slug, "컨테이너", r["id"], w)
    if w.get("status_code") != "FINISHED":
        return False
    state[slug] = {"container": r["id"]}
    save()
    return True


def publish(slug):
    s = state[slug]
    if "media_id" in s:
        print(slug, "이미 게시됨", s.get("permalink"))
        return s.get("permalink")
    r = call("POST", f"{IG}/media_publish", creation_id=s["container"])
    if "id" not in r:
        print(slug, "게시 실패", r)
        return None
    info = call("GET", r["id"], fields="permalink,timestamp,media_type")
    s.update(media_id=r["id"], permalink=info.get("permalink"), timestamp=info.get("timestamp"))
    save()
    print(slug, "게시됨", info.get("permalink"))
    return info.get("permalink") or f"(media {r['id']})"


def notify(msg, dry=False):
    print("[텔레그램]" + (" (보내지 않음)" if dry else ""), msg.replace("\n", " / "))
    if not dry:
        subprocess.run([str(NOTIFY), msg], check=False)


def schedule(at, slugs):
    datetime.fromisoformat(at)  # 형식 확인
    batches = json.loads(SCHEDULE.read_text()) if SCHEDULE.exists() else []
    batches.append({"at": at, "posts": [build_item(s) for s in slugs]})
    batches.sort(key=lambda b: b["at"])
    SCHEDULE.write_text(json.dumps(batches, indent=1, ensure_ascii=False))
    print("예약:", at, slugs)


def due(now, dry=False):
    batches = json.loads(SCHEDULE.read_text()) if SCHEDULE.exists() else []
    todo = [b for b in batches if not all("media_id" in state.get(it["slug"], {}) for it in b["posts"])]
    print(now.isoformat(timespec="minutes"), "남은 묶음", len(todo))
    if not todo:
        return
    b = todo[0]
    slugs = [it["slug"] for it in b["posts"]]
    if datetime.fromisoformat(b["at"]) > now:
        print("아직 시간 전:", b["at"], slugs)
        return
    if dry:
        print("지금 올릴 묶음:", b["at"], slugs)
    else:
        # 묶음 전체 컨테이너를 먼저 만들어 두고, 하나라도 실패하면 아무것도 공개하지 않는다
        if not all(prepare(it) for it in b["posts"]):
            return notify(f"⚠️ 인스타 예약 게시 실패({b['at']}): 컨테이너 준비 단계 — 아무것도 공개되지 않았습니다. 로그 {LOG}")
        for i, it in enumerate(b["posts"]):
            if not publish(it["slug"]):
                return notify(f"⚠️ 인스타 예약 게시가 {it['slug']} 에서 멈췄습니다({i}개 올라감). 로그 {LOG}")
            time.sleep(5)
    lines = [f"📸 인스타 예약 게시 {len(b['posts'])}개 올렸습니다 ({b['at'].replace('T', ' ')})"]
    for it in b["posts"]:
        lines.append(f"· {it['title']}\n  {state.get(it['slug'], {}).get('permalink', '(테스트)')}")
    lines.append("스토리 공유: 링크 열기 → 보내기(종이비행기) → 스토리에 추가 → 내 스토리")
    if len(todo) == 1:
        lines.append("📌 런칭 9개 끝. 이제 03 잠 못 드는 밤 → 02 사용법 → 01 소개 순서로 ⋯ → 「프로필에 고정」 해 주세요.")
    notify("\n".join(lines), dry=dry)


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "prepare":
        for slug in args:
            prepare(build_item(slug))
    elif cmd == "publish":
        for slug in args:
            publish(slug)
            time.sleep(5)
    elif cmd == "schedule":
        schedule(args[0], args[1:])
    elif cmd == "due":
        now = datetime.fromisoformat(args[args.index("--now") + 1]) if "--now" in args else datetime.now()
        due(now, dry="--dry" in args)
    else:
        sys.exit(__doc__)
