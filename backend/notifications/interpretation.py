"""오늘의 말씀 '풀이' — 프롬프트, 말투 검사, 생성 함수.

한국어 풀이는 미리 만들어 검토한 것(`docs/verse_picks/interpretations.tsv` →
`notifications/daily_interpretations.json`)을 쓰고, 운영 중 즉석 생성은 외국어와
검토본이 없는 경우에만 한다. 두 경로가 같은 프롬프트를 쓰도록 여기에 모았다.
표준 라이브러리 외 의존성이 없다 — 클라이언트(anthropic)는 호출하는 쪽이 넘긴다.
(app.py 를 import 하면 임베딩 모델과 인덱스까지 올라오므로 스크립트에서 쓸 수 없다.)

프롬프트를 고칠 때 알아 둘 것 (2026-09-17 품질 개편):
(1) 예전 프롬프트는 '2문장 이내'로 묶고 예시를 「~라는 말씀이에요. 오늘 ~해 보면
    어떨까요」 한 틀로 줬다. 모든 풀이가 그 틀을 베껴 어느 구절에나 붙일 수 있는 말이
    됐다. 분량을 3~4문장으로 늘리고 예시는 끝맺음이 서로 다르게 줬다.
(2) 본문의 '너'를 풀이에 그대로 옮겨 사용자에게 반말을 했다(「너의 잘못을 용서받았다는
    말씀이에요」). 규칙으로 막고, 생성 뒤에도 검사해서 걸리면 다시 쓰게 한다.
(3) 예전에는 배경을 아예 못 쓰게 했다. 그런데 카드는 서사를 벗긴 말씀만 보여 주므로
    (요한복음 8:11b), 누가 누구에게 한 말인지는 풀이가 알려 줘야 뜻이 산다.
    널리 알려진 배경만 허용한다.
(4) 목록 457개 중 교훈이 276개다. 전부 위로하듯 풀면 교훈 구절이 물러진다.
(5) 2026-11-03 — 읽는 사람을 '대부분 기독교인'에서 '신자든 아니든'으로 바꿨다. 목록을
    비신자 기준으로 다시 고른 뒤라 풀이도 맞췄다. 기도로 맺거나 신앙 실천을 권하거나 교회 말을
    풀지 않고 쓰면 교회 밖 사람에게는 닿지 않는다. 하나님 이야기를 빼라는 뜻은 아니다.
"""
from __future__ import annotations

import hashlib
import re

KO_SYSTEM = """당신은 성경을 깊이 알고, 교회에 다니지 않는 사람에게도 쉬운 말로 풀어 줄 줄 아는 따뜻한 글쓴이입니다. 앱의 '오늘의 말씀' 카드 아래에 붙는 짧은 묵상 글을 씁니다.
읽는 사람은 기독교인일 수도, 교회에 다니지 않는 사람일 수도 있습니다. 둘 다 읽고 나면 이 말씀이 무슨 뜻이고 오늘 어떤 위로나 교훈이 되는지 알 수 있어야 합니다.
하루를 시작하며 이 카드를 봅니다. 카드에는 말씀 한 구절만 있고 앞뒤 이야기는 없습니다.

## 무엇을 쓰는가
3~4문장, 공백 포함 150~230자의 한 단락입니다. 아래가 자연스럽게 이어지게 씁니다.
- 이 말씀이 무슨 뜻인지. 본문을 다시 옮기지 말고 핵심을 짚습니다.
  누가 누구에게 어떤 자리에서 한 말인지 알아야 뜻이 사는 구절이면 그 배경을 짧게 알려 줍니다.
- 한층 깊이 들어간 관찰 하나. 낱말의 뜻, 말의 순서, 대구가 대비하는 것 같은 것입니다.
  '놓치기 쉬운 것은'처럼 예고하지 말고 바로 말합니다.
- 오늘 하루에 가져갈 것. 막연한 다짐이 아니라 떠올릴 수 있는 장면이나 태도로 씁니다.
  구절의 성격에 맞춥니다. 힘든 시간을 지나는 사람에게 건네는 위로의 말씀이면 다독이듯, 삶의 지혜나
  권면이면 훈계하지 말되 또렷하게 씁니다.
- 읽는 사람의 형편(병, 가난, 이별, 실패 등)을 짐작해서 단정하지 않습니다. 누구에게나 닿는 장면을 고릅니다.

## 말투 — 반드시 지킵니다
- 모든 문장을 존댓말(~요, ~니다)로 끝냅니다. 반말이나 '~다'로 끝나는 문장을 쓰지 않습니다.
- 읽는 사람을 '너, 너희, 네가, 당신, 그대'로 부르지 않습니다. 본문에 '너'가 있어도 풀이에는 옮기지 않습니다.
  한국어는 주어를 빼도 자연스럽습니다. 꼭 필요하면 '우리'라고 씁니다.
- 하나님과 예수님께는 높임말을 씁니다.

## 하지 않는 것
- 첫 줄에 제목을 달거나 본문을 옮겨 적기. 곧바로 풀이 문장으로 시작합니다.
  본문의 낱말을 짚을 때만 작은따옴표로 짧게 인용합니다('더디', '없을지라도').
- 본문을 조금 바꿔 되풀이하고 끝내기. 어느 구절에나 붙일 수 있는 말('힘내세요', '믿어도 괜찮아요')로 채우기.
- 첫 문장을 '~라는 말씀이에요'로 시작하기. '여기서 핵심은', '놓치기 쉬운 것은', '중요한 것은' 같은
  안내 문구로 말을 여는 것. 안내하지 말고 바로 말합니다.
- 'A가 아니라 B' 꼴을 습관처럼 쓰기. 흔한 오해를 바로잡을 때만 한 번 씁니다.
- '조용히', '천천히', '한 걸음', '숨을 고르다', '~하는 자리' 같은 말을 버릇처럼 넣기.
- 본문의 옛말을 그대로 옮기기. 경외, 긍휼, 인자, 명철, 권고, 미쁘다, 정녕 같은 말은 오늘 쓰는 말로 바꿉니다.
  같은 한자어라도 지금과 뜻이 다르면(경영=계획, 권고=돌보심) 오늘의 뜻으로 오해하지 않게 풀어 줍니다.
- 확실하지 않은 배경, 지어낸 이야기, 원어 풀이. 널리 알려진 사실이 아니면 쓰지 않습니다.
- 책망이나 경고를 억지 위로로 바꾸기. '믿으면 다 잘된다' 식의 약속이나 과장.
- 기도로 맺기('주님, ~해 주세요'). 기도·예배·찬양·묵상 같은 신앙 실천을 오늘 할 일로 권하기.
  오늘 가져갈 것은 누구나 해 볼 수 있는 장면이나 태도로 씁니다.
- 읽는 사람을 신자로 전제하기('믿음의 사람은', '성도인 우리'). 복음, 구원, 성령, 거룩, 영광 같은 교회 말을
  풀지 않고 쓰기. 말씀이 하나님께서 하시는 일을 말하면 그것을 그대로 전하는 것은 괜찮습니다.

## 출력
제목, 따옴표로 감싼 본문 인용, 구절 번호 없이 풀이 한 단락만 출력합니다.

## 예시 (깊이와 말투만 참고하고, 문장 구조는 따라 하지 않습니다)

구절: 예레미야애가 3:22-23
본문: 여호와의 자비와 긍휼이 무궁하시므로 우리가 진멸되지 아니함이니이다 이것이 아침마다 새로우니 주의 성실이 크도소이다
풀이: 예루살렘이 무너진 뒤에 부른 슬픈 노래 한가운데 나오는 고백이에요. 모든 것을 잃은 자리에서도 끝나지 않은 것이 있었는데, 바로 하나님의 한결같은 사랑과 불쌍히 여기시는 마음이었습니다. 그 사랑은 어제 다 쓰고 사라지는 것이 아니라 아침마다 새로 주어진다고 노래해요. 어제의 무거움이 오늘 아침까지 따라왔더라도, 오늘 몫의 사랑은 아직 그대로 남아 있습니다.

구절: 잠언 15:22
본문: 의논이 없으면 경영이 파하고 모사가 많으면 경영이 성립하느니라
풀이: 여기서 '경영'은 사업이 아니라 마음에 품은 계획을, '모사'는 곁에서 조언해 주는 사람을 뜻해요. 혼자 세운 계획은 무너지기 쉽지만 여러 사람의 지혜가 모이면 이루어진다는 가르침입니다. 누군가에게 묻는 것은 부족함을 드러내는 일이 아니라 계획을 단단하게 만드는 일이에요. 혼자 오래 붙들고 있던 고민이 있다면, 오늘은 믿을 만한 한 사람에게 먼저 꺼내 보세요."""

_KIND_HINT_KO = {
    # '아픈 사람'이라고 쓰면 모델이 병상에 누운 사람으로 읽는다(「약 먹는 시간」).
    "위안": "힘든 시간을 지나는 마음에 건네는 위로의 말씀",
    "교훈": "살아가는 데 도움이 되는 지혜나 권면",
}


def ko_user_prompt(
    reference: str, text: str, kind: str | None = None, form: str | None = None
) -> str:
    """form 은 사전 생성 때만 준다 — 풀이 457개가 한 틀로 끝나지 않도록 카드마다 첫머리와
    끝맺음을 나눠 지정한다(scripts/generate_verse_interpretations.py)."""
    lines = [f"구절: {reference}", f"본문: {text}"]
    hint = _KIND_HINT_KO.get(kind or "")
    if hint:
        lines.append(f"구절의 성격: {hint}")
    if form:
        lines.append(f"이번 풀이의 형식: {form}")
    lines.append("풀이:")
    return "\n".join(lines)


# 앱 화면 문구(WithGod/src/shared/lib/i18n/locales)와 같은 말씨. 정해 주지 않으면 프랑스어
# 풀이가 장마다 vous 와 tu 를 오갔다(2026-11-03 표본).
# 「Notice…」처럼 관찰을 예고하는 첫머리. 일반 지시만으로는 Haiku 가 23%에서 썼다(2026-11-03 배치
# 2,632건 중 599건) — 언어마다 실제로 나온 말을 짚어 준다. 검사(_ANNOUNCE_OPENING)와 짝이다.
_INTL_ANNOUNCE_EXAMPLES = {
    "English": "'Notice', 'Note that', 'What stands out'",
    "Spanish": "'Fíjate', 'Observa', 'Lo que (más) llama la atención'",
    "Portuguese": "'Repare', 'O que chama a atenção'",
    "German": "'Auffällig ist', 'Beachte', 'Bemerkenswert ist'",
    "French": "'Remarquez', 'Notez', 'Ce qui frappe'",
    "Italian": "'Colpisce', 'Nota che', 'Ciò che colpisce'",
    "Polish": "'Zwróć uwagę', 'Zauważ', 'Warto zauważyć'",
}
_INTL_ADDRESS = {
    "German": "informal 'du'", "French": "informal 'tu' (never 'vous')", "Spanish": "informal 'tú'",
    "Portuguese": "'você'", "Italian": "informal 'tu'", "Polish": "informal 'ty'",
}


def intl_system(lang_name: str) -> str:
    address = _INTL_ADDRESS.get(lang_name)
    announce = _INTL_ANNOUNCE_EXAMPLES.get(lang_name, "'Notice', 'It is easy to miss'")
    address_line = (
        f"When you speak to the reader, use {address}, as the rest of the app does.\n\n" if address else ""
    )
    return (
        f"You know the Bible deeply and explain it warmly in plain words, writing ONLY in {lang_name}. "
        "You write the short devotional note shown under an app's 'verse of the day' card. "
        "Readers start their day with it; they may be Christians or people who never go to church, "
        "and both should come away knowing what the verse means and what comfort or lesson it "
        "offers today. The card shows only the verse, without its surrounding story.\n\n"
        "Write ONE paragraph of 3-4 short sentences (about 60-90 words) that flows through:\n"
        "- what the verse means — do not restate it; if knowing who said it to whom, and "
        "in what situation, brings the verse to life, give that background briefly;\n"
        "- one deeper observation (a word, the order, the contrast in a parallelism) — state "
        f"it directly; never open a sentence by announcing it ({announce});\n"
        "- something concrete to carry into today — a scene or an attitude, not a vague resolution.\n"
        "Match the verse: comfort verses get a gentle, consoling voice; wisdom or exhortation "
        "gets a clear voice, never lecturing.\n\n"
        "Do not:\n"
        "- merely restate the verse, or fill space with lines that fit any verse;\n"
        "- open with a formula like 'This verse says...';\n"
        "- invent background or stories, or add original-language notes; only widely known facts;\n"
        "- turn a rebuke or warning into unrelated comfort; promise that faith makes everything "
        "go well, or exaggerate;\n"
        "- end with a prayer, or tell the reader to pray, worship or read the Bible today — give "
        "something anyone can carry into the day;\n"
        "- assume the reader is a believer, or use church words (gospel, salvation, the Holy Spirit, "
        "holiness, glory) without plain language. Saying what God does, as the verse says it, is fine.\n\n"
        "A reviewed Korean note may be given. It already follows these rules: write that same note "
        f"for {lang_name} readers. Keep its meaning and its background facts, and let your last "
        "sentence do what its last sentence does — the same suggestion, the same reassurance or the "
        "same question. Add nothing it does not say: no extra facts, no remarks on Hebrew or Greek "
        "words, no new advice. It may comment on the wording of the Korean Bible; keep such a remark "
        f"only if it fits the {lang_name} verse text, quote only words that appear in that text, and "
        "otherwise leave it out.\n\n"
        + address_line
        + "Output the paragraph only — no heading, no quotation of the verse, no reference."
    )


def intl_user_prompt(reference: str, text: str, lang_name: str, ko_note: str = "") -> str:
    """ko_note 는 한국어 검토본 풀이다. 외국어 풀이가 같은 기준(비신자 기준·기도 끝 없음)을
    물려받도록 바탕으로 준다 — 2026-11-03 전에는 외국어만 아무 검토 없이 즉석 생성했다."""
    lines = [f"Verse: {reference}", f"Text: {text}"]
    if ko_note:
        lines.append(f"Reviewed Korean note: {ko_note}")
    return "\n".join(lines) + f"\n\nDevotional note in {lang_name}:"


# ── 말투 검사(한국어) ─────────────────────────────────────────────
# 읽는 사람을 낮춰 부르는 2인칭. 앞뒤가 한글이면 다른 낱말의 일부다(너무, 너그럽다, 건너).
_INFORMAL_ADDRESS = re.compile(
    r"(?<![가-힣])"
    r"(?:너희|너|네가|네게|당신|그대)"
    r"(?:들|의|를|을|는|은|도|가|이|에게|께서|께|와|과|만|한테|랑)?"
    r"(?![가-힣])"
)
# '네 마음'처럼 조사 없이 쓰는 '네'. '네 가지'·'네 번' 같은 수사는 뺀다.
_INFORMAL_NE = re.compile(
    r"(?<![가-힣])네 (?!가지|번|개|명|시|살|째|사람|곳|달|해|권|편|장|절|걸음)"
)
# 존댓말 문장 끝. 따옴표·괄호가 뒤에 붙어도 된다.
_POLITE_END = re.compile(r"(?:요|니다|니까|죠)[\"'”’)]*$")
# 문장 나누기. 따옴표 안의 문장부호(“일어나라!”)에서 끊기지 않게 따옴표 덩어리는 통째로 넘긴다.
_SENTENCE = re.compile(r"(?:[\"“][^\"”]*[\"”]|[‘'][^’']*[’']|[^.!?\"“‘'])+[.!?]?")
_SENTENCE_END = re.compile(r"[.!?][\"'”’)]*$")


def _letters(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def echoes_verse(text: str, verse_text: str, span: int = 14) -> bool:
    """풀이가 본문을 한 마디(글자 14개) 넘게 그대로 옮겼는가. 낱말 인용('더디')은 괜찮다."""
    t, v = _letters(text), _letters(verse_text)
    if not v:
        return False
    span = min(span, len(v))
    return any(v[i:i + span] in t for i in range(len(v) - span + 1))


def find_problems(text: str, verse_text: str = "") -> list[str]:
    """한국어 풀이의 결함을 찾는다 — 반말 호칭, 존댓말이 아닌 문장 끝, 본문 되옮기기.
    빈 리스트면 통과."""
    problems = []
    for m in _INFORMAL_ADDRESS.finditer(text):
        problems.append(f"반말 호칭 '{m.group(0)}'")
    for m in _INFORMAL_NE.finditer(text):
        problems.append(f"반말 호칭 '{m.group(0).strip()}'")
    for sentence in _SENTENCE.findall(text):
        body = sentence.strip().rstrip(".!?").strip()
        if body and not _POLITE_END.search(body):
            problems.append(f"존댓말이 아닌 문장 끝 '…{body[-8:]}'")
    if verse_text and echoes_verse(text, verse_text):
        problems.append("본문을 그대로 옮겨 적음")
    return problems


# 사전 생성 검수용 말버릇. 결함은 아니라서 운영 경로에서는 보지 않는다.
# 프롬프트로 막아도 gpt-5.5 가 자주 되살리는 표현들이다.
HABIT_PHRASES = ("놓치기 쉬운", "놓치지 말", "핵심은", "중요한 것은", "믿어도 괜찮", "힘내세요")
_FORMULA_OPENING = re.compile(r"^[^.!?]*라는 말씀이에요")


def find_habits(text: str) -> list[str]:
    hits = [p for p in HABIT_PHRASES if p in text]
    if _FORMULA_OPENING.match(text):
        hits.append("첫 문장 '~라는 말씀이에요'")
    return hits


_RETRY_NOTE_KO = (
    "방금 쓴 풀이에 이런 문제가 있습니다: {problems}.\n"
    "규칙에 맞게 풀이 한 단락만 다시 쓰세요. 읽는 사람을 '너·당신'으로 부르지 말고, "
    "모든 문장을 존댓말로 끝내고, 제목이나 본문 인용 없이 풀이 문장으로 바로 시작합니다."
)


# ── 외국어 검사 ─────────────────────────────────────────────────
# 외국어 검토본을 두는 언어. languages.SUPPORTED_LANGUAGES 에서 ko 를 뺀 것과 같아야 한다
# (이 모듈은 표준 라이브러리만 써서 languages 를 import 하지 않는다 — 테스트가 맞춰 본다).
INTL_LANGS = ("en", "es", "pt", "de", "fr", "it", "pl")
# 프롬프트로 막아도 Haiku 가 되살리는 것들이다(2026-11-03 운영 캐시): 기도로 맺기,
# 「hand over to God」 같은 맡김 권유, 「Notice…」「Remarquez…」 같은 예고.
# 한국어 검토본을 바탕으로 쓰게 한 뒤에도 남으면 한 번 고쳐 쓰게 한다.
_HANGUL = re.compile(r"[가-힣]")
# 문장 첫머리에서 하나님을 부르는 말 = 기도. 「the Lord is near」처럼 문장 안에 오는 것은 통과.
_PRAYER_OPENING = re.compile(
    r"(?:^|[.!?]\s+)[\"“«„]?(?:O\s+|Oh\s+|Ó\s+|Ô\s+)?"
    r"(?:Lord|God|Father|Jesus|Señor|Dios|Padre|Senhor|Deus|Pai|Herr|Gott|Vater|"
    r"Seigneur|Dieu|Père|Signore|Dio|Panie|Boże|Ojcze|Jezu)\s*[,!]"
)
# 대소문자를 가리고 문장부호까지 본다 — 스페인어 「que se amen」(서로 사랑하라)이 걸렸다.
_AMEN = re.compile(r"\b(?:Amen|Amén|Amém)[.!]")
# 마지막 문장에서 기도·맡김을 오늘 할 일로 권하는 말. 언어마다 따로 둔다 — 스페인어
# 「ora」(기도하라)가 이탈리아어에서는 「지금」이다.
_PRACTICE_CLOSING = {
    lang: re.compile(pattern, re.I)
    for lang, pattern in {
        "en": r"\bpray|\bprayer|hand (?:\w+ )?over to God|\bentrust|(?:give|bring) (?:it|them|this|that) to God",
        "es": r"\bor(?:a|ar|e|emos|ad)\b|\boración|entr[eé]ga\w* .{0,30}a Dios|en (?:las )?manos de Dios",
        # 「coração」(마음) 안에 「oração」(기도)가 들어 있다 — 낱말 경계를 꼭 둔다
        "pt": r"\bor(?:e|ar|emos)\b|\boração|entregue? .{0,30}a Deus|nas mãos de Deus",
        "de": r"\bbet(?:e|en|et)\b|Gebet|Gott (?:an)?vertrau|in Gottes Hände|Gott (?:hin|ab)geben",
        "fr": r"\bpri(?:e|ez|ons|er|ère)s?\b|confie[rz]? .{0,30}à Dieu|entre les mains de Dieu",
        "it": r"\bpreg(?:a|hi|hiera|are|ate)\b|affida\w* .{0,30}a Dio|nelle mani di Dio",
        "pl": r"módl|modlitw|powierz\w* .{0,30}Bogu|oddaj\w* .{0,30}Bogu",
    }.items()
}
_ANNOUNCE_OPENING = re.compile(
    r"(?:^|[.!?]\s+)(?:Notice|Note (?:that|how)|It is easy to miss|Look at how|What stands out|"
    r"Remarquez|Notez|Observez|Ce qui frappe|Fíjate|Observa(?:d)?|Nota (?:que|cómo|come|che)|Notemos|"
    r"Lo que (?:más )?llama la atención|Repare|O que (?:mais )?chama a atenção|"
    r"Beachten Sie|Beachte|Auffällig ist|Bemerkenswert ist|Notate|Osserva|Colpisce|Ciò che colpisce|"
    r"Zwróć uwagę|Zauważ|Warto zauważyć|Uderza)\b"
)
# 한국어 검토본에는 원어 풀이가 없다(지어낸 원어 풀이 금지) — 외국어에서 생기면 덧붙인 것이다.
_ORIGINAL_LANGUAGE = re.compile(
    r"\b(?:Hebrew|Greek|hebreo|griego|hebraico|grego|hebräisch\w*|griechisch\w*|hébreu|grec|grecque|"
    r"ebraico|greco|hebrajsk\w*|greck\w*)\b",
    re.I,
)
_INTL_WORDS = (30, 140)
_INTL_SENTENCE = re.compile(r"[^.!?]+[.!?]*")


def _words(s: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", s.lower())


def find_intl_problems(text: str, lang: str = "") -> list[str]:
    """외국어 풀이의 결함 — 한글 섞임, 기도문(하나님을 부르기·아멘). 빈 리스트면 통과."""
    problems = []
    if _HANGUL.search(text):
        problems.append("contains Korean characters")
    if _PRAYER_OPENING.search(text) or _AMEN.search(text):
        problems.append("addresses God in prayer")
    return problems


def find_intl_habits(text: str, verse_text: str = "", lang: str = "") -> list[str]:
    """외국어 풀이의 말버릇 — 기도·맡김 권유로 맺기, 예고 문구, 원어 풀이, 길이, 본문 되옮기기.

    결함이 아니라서 고쳐 쓴 답이 더 나쁘면 첫 답을 쓴다. 기도 권유를 결함으로 두지 않는 까닭:
    예레미야 33:3 「부르짖으라」처럼 본문이 기도를 말하는 구절은 한국어 검토본도 「부르짖는 사람에게
    하나님은 귀를 기울이십니다」로 맺는다. 그 평서문을 옮기면 기도라는 말이 마지막 문장에 남는다.
    """
    habits = []
    sentences = [s.strip() for s in _INTL_SENTENCE.findall(text) if s.strip()]
    practice = _PRACTICE_CLOSING.get(lang)
    if practice and sentences and practice.search(sentences[-1]):
        habits.append("the closing sentence tells the reader to pray or hand things over to God")
    if _ANNOUNCE_OPENING.search(text):
        habits.append("announces an observation ('Notice…', 'What stands out…') instead of stating it")
    if _ORIGINAL_LANGUAGE.search(text):
        habits.append("adds a remark on Hebrew or Greek wording")
    n = len(_words(text))
    if not _INTL_WORDS[0] <= n <= _INTL_WORDS[1]:
        habits.append(f"{n} words (aim for 60-90)")
    v = _words(verse_text)
    if len(v) >= 8:
        t = " ".join(_words(text))
        if any(" ".join(v[i:i + 8]) in t for i in range(len(v) - 7)):
            habits.append("copies the verse text")
    return habits


_RETRY_NOTE_INTL = (
    "The note you wrote has these problems: {problems}.\n"
    "Rewrite it as one paragraph following the rules. Do not pray or address God, do not tell the "
    "reader to pray or hand things over to God, and state any observation directly."
)

# 생각(thinking) 강도. 운영 즉석 생성은 low, 사전 생성은 medium(더 정확하다).
# gpt-5.5 시절 low 3~5초·medium 5~11초였다.
REASONING_EFFORT = "low"
TIMEOUT_SECONDS = 60
# 생각 토큰도 한도에 들어간다. 풀이 한 단락은 수백 토큰이라 여유를 크게 둔다.
MAX_TOKENS = 4000


def _complete(client, model: str, messages: list[dict], reasoning_effort: str) -> str:
    """Anthropic Messages API 로 부른다. 첫 메시지가 system 이면 system 으로 뺀다.

    Claude 는 temperature 를 받지 않고(Haiku 5.5 는 400), 생각을 켜 둔 채 effort 로
    깊이를 정한다. 응답 첫 블록이 생각일 수 있어 글 블록만 모은다.
    """
    system = ""
    if messages and messages[0]["role"] == "system":
        system, messages = messages[0]["content"], messages[1:]
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
        thinking={"type": "adaptive"},
        output_config={"effort": reasoning_effort},
        timeout=TIMEOUT_SECONDS,
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def cache_tag(model: str, reasoning_effort: str = REASONING_EFFORT) -> str:
    """운영 캐시 키에 붙이는 꼬리표. 모델이나 프롬프트가 바뀌면 값이 달라져서
    예전 방식으로 만든 풀이를 계속 내보내지 않고 새로 만든다."""
    basis = "|".join([
        model,
        reasoning_effort,
        KO_SYSTEM,
        ko_user_prompt("{reference}", "{text}"),
        intl_system("{lang}"),
        intl_user_prompt("{reference}", "{text}", "{lang}", "{ko_note}"),
        _RETRY_NOTE_INTL,
    ])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:6]


def tidy(text: str, verse_text: str = "") -> str:
    """모델 출력에서 풀이 단락만 남긴다.

    gpt-5 계열은 규칙을 줘도 첫 줄에 제목(「말을 아끼는 지혜」)이나 본문 인용을 붙일
    때가 있다. 문장부호로 끝나지 않는 줄과 본문을 옮긴 줄을 앞에서부터 걷어 낸다.
    """
    lines = [ln.strip() for ln in text.replace("**", "").splitlines() if ln.strip()]
    while len(lines) > 1 and (
        not _SENTENCE_END.search(lines[0]) or (verse_text and echoes_verse(lines[0], verse_text))
    ):
        lines.pop(0)
    out = re.sub(r"^\s*풀이\s*[:：]\s*", "", " ".join(lines))
    return re.sub(r"\s+", " ", out).strip()


def generate_interpretation(
    client,
    model: str,
    reference: str,
    text: str,
    lang: str = "ko",
    lang_name: str | None = None,
    kind: str | None = None,
    reasoning_effort: str = REASONING_EFFORT,
    check_habits: bool = False,
    form: str | None = None,
    ko_note: str = "",
) -> str:
    """풀이 한 단락을 만든다.

    한국어는 결함 검사(`find_problems`)에 걸리면 무엇이 문제인지 알려 주고 한 번 고쳐
    쓰게 한다. 그래도 걸리면 예외를 올린다 — 상위(VerseInterpreter)가 한 줄 적용문으로
    폴백하고 캐시에는 남기지 않는다. `check_habits` 는 사전 생성용으로, 말버릇도
    고쳐 쓰게 하되 끝내 남으면 예외 없이 그대로 돌려준다(사람이 검토한다).

    외국어는 한국어 검토본(`ko_note`)을 바탕으로 쓰고, 결함(`find_intl_problems`)이나
    말버릇(`find_intl_habits`)이 있으면 한 번 고쳐 쓰게 한다. 처리 규칙은 한국어와 같다.
    """
    if lang != "ko":
        name = lang_name or lang
        messages = [
            {"role": "system", "content": intl_system(name)},
            {"role": "user", "content": intl_user_prompt(reference, text, name, ko_note)},
        ]
        raw = _complete(client, model, messages, reasoning_effort)
        first = tidy(raw, text)
        defects, habits = find_intl_problems(first, lang), find_intl_habits(first, text, lang)
        if not defects and not habits:
            return first
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": _RETRY_NOTE_INTL.format(problems="; ".join(defects + habits))},
        ]
        second = tidy(_complete(client, model, messages, reasoning_effort), text)
        if not find_intl_problems(second, lang):
            return second
        if not defects:
            return first
        raise ValueError(f"풀이 검사 실패({reference}, {lang}): {'; '.join(find_intl_problems(second, lang))}")

    messages = [
        {"role": "system", "content": KO_SYSTEM},
        {"role": "user", "content": ko_user_prompt(reference, text, kind, form)},
    ]
    raw = _complete(client, model, messages, reasoning_effort)
    first = tidy(raw, text)
    defects = find_problems(first, text)
    habits = find_habits(first) if check_habits else []
    if not defects and not habits:
        return first

    messages += [
        {"role": "assistant", "content": raw},
        {"role": "user", "content": _RETRY_NOTE_KO.format(problems=", ".join(defects + habits))},
    ]
    second = tidy(_complete(client, model, messages, reasoning_effort), text)
    if not find_problems(second, text):
        return second
    if not defects:
        return first  # 첫 답은 말버릇만 있었다 — 고쳐 쓴 답이 더 나쁘면 첫 답을 쓴다
    raise ValueError(f"풀이 검사 실패({reference}): {', '.join(find_problems(second, text))}")
