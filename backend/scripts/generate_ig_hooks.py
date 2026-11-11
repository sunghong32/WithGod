#!/usr/bin/env python3
"""Daily Verse 인스타 카피(카드 라벨·훅·요청 한 줄·주제 해시태그)를 만든다 (이슈 #62).

말씀마다 영어 본문(앱과 같은 WEB 변환)과 앱의 영어 풀이를 주고 Claude 에 JSON 으로 받는다. 받은 문구는
`instagram/caption.py` 의 find_copy_problems(신의 목소리·사람 행세·광고·자해·줄표·상투어·길이)로 검사해
통과한 것만 `instagram/hooks_en.tsv` 에 쓴다. 걸린 것은 --fix 로 즉석에서 다시 만든다.

⚠️ backend/.env 의 ANTHROPIC_API_KEY 는 **운영 서버와 같은 키**다. 대량 생성(전부)은 사용자에게 먼저
알리고 --submit(Batch API, 반값)으로 보낸다.

    python scripts/generate_ig_hooks.py --only psa-34-18,isa-41-10   # 몇 개만 즉석 생성(시험)
    python scripts/generate_ig_hooks.py --submit                     # 빠진 것 전부 배치로
    python scripts/generate_ig_hooks.py --collect <batch_id>         # 배치 결과 반영
    python scripts/generate_ig_hooks.py --fix                        # 걸린·빠진 것 즉석으로
    python scripts/generate_ig_hooks.py --report                     # 검사·겹침만 보기
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from instagram.caption import (  # noqa: E402
    CTA_MAX, HOOK_MAX, KICKER_MAX, TOPIC_HASHTAGS, find_copy_problems,
)
from instagram.posts import (  # noqa: E402
    HOOKS_TSV, en_note, load_daily_verses, load_hooks, localize_all, save_hooks, tidy_copy,
)

MODEL = "claude-opus-5-5"
EFFORT = "low"
MAX_TOKENS = 4000
# 훅이 말씀마다 같은 틀로 찍혀 나오지 않게 순서대로 돌려 주는 형태 힌트.
SHAPES = (
    "Start the hook with “For the …” or “For when …”, naming a specific moment.",
    "Make the hook a plain, honest observation about that feeling, as one short sentence.",
    "Make the hook two very short sentences: the hard part first, then a turn toward the verse.",
    "Make the hook speak to the reader directly (“you”), about where they might be today.",
)

SYSTEM = f"""You write the short copy around a daily Bible verse card for the Instagram account @withgod.app.
The account belongs to WithGod, a Bible verse app. Readers are mostly English speakers; many are not Christians,
and some come to the account on a hard day. Each post is one card with one verse from the World English Bible.

You return four things:
1. kicker: the small label printed above the verse on the card. 2 to 5 words, at most {KICKER_MAX - 4} characters,
   naming the situation or feeling where this verse speaks. Use the account's style: “When you’re afraid”,
   “When you’re worn out”, “When your heart is broken”, “For an ordinary day”, “When nothing makes sense”.
   Sentence case, no final punctuation.
2. hook: the first line of the caption, shown before “more”. At most {HOOK_MAX - 20} characters. Plain, warm,
   specific to this verse’s moment. Examples of the voice: “For the days fear gets the first word.”,
   “Not a perfect day. Still a day worth being glad in.”
   Do not quote or paraphrase the verse (it comes on the next line). No questions that bait clicks.
3. cta: one sentence, at most {CTA_MAX - 20} characters, inviting the reader to save the post, send it to someone,
   or share in the comments, tied to the moment. Examples: “Save this for the next time fear gets loud.”,
   “Send this to someone who has been carrying a lot.” Do not mention the app, links, following, or likes.
4. topic: one hashtag from this list that fits best: {", ".join(TOPIC_HASHTAGS)}.

Rules for everything you write:
- Never speak as God or claim to pass on a message from God (“God is telling you”, “this is your sign”).
- Never write as a person or a pastor: no I, me, my, no personal stories.
- Do not assume the reader believes, prays, or goes to church. Avoid church jargon.
- No dashes of any kind between phrases (no em dash, en dash, or spaced hyphen). Use commas and periods.
- No emojis, hashtags, or @ in the kicker, hook, or cta.
- Avoid these words: journey, testament, profound, beacon, tapestry, delve, unlock, navigate, embrace.
- Do not mention suicide, self-harm, wanting to die, or ads.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "kicker": {"type": "string"},
        "hook": {"type": "string"},
        "cta": {"type": "string"},
        "topic": {"type": "string", "enum": list(TOPIC_HASHTAGS)},
    },
    "required": ["kicker", "hook", "cta", "topic"],
    "additionalProperties": False,
}


def user_prompt(job: dict) -> str:
    return (
        f"Verse ({job['ref']}, World English Bible):\n{job['text']}\n\n"
        f"The app’s note on this verse, for context only (do not copy it):\n{job['note']}\n\n"
        f"Shape for the hook: {job['shape']}"
    )


def request_params(job: dict) -> dict:
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": user_prompt(job)}],
        "output_config": {"effort": EFFORT,
                          "format": {"type": "json_schema", "schema": SCHEMA}},
    }


def client():
    import anthropic

    from settings import load_dotenv

    # 워크트리에는 backend/.env 가 없다 — WITHGOD_ENV_FILE 로 메인 체크아웃의 .env 를 가리킬 수 있다.
    load_dotenv(os.environ.get("WITHGOD_ENV_FILE") or None)
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def parse(job: dict, message) -> tuple[dict | None, list[str]]:
    if getattr(message, "stop_reason", "") == "refusal":
        return None, ["refusal"]
    text = "".join(b.text for b in message.content if b.type == "text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, ["JSON 아님"]
    row = {
        "verse_id": job["verse_id"],
        "kicker": tidy_copy(data["kicker"]).rstrip(".!"),
        "hook": tidy_copy(data["hook"]),
        "cta": tidy_copy(data["cta"]),
        "topic": data["topic"],
    }
    return row, check(row)


def check(row: dict) -> list[str]:
    problems = (
        find_copy_problems(row["kicker"], limit=KICKER_MAX, field="kicker")
        + find_copy_problems(row["hook"], limit=HOOK_MAX, field="hook")
        + find_copy_problems(row["cta"], limit=CTA_MAX, field="cta")
    )
    if row["topic"] not in TOPIC_HASHTAGS:
        problems.append(f"topic: {row['topic']}")
    return problems


def build_jobs() -> tuple[list[dict], list[str]]:
    items = load_daily_verses()
    en = localize_all(items)
    intl = json.loads(Path(__file__).resolve().parent.parent.joinpath(
        "notifications", "daily_interpretations_intl.json").read_text(encoding="utf-8"))
    jobs = []
    for i, item in enumerate(items):
        note = en_note(item["verse_id"], item["text"], intl)
        if not note:
            raise SystemExit(f"{item['reference']}: 영어 풀이 검토본이 없다")
        e = en[item["verse_id"]]
        jobs.append({"verse_id": item["verse_id"], "ref": e["ref"], "text": e["text"], "note": note,
                     "shape": SHAPES[i % len(SHAPES)]})
    return jobs, [it["verse_id"] for it in items]


def generate_now(jobs: list[dict], workers: int = 6) -> tuple[dict, list[str]]:
    api = client()
    out, failed = {}, []

    def work(job: dict) -> tuple[dict | None, list[str]]:
        for _ in range(3):  # 검사에 걸리면 두 번까지 다시 만든다
            row, problems = parse(job, api.messages.create(**request_params(job)))
            if row and not problems:
                return row, []
        return row, problems

    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(work, j): j for j in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            try:
                row, problems = fut.result()
            except Exception as exc:  # noqa: BLE001 — 한 건이 실패해도 나머지는 계속
                failed.append(f"{job['verse_id']}: {exc}")
                continue
            if problems:
                failed.append(f"{job['verse_id']}: {'; '.join(problems)}")
            else:
                out[job["verse_id"]] = row
    return out, failed


def report(rows: dict[str, dict], order: list[str]) -> None:
    missing = [v for v in order if v not in rows]
    flagged = {v: check(r) for v, r in rows.items() if check(r)}
    print(f"{len(rows)}/{len(order)}개 · 빠짐 {len(missing)} · 검사 걸림 {len(flagged)}")
    for v, p in list(flagged.items())[:10]:
        print(f"  [{v}] {'; '.join(p)}")
    if rows:
        kickers = Counter(r["kicker"] for r in rows.values())
        hooks = Counter(" ".join(r["hook"].split()[:3]) for r in rows.values())
        topics = Counter(r["topic"] for r in rows.values())
        print("  겹치는 라벨:", ", ".join(f"{k} ×{n}" for k, n in kickers.most_common(8) if n > 1) or "없음")
        print("  훅 첫 세 낱말:", ", ".join(f"{k} ×{n}" for k, n in hooks.most_common(6)))
        print("  주제:", ", ".join(f"{k} {n}" for k, n in topics.most_common()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--only", help="쉼표로 구분한 verse_id 만 즉석 생성")
    g.add_argument("--submit", action="store_true", help="빠진 것 전부 Batch API 로")
    g.add_argument("--collect", metavar="BATCH_ID")
    g.add_argument("--fix", action="store_true", help="빠지거나 검사에 걸린 것 즉석으로")
    g.add_argument("--report", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    jobs, order = build_jobs()
    rows = load_hooks()
    by_id = {j["verse_id"]: j for j in jobs}

    if args.report:
        report(rows, order)
        return 0

    if args.only:
        picked = [by_id[v.strip()] for v in args.only.split(",") if v.strip()]
        new, failed = generate_now(picked, args.workers)
    elif args.fix:
        picked = [j for j in jobs if j["verse_id"] not in rows or check(rows[j["verse_id"]])]
        print(f"{len(picked)}건 즉석 생성 — {MODEL} (effort {EFFORT})")
        new, failed = generate_now(picked, args.workers)
    elif args.submit:
        todo = [j for j in jobs if j["verse_id"] not in rows]
        if not todo:
            print("보낼 것이 없다.")
            return 0
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        batch = client().messages.batches.create(requests=[
            Request(custom_id=j["verse_id"], params=MessageCreateParamsNonStreaming(**request_params(j)))
            for j in todo
        ])
        print(f"{len(todo)}건을 배치로 보냈다 — {batch.id} ({batch.processing_status})")
        print(f"끝나면: python scripts/generate_ig_hooks.py --collect {batch.id}")
        return 0
    else:
        api = client()
        batch = api.messages.batches.retrieve(args.collect)
        if batch.processing_status != "ended":
            c = batch.request_counts
            print(f"아직 처리 중 — 처리 중 {c.processing} · 성공 {c.succeeded} · 실패 {c.errored}")
            return 2
        new, failed = {}, []
        for result in api.messages.batches.results(args.collect):
            job = by_id.get(result.custom_id)
            if job is None:
                continue
            if result.result.type != "succeeded":
                failed.append(f"{job['verse_id']}: {result.result.type}")
                continue
            row, problems = parse(job, result.result.message)
            if problems:
                failed.append(f"{job['verse_id']}: {'; '.join(problems)}")
            else:
                new[job["verse_id"]] = row

    rows.update(new)
    save_hooks(rows, order)
    print(f"반영 {len(new)}건 → {HOOKS_TSV.name}")
    for line in failed:
        print("  실패·걸림:", line)
    if failed:
        print("  → python scripts/generate_ig_hooks.py --fix")
    report(rows, order)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
