"""Play Console 트랙 출시 노트 설정 (제출 후 실행).

eas submit 은 출시 노트를 지원하지 않아, 제출 뒤 이 스크립트로 채운다.
테스터가 '무엇이 바뀌었는지' 알고 테스트할 수 있게 하는 용도(CLAUDE.md 규칙).

    python3 scripts/play_release_notes.py --track alpha --notes "..." [--lang ko-KR]

요구: pip install google-auth requests / 키: backend/secrets/play-submit-key.json
노트는 500자 제한(Play 정책).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parent.parent
KEY_PATH = ROOT / "backend" / "secrets" / "play-submit-key.json"
PACKAGE = "kr.co.mincha.withgod"
BASE = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", default="alpha")
    ap.add_argument("--notes", required=True)
    ap.add_argument("--lang", default="ko-KR")
    args = ap.parse_args()
    if len(args.notes) > 500:
        raise SystemExit(f"노트가 500자 초과({len(args.notes)}자) — Play 제한")

    creds = service_account.Credentials.from_service_account_file(
        str(KEY_PATH), scopes=["https://www.googleapis.com/auth/androidpublisher"]
    )
    creds.refresh(Request())
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {creds.token}"

    edit = s.post(f"{BASE}/edits", timeout=30).json()
    edit_id = edit["id"]

    track = s.get(f"{BASE}/edits/{edit_id}/tracks/{args.track}", timeout=30).json()
    releases = track.get("releases") or []
    if not releases:
        raise SystemExit(f"{args.track} 트랙에 릴리스가 없음")
    # 최신 릴리스(목록 첫 항목)에 노트를 단다.
    releases[0]["releaseNotes"] = [{"language": args.lang, "text": args.notes}]

    r = s.put(
        f"{BASE}/edits/{edit_id}/tracks/{args.track}",
        json={"track": args.track, "releases": releases},
        timeout=30,
    )
    r.raise_for_status()
    commit = s.post(f"{BASE}/edits/{edit_id}:commit", timeout=30)
    commit.raise_for_status()
    vc = releases[0].get("versionCodes", ["?"])
    print(f"완료: {args.track} 트랙 versionCode {vc} 에 출시 노트 설정 ({len(args.notes)}자)")


if __name__ == "__main__":
    main()
