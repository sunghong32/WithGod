# -*- coding: utf-8 -*-
"""외국어 오늘의 말씀 풀이 사전 생성 → `docs/verse_picks/interpretations_intl/<lang>.tsv`.

한국어 검토본(`docs/verse_picks/interpretations.tsv`)을 바탕으로 7개 언어 풀이를 만든다.
그전에는 외국어만 운영 중에 아무 검토 없이 즉석 생성했다 — 2026-11-03 한국어 풀이를 비신자
기준으로 고친 날에도 영어 풀이는 「hand over to God」 같은 맡김 권유와 「Notice…」 예고로
끝났다. 한국어 검토본을 바탕으로 쓰게 하면 기준(기도 끝 없음, 신앙 실천 권유 없음)을 물려받고,
결과를 자동 검사(`find_intl_problems`·`find_intl_habits`)로 걸러 통과한 것만 남긴다.

    python scripts/generate_intl_interpretations.py --sample 8            # 표본만 만들어 보여 준다(저장 안 함)
    python scripts/generate_intl_interpretations.py --submit               # 빠진·낡은 행을 Batch API 로 보낸다
    python scripts/generate_intl_interpretations.py --collect msgbatch_…   # 결과를 받아 검사하고 저장(걸린 것은 --fix)
    python scripts/generate_intl_interpretations.py --fix                  # 빠진·낡은·결함 행을 즉석으로 다시 만든다
    python scripts/generate_intl_interpretations.py --check                # 생성 없이 검수표만
    python scripts/build_daily_verses.py --apply                           # 운영 파일로 반영

대량 생성은 Batch API 로 보낸다. 로컬 `backend/.env` 키는 운영과 같아서, 수천 건을 즉석으로
부르면 운영 요청과 분당 한도를 나눠 쓴다(배치는 따로 처리되고 값도 절반이다).

현지 본문은 운영과 같은 방식(`languages.localize_ko_ref` + 다국어 임베더)으로 찾는다.
TSV 형식은 `reference<TAB>바탕 지문<TAB>현지 참조<TAB>풀이`. 바탕 지문은 한국어 카드 본문과
한국어 풀이의 지문이라, 한국어 쪽을 고치면 빌드가 그 행을 낡은 것으로 보고 반영하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_daily_verses import INTL_DIR, OUT as DAILY_VERSES  # noqa: E402
from build_daily_verses import load_intl_interpretations, load_interpretations  # noqa: E402
from notifications.interpretation import (  # noqa: E402
    INTL_LANGS,
    MAX_TOKENS,
    _complete,
    find_intl_habits,
    find_intl_problems,
    generate_interpretation,
    intl_system,
    intl_user_prompt,
    tidy,
)
from notifications.verse_provider import intl_source_fingerprint  # noqa: E402

LANG_NAMES = {
    "en": "English", "es": "Spanish", "pt": "Portuguese", "de": "German",
    "fr": "French", "it": "Italian", "pl": "Polish",
}


# 마지막 문장이 한국어에는 없는 하나님 이야기를 끌어오는지. 자동 검사를 다 통과한 2,632건 중
# 34건이 「thank God for…」「turn to God with one honest request」처럼 한국어 검토 때 걷어 낸
# 신앙 실천 권유를 되살렸다. 한국어 풀이와 견줘야 알 수 있어 운영 검사가 아니라 여기서만 본다.
_GOD = {
    "en": r"\b(?:God|Lord|Jesus)\b", "es": r"\b(?:Dios|Señor|Jesús)\b", "pt": r"\b(?:Deus|Senhor|Jesus)\b",
    "de": r"\b(?:Gott\w*|Herr\w*|Jesus)\b", "fr": r"\b(?:Dieu|Seigneur|Jésus)\b",
    "it": r"\b(?:Dio|Signore|Gesù)\b", "pl": r"\b(?:Bóg|Boga|Bogu|Bogiem|Pan(?:a|u|em|ie)?|Jezus\w*)\b",
}
_KO_GOD = re.compile(r"하나님|주님|주께|예수|그분|하늘 아버지|여호와")
_CLOSING_NOTE = (
    "Your last sentence brings in God (thanking, praying, turning to or bringing something to God), "
    "but the last sentence of the Korean note does not. Rewrite the paragraph so that its last "
    "sentence does exactly what the Korean last sentence does."
)


def _last_sentence(s: str) -> str:
    parts = [p for p in re.split(r"(?<=[.!?])\s+", s.strip()) if p]
    return parts[-1] if parts else ""


def closing_adds_god(job: dict, note: str) -> bool:
    return bool(re.search(_GOD[job["lang"]], _last_sentence(note))) and not _KO_GOD.search(
        _last_sentence(job["ko_note"]))


def header(lang: str) -> str:
    return (
        f"# 오늘의 말씀 풀이(외국어 검토본, {lang}) — reference<TAB>바탕 지문<TAB>현지 참조<TAB>풀이\n"
        "# 생성: scripts/generate_intl_interpretations.py — 한국어 검토본을 바탕으로 만들고 자동 검사를 통과한 것만 남긴다.\n"
        "# 바탕 지문 = 한국어 카드 본문+풀이의 지문. 한국어 쪽이 바뀌면 build_daily_verses.py 가 반영하지 않는다.\n"
        "# 반영: python scripts/build_daily_verses.py --apply → notifications/daily_interpretations_intl.json"
    )


def _one_line(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def save(lang: str, rows: dict[str, tuple[str, str, str]], order: list[str]) -> None:
    INTL_DIR.mkdir(parents=True, exist_ok=True)
    lines = [header(lang)]
    for ref in order:
        if ref in rows:
            fp, local_ref, note = rows[ref]
            lines.append(f"{ref}\t{fp}\t{local_ref}\t{_one_line(note)}")
    (INTL_DIR / f"{lang}.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_localizer():
    """운영과 같은 정렬(번역본마다 다른 절 번호를 임베딩으로 맞춘다)을 쓰려고 스토어와 임베더를 올린다."""
    import pandas as pd

    import embedding
    import languages

    languages.register_ko_store(pd.read_parquet(ROOT / "data" / "verses_meta.parquet"), None)
    languages.set_encoder(embedding.load_query_embedder().encode)
    return languages.localize_ko_ref


def load_jobs(langs: list[str]) -> tuple[list[dict], list[str]]:
    """(언어 × 카드) 작업 목록. 각 작업에 현지 본문과 바탕이 될 한국어 검토본을 붙인다."""
    entries = json.loads(DAILY_VERSES.read_text(encoding="utf-8"))
    ko = load_interpretations()
    localize = make_localizer()
    jobs, skipped = [], []
    for e in entries:
        got = ko.get(e["reference"])
        if not got or got[0] != e["text"]:
            skipped.append(f"{e['reference']}: 한국어 검토본 없음/낡음")
            continue
        for lang in langs:
            local = localize(lang, e["reference"], e["text"])
            if not local:
                skipped.append(f"{e['reference']} ({lang}): 현지화 실패")
                continue
            jobs.append({
                "lang": lang, "verse_id": e["verse_id"], "reference": e["reference"],
                "local_ref": local["ref"], "local_text": local["text"], "ko_note": got[1],
                "fp": intl_source_fingerprint(e["text"], got[1]),
            })
    return jobs, [e["reference"] for e in entries]


def needs_work(job: dict, rows: dict[str, dict]) -> bool:
    row = rows[job["lang"]].get(job["reference"])
    return (row is None or row[0] != job["fp"] or bool(find_intl_problems(row[2], job["lang"]))
            or closing_adds_god(job, row[2]))


def request_params(job: dict, model: str, effort: str) -> dict:
    name = LANG_NAMES[job["lang"]]
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": intl_system(name),
        "messages": [{"role": "user", "content": intl_user_prompt(
            job["local_ref"], job["local_text"], name, job["ko_note"])}],
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort},
    }


def client():
    import anthropic

    from settings import load_dotenv

    load_dotenv()
    # ⚠️ 운영 서버와 같은 키다(backend/.env). 대량 생성은 --submit(Batch API)으로 보낸다.
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def generate_now(jobs: list[dict], model: str, effort: str, workers: int) -> tuple[dict, list[str]]:
    """즉석 생성(고쳐 쓰기 한 번 포함). {(lang, reference): 풀이}, 실패 목록."""
    api = client()
    out, failed = {}, []

    def work(job: dict) -> str:
        note = generate_interpretation(
            api, model, job["local_ref"], job["local_text"], lang=job["lang"],
            lang_name=LANG_NAMES[job["lang"]], reasoning_effort=effort, ko_note=job["ko_note"],
        )
        if not closing_adds_god(job, note):
            return note
        params = request_params(job, model, effort)
        messages = [{"role": "system", "content": params["system"]}, *params["messages"],
                    {"role": "assistant", "content": note}, {"role": "user", "content": _CLOSING_NOTE}]
        second = tidy(_complete(api, model, messages, effort), job["local_text"])
        ok = not find_intl_problems(second, job["lang"]) and not closing_adds_god(job, second)
        return second if ok else note

    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(work, j): j for j in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            try:
                out[(job["lang"], job["reference"])] = fut.result()
            except Exception as exc:  # noqa: BLE001 — 한 건이 실패해도 나머지는 계속 만든다
                failed.append(f"{job['reference']} ({job['lang']}): {exc}")
    return out, failed


def report(jobs: list[dict], rows: dict[str, dict]) -> None:
    by_lang = {}
    for job in jobs:
        by_lang.setdefault(job["lang"], []).append(job)
    for lang, items in by_lang.items():
        missing = stale = defects = habits = 0
        words = []
        examples = []
        for job in items:
            row = rows[lang].get(job["reference"])
            if row is None:
                missing += 1
                continue
            if row[0] != job["fp"]:
                stale += 1
            p = find_intl_problems(row[2], lang)
            h = find_intl_habits(row[2], job["local_text"], lang)
            if closing_adds_god(job, row[2]):
                h.append("closing brings in God where the Korean closing does not")
            defects += bool(p)
            habits += bool(h)
            if (p or h) and len(examples) < 5:
                examples.append(f"    [{job['reference']}] {'; '.join(p + h)}")
            words.append(len(row[2].split()))
        words.sort()
        span = f"단어 {words[0]}~{words[-1]}(중앙 {words[len(words) // 2]})" if words else ""
        print(f"{lang}: {len(items)}개 · 빠짐 {missing} · 낡음 {stale} · 결함 {defects} · 말버릇 {habits} · {span}")
        for line in examples:
            print(line)
        endings = Counter(re.sub(r"[^\w]", "", r[2].split()[-1]).lower() for r in rows[lang].values() if r[2])
        print("    끝말:", " · ".join(f"{w} {n}" for w, n in endings.most_common(6)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sample", type=int, metavar="N", help="카드 N장 × 언어를 즉석으로 만들어 보여 준다(저장 안 함)")
    mode.add_argument("--submit", action="store_true", help="빠진·낡은·결함 행을 Batch API 로 보낸다")
    mode.add_argument("--collect", metavar="BATCH_ID", help="배치 결과를 받아 검사하고 저장한다")
    mode.add_argument("--fix", action="store_true", help="빠진·낡은·결함 행을 즉석으로 다시 만든다")
    mode.add_argument("--check", action="store_true", help="생성 없이 검수표만 본다")
    ap.add_argument("--langs", default=",".join(INTL_LANGS))
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--effort", default="medium", help="생각 강도(low/medium/high)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()]
    unknown = [lang for lang in langs if lang not in INTL_LANGS]
    if unknown:
        raise SystemExit(f"모르는 언어: {unknown}")
    jobs, order = load_jobs(langs)
    rows = {lang: load_intl_interpretations(lang) for lang in langs}

    if args.check:
        report(jobs, rows)
        return 0

    if args.sample:
        refs = order[:: max(1, len(order) // args.sample)][: args.sample]
        picked = [j for j in jobs if j["reference"] in set(refs)]
        notes, failed = generate_now(picked, args.model, args.effort, args.workers)
        for job in picked:
            note = notes.get((job["lang"], job["reference"]))
            if note is None:
                continue
            flags = find_intl_problems(note, job["lang"]) + find_intl_habits(note, job["local_text"], job["lang"])
            print(f"■ {job['local_ref']} [{job['lang']}]{'  ⚠ ' + '; '.join(flags) if flags else ''}\n  {note}\n")
        for f in failed:
            print("  실패", f)
        return 0

    todo = [j for j in jobs if needs_work(j, rows)]

    if args.submit:
        if not todo:
            print("보낼 행이 없다.")
            return 0
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        batch = client().messages.batches.create(requests=[
            Request(custom_id=f"{j['lang']}_{j['verse_id']}",
                    params=MessageCreateParamsNonStreaming(**request_params(j, args.model, args.effort)))
            for j in todo
        ])
        print(f"{len(todo)}건을 배치로 보냈다 — {batch.id} ({batch.processing_status})")
        print(f"끝나면: python scripts/generate_intl_interpretations.py --collect {batch.id}")
        return 0

    if args.collect:
        api = client()
        batch = api.messages.batches.retrieve(args.collect)
        if batch.processing_status != "ended":
            c = batch.request_counts
            print(f"아직 처리 중 — 처리 중 {c.processing} · 성공 {c.succeeded} · 실패 {c.errored}")
            return 2
        by_id = {f"{j['lang']}_{j['verse_id']}": j for j in jobs}
        kept, flagged, failed = 0, [], []
        for result in api.messages.batches.results(args.collect):
            job = by_id.get(result.custom_id)
            if job is None:
                continue  # 이번 실행에서 고른 언어가 아니거나 목록에서 빠진 카드
            if result.result.type != "succeeded":
                failed.append(f"{job['reference']} ({job['lang']}): {result.result.type}")
                continue
            msg = result.result.message
            note = tidy("".join(b.text for b in msg.content if b.type == "text"), job["local_text"])
            flags = find_intl_problems(note, job["lang"]) + find_intl_habits(note, job["local_text"], job["lang"])
            if closing_adds_god(job, note):
                flags.append("closing brings in God where the Korean closing does not")
            if flags:
                flagged.append(f"{job['reference']} ({job['lang']}): {'; '.join(flags)}")
                continue  # 걸린 것은 --fix 가 고쳐 쓰기를 포함해 즉석으로 다시 만든다
            rows[job["lang"]][job["reference"]] = (job["fp"], job["local_ref"], note)
            kept += 1
        for lang in langs:
            save(lang, rows[lang], order)
        print(f"저장 {kept} · 검사에 걸림 {len(flagged)} · 실패 {len(failed)}")
        for line in (flagged + failed)[:20]:
            print("   ", line)
        if flagged or failed:
            print("→ python scripts/generate_intl_interpretations.py --fix")
        return 0

    # --fix
    if not todo:
        print("다시 만들 행이 없다.")
        report(jobs, rows)
        return 0
    print(f"{len(todo)}건 즉석 생성 — {args.model} (생각 {args.effort}), 동시 {args.workers}")
    started = time.time()
    notes, failed = generate_now(todo, args.model, args.effort, args.workers)
    for job in todo:
        note = notes.get((job["lang"], job["reference"]))
        if note:
            rows[job["lang"]][job["reference"]] = (job["fp"], job["local_ref"], note)
    for lang in langs:
        save(lang, rows[lang], order)
    print(f"완료 {len(notes)} · 실패 {len(failed)} · {time.time() - started:.0f}초")
    for f in failed[:20]:
        print("  실패", f)
    report(jobs, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
