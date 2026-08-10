"""이미 업로드된 버전코드를 다른 Play 트랙에도 배포한다.

내부 테스트(internal)는 심사가 없어 바로 받을 수 있는데, eas submit 은 프로필에
지정된 트랙 하나로만 올린다. 같은 AAB 를 다시 업로드하면 "버전코드 중복" 으로
거부되므로, **이미 올라간 버전코드를 트랙에만 추가**하는 경로가 필요하다.

    python3 scripts/play_promote_track.py --version-code 24 --track internal --notes "..."

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
    ap.add_argument("--version-code", required=True, type=int)
    ap.add_argument("--track", default="internal")
    ap.add_argument("--notes", default="")
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

    edit_id = s.post(f"{BASE}/edits", timeout=30).json()["id"]

    release: dict = {
        "versionCodes": [str(args.version_code)],
        "status": "completed",
    }
    if args.notes:
        release["releaseNotes"] = [{"language": args.lang, "text": args.notes}]

    r = s.put(
        f"{BASE}/edits/{edit_id}/tracks/{args.track}",
        json={"track": args.track, "releases": [release]},
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"실패 {r.status_code}: {r.text}")

    commit = s.post(f"{BASE}/edits/{edit_id}:commit", timeout=30)
    if not commit.ok:
        raise SystemExit(f"커밋 실패 {commit.status_code}: {commit.text}")

    print(f"완료: {args.track} 트랙에 versionCode {args.version_code} 배포")


if __name__ == "__main__":
    main()
