"""위로의 말씀 — 후보 선별과 카드별 코멘트 프롬프트.

/recommend/stream 흐름: 질의 확장 → 임베딩 검색(languages.collect_candidates, 후보마다 앞뒤 절)
→ select_verses(LLM 이 후보 번호를 고른다) → 카드마다 build_single_comment_prompt 로 코멘트.

임베딩 검색은 낱말이 겹치는 절을 물어온다. 2026-11-25 「가족과 보낼 추수감사절이 두렵다」에
에스겔 21:17(칼 심판 신탁의 끝 「내 분노를 다하리라」)과 욥기 31:34(「내가 죄를 숨겼다면」 하는
결백 맹세의 조건절, 본문에 'families')가 매번 상위 5위 안에 들었고, 선별이 가끔 그것을 골랐다.
코멘트는 욥기 31:34 를 「욥의 고백」으로 풀어 뜻을 뒤집었다. 그래서 선별은 앞뒤 절을 보고
부적합 후보를 먼저 적어 낸 뒤(excluded) 나머지에서 고르고, 코멘트에는 조건절·화자를 틀리게
단정하지 말라는 규칙을 둔다.
"""
from __future__ import annotations

import json
import logging
from typing import List

import llm
from languages import LANGUAGE_NAMES_EN

log = logging.getLogger("with-god")


def _clip(s: str, n: int) -> str:
    return (s[:n] + "…") if len(s) > n else s


def _clip_tail(s: str, n: int) -> str:
    """앞 절은 끝부분이 이음새라 뒤쪽을 남긴다."""
    return ("…" + s[-n:]) if len(s) > n else s


# ---------- 선별 ----------

SELECT_SYSTEM = (
    "너는 사용자의 감정·상황에 맞는 성경 구절을 고르는 목회적 도우미다. "
    "고른 구절은 그 절 하나만 카드에 떼어 보여 주고 아래에 위로의 글을 붙인다. "
    "후보가 한국어가 아닐 수도 있다.\n\n"
    "먼저 excluded 에 '카드로 떼어 보여 주면 안 되는' 후보만 적는다. 아래 다섯 중 하나에 분명히 "
    "해당하는 것뿐이고, 애매하거나 단지 덜 어울리는 후보는 적지 않는다.\n"
    "1. 심판·진노·저주·멸망의 선언 — 하나님이 벌을 내리거나 원수를 치시는 말. 쉼·평안 같은 낱말이 "
    "있어도 심판 신탁 안의 말이면 해당한다(예: 에스겔 21:17 「내 분노를 다하리라」, "
    "'I will cause my wrath to rest').\n"
    "2. 떼어 놓으면 뜻이 뒤집히는 문장 토막 — 조건절·결백 맹세(「내가 …하였다면」)나 그 조건에 매달린 "
    "이유절, 반어 질문이나 논증의 한 토막(예: 욥기 31:33-34 는 「내가 죄를 숨겼다면」 하는 결백 맹세의 "
    "조건이지 고백이 아니다). 앞 절과 이어진 문장이라도 그 절만으로 뜻이 온전하면 해당하지 않는다"
    "(예: 로마서 12:12 「소망 중에 즐거워하며 환난 중에 참으며」).\n"
    "3. 사람을 꾸짖는 책망·규탄, 율법 조문, 족보·명단(예: 「평강하다 평강하다 하나 평강이 없도다」).\n"
    "4. 성경이 옳다고 하지 않는 말 — 악인·유혹자·어리석은 자의 대사, 욥의 세 친구의 훈계, "
    "죽음을 바라는 탄식.\n"
    "5. 낱말만 겹쳐 이 사람의 상처를 건드리는 말 — 본래 특정한 사람에게 한 당부·명령이 지금 이 사람에게 "
    "하는 말처럼 들려 아프게 하는 것(예: 어머니를 여읜 사람에게 「네 어미를 즐겁게 하라」, 가족에게 "
    "거절당한 사람에게 혼인 시편의 「네 아비 집을 잊어버릴지어다」).\n"
    "시편의 탄식과 기도, 「두려워 말라 내가 너와 함께 함이라」 같은 약속, 소망을 붙드는 고백은 "
    "여기에 해당하지 않는다.\n\n"
    "그다음 picks 에 excluded 가 아닌 후보 중 가장 잘 맞는 것을 고른다. 낱말이 겹치는 구절보다 "
    "의미와 정서가 통하는 구절, 지금 이 사람에게 위로·소망·힘이 되는 구절을 먼저 고른다"
    "(예: '가족'이라는 낱말이 나와도 다른 이야기를 하는 구절보다, 두려움에 답하는 구절)."
)

PICKS_SCHEMA = {
    "type": "object",
    # 키 순서가 출력 순서다 — excluded 를 먼저 적게 해야 걸러 낸 뒤에 고른다.
    "properties": {
        "excluded": {"type": "array", "items": {"type": "integer"}},
        "picks": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["excluded", "picks"],
    "additionalProperties": False,
}


def _candidate_line(n: int, c: dict) -> str:
    ctx = c.get("context") or {}
    line = f"{n}. {c['ref']} :: {_clip(str(c['text']), 160)}"
    if ctx.get("continues"):
        line += " (앞 절에서 이어지는 문장)"
    if ctx.get("before"):
        line += f"\n   앞: {_clip_tail(str(ctx['before']), 100)}"
    if ctx.get("after"):
        line += f"\n   뒤: {_clip(str(ctx['after']), 100)}"
    return line


def build_select_prompt(mood: str, candidates: List[dict], picks: int) -> str:
    listed = "\n".join(_candidate_line(n + 1, c) for n, c in enumerate(candidates))
    return (
        f'사용자 입력: "{mood}"\n\n'
        f"후보 구절({len(candidates)}개). 「앞」「뒤」는 같은 장의 앞뒤 절로, 문맥을 판단하는 데만 쓴다:\n"
        f"{listed}\n\n"
        "excluded 에는 위 1~5 에 분명히 해당하는 후보 번호만 적어라(없으면 빈 목록). "
        f"picks 에는 excluded 가 아닌 후보 중 사용자 입력의 감정·상황에 가장 잘 어울리는 {picks}개를 "
        "가장 잘 맞는 순서대로 적어라."
    )


def pick_from_response(parsed, candidates: List[dict], picks: int) -> List[dict]:
    """LLM 응답(번호)을 후보로 바꾼다. excluded 로 적힌 후보는 picks 에 있어도 버리고,
    모자라면 excluded 가 아닌 후보를 유사도 순으로 채운다. 그래도 하나도 없으면 빈 목록."""
    if not isinstance(parsed, dict):
        parsed = {"picks": parsed}
    excluded: set[int] = set()
    for n in parsed.get("excluded") or []:
        try:
            excluded.add(int(n) - 1)
        except (TypeError, ValueError):
            continue
    selected: List[dict] = []
    seen: set[int] = set()
    for n in parsed.get("picks") or []:
        try:
            idx = int(n) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(candidates) and idx not in seen and idx not in excluded:
            seen.add(idx)
            selected.append(candidates[idx])
        if len(selected) >= picks:
            break
    for i, c in enumerate(candidates):
        if len(selected) >= picks:
            break
        if i not in seen and i not in excluded:
            seen.add(i)
            selected.append(c)
    return selected


def select_verses(mood: str, candidates: List[dict], picks: int) -> List[dict]:
    """후보 중 사용자 입력의 '의미·정서'에 맞는 picks개를 LLM 이 고른다.

    유사도 상위를 그대로 확정하지 않고, 넓게 뽑은 후보를 앞뒤 절과 함께 보여 주어
    부적합한 것(심판·문장 토막·책망·악인의 말·낱말만 겹침)을 먼저 적어 내게 한 뒤 고른다.
    호출이 실패하면 유사도 상위 picks개로 폴백한다.
    """
    fallback = candidates[:picks]
    if not llm.configured() or len(candidates) <= picks:
        return fallback
    user = build_select_prompt(mood, candidates, picks)
    try:
        parsed = json.loads(llm.complete_json(SELECT_SYSTEM, user, max_tokens=200, schema=PICKS_SCHEMA))
    except Exception:
        log.exception("verse selection failed; fallback to top-k")
        return fallback
    selected = pick_from_response(parsed, candidates, picks)
    excluded = [
        candidates[int(n) - 1]["ref"]
        for n in (parsed.get("excluded") or [] if isinstance(parsed, dict) else [])
        if isinstance(n, int) and 1 <= n <= len(candidates)
    ]
    if excluded:
        log.info("선별에서 제외한 후보 %d개: %s", len(excluded), ", ".join(excluded))
    if not selected:
        # 후보가 모두 부적합으로 적힌 극단. 빈 화면보다는 유사도 상위를 보인다.
        log.warning("선별이 후보 %d개를 모두 제외함 — 유사도 상위로 폴백", len(candidates))
        return fallback
    if len(selected) < picks:
        # 부적합을 채워 3장을 맞추기보다 적게 보낸다(앱은 받은 만큼 그린다). 11/25 시험 36회 중 1회.
        log.info("선별 뒤 남은 후보가 모자라 %d장만 보냄", len(selected))
    return selected


# ---------- 카드별 코멘트 ----------

# 비한국어 프롬프트의 tag 예시(대상 언어로 줘야 tag 도 그 언어로 나온다).
TAG_EXAMPLES = {
    "en": "Fear", "es": "Miedo", "pt": "Medo", "de": "Angst",
    "fr": "Peur", "it": "Paura", "pl": "Lęk",
}


def build_single_comment_prompt(mood: str, verse: dict, style_limits: dict, lang: str = "ko") -> str:
    """스트리밍용: 구절 1개에 대해 tag + comment(말씀 풀이+적용)를 생성하는 프롬프트.

    문맥(조건절·화자)을 틀리게 단정하지 말라는 규칙을 둔다. 앞뒤 절 본문은 일부러 넣지 않는다 —
    2026-11-25 욥기 31:34 로 견줘 보니 「앞 절: 내가 허물을 가리웠다면」을 따로 주면 오히려
    그것을 고백으로 읽었다(규칙만 7번 중 6번 맞음, 앞뒤 절까지 주면 8번 중 3번, 옛 프롬프트 7번 중 4번).
    모델은 이름난 구절의 정경 문맥을 이미 안다. 앞뒤 절은 선별(select_verses)에서만 쓴다."""
    if lang != "ko":
        name = LANGUAGE_NAMES_EN.get(lang, lang)
        tag_ex = TAG_EXAMPLES.get(lang, "Comfort")
        return f"""
Role: You are a warm, wise pastor. Write ONLY in {name}.

Bible verse (already in {name} — quote it as-is, do not re-translate):
{verse['ref']} :: {verse['text']}
The believer's heart: "{mood}"

Task: Write a short pastoral reflection as 'comment'.
- Length: {style_limits['comment_limit_intl']}.
- Weave these into ONE smooth paragraph, without numbering or headings:
  (1) what this verse originally means, explained simply;
  (2) how it gently comforts and applies to this person's situation.
- Be honest about the verse: if it is a rebuke, judgment oracle, or warning,
  do not twist it into unrelated comfort — explain its real meaning and find
  the honest hope in or around it.
- Read the verse in its context. If it is the condition of an oath ("if I have…"),
  a question, one step of an argument, or someone else's words (e.g. Job's friends),
  say what it really is — never turn a condition into a fact or a confession.
- Do not name the speaker, or call the verse a confession, promise, or command,
  unless the verse or its known context makes that clear. When unsure,
  stay with what the words themselves say.
- Vary your phrasing naturally; do not open with a formula like "In [ref], ...".
- 'tag': 1–2 emotion themes, in {name} (e.g. "{tag_ex}").
- Output exactly ONE JSON object, nothing else (keep key order):
{{
  "tag": "{tag_ex}",
  "comment": "a pastoral comment in {name}"
}}
""".strip()
    return f"""
역할: 당신은 따뜻한 한국인 목사님입니다. (반드시 한국어만 사용)

성경 구절: {verse['ref']} :: {verse['text']}
성도의 마음: "{mood}"

요청: 이 구절을 성도에게 건네는 짧은 '말씀 나눔'을 comment 로 작성하세요.
- comment 분량: {style_limits['comment_limit']}.
- 반드시 아래 두 가지를 자연스러운 한 단락에 함께 담으세요:
  (1) 이 구절이 본래 무슨 뜻인지 쉽게 풀어 설명 (성경 풀이)
  (2) 그 말씀이 지금 성도의 상황에 어떤 위로·의미가 되는지 다정한 적용
- (1)(2) 같은 번호·표시나 소제목은 넣지 말고 매끄럽게 이어 쓰세요.
- 구절을 앞뒤 문맥 속에서 읽으세요. 결백 맹세의 조건(「내가 …하였다면」)·질문·논증의 한 토막이거나
  다른 사람(욥의 친구 등)의 말이면 그렇다고 밝히고, 조건을 사실이나 고백으로 바꿔 말하지 마세요.
- 구절이나 알려진 문맥에서 분명히 드러나지 않으면 누가 한 말인지, 고백·약속·명령인지 단정하지 마세요.
  확실하지 않으면 구절의 낱말이 말하는 데까지만 풀어 주세요.
- 'tag'는 감정 주제 1~2개. 예: "두려움", "위로", "소망", "회복" 등
- 출력은 JSON 객체 1개만. 다른 설명/서문/주석 금지.

정확한 JSON 객체 1개로만 출력 (아래 키 순서 유지):
{{
  "tag": "두려움",
  "comment": "말씀 풀이와 적용이 함께 담긴 목회적 코멘트"
}}
""".strip()
