#!/usr/bin/env python3
"""Daily Verse 인스타 캐러셀을 미리 만든다 — 슬라이드 렌더 + 문구 검사 + S3 업로드 + 매니페스트 (이슈 #62).

이 맥에서만 돈다(Chrome 헤드리스로 슬라이드를 찍는다). 운영 서버는 결과물(매니페스트 + S3 이미지)만 쓴다.

    python scripts/build_ig_daily_posts.py --only pro-10-25,mat-6-28   # 몇 개만 찍고 캡션 출력(시험)
    python scripts/build_ig_daily_posts.py                              # 카피가 있는 말씀 전부 + 매니페스트
    python scripts/build_ig_daily_posts.py --upload                     # + S3 에 없는 슬라이드 올리기

한 게시물 = 그림 표지 + 말씀 + 그림 설명 + 앱 풀이 카드(장면이 카피에 있을 때). 장면이 없으면 말씀 카드가
표지다. 수·일요일에 붙는 앱 안내 장은
한 장만 만들어 매니페스트 `app_slide` 에 두고 실행기가 그날 끝에 붙인다.

재료: 목록(daily_verses.json) · 영어 본문(앱과 같은 변환) · 영어 풀이 검토본 · 카피(instagram/copy_en.json)
· 장면 그림(instagram/build/art/, git 제외 — 출처는 instagram/art_sources.json).
슬라이드는 `instagram/build/slides/` 에 쌓인다. S3 키는 슬라이드 내용 지문이라 바뀐 장만 새로 올라간다.
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

from instagram.caption import build_caption, find_post_problems, find_slide_problems  # noqa: E402
from instagram.posts import (  # noqa: E402
    MANIFEST, en_note, image_key, load_copy, load_daily_verses, localize_all, manifest_entry, tidy_copy,
)

INSTAGRAM = Path(__file__).resolve().parent.parent / "instagram"
BUILD_DIR = INSTAGRAM / "build"
SLIDES_DIR = BUILD_DIR / "slides"
ART_DIR = BUILD_DIR / "art"
# 슬라이드 틀(card.py 의 CSS·HTML)을 바꾸면 올린다 — 지문이 바뀌어 모든 장을 다시 올린다.
TEMPLATE_VERSION = "3"
DEFAULT_BUCKET = "with-god-ig-cards"
S3_REGION = "ap-northeast-2"
NOTE_LABEL = "what it can mean today"
NOTE_SOURCE = "The WithGod app’s note on this verse, written with AI"
APP_SLIDE = {
    "kind": "app", "pal": "brand",
    "headline": "Tell it how you feel. *It finds the verse.*",
    "body": "WithGod searches the whole Bible for verses that speak to what you’re going through.",
    "extra": "Free on iPhone, iPad and Android",
}
APP_ALT = ("Tell it how you feel. It finds the verse. WithGod searches the whole Bible for verses that speak "
           "to what you’re going through. Link in bio. Free on iPhone, iPad and Android.")


def slides_for(entry: dict, copy: dict) -> list[tuple[dict, str]]:
    """(슬라이드, 대체 텍스트) 목록 — 장면이 있으면 그림 표지 + 말씀 + 그림 설명(글만) + 앱 풀이 카드,
    없으면 말씀 + 앱 풀이 카드. 그리드·피드에 먼저 보이는 장이 그림이어야 흔한 말씀 카드 계정과 구별된다."""
    pal = copy["pal"]
    verse = ({"kind": "verse", "pal": pal, "label": copy["label"], "text": entry["text"],
              "emph": copy["emph"], "ref": entry["display_ref"]}, entry["alt_text"])
    out = []
    scene = copy.get("scene")
    if scene:
        art = ART_DIR / scene["art"]
        if not art.exists():
            raise FileNotFoundError(f"그림 없음: {art}")
        label = tidy_copy(copy["label"])
        out.append(({"kind": "cover", "pal": pal, "label": label, "ref": entry["display_ref"], "art": str(art),
                     "focus": scene.get("focus", "50% 50%")},
                    f"{scene['alt']} Text: {label[:1].lower() + label[1:]}. {entry['display_ref']}."))
        out.append(verse)
        out.append(({"kind": "scene", "pal": pal, "label": scene["label"], "body": scene["body"],
                     "credit": scene["credit"]}, f"{scene['label'].capitalize()}: {scene['body']}"))
    else:
        out.append(verse)
    out.append(({"kind": "note", "pal": pal, "label": NOTE_LABEL, "body": tidy_copy(entry["note"]), "source": NOTE_SOURCE},
                f"What it can mean today, from the WithGod app’s note on this verse (written with AI): {entry['note']}"))
    for i, (slide, _) in enumerate(out):
        slide["arrow"] = i < len(out) - 1
    return out


def slide_digest(slide: dict) -> str:
    h = hashlib.sha256((TEMPLATE_VERSION + json.dumps(slide, sort_keys=True, ensure_ascii=False)).encode())
    if slide.get("art"):
        h.update(Path(slide["art"]).read_bytes())
    return h.hexdigest()


def upload(files: dict[str, Path], bucket: str) -> int:
    """{S3 키: 로컬 파일} 중 S3 에 없는 것만 올린다."""
    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client("s3", region_name=S3_REGION)
    sent = 0
    for key, path in files.items():
        try:
            s3.head_object(Bucket=bucket, Key=key)
            continue  # 같은 지문 = 같은 장이 이미 있다
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("404", "NoSuchKey", "NotFound"):
                raise
        s3.upload_file(str(path), bucket, key,
                       ExtraArgs={"ContentType": "image/jpeg", "CacheControl": "public, max-age=31536000"})
        sent += 1
    return sent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="쉼표로 구분한 verse_id 만(매니페스트는 건드리지 않는다)")
    ap.add_argument("--upload", action="store_true", help="S3 에 없는 슬라이드를 올린다")
    ap.add_argument("--bucket", default=os.environ.get("IG_S3_BUCKET", DEFAULT_BUCKET))
    ap.add_argument("--no-render", action="store_true", help="이미 찍어 둔 슬라이드를 쓴다")
    ap.add_argument("--sheets", action="store_true", help="게시물별 한눈에 보기(build/sheets/)")
    args = ap.parse_args()

    items = load_daily_verses()
    copies = load_copy()
    only = [v.strip() for v in args.only.split(",")] if args.only else None
    if only:
        unknown = set(only) - {i["verse_id"] for i in items}
        if unknown:
            raise SystemExit(f"목록에 없는 verse_id: {sorted(unknown)}")
    stale = set(copies) - {i["verse_id"] for i in items}
    if stale:
        print(f"참고: 목록에서 빠진 말씀의 카피 {len(stale)}개 — {sorted(stale)[:5]}")
    en = localize_all(items)
    intl = json.loads((Path(__file__).resolve().parent.parent / "notifications" /
                       "daily_interpretations_intl.json").read_text(encoding="utf-8"))

    entries, jobs, files, problems = {}, [], {}, []
    for item in items:
        vid = item["verse_id"]
        if (only and vid not in only) or vid not in copies:
            continue
        note = en_note(vid, item["text"], intl)
        if not note:
            problems.append(f"{vid} 영어 풀이 없음")
            continue
        copy = copies[vid]
        e = manifest_entry(item, en[vid], copy, note)
        if copy["emph"] not in e["text"]:
            problems.append(f"{vid} emph: 본문에 없는 구절")
        problems += [f"{vid} {p}" for p in find_post_problems(e) + find_slide_problems(copy)]
        try:
            slides = slides_for(e, copy)
        except FileNotFoundError as exc:
            problems.append(f"{vid} {exc}")
            continue
        e["images"], e["alt_texts"] = [], []
        for n, (slide, alt) in enumerate(slides, 1):
            key = image_key(f"{vid}-{n}", slide_digest(slide))
            path = SLIDES_DIR / f"{vid}-{n}.jpg"
            jobs.append((slide, path))
            files[key] = path
            e["images"].append(key)
            e["alt_texts"].append(alt[:1000])
        entries[vid] = e
    if problems:
        print(f"문제 {len(problems)}건:")
        for p in problems[:60]:
            print("  ", p)
        return 1

    app_path = SLIDES_DIR / "app.jpg"
    app_key = image_key("app", slide_digest(APP_SLIDE))
    jobs.append((APP_SLIDE, app_path))
    files[app_key] = app_path

    if not args.no_render:
        from instagram.card import render_slides

        print(f"{len(entries)}개 게시물 · {len(jobs)}장 렌더 → {SLIDES_DIR}")
        render_slides(jobs)
    if args.sheets:
        from instagram.card import sheet

        (BUILD_DIR / "sheets").mkdir(parents=True, exist_ok=True)
        for vid, e in entries.items():
            sheet([SLIDES_DIR / f"{vid}-{n}.jpg" for n in range(1, len(e["images"]) + 1)],
                  BUILD_DIR / "sheets" / f"{vid}.jpg")
        print("한눈에 보기:", BUILD_DIR / "sheets")

    if args.upload:
        print(f"S3 업로드 {upload(files, args.bucket)}장 (s3://{args.bucket}/cards/)")
    if only:
        for vid, e in entries.items():
            print(f"\n===== {vid} · {e['display_ref']} · {len(e['images'])}장")
            print(build_caption(hook=e["hook"], verse_text=e["text"], ref=e["display_ref"],
                                cta=e["cta"], topic=e["topic"]))
        return 0

    MANIFEST.write_text(json.dumps({
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "template_version": TEMPLATE_VERSION,
        "app_slide": {"image": app_key, "alt_text": APP_ALT},
        "posts": entries,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"매니페스트 {len(entries)}개(목록 {len(items)}개 중) → {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
