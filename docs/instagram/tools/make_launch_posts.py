#!/usr/bin/env python3
"""@withgod.app 런칭용 게시물 9개(이미지 + 캡션)를 만든다.

- 슬라이드는 HTML 로 짜서 Chrome 헤드리스로 1080x1350(4:5) PNG 를 찍는다.
- 디자인: 게시물마다 감정에 맞는 하늘빛 팔레트 + 필름 질감, 핵심 구절은 형광펜(어두운 배경은 이탤릭).
- 성경 본문은 앱이 쓰는 영어 본문(WEB, backend/data/langs/en/verses.csv)에서 그대로 읽는다.
- 단일 말씀 카드의 캡션은 앱의 영어 풀이 검토본(daily_interpretations_intl.json)을 쓴다.
- 폰트는 OFL — Fraunces(제목·본문), Inter(작은 글씨) — tools/fonts/.

실행: python3 docs/instagram/tools/make_launch_posts.py
결과: docs/instagram/launch/ (게시물별 폴더, captions.md, grid-preview.png)
"""
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[2]  # 저장소 루트
OUT = TOOLS.parent / "launch"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1080, 1350

VERSES_CSV = ROOT / "backend/data/langs/en/verses.csv"
INTERP_JSON = ROOT / "backend/notifications/daily_interpretations_intl.json"
APP_SHOT = TOOLS / "app-screens/result-top.png"

HASHTAGS_BASE = ["#bibleverse", "#dailybibleverse", "#scripture", "#faith"]
LINK_LINE = "Free on iPhone, iPad and Android. Link in bio."

# ---------------------------------------------------------------- 본문

_BOOK_CODE = {
    "Isaiah": "isa", "Matthew": "mat", "Psalm": "psa", "Philippians": "php",
    "1 Peter": "1pe", "Deuteronomy": "deu", "John": "jhn", "Habakkuk": "hab",
    "Romans": "rom",
}


def _load_verses() -> dict[tuple[str, int, int], str]:
    rows = {}
    with VERSES_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            book = "Psalm" if r["book"] == "Psalms" else r["book"]
            rows[(book, int(r["chapter"]), int(r["verse"]))] = r["text"]
    return rows


_VERSES = _load_verses()


def _tidy(text: str) -> str:
    """짝 없는 따옴표를 떼고 첫 글자를 대문자로(앱의 tidy_verse_text 와 같은 규칙)."""
    text = text.strip()
    if text.count("“") != text.count("”"):
        text = text.replace("“", "").replace("”", "")
    text = text.strip()
    return text[0].upper() + text[1:]


def verse(ref: str, emph: str) -> dict:
    """'Philippians 4:6-7' → {'ref', 'text', 'id', 'emph'}. 범위는 절을 이어 붙인다.

    emph 는 카드에서 형광펜으로 칠할 구절(본문에 그대로 있어야 한다).
    """
    m = re.fullmatch(r"(.+) (\d+):(\d+)(?:-(\d+))?", ref)
    assert m, ref
    book, ch, v1 = m.group(1), int(m.group(2)), int(m.group(3))
    v2 = int(m.group(4) or v1)
    parts = [_VERSES[(book, ch, v)] for v in range(v1, v2 + 1)]
    text = _tidy(" ".join(parts))
    assert emph in text, (ref, emph)
    return {"ref": ref.replace("-", "–"), "text": text, "id": f"{_BOOK_CODE[book]}-{ch}-{v1}", "emph": emph}


def reflection(verse_id: str) -> str:
    data = json.loads(INTERP_JSON.read_text(encoding="utf-8"))
    hits = [v for k, v in data.items() if k.startswith(f"en:{verse_id}:")]
    assert len(hits) == 1, verse_id
    return hits[0].strip()


def plain(text: str) -> str:
    """제목의 *강조* 표시와 줄바꿈을 뺀 글(대체 텍스트·캡션용)."""
    return " ".join(text.replace("*", "").split())


# ---------------------------------------------------------------- 게시물 정의
# 그리드 순서(1 = 맨 위 왼쪽). 1~3 은 고정 게시물.
# pal: 표지(cover)·안쪽 장(inner)·마지막 장(cta)의 팔레트(CSS 의 .p-<이름>).

def nights():
    items = [
        ("When your thoughts keep racing", "Philippians 4:6-7", "will guard your hearts and your thoughts"),
        ("When it’s too much to carry", "1 Peter 5:7", "because he cares for you."),
        ("When you can’t stop working it out", "Psalm 127:2", "he gives sleep to his loved ones."),
        ("When you finally lie down", "Psalm 4:8", "In peace I will both lay myself down and sleep,"),
        ("For the morning after", "Psalm 3:5", "I awakened, for the LORD sustains me."),
    ]
    return [(label, verse(r, emph)) for label, r, emph in items]


def alone():
    items = [
        ("You’re not the first to feel this", "Psalm 25:16", "Turn to me,"),
        ("When you’re facing it by yourself", "Deuteronomy 31:8", "He will be with you."),
        ("When the people closest let you down", "Psalm 27:10", "then the LORD will take me up."),
        ("When you’re far from home", "Psalm 139:9-10", "your right hand will hold me."),
        ("When you feel left behind", "John 14:18", "I will not leave you orphans."),
    ]
    return [(label, verse(r, emph)) for label, r, emph in items]


def waiting():
    items = [
        ("When waiting is all you can do", "Psalm 130:5", "I hope in his word."),
        ("When it’s taking longer than you hoped", "Habakkuk 2:3", "Though it takes time, wait for it,"),
        ("When you’re losing heart", "Psalm 27:14", "let your heart take courage."),
        ("When you can’t see it yet", "Romans 8:25", "we wait for it with patience."),
        ("When you’re tired of waiting", "Isaiah 40:31", "will renew their strength."),
    ]
    return [(label, verse(r, emph)) for label, r, emph in items]


def refs_sentence(items) -> str:
    refs = [v["ref"] for _, v in items]
    return ", ".join(refs[:-1]) + " and " + refs[-1]


def build_posts() -> list[dict]:
    posts = []

    # 1. 소개 (고정)
    posts.append({
        "slug": "01-pinned-intro",
        "title": "소개 (고정)",
        "pal": {"cover": "brand", "inner": "dawn", "cta": "brand"},
        "slides": [
            {"kind": "cover", "kicker": "welcome",
             "headline": "Whatever you’re going through, *there’s a verse for it.*"},
            {"kind": "list", "headline": "Some days are *heavy.*",
             "lines": ["You can’t sleep.", "You feel alone in a full room.",
                       "You’re waiting on news that won’t come.",
                       "You’re tired in a way sleep doesn’t fix."]},
            {"kind": "statement", "kicker": "so we made an app",
             "headline": "Tell it how you feel. *It finds the verse.*",
             "body": "Write what’s on your heart, in your own words. "
                     "WithGod searches the whole Bible for verses that speak to it."},
            {"kind": "statement", "kicker": "what you get",
             "headline": "The verse, *and what it can mean today.*",
             "body": "The verse is always the Bible’s own words. "
                     "AI helps find it and adds a short note on what it can mean for you."},
            {"kind": "statement", "kicker": "here on instagram",
             "headline": "A new verse *every morning.*",
             "body": "Plus verses for the feelings that are hard to name. "
                     "Save the ones that help. Send them to someone who needs one."},
            {"kind": "cta", "headline": "Tell the app how you feel. *It finds yours.*",
             "extra": "Free on iPhone, iPad and Android"},
        ],
        "caption": "\n\n".join([
            "Whatever you’re going through, there’s a verse for it.",
            "WithGod is a free app. Write how you feel, "
            "in your own words, and it searches the whole Bible for verses that speak to it. "
            "Each verse comes with a short note, written with AI, on what it can mean for you today.",
            "Here you’ll find a new verse every morning, plus verses for the feelings that are hard to name.",
            "Get the app through the link in bio. Free on iPhone, iPad and Android.",
            " ".join(HASHTAGS_BASE + ["#christianapp"]),
        ]),
    })

    # 2. 사용법 (고정) — 실제 앱 화면(시뮬레이터, 영어)
    posts.append({
        "slug": "02-pinned-how-it-works",
        "title": "사용법 (고정)",
        "pal": {"cover": "paper", "inner": "paper", "cta": "brand"},
        "slides": [
            {"kind": "cover", "kicker": "how it works", "headline": "Find your verse\nin *3 steps*"},
            {"kind": "step", "num": 1, "headline": "Say how you feel.",
             "body": "In your own words. One sentence is enough.", "shot": "step1"},
            {"kind": "step", "num": 2, "headline": "Get a verse for it.",
             "body": "The Bible’s own words, never rewritten.", "shot": "step2"},
            {"kind": "step", "num": 3, "headline": "See what it means for you.",
             "body": "A short note, written with AI, for what you shared.", "shot": "step3"},
            {"kind": "cta", "headline": "Try it *tonight.*",
             "extra": "Free on iPhone, iPad and Android.\nPlus a new verse every morning."},
        ],
        "caption": "\n\n".join([
            "Find your verse in three steps. You only need one sentence.",
            "1. Say how you feel, in your own words.\n"
            "2. Get Bible verses that speak to it. The verse text is never rewritten.\n"
            "3. Read a short note, written with AI, on what each verse can mean for you.",
            "We tried “I can’t sleep. My mind keeps racing about tomorrow.” "
            "The app found Psalm 4:8: “In peace I will both lay myself down and sleep, "
            "for you alone, LORD, make me live in safety.”",
            "Try it tonight. " + LINK_LINE,
            " ".join(HASHTAGS_BASE + ["#christianapp"]),
        ]),
    })

    # 3. 대표 캐러셀 (고정)
    n = nights()
    posts.append({
        "slug": "03-pinned-nights",
        "title": "대표 캐러셀: 잠 못 드는 밤 (고정)",
        "pal": {"cover": "night", "inner": "night", "cta": "night"},
        "slides": [{"kind": "cover", "kicker": "5 verses",
                    "headline": "For the nights your mind won’t *slow down*"}]
                  + [{"kind": "verse", "label": label, "verse": v} for label, v in n]
                  + [{"kind": "cta", "headline": "Still *awake?*",
                      "body": "Tell WithGod what’s keeping you up.\nIt finds the verse for that.",
                      "extra": "Save this for a restless night."}],
        "caption": "\n\n".join([
            "For the nights your mind won’t slow down.",
            f"Five verses for when the worries follow you to bed: {refs_sentence(n)}.",
            "You don’t have to solve everything before you sleep tonight.",
            "Save this for a restless night, and send it to someone who’s still awake.",
            " ".join(HASHTAGS_BASE + ["#peace"]),
        ]),
    })

    def single(slug, title, pal, ref, emph, label, hook, cta, tag):
        v = verse(ref, emph)
        return {
            "slug": slug, "title": title, "pal": {"inner": pal},
            "slides": [{"kind": "verse", "label": label, "verse": v, "single": True}],
            "caption": "\n\n".join([
                hook,
                f"“{v['text']}” {v['ref']}",
                "From the WithGod app’s note on this verse (written with AI):\n" + reflection(v["id"]),
                cta,
                " ".join(HASHTAGS_BASE + [tag]),
            ]),
        }

    posts.append(single(
        "04-isaiah-41-10", "말씀 카드: 두려울 때", "mist", "Isaiah 41:10", "for I am with you.",
        "When you’re afraid",
        "For the days fear gets the first word.",
        "Save this for the next time fear gets loud. A new verse here every morning.",
        "#encouragement"))

    a = alone()
    posts.append({
        "slug": "05-when-you-feel-alone",
        "title": "캐러셀: 외로울 때",
        "pal": {"cover": "twilight", "inner": "lilac", "cta": "twilight"},
        "slides": [{"kind": "cover", "kicker": "5 verses", "headline": "When you feel *alone*"}]
                  + [{"kind": "verse", "label": label, "verse": v} for label, v in a]
                  + [{"kind": "cta", "headline": "Feeling it *today?*",
                      "body": "Tell WithGod what it’s like.\nIt finds the verse for that.",
                      "extra": "Send this to someone who might need it."}],
        "caption": "\n\n".join([
            "When you feel alone, even in a full room.",
            f"Five verses for the lonely days: {refs_sentence(a)}.",
            "The first one is a prayer from someone who felt the same way, three thousand years ago.",
            "Send this to someone who might be feeling it today.",
            " ".join(HASHTAGS_BASE + ["#loneliness"]),
        ]),
    })

    posts.append(single(
        "06-matthew-11-28", "말씀 카드: 지쳤을 때", "sand", "Matthew 11:28", "and I will give you rest.",
        "When you’re worn out",
        "Running on empty?",
        "Send this to someone who’s been carrying a lot lately.",
        "#rest"))

    posts.append(single(
        "07-psalm-34-18", "말씀 카드: 마음이 무너졌을 때", "rose", "Psalm 34:18",
        "The LORD is near to those who have a broken heart,",
        "When your heart is broken",
        "If your heart is in pieces today, read this slowly.",
        "If someone you love is hurting, send this to them. You don’t have to find the right words.",
        "#comfort"))

    w = waiting()
    posts.append({
        "slug": "08-when-youre-waiting",
        "title": "캐러셀: 기다림이 길 때",
        "pal": {"cover": "sage", "inner": "sagelight", "cta": "sage"},
        "slides": [{"kind": "cover", "kicker": "5 verses",
                    "headline": "When you’re waiting and *nothing moves*"}]
                  + [{"kind": "verse", "label": label, "verse": v} for label, v in w]
                  + [{"kind": "cta", "headline": "Still waiting *on something?*",
                      "body": "Tell WithGod about it.\nIt finds the verse for that.",
                      "extra": "Save this for the long days."}],
        "caption": "\n\n".join([
            "When you’re waiting and nothing moves.",
            f"Five verses for the long middle: {refs_sentence(w)}.",
            "Save this for the days the waiting feels longest.",
            " ".join(HASHTAGS_BASE + ["#hope"]),
        ]),
    })

    posts.append(single(
        "09-psalm-118-24", "말씀 카드: 감사 (추수감사절 주간)", "sunrise", "Psalm 118:24",
        "This is the day that the LORD has made.",
        "For an ordinary day",
        "For the plain, ordinary days too.",
        "Share yours in the comments if you like. A new verse here every morning.",
        "#gratitude"))

    return posts


# ---------------------------------------------------------------- HTML

DARK = {"brand", "night", "twilight", "sage"}

CSS = """
@font-face{font-family:"WGDisplay";src:url(FONTS/Fraunces-Variable.ttf);font-weight:100 900;font-style:normal}
@font-face{font-family:"WGDisplay";src:url(FONTS/Fraunces-Italic-Variable.ttf);font-weight:100 900;font-style:italic}
@font-face{font-family:"WGSans";src:url(FONTS/inter_medium.ttf);font-weight:500}
@font-face{font-family:"WGSans";src:url(FONTS/inter_semibold.ttf);font-weight:600}
*{box-sizing:border-box}
html,body{margin:0;width:1080px;height:1350px;overflow:hidden}
body{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.s{position:relative;width:1080px;height:1350px;overflow:hidden;background:var(--bg);color:var(--ink);
  font-family:"WGDisplay",Georgia,serif;font-variation-settings:"SOFT" 50,"WONK" 0}
.s::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:var(--grain);mix-blend-mode:multiply;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .5 0 0 0 0 .45 0 0 0 0 .4 0 0 0 .9 0'/></filter><rect width='300' height='300' filter='url(%23n)'/></svg>")}

/* 팔레트: 감정마다 다른 하늘 */
.p-brand{--bg:radial-gradient(900px 700px at 82% 10%,rgba(255,255,255,.22),transparent 60%),
  linear-gradient(170deg,#2B5FBF 0%,#3A78D4 50%,#5A90E0 100%);
  --ink:#FFF8EC;--soft:rgba(255,248,236,.9);--muted:rgba(255,248,236,.74);--accent:#FFDFA8;
  --tag-bg:#FFDFA8;--tag-ink:#1F3F78;--grain:.22}
.p-dawn{--bg:radial-gradient(1000px 700px at 18% 0%,rgba(255,255,255,.8),transparent 60%),
  linear-gradient(180deg,#D8E5F5 0%,#ECEFEE 50%,#F5E6D2 100%);
  --ink:#17233A;--soft:#3E4A62;--muted:#5D6A80;--accent:#2F64B5;--mark:rgba(118,168,236,.42);
  --tag-bg:#2F64B5;--tag-ink:#FFF8EC;--grain:.3}
.p-paper{--bg:radial-gradient(1000px 800px at 80% 0%,rgba(255,255,255,.75),transparent 60%),
  linear-gradient(180deg,#F3F0E9 0%,#EEE6D6 100%);
  --ink:#1E2433;--soft:#454B5C;--muted:#6B6F7C;--accent:#2F64B5;--mark:rgba(118,168,236,.4);
  --tag-bg:#1E2433;--tag-ink:#F3F0E9;--grain:.32}
.p-night{--bg:radial-gradient(900px 700px at 78% 16%,rgba(140,150,255,.32),transparent 60%),
  linear-gradient(180deg,#0E1433 0%,#1E2758 48%,#4B4A86 82%,#8A6F9E 100%);
  --ink:#FBF4E6;--soft:rgba(251,244,230,.9);--muted:rgba(251,244,230,.7);--accent:#F6D9A8;
  --tag-bg:#F6D9A8;--tag-ink:#1E2758;--grain:.26}
.p-mist{--bg:radial-gradient(1000px 600px at 30% 0%,rgba(255,255,255,.75),transparent 60%),
  linear-gradient(180deg,#B9CCDF 0%,#DCE2E4 45%,#F1E6D3 80%,#F4DDC0 100%);
  --ink:#1E2B3D;--soft:#3B4A5E;--muted:#4E6178;--accent:#2F5A8C;--mark:rgba(120,165,220,.45);--grain:.24}
.p-twilight{--bg:radial-gradient(800px 600px at 22% 92%,rgba(255,190,150,.32),transparent 60%),
  linear-gradient(180deg,#252A55 0%,#3B4180 52%,#7671AA 100%);
  --ink:#FBF4EC;--soft:rgba(251,244,236,.9);--muted:rgba(251,244,236,.72);--accent:#F7C9A2;
  --tag-bg:#F7C9A2;--tag-ink:#252A55;--grain:.26}
.p-lilac{--bg:radial-gradient(1000px 700px at 75% 0%,rgba(255,255,255,.7),transparent 60%),
  linear-gradient(180deg,#D9DAEE 0%,#E8E4EF 55%,#F3E7E0 100%);
  --ink:#221F3A;--soft:#403C5E;--muted:#5B5878;--accent:#4B4590;--mark:rgba(160,150,230,.42);--grain:.28}
.p-sand{--bg:radial-gradient(900px 700px at 82% 8%,rgba(255,241,214,.75),transparent 60%),
  linear-gradient(180deg,#ECDDC7 0%,#E5CFB1 60%,#DCBD99 100%);
  --ink:#35251A;--soft:#553D2C;--muted:#7A5B43;--accent:#8A4B26;--mark:rgba(236,168,80,.58);--grain:.32}
.p-rose{--bg:radial-gradient(900px 600px at 28% 0%,rgba(255,242,236,.75),transparent 60%),
  linear-gradient(180deg,#EED8D3 0%,#E4BFBC 55%,#D5A6AA 100%);
  --ink:#3A1E28;--soft:#5A3442;--muted:#7A4C58;--accent:#8E3F55;--mark:rgba(255,228,208,.95);--grain:.28}
.p-sage{--bg:radial-gradient(800px 600px at 82% 12%,rgba(255,245,215,.34),transparent 60%),
  linear-gradient(180deg,#2C463B 0%,#4A6A58 55%,#7F9A83 100%);
  --ink:#F6F1E4;--soft:rgba(246,241,228,.9);--muted:rgba(246,241,228,.74);--accent:#F3DFA2;
  --tag-bg:#F3DFA2;--tag-ink:#2C463B;--grain:.26}
.p-sagelight{--bg:radial-gradient(1000px 700px at 20% 0%,rgba(255,255,255,.7),transparent 60%),
  linear-gradient(180deg,#DCE5D9 0%,#E7EADF 55%,#F1E9D8 100%);
  --ink:#22332A;--soft:#3E5246;--muted:#567062;--accent:#3D6B52;--mark:rgba(170,205,140,.62);--grain:.3}
.p-sunrise{--bg:radial-gradient(760px 520px at 50% 106%,rgba(255,247,224,.95),transparent 70%),
  linear-gradient(180deg,#F2D9A6 0%,#F1C78A 52%,#EBB37E 100%);
  --ink:#3B2513;--soft:#5A3B22;--muted:#7A5330;--accent:#9A4B1C;--mark:rgba(255,249,232,.85);--grain:.3}

em{font-style:italic;font-weight:inherit;color:var(--accent)}
.stars{position:absolute;left:0;top:0;width:3px;height:3px;border-radius:50%;background:#fff;opacity:.85;
  box-shadow:120px 160px #fff,300px 90px #fffbe8,520px 210px #fff,760px 120px #fff,900px 300px #fffbe8,
  640px 380px #fff,210px 330px #fff,980px 70px #fff,420px 60px #fff,840px 470px #fff,60px 520px #fff,
  350px 470px #fffbe8,1010px 560px #fff,700px 600px #fffbe8}
.tag{position:absolute;left:100px;top:116px;font:600 28px/1 "WGSans";letter-spacing:.01em;background:var(--tag-bg);
  color:var(--tag-ink);padding:15px 28px;border-radius:999px;transform:rotate(-3deg);transform-origin:left center;
  box-shadow:0 8px 20px rgba(0,0,0,.10)}
.foot{position:absolute;left:100px;right:100px;bottom:80px;display:flex;justify-content:space-between;
  align-items:center;font:500 28px "WGSans";letter-spacing:.01em;color:var(--muted)}
.foot svg{width:44px;height:44px}

/* 표지 */
.cover{position:absolute;left:100px;right:100px;top:230px;bottom:230px;display:flex;flex-direction:column;
  justify-content:flex-end}
.cover h1{margin:0;font-weight:600;font-size:122px;line-height:1.0;letter-spacing:-.028em;text-wrap:balance;
  font-variation-settings:"SOFT" 100,"WONK" 0}
.cover h1 em{font-weight:500}

/* 말씀 */
.vbox{position:absolute;left:100px;right:100px;top:140px;bottom:210px;display:flex;flex-direction:column;
  justify-content:center}
.vlabel{font-style:italic;font-weight:400;font-size:46px;line-height:1.2;color:var(--muted)}
.vtext{margin-top:40px;font-weight:400;line-height:1.36;letter-spacing:-.005em;text-wrap:pretty;max-width:880px}
.vtext mark{color:inherit;background:linear-gradient(transparent 56%,var(--mark) 56%,var(--mark) 94%,transparent 94%);
  -webkit-box-decoration-break:clone;box-decoration-break:clone;padding:0 .06em}
.dark .vtext mark{background:none;font-style:italic;color:var(--accent)}
.vref{margin-top:46px;font:500 30px "WGSans";letter-spacing:.03em;color:var(--muted)}
.vref .tr{margin-left:12px;font-size:22px;letter-spacing:.12em;opacity:.8}

/* 소개 안쪽 장 */
.sbox{position:absolute;left:100px;right:100px;top:140px;bottom:210px;display:flex;flex-direction:column;
  justify-content:center}
.lab{font-style:italic;font-weight:400;font-size:46px;line-height:1.2;color:var(--muted)}
.sbox h2{margin:26px 0 0;font-weight:600;font-size:98px;line-height:1.02;letter-spacing:-.026em;text-wrap:balance;
  font-variation-settings:"SOFT" 100,"WONK" 0}
.sbox h2:first-child{margin-top:0}
.sbox p{margin:44px 0 0;font-size:46px;line-height:1.42;color:var(--soft);text-wrap:pretty}
.lines{margin-top:64px;display:flex;flex-direction:column;gap:26px}
.lines div{font-style:italic;font-size:54px;line-height:1.22;color:var(--soft);text-wrap:balance}

/* 마지막 장 */
.cbox{position:absolute;left:100px;right:100px;top:200px;bottom:230px;display:flex;flex-direction:column;
  justify-content:flex-end;align-items:flex-start}
.cbox h2{margin:0;font-weight:600;font-size:116px;line-height:1.0;letter-spacing:-.028em;text-wrap:balance;
  font-variation-settings:"SOFT" 100,"WONK" 0}
.cbox h2 em{font-weight:500}
.cbox p{margin:40px 0 0;font-size:48px;line-height:1.36;color:var(--soft);max-width:860px;text-wrap:pretty}
.pill{margin-top:58px;font:600 34px/1 "WGSans";background:var(--tag-bg);color:var(--tag-ink);padding:22px 40px;
  border-radius:999px;transform:rotate(-2deg);transform-origin:left center;box-shadow:0 10px 24px rgba(0,0,0,.12)}
.extra{margin-top:40px;font-style:italic;font-size:40px;line-height:1.35;color:var(--muted)}

/* 사용법 */
.stop{position:absolute;left:100px;right:100px;top:92px;display:flex;gap:34px;align-items:flex-start}
.num{flex:none;font-style:italic;font-weight:500;font-size:160px;line-height:.8;color:var(--accent);margin-top:6px}
.stop h2{margin:4px 0 0;font-weight:600;font-size:78px;line-height:1.02;letter-spacing:-.024em;text-wrap:balance;
  font-variation-settings:"SOFT" 100,"WONK" 0}
.stop p{margin:16px 0 0;font-size:40px;line-height:1.35;color:var(--soft);text-wrap:balance}
.phone{position:absolute;left:50%;transform:translateX(-50%);top:450px;width:760px;height:1100px;
  border:16px solid #20263A;border-bottom:none;border-radius:104px 104px 0 0;overflow:hidden;background:#fff;
  box-shadow:0 30px 70px rgba(30,36,51,.22)}
.phone img{display:block;width:100%}
"""

FIT_JS = """
<script>
function overflows(box){
  var b = box.getBoundingClientRect(), kids = box.children;
  var top = kids[0].getBoundingClientRect().top;
  var bottom = kids[kids.length - 1].getBoundingClientRect().bottom;
  return top < b.top - 1 || bottom > b.bottom + 1;
}
function fit(sel, boxSel, minPx){
  document.querySelectorAll(sel).forEach(function(el){
    var box = el.closest(boxSel), size = parseFloat(getComputedStyle(el).fontSize), guard = 0;
    while ((overflows(box) || el.scrollWidth > el.clientWidth + 1) && size > minPx && guard++ < 80) {
      size -= 2; el.style.fontSize = size + 'px';
    }
  });
}
/* 낱말을 span 으로 감싼다(형광펜 등 안쪽 태그는 그대로 둔다). */
function wrapWords(el){
  var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(function(t){
    var frag = document.createDocumentFragment();
    t.nodeValue.split(/(\\s+)/).forEach(function(p){
      if (!p) return;
      if (/^\\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
      var s = document.createElement('span'); s.className = 'w'; s.textContent = p; frag.appendChild(s);
    });
    t.parentNode.replaceChild(frag, t);
  });
}
/* 마지막 줄에 한 단어만 남으면(외톨이 단어) 폭을 조금씩 줄여 다시 나눈다. */
function noOrphan(sel){
  document.querySelectorAll(sel).forEach(function(el){
    wrapWords(el);
    var ws = el.querySelectorAll('span.w');
    if (ws.length < 4) return;
    var base = el.clientWidth;
    for (var cut = 0; cut <= 200; cut += 10) {
      el.style.maxWidth = (base - cut) + 'px';
      if (ws[ws.length - 1].getBoundingClientRect().top === ws[ws.length - 2].getBoundingClientRect().top) return;
    }
    el.style.maxWidth = base + 'px';
  });
}
document.fonts.ready.then(function(){
  fit('.vtext', '.vbox', 38); noOrphan('.vtext'); fit('.vtext', '.vbox', 38);
  fit('.cover h1', '.cover', 64); fit('.sbox h2', '.sbox', 56); fit('.cbox h2', '.cbox', 56);
});
</script>
"""

ARROW = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
         'stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h15M13 6l6 6-6 6"/></svg>')


def rich(text: str) -> str:
    """HTML 이스케이프 + *강조* → <em>, 줄바꿈 → <br>."""
    out = html.escape(text)
    out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)
    return out.replace("\n", "<br>")


def verse_html(v: dict) -> str:
    text, emph = html.escape(v["text"]), html.escape(v["emph"])
    return text.replace(emph, f"<mark>{emph}</mark>", 1)


def lower_first(text: str) -> str:
    return text[0].lower() + text[1:]


def verse_size(text: str) -> int:
    n = len(text)
    if n <= 80:
        return 78
    if n <= 130:
        return 70
    if n <= 190:
        return 62
    return 56


def foot(arrow: bool = False) -> str:
    return f'<div class="foot"><span>@withgod.app</span>{ARROW if arrow else ""}</div>'


def slide_html(s: dict, pal: str) -> str:
    k = s["kind"]
    cls = f"s p-{pal}" + (" dark" if pal in DARK else "")
    stars = '<div class="stars"></div>' if pal == "night" else ""
    if k == "cover":
        body = (f'<div class="tag">{html.escape(s["kicker"])}</div>'
                f'<div class="cover"><h1>{rich(s["headline"])}</h1></div>{foot(arrow=True)}')
    elif k == "verse":
        v = s["verse"]
        body = (f'<div class="vbox"><div class="vlabel">{html.escape(lower_first(s["label"]))}</div>'
                f'<div class="vtext" style="font-size:{verse_size(v["text"])}px">{verse_html(v)}</div>'
                f'<div class="vref">{html.escape(v["ref"])}<span class="tr">WEB</span></div></div>{foot()}')
    elif k == "list":
        lines = "".join(f"<div>{html.escape(x)}</div>" for x in s["lines"])
        body = f'<div class="sbox"><h2>{rich(s["headline"])}</h2><div class="lines">{lines}</div></div>{foot()}'
    elif k == "statement":
        body = (f'<div class="sbox"><div class="lab">{html.escape(s["kicker"])}</div><h2>{rich(s["headline"])}</h2>'
                f'<p>{html.escape(s["body"])}</p></div>{foot()}')
    elif k == "cta":
        inner = f'<h2>{rich(s["headline"])}</h2>'
        if s.get("body"):
            inner += f'<p>{rich(s["body"])}</p>'
        inner += '<div class="pill">Link in bio</div>'
        if s.get("extra"):
            inner += f'<div class="extra">{rich(s["extra"])}</div>'
        body = f'<div class="cbox">{inner}</div>{foot()}'
    elif k == "step":
        body = (f'<div class="stop"><div class="num">{s["num"]}</div><div><h2>{rich(s["headline"])}</h2>'
                f'<p>{html.escape(s["body"])}</p></div></div>'
                f'<div class="phone"><img src="ASSETS/{s["shot"]}.png"></div>')
    else:
        raise ValueError(k)
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f'<body><div class="{cls}">{stars}{body}</div>{FIT_JS}</body></html>')


def slide_pal(post: dict, s: dict) -> str:
    pal = post["pal"]
    if s["kind"] == "cover":
        return pal["cover"]
    if s["kind"] == "cta":
        return pal["cta"]
    return pal["inner"]


# ---------------------------------------------------------------- 자산(앱 화면)

def make_assets(dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    shot = Image.open(APP_SHOT).convert("RGB")
    header_h = 369  # 상태 표시줄 + 「Words of Comfort」 머리(고정)

    def view(offset: int, height: int = 1900) -> Image.Image:
        """머리는 고정한 채 본문만 offset 만큼 스크롤한 화면."""
        canvas = Image.new("RGB", (shot.width, height), (249, 250, 251))
        canvas.paste(shot.crop((0, 0, shot.width, header_h)), (0, 0))
        body = shot.crop((0, header_h + offset, shot.width, min(shot.height, header_h + offset + height - header_h)))
        canvas.paste(body, (0, header_h))
        return canvas

    def spotlight(img: Image.Image, box, radius=44) -> Image.Image:
        """box 밖을 옅게 덮고, box 둘레에 파란 테를 두른다."""
        img = img.convert("RGBA")
        mask = Image.new("L", img.size, 150)
        ImageDraw.Draw(mask).rounded_rectangle(box, radius, fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(3))
        veil = Image.new("RGBA", img.size, (243, 240, 233, 255))  # .p-paper 바탕색
        veil.putalpha(mask)
        out = Image.alpha_composite(img, veil)
        d = ImageDraw.Draw(out)
        x0, y0, x1, y1 = box
        d.rounded_rectangle((x0 - 6, y0 - 6, x1 + 6, y1 + 6), radius + 6, outline=(74, 144, 226, 255), width=8)
        return out.convert("RGB")

    spotlight(view(0), (262, 421, 1166, 653)).save(dst / "step1.png")
    spotlight(view(0), (44, 826, 1162, 1306)).save(dst / "step2.png")
    off = 860
    spotlight(view(off), (104, 1338 - off, 1102, 2478 - off), radius=40).save(dst / "step3.png")


# ---------------------------------------------------------------- 렌더

def render(jobs: list[tuple[Path, Path]], workers: int = 6) -> None:
    def shoot(job):
        html_path, png_path = job
        # 헤드리스 창은 가끔 보이는 높이가 창보다 87px 짧게 잡힌다(동시 실행 때). 넉넉한 창으로 찍고 위 1350 만 자른다.
        with tempfile.TemporaryDirectory() as prof:
            subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                 "--force-device-scale-factor=1", f"--window-size={W},{H + 200}",
                 "--virtual-time-budget=4000", f"--user-data-dir={prof}",
                 "--allow-file-access-from-files",
                 f"--screenshot={png_path}", html_path.as_uri()],
                check=True, capture_output=True, timeout=120,
            )
        im = Image.open(png_path).convert("RGB").crop((0, 0, W, H))
        bottom = [im.getpixel((x, H - 1)) for x in (5, W // 2, W - 5)]
        assert all(px != (255, 255, 255) for px in bottom), (png_path, "아래가 비어 있다")
        im.save(png_path)

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(shoot, jobs))


def main() -> None:
    posts = build_posts()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix="ig-launch-"))
    make_assets(work / "assets")

    jobs = []
    for p in posts:
        pdir = OUT / p["slug"]
        pdir.mkdir()
        for i, s in enumerate(p["slides"], 1):
            doc = slide_html(s, slide_pal(p, s))
            doc = doc.replace("FONTS/", (TOOLS / "fonts").as_uri() + "/")
            doc = doc.replace("ASSETS/", (work / "assets").as_uri() + "/")
            hp = work / f"{p['slug']}-{i:02d}.html"
            hp.write_text(doc, encoding="utf-8")
            jobs.append((hp, pdir / f"{i:02d}.png"))
    render(jobs)
    write_captions(posts)
    write_previews(posts)
    shutil.rmtree(work)
    print(f"{len(posts)} posts, {len(jobs)} images → {OUT}")


# ---------------------------------------------------------------- 캡션·미리보기

UPLOAD_ORDER = ["09-psalm-118-24", "08-when-youre-waiting", "07-psalm-34-18",
                "06-matthew-11-28", "05-when-you-feel-alone", "04-isaiah-41-10",
                "03-pinned-nights", "02-pinned-how-it-works", "01-pinned-intro"]


def alt_text(s: dict) -> str:
    k = s["kind"]
    if k == "verse":
        v = s["verse"]
        return f"Bible verse card. {s['label']}: “{v['text']}” {v['ref']} (World English Bible)."
    if k == "cover":
        return f"{plain(s['headline'])} (title card)"
    if k == "step":
        return f"Step {s['num']}: {s['headline']} {s['body']} Screenshot of the WithGod app."
    if k == "list":
        return plain(s["headline"]) + " " + " ".join(s["lines"])
    if k == "cta":
        return " ".join(x for x in [plain(s["headline"]), plain(s.get("body", "")), "Link in bio.",
                                    plain(s.get("extra", ""))] if x)
    return f"{plain(s['headline'])} {s['body']}"


def write_captions(posts: list[dict]) -> None:
    by_slug = {p["slug"]: p for p in posts}
    out = ["# @withgod.app 런칭 게시물 9개 — 캡션", "",
           "올리는 순서는 아래 번호 순서(오래된 것부터). 그리드는 최신이 왼쪽 위라서 거꾸로 올린다.",
           "하루 3개씩 사흘에 나눠 올린다(1~3 → 4~6 → 7~9). 마지막 날 고정용 3개를 올린 뒤 "
           "**03 → 02 → 01 순서로 고정**하면 01 이 맨 왼쪽에 온다. 순서가 다르게 보이면 고정을 풀고 다시 고정한다.",
           "캡션은 코드 블록을 그대로 복사해 붙인다. 대체 텍스트는 각 게시물의 고급 설정 → 대체 텍스트에 넣는다.", ""]
    for n, slug in enumerate(UPLOAD_ORDER, 1):
        p = by_slug[slug]
        kind = f"캐러셀 {len(p['slides'])}장" if len(p["slides"]) > 1 else "이미지 1장"
        day = (n - 1) // 3 + 1
        out += [f"## {n}. `{slug}` — {p['title']} ({kind}, {day}일째)", "",
                "```", p["caption"], "```", "", "<details><summary>대체 텍스트</summary>", ""]
        out += [f"{i}. {plain(alt_text(s))}" for i, s in enumerate(p["slides"], 1)]
        out += ["", "</details>", ""]
    (OUT / "captions.md").write_text("\n".join(out), encoding="utf-8")


def write_previews(posts: list[dict]) -> None:
    # 프로필 그리드: 4:5 이미지를 3:4 로 가운데 잘라 3열로(인스타 프로필 그리드와 같은 비율).
    tw, th, gap = 360, 480, 6
    grid = Image.new("RGB", (tw * 3 + gap * 2, th * 3 + gap * 2), (255, 255, 255))
    for i, p in enumerate(posts):
        im = Image.open(OUT / p["slug"] / "01.png")
        cw = int(H * 3 / 4)
        x0 = (W - cw) // 2
        thumb = im.crop((x0, 0, x0 + cw, H)).resize((tw, th), Image.LANCZOS)
        r, c = divmod(i, 3)
        grid.paste(thumb, (c * (tw + gap), r * (th + gap)))
    grid.save(OUT / "grid-preview.png")

    # 게시물별 한눈에 보기(캐러셀만)
    for p in posts:
        if len(p["slides"]) == 1:
            continue
        files = sorted((OUT / p["slug"]).glob("*.png"))
        sw, sh, g = 270, 338, 10
        sheet = Image.new("RGB", (len(files) * (sw + g) - g, sh), (255, 255, 255))
        for i, f in enumerate(files):
            sheet.paste(Image.open(f).resize((sw, sh), Image.LANCZOS), (i * (sw + g), 0))
        sheet.save(OUT / f"sheet-{p['slug']}.png")


if __name__ == "__main__":
    main()
