#!/usr/bin/env python3
"""Daily Verse 인스타 게시물 376개를 미리 만든다 — 카드 렌더 + 캡션 검사 + S3 업로드 + 매니페스트 (이슈 #62).

이 맥에서만 돈다(Chrome 헤드리스로 카드를 찍는다). 운영 서버는 결과물(매니페스트 + S3 이미지)만 쓴다.

    python scripts/build_ig_daily_posts.py --only psa-34-18,isa-41-10   # 몇 장만 찍고 캡션 출력(시험)
    python scripts/build_ig_daily_posts.py                              # 전부 찍고 매니페스트 갱신
    python scripts/build_ig_daily_posts.py --upload                     # + S3 에 없는 카드 올리기

재료: 목록(daily_verses.json) · 영어 본문(앱과 같은 변환) · 영어 풀이 검토본 · 카피(instagram/hooks_en.tsv).
카드 이미지는 `instagram/build/`(git 제외)에 쌓인다. S3 키는 카드 내용 지문이라 바뀐 카드만 새로 올라간다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from instagram.caption import build_caption, find_post_problems  # noqa: E402
from instagram.posts import (  # noqa: E402
    MANIFEST, en_note, image_key, load_daily_verses, load_hooks, localize_all, manifest_entry,
)

BUILD_DIR = Path(__file__).resolve().parent.parent / "instagram" / "build"
# 카드 틀(card.py 의 CSS·HTML)을 바꾸면 올린다 — 지문이 바뀌어 모든 카드를 다시 올린다.
TEMPLATE_VERSION = "1"
DEFAULT_BUCKET = "with-god-ig-cards"
S3_REGION = "ap-northeast-2"


def card_digest(entry: dict) -> str:
    raw = "|".join([TEMPLATE_VERSION, entry["kicker"], entry["text"], entry["display_ref"]])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upload(entries: dict[str, dict], bucket: str) -> int:
    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client("s3", region_name=S3_REGION)
    sent = 0
    for vid, e in entries.items():
        try:
            s3.head_object(Bucket=bucket, Key=e["image"])
            continue  # 같은 지문 = 같은 카드가 이미 있다
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("404", "NoSuchKey", "NotFound"):
                raise
        s3.upload_file(str(BUILD_DIR / f"{vid}.jpg"), bucket, e["image"],
                       ExtraArgs={"ContentType": "image/jpeg", "CacheControl": "public, max-age=31536000"})
        sent += 1
    return sent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="쉼표로 구분한 verse_id 만(매니페스트는 건드리지 않는다)")
    ap.add_argument("--upload", action="store_true", help="S3 에 없는 카드를 올린다")
    ap.add_argument("--bucket", default=os.environ.get("IG_S3_BUCKET", DEFAULT_BUCKET))
    ap.add_argument("--no-render", action="store_true", help="이미 찍어 둔 카드를 쓴다")
    ap.add_argument("--grid", type=Path, help="프로필 그리드 미리보기 PNG 경로")
    args = ap.parse_args()

    items = load_daily_verses()
    only = [v.strip() for v in args.only.split(",")] if args.only else None
    if only:
        unknown = set(only) - {i["verse_id"] for i in items}
        if unknown:
            raise SystemExit(f"목록에 없는 verse_id: {sorted(unknown)}")
    en = localize_all(items)
    hooks = load_hooks()
    intl = json.loads((Path(__file__).resolve().parent.parent / "notifications" /
                       "daily_interpretations_intl.json").read_text(encoding="utf-8"))

    entries, problems = {}, []
    for item in items:
        vid = item["verse_id"]
        if only and vid not in only:
            continue
        if vid not in hooks:
            problems.append(f"{vid} 카피 없음(scripts/generate_ig_hooks.py)")
            continue
        note = en_note(vid, item["text"], intl)
        if not note:
            problems.append(f"{vid} 영어 풀이 없음")
            continue
        e = manifest_entry(item, en[vid], hooks[vid], note)
        e["image"] = image_key(vid, card_digest(e))
        problems += [f"{vid} {p}" for p in find_post_problems(e)]
        entries[vid] = e
    if problems:
        print(f"문제 {len(problems)}건:")
        for p in problems[:40]:
            print("  ", p)
        return 1

    if not args.no_render:
        from instagram.card import grid_preview, render_cards

        cards = [{"name": vid, "kicker": e["kicker"], "text": e["text"], "ref": e["display_ref"]}
                 for vid, e in entries.items()]
        print(f"{len(cards)}장 렌더 → {BUILD_DIR}")
        render_cards(cards, BUILD_DIR)
    if args.grid:
        from instagram.card import grid_preview

        grid_preview([BUILD_DIR / f"{vid}.jpg" for vid in entries], args.grid)
        print("그리드 미리보기:", args.grid)

    if args.upload:
        print(f"S3 업로드 {upload(entries, args.bucket)}장 (s3://{args.bucket}/cards/)")
    if only:
        for vid, e in entries.items():
            print(f"\n===== {vid} · {e['display_ref']} · {BUILD_DIR / (vid + '.jpg')}")
            print(build_caption(hook=e["hook"], verse_text=e["text"], ref=e["display_ref"],
                                note=e["note"], cta=e["cta"], topic=e["topic"]))
        return 0

    MANIFEST.write_text(json.dumps({
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "template_version": TEMPLATE_VERSION,
        "posts": entries,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"매니페스트 {len(entries)}개 → {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
