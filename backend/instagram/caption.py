"""Daily Verse 캡션 조립과 문구 검사 (이슈 #62).

캡션 모양(런칭 게시물의 말씀 카드 캡션과 같은 틀):

    {훅 — 피드에서 「더 보기」 전에 보이는 첫 줄, 125자 이내}

    “{WEB 본문 그대로}” {참조}

    Swipe for the scene behind it and the WithGod app’s note … (written with AI).

    {요청 한 줄 — 저장·보내기·댓글}

    #bibleverse #dailybibleverse #{주제}

앱 풀이는 캐러셀 마지막 카드에 싣는다(11/12 사용자 — 게시물 하나로 읽히게). 캡션은 넘겨 보라는 한 줄만
둔다. 한 장짜리로 올릴 때만 캡션에 풀이를 싣는다. AI 로 쓴 풀이라 어디서든 그렇게 밝힌다(사람·목회자가 쓴 척
금지 규칙). 훅·카드 라벨·요청 줄과
캐러셀 안쪽 장 글은 `instagram/copy_en.json` 에 손으로 쓰고(API 로 만들지 않는다) 여기 규칙으로 검사한다.
"""
from __future__ import annotations

import re

# 인스타 캡션 상한(공식 문서: 2,200자, 해시태그 30, @ 20). 피드는 첫 줄 약 125자 뒤를 접는다.
CAPTION_MAX = 2200
HOOK_MAX = 125
KICKER_MAX = 40  # 런칭 라벨 최장 38자(「When it’s taking longer than you hoped」)
CTA_MAX = 100
ALT_TEXT_MAX = 1000
# 캐러셀 장면 장 글(card.py 의 scene 장)
SCENE_MAX = 240
CREDIT_MAX = 80
SCENE_LABELS = ("the scene", "the picture")

NOTE_INTRO = "From the WithGod app’s note on this verse (written with AI):"
SWIPE_LINE = "Swipe for the scene behind it and the WithGod app’s note on what it can mean today (written with AI)."
BASE_HASHTAGS = ("#bibleverse", "#dailybibleverse")
# 주제 해시태그 — 생성기가 이 안에서만 고른다(새 태그는 여기 더하고 테스트를 고친다).
TOPIC_HASHTAGS = (
    "#hope", "#peace", "#strength", "#comfort", "#encouragement", "#gratitude", "#rest",
    "#courage", "#wisdom", "#love", "#grace", "#forgiveness", "#joy", "#trust", "#patience",
    "#kindness",
)
# 앱 안내 줄 — 매일 붙이면 광고 계정처럼 보여서 요일을 정해 붙인다(daily_post.app_line_for).
APP_LINE = "Tell the free WithGod app how you feel. It finds a verse for that. Link in bio."

# ── 문구 검사 ─────────────────────────────────────────────────────
# 새로 쓰는 문구(훅·라벨·요청 줄)에 거는 규칙. 앱 풀이 검토본은 이미 비신자 기준으로 검토했으니
# 줄표·자해 표현·광고 문구만 다시 본다(find_caption_problems).

# 신의 목소리로 말하기 — 「God is telling you…」「God wants you to know」 따위.
_RE_DIVINE_VOICE = re.compile(
    r"\b(?:god|jesus|the lord|heaven|the holy spirit)\b[^.?!]{0,20}?\b"
    r"(?:is\s+)?(?:telling|tells|says\s+to|speaking\s+to|whispering|wants\s+you|has\s+a\s+message)\b"
    r"|\bthis\s+is\s+your\s+sign\b|\ba\s+message\s+from\s+(?:god|heaven)\b",
    re.I,
)
# 사람이 쓴 척 — 1인칭 단수 경험담, 목회자·사역자 행세.
_RE_PERSONA = re.compile(
    r"\b(?:I|I'm|I’m|I've|I’ve|I'd|I’d)\b|\b(?i:me|my|mine)\b"
    r"|\b(?i:(?:as\s+a\s+)?(?:pastor|minister|preacher|priest))\b",
)
# 광고 관련(광고를 넣을 예정이라 「No ads」류를 약속하지 않는다).
_RE_ADS = re.compile(r"\b(?:no|zero|without)\s+ads?\b|\bad[- ]free\b", re.I)
# 자해·자살 주제는 다루지 않는다.
_RE_SELF_HARM = re.compile(
    r"suicid|self[- ]harm|kill\s+(?:my|your|him|her|them)sel|end\s+(?:my|your|it\s+all)|"
    r"want\s+to\s+die|cutting\s+(?:my|your)sel|overdose",
    re.I,
)
# 클릭 낚시·과장 + 인스타 영어권에서 흔한 AI 말투(Instagram Agent Skill 의 slop 목록에서 고름).
_RE_SLOP = re.compile(
    r"\b(?:journey|testament\s+to|profound|beacon|tapestry|delve|unlock|game[- ]changer|"
    r"you\s+won['’]t\s+believe|life[- ]changing|powerful\s+reminder|let\s+that\s+sink\s+in|"
    r"in\s+today['’]s\s+world|navigate|embrace\s+the)\b",
    re.I,
)
_RE_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_RE_LINK = re.compile(r"https?://|www\.|\.com\b|link\s+in\s+bio", re.I)


def find_copy_problems(text: str, *, limit: int, field: str) -> list[str]:
    """훅·카드 라벨·요청 줄 하나의 규칙 위반 목록(없으면 빈 목록)."""
    problems = []
    s = (text or "").strip()
    if not s:
        return [f"{field}: 비어 있음"]
    if len(s) > limit:
        problems.append(f"{field}: {len(s)}자 > {limit}")
    if "—" in s or "–" in s or " - " in s:
        problems.append(f"{field}: 줄표")
    if "\n" in s:
        problems.append(f"{field}: 줄바꿈")
    if "#" in s or "@" in s:
        problems.append(f"{field}: 해시태그·@")
    for name, rx in (
        ("신의 목소리", _RE_DIVINE_VOICE),
        ("사람이 쓴 척", _RE_PERSONA),
        ("광고 문구", _RE_ADS),
        ("자해·자살", _RE_SELF_HARM),
        ("상투어", _RE_SLOP),
        ("이모지", _RE_EMOJI),
        ("링크", _RE_LINK),
    ):
        m = rx.search(s)
        if m:
            problems.append(f"{field}: {name}「{m.group(0)}」")
    return problems


def find_caption_problems(caption: str) -> list[str]:
    """완성된 캡션 전체 검사 — 길이·줄표·광고·자해 표현·해시태그 수."""
    problems = []
    if len(caption) > CAPTION_MAX:
        problems.append(f"캡션 {len(caption)}자 > {CAPTION_MAX}")
    first = caption.split("\n", 1)[0]
    if len(first) > HOOK_MAX:
        problems.append(f"첫 줄 {len(first)}자 > {HOOK_MAX}")
    if "—" in caption:
        problems.append("긴 줄표(—)")
    for name, rx in (("광고 문구", _RE_ADS), ("자해·자살", _RE_SELF_HARM)):
        m = rx.search(caption)
        if m:
            problems.append(f"{name}「{m.group(0)}」")
    tags = re.findall(r"(?<!\w)#\w+", caption)
    if len(tags) != 3:
        problems.append(f"해시태그 {len(tags)}개")
    return problems


def hashtags(topic: str) -> str:
    if topic not in TOPIC_HASHTAGS:
        raise ValueError(f"모르는 주제 해시태그: {topic}")
    return " ".join((*BASE_HASHTAGS, topic))


def display_ref(ref: str) -> str:
    """앱 참조(「Psalms 34:18」「Psalms 40:1-2」)를 카드·캡션 표기로 — 시편 한 편은 단수, 범위는 반각 줄표(–).

    런칭 카드와 같은 표기다. 본문·절 번호는 건드리지 않는다.
    """
    ref = re.sub(r"^Psalms (?=\d)", "Psalm ", ref.strip())
    return re.sub(r"(?<=\d)-(?=\d)", "–", ref)


def build_caption(*, hook: str, verse_text: str, ref: str, cta: str, topic: str, app_line: str = "",
                  note: str = "") -> str:
    """캡션 조립. ref 는 표시용(display_ref) 참조. note(앱 풀이)를 주면 한 장짜리 게시물이라 캡션에
    풀이를 싣고, 안 주면 캐러셀이라 풀이 카드로 넘겨 보라는 줄을 둔다."""
    blocks = [
        hook.strip(),
        f"“{verse_text.strip()}” {ref} (WEB)",
        f"{NOTE_INTRO}\n{note.strip()}" if note else SWIPE_LINE,
        cta.strip(),
    ]
    if app_line:
        blocks.append(app_line)
    blocks.append(hashtags(topic))
    return "\n\n".join(blocks)


def build_alt_text(*, kicker: str, verse_text: str, ref: str) -> str:
    """이미지 대체 텍스트(공식 API `alt_text`, 1,000자) — 런칭 카드와 같은 틀."""
    alt = f"Bible verse card. {kicker}: “{verse_text}” {ref} (World English Bible)."
    if len(alt) > ALT_TEXT_MAX:
        alt = alt[: ALT_TEXT_MAX - 1].rstrip() + "…"
    return alt


def find_slide_problems(copy: dict) -> list[str]:
    """copy_en.json 한 말씀의 캐러셀 안쪽 장 글 검사(장면·오늘의 한마디). 강조 구절은 본문에 그대로 있어야 한다."""
    problems = []
    scene = copy.get("scene")
    if scene:
        if scene.get("label") not in SCENE_LABELS:
            problems.append(f"scene.label: {scene.get('label')!r} (허용: {', '.join(SCENE_LABELS)})")
        problems += find_copy_problems(scene.get("body", ""), limit=SCENE_MAX, field="scene.body")
        if not (scene.get("credit") or "").strip() or len(scene["credit"]) > CREDIT_MAX:
            problems.append("scene.credit: 비었거나 김")
        if not (scene.get("alt") or "").strip() or len(scene["alt"]) > ALT_TEXT_MAX:
            problems.append("scene.alt: 비었거나 김")
        if not scene.get("art"):
            problems.append("scene.art: 그림 파일 없음")

    return problems


def find_post_problems(entry: dict) -> list[str]:
    """매니페스트 항목 하나 — 카피 셋과, 앱 안내 줄을 붙이는 날·안 붙이는 날 캡션 둘 다."""
    problems = (
        find_copy_problems(entry["kicker"], limit=KICKER_MAX, field="kicker")
        + find_copy_problems(entry["hook"], limit=HOOK_MAX, field="hook")
        + find_copy_problems(entry["cta"], limit=CTA_MAX, field="cta")
    )
    for app_line in ("", APP_LINE):
        for note in ("", entry["note"]):  # 캐러셀(풀이 카드)과 한 장짜리(캡션에 풀이) 둘 다
            caption = build_caption(hook=entry["hook"], verse_text=entry["text"], ref=entry["display_ref"],
                                    cta=entry["cta"], topic=entry["topic"], app_line=app_line, note=note)
            problems += find_caption_problems(caption)
    if len(entry.get("alt_text", "")) > ALT_TEXT_MAX:
        problems.append("대체 텍스트 길이")
    return problems
