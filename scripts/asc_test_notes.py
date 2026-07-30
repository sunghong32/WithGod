"""TestFlight '테스트 내용'(What to Test) 자동 설정 (제출 후 실행).

eas submit 은 테스트 노트를 지원하지 않아, 제출 뒤 이 스크립트로 채운다.
테스터가 '무엇이 바뀌었는지' 알고 테스트할 수 있게 하는 용도(CLAUDE.md 규칙).

    python3 scripts/asc_test_notes.py --notes "..." [--build 30] [--wait]

- --build 없이 실행하면 가장 최근 업로드된 빌드에 설정한다.
- --wait 를 주면 빌드가 애플 처리(PROCESSING) 중일 때 최대 20분 폴링한다.

요구: pip install pyjwt cryptography requests
키: backend/secrets/AuthKey_<KeyID>.p8 + asc-api-key.json ({issuerId, keyId})
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import jwt
import requests

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "backend" / "secrets"
APP_ID = "6757704775"
BASE = "https://api.appstoreconnect.apple.com/v1"


def make_token() -> str:
    config = json.loads((SECRETS / "asc-api-key.json").read_text())
    key = (SECRETS / f"AuthKey_{config['keyId']}.p8").read_text()
    now = int(time.time())
    return jwt.encode(
        {"iss": config["issuerId"], "iat": now, "exp": now + 15 * 60,
         "aud": "appstoreconnect-v1"},
        key,
        algorithm="ES256",
        headers={"kid": config["keyId"], "typ": "JWT"},
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", required=True)
    ap.add_argument("--build", help="빌드 번호(CFBundleVersion). 생략 시 최신 빌드")
    ap.add_argument("--locale", default="ko")
    ap.add_argument("--wait", action="store_true", help="처리 중이면 최대 20분 대기")
    args = ap.parse_args()

    s = requests.Session()

    def auth() -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token()}"}

    deadline = time.time() + 20 * 60
    while True:
        params = {"filter[app]": APP_ID, "sort": "-uploadedDate", "limit": "5"}
        if args.build:
            params["filter[version]"] = args.build
        builds = s.get(f"{BASE}/builds", params=params, headers=auth(), timeout=30).json()
        if not builds.get("data"):
            # 방금 제출한 빌드는 애플 인제스트 전이라 목록에 늦게 나타난다
            if args.wait and time.time() < deadline:
                print("빌드가 아직 목록에 없음 — 대기")
                time.sleep(60)
                continue
            raise SystemExit(f"빌드를 찾을 수 없음: {builds.get('errors')}")
        build = builds["data"][0]
        state = build["attributes"]["processingState"]
        print(f"빌드 {build['attributes']['version']} 상태: {state}")
        if state == "VALID":
            break
        if state in ("FAILED", "INVALID"):
            raise SystemExit("빌드 처리 실패 상태 — 노트를 설정할 수 없음")
        if not args.wait or time.time() > deadline:
            raise SystemExit("아직 애플 처리 중 — --wait 로 대기하거나 잠시 후 재시도")
        time.sleep(60)

    build_id = build["id"]
    existing = s.get(
        f"{BASE}/builds/{build_id}/betaBuildLocalizations",
        headers=auth(), timeout=30,
    ).json().get("data", [])
    match = [l for l in existing if l["attributes"].get("locale") == args.locale]

    if match:
        r = s.patch(
            f"{BASE}/betaBuildLocalizations/{match[0]['id']}",
            headers={**auth(), "Content-Type": "application/json"},
            json={"data": {"type": "betaBuildLocalizations", "id": match[0]["id"],
                           "attributes": {"whatsNew": args.notes}}},
            timeout=30,
        )
    else:
        r = s.post(
            f"{BASE}/betaBuildLocalizations",
            headers={**auth(), "Content-Type": "application/json"},
            json={"data": {"type": "betaBuildLocalizations",
                           "attributes": {"locale": args.locale, "whatsNew": args.notes},
                           "relationships": {"build": {"data": {"type": "builds", "id": build_id}}}}},
            timeout=30,
        )
    if r.status_code >= 300:
        raise SystemExit(f"실패 {r.status_code}: {r.text[:300]}")
    print(f"완료: 빌드 {build['attributes']['version']} 테스트 내용 설정 ({len(args.notes)}자)")


if __name__ == "__main__":
    main()
