"""Daily Verse 캐러셀 슬라이드(1080×1350 JPEG) 렌더러 — 이 맥에서만 돈다 (이슈 #62).

디자인은 런칭 게시물(`docs/instagram/tools/make_launch_posts.py`)과 같은 틀이다 — 감정별 하늘빛 팔레트 +
필름 질감, Fraunces 본문, 핵심 구절 형광펜, 왼쪽 정렬, 아래 @withgod.app. 프로필 그리드가 런칭 9개와
한 계정으로 보여야 해서 팔레트·글꼴·여백 값을 그대로 옮겼다.

슬라이드 종류(한 게시물 = 표지 → [말씀] → 앱 풀이, 수·일요일엔 + 앱 안내):
- cover: 표지(그리드·피드에 보이는 장). 위에서부터 「Daily Bible Verse」 → 감정 라벨 스티커(수평) → 말씀 한 줄
  (카피의 `line`, 가장 큰 글씨) → 장절. 오늘의 한 단어(`word`)는 아래 빈 곳에 아주 크고 옅게 깐다.
  11/23 사용자: "대충 넘기면 성경 게시글인지 안 보인다" — 그 전 표지는 한 단어를 300px 로 크게 둔 것이었다.
  말씀은 분위기와 상관없이 늘 위쪽에서 시작한다(아래에 두면 배경 단어와 겹쳐 읽기 어렵다).
  그림·사진은 쓰지 않는다(11/19 사용자: "사진을 안 쓰는 방향으로 우리만의 디자인").
- verse: 말씀 전문 + 라벨 + 참조. 표지 한 줄이 절 전체면 빠진다(같은 말씀을 두 번 보여 주지 않는다).
- note: 앱의 영어 풀이 전문(AI 로 쓴 것이라 그렇게 밝힌다). 캡션 대신 카드에 실어 게시물 하나로 읽히게 한다.
- app: 앱 안내(수·일요일만).

분위기(`mood`, 카피의 주제 태그에서 정한다 — caption.mood_for): 표지·말씀·풀이 장이 같은 배경 요소를 써서
넘겨도 한 장처럼 이어진다. 오늘의 말씀이 늘 밝지는 않아서(11/19 사용자) 말씀 성격에 따라 바꾼다.
- comfort 위로: 둥근 달빛(어두운 팔레트면 옅은 별), 표지 배경 단어는 기울임
- hope 소망: 아래에서 빛이 올라옴(어두운 팔레트면 별 — 밤에서 시작하는 소망)
- peace 평안: 왼쪽 위 둥근 빛
- wisdom 지혜: 말씀·풀이 장 위쪽에 강조색 선, 표지 배경 단어는 기울임
- joy 기쁨: 오른쪽 위 해

HTML 을 Chrome 헤드리스로 찍고 Pillow 로 JPEG 로 바꾼다(API 는 JPEG 만 받는다). 운영 서버(1GB)는 렌더하지
않는다 — 미리 찍어 S3 에 올려 두고 서버는 게시만 한다.
"""
from __future__ import annotations

import html
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1080, 1350
JPEG_QUALITY = 92

# 어두운 팔레트 — 형광펜 대신 이탤릭 강조색을 쓴다(런칭과 같다).
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

/* 팔레트(런칭과 같은 값) */
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
mark{color:inherit;background:linear-gradient(transparent 56%,var(--mark) 56%,var(--mark) 94%,transparent 94%);
  -webkit-box-decoration-break:clone;box-decoration-break:clone;padding:0 .06em}
.dark mark{background:none;font-style:italic;color:var(--accent)}
.foot{position:absolute;left:100px;right:100px;bottom:80px;display:flex;justify-content:space-between;
  align-items:center;font:500 28px "WGSans";letter-spacing:.01em;color:var(--muted)}
.foot svg{width:44px;height:44px}
.lab{font-style:italic;font-weight:400;font-size:46px;line-height:1.2;color:var(--muted)}

/* 표지(말씀) */
.vbox{position:absolute;left:100px;right:100px;top:140px;bottom:210px;display:flex;flex-direction:column;
  justify-content:center}
.vtext{margin-top:40px;font-weight:400;line-height:1.36;letter-spacing:-.005em;text-wrap:pretty;max-width:880px}
.vref{margin-top:46px;font:500 30px "WGSans";letter-spacing:.03em;color:var(--muted)}
.vref .tr{margin-left:12px;font-size:22px;letter-spacing:.12em;opacity:.8}

/* 표지 — 위에서부터 「Daily Bible Verse」 → 감정 스티커 → 말씀 → 장절, 아래에 오늘의 한 단어를 옅게 */
.head{position:absolute;left:100px;top:104px;font-style:italic;font-weight:500;font-size:60px;line-height:1;
  letter-spacing:-.012em;color:var(--accent);font-variation-settings:"SOFT" 100,"WONK" 0}
.tag{position:absolute;left:100px;top:196px;font:600 30px/1 "WGSans";letter-spacing:.01em;background:var(--tag-bg,var(--ink));
  color:var(--tag-ink,#FBF4E6);padding:16px 30px;border-radius:999px;box-shadow:0 8px 20px rgba(0,0,0,.10);max-width:860px}
.cvbox{position:absolute;left:100px;right:96px;top:318px;bottom:470px;display:flex;flex-direction:column;
  justify-content:flex-start}
.ctext{font-weight:400;line-height:1.28;letter-spacing:-.008em;color:var(--ink);text-wrap:pretty;max-width:884px;
  font-variation-settings:"SOFT" 60,"WONK" 0}
.cref{margin-top:40px;font:600 38px "WGSans";letter-spacing:.015em;color:var(--ink)}
.cref .tr{margin-left:14px;font:500 24px "WGSans";letter-spacing:.12em;color:var(--muted)}
.ghost{position:absolute;left:-30px;bottom:150px;font-weight:700;font-size:420px;line-height:.8;white-space:nowrap;
  letter-spacing:-.05em;color:var(--ink);opacity:.07;font-variation-settings:"SOFT" 100,"WONK" 1;pointer-events:none}
.dark .ghost{opacity:.09}
.m-comfort .ghost,.m-wisdom .ghost{font-style:italic;font-weight:400}

/* 분위기별 배경 요소(표지·말씀·풀이 장 공통) */
.fx{position:absolute;pointer-events:none}
.stars{left:0;top:0;width:3px;height:3px;border-radius:50%;background:#fff;opacity:.55;
  box-shadow:120px 160px #fff,300px 90px #fffbe8,520px 210px #fff,760px 120px #fff,900px 300px #fffbe8,
  640px 380px #fff,210px 330px #fff,980px 70px #fff,420px 60px #fff,840px 470px #fff,60px 520px #fff,
  350px 470px #fffbe8,1010px 560px #fff,700px 600px #fffbe8}
.moon{right:-120px;top:-120px;width:560px;height:560px;border-radius:50%;
  background:radial-gradient(circle,rgba(255,255,255,.6),rgba(255,255,255,0) 68%)}
.dark .moon{background:radial-gradient(circle,rgba(255,236,210,.30),rgba(255,236,210,0) 68%)}
.rise{left:-25%;right:-25%;bottom:-460px;height:1100px;border-radius:50%;
  background:radial-gradient(closest-side,rgba(255,240,206,.95),rgba(255,240,206,0))}
.dark .rise{background:radial-gradient(closest-side,rgba(255,196,140,.62),rgba(255,196,140,0))}
.halo{left:-260px;top:-260px;width:900px;height:900px;border-radius:50%;
  background:radial-gradient(circle,rgba(255,255,255,.8),rgba(255,255,255,0) 68%)}
.dark .halo{background:radial-gradient(circle,rgba(255,255,255,.14),rgba(255,255,255,0) 68%)}
.sunr{right:-240px;top:-240px;width:860px;height:860px;border-radius:50%;
  background:radial-gradient(circle,rgba(255,252,236,1) 0%,rgba(255,241,200,.9) 36%,rgba(255,226,170,0) 70%)}
.wrule{left:100px;top:118px;width:150px;height:5px;background:var(--accent)}

/* 앱 풀이 */
.nbox{position:absolute;left:100px;right:100px;top:130px;bottom:205px;display:flex;flex-direction:column;
  justify-content:center}
.nbox p{margin:30px 0 0;line-height:1.42;letter-spacing:-.004em;text-wrap:pretty}
.extra{margin-top:48px;font-style:italic;font-size:40px;line-height:1.35;color:var(--muted);text-wrap:pretty}
.src{position:absolute;left:100px;right:100px;bottom:140px;font:500 22px/1.3 "WGSans";letter-spacing:.02em;
  color:var(--muted);opacity:.85}

/* 앱 안내 */
.cbox{position:absolute;left:100px;right:100px;top:200px;bottom:230px;display:flex;flex-direction:column;
  justify-content:flex-end;align-items:flex-start}
.cbox h2{margin:0;font-weight:600;font-size:116px;line-height:1.0;letter-spacing:-.028em;text-wrap:balance;
  font-variation-settings:"SOFT" 100,"WONK" 0}
.cbox h2 em{font-weight:500}
.cbox p{margin:40px 0 0;font-size:48px;line-height:1.36;color:var(--soft);max-width:860px;text-wrap:pretty}
.pill{margin-top:58px;font:600 34px/1 "WGSans";background:var(--tag-bg);color:var(--tag-ink);padding:22px 40px;
  border-radius:999px;transform:rotate(-2deg);transform-origin:left center;box-shadow:0 10px 24px rgba(0,0,0,.12)}
"""

# 상자를 넘치면 글자를 2px씩 줄이고, 마지막 줄 외톨이 단어를 피한다(런칭과 같은 방식).
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
function fitGhost(){
  // 배경 단어가 오른쪽 밖으로 잘려 「Humilit」처럼 끊기지 않게 폭에 맞춘다(왼쪽만 살짝 넘친다).
  document.querySelectorAll('.ghost').forEach(function(el){
    var size = parseFloat(getComputedStyle(el).fontSize), guard = 0;
    while (el.getBoundingClientRect().right > 1080 - 24 && size > 200 && guard++ < 80) {
      size -= 6; el.style.fontSize = size + 'px';
    }
  });
}
document.fonts.ready.then(function(){
  fit('.vtext', '.vbox', 38); noOrphan('.vtext'); fit('.vtext', '.vbox', 38);
  fit('.ctext', '.cvbox', 46); noOrphan('.ctext'); fit('.ctext', '.cvbox', 46);
  fitGhost();
  fit('.nbox p', '.nbox', 32); noOrphan('.nbox p'); fit('.nbox p', '.nbox', 32);
  fit('.cbox h2', '.cbox', 56);
  document.body.setAttribute('data-ready', '1');
});
</script>
"""

ARROW = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
         'stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h15M13 6l6 6-6 6"/></svg>')


def verse_size(text: str) -> int:
    """본문 길이별 시작 글자 크기(런칭 카드와 같은 계단)."""
    n = len(text)
    if n <= 80:
        return 78
    if n <= 130:
        return 70
    if n <= 190:
        return 62
    return 56


def cover_size(text: str) -> int:
    """표지 말씀 길이별 시작 글자 크기. 표지 말씀은 둘째 장보다 크게 — 피드에서 첫눈에 읽히는 게 표지의 일이다."""
    n = len(text)
    if n <= 60:
        return 86
    if n <= 90:
        return 78
    if n <= 120:
        return 70
    return 62


def cover_emph(line: str, emph: str) -> str:
    """표지 말씀의 형광펜 구절 — 한 줄의 일부일 때만(한 줄이 거의 다 강조 구절이면 칠하지 않는다).
    강조 구절 끝의 쉼표·세미콜론은 뗀다(표지 한 줄이 그 앞에서 끝날 수 있다)."""
    emph = (emph or "").rstrip(",;")
    return emph if emph and emph in line and len(emph) < 0.8 * len(line) else ""


def note_size(text: str) -> int:
    """앱 풀이(영어 346~676자, 보통 470자) 길이별 시작 글자 크기. 넘치면 FIT_JS 가 더 줄인다."""
    n = len(text)
    if n <= 420:
        return 46
    if n <= 520:
        return 43
    if n <= 600:
        return 40
    return 38


def marked(text: str, emph: str = "", tag: str = "mark") -> str:
    """HTML 이스케이프 + 강조 구절(본문에 그대로 있어야 한다)을 <mark>/<em> 으로."""
    out = html.escape(text)
    if emph:
        e = html.escape(emph)
        if e not in out:
            raise ValueError(f"강조 구절이 본문에 없다: {emph!r}")
        out = out.replace(e, f"<{tag}>{e}</{tag}>", 1)
    return out


def rich(text: str) -> str:
    """*강조* → <em>, 줄바꿈 → <br>."""
    out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html.escape(text))
    return out.replace("\n", "<br>")


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _fx(mood: str, dark: bool, kind: str) -> str:
    """분위기 배경 요소. 표지·말씀·풀이 장에만(앱 안내 장은 브랜드 장이라 그대로)."""
    if not mood or kind not in ("cover", "verse", "note"):
        return ""
    stars = '<div class="fx stars"></div>' if dark else ""
    return {
        "comfort": stars + '<div class="fx moon"></div>',
        "hope": stars + '<div class="fx rise"></div>',
        "peace": '<div class="fx halo"></div>',
        "wisdom": "" if kind == "cover" else '<div class="fx wrule"></div>',  # 표지는 그 자리에 Daily Bible Verse
        "joy": '<div class="fx sunr"></div>',
    }[mood]


def _foot(arrow: bool) -> str:
    return f'<div class="foot"><span>@withgod.app</span>{ARROW if arrow else ""}</div>'


def slide_html(s: dict) -> str:
    """슬라이드 하나의 HTML. s["kind"] 별 필드는 모듈 설명 참고."""
    k, pal = s["kind"], s["pal"]
    cls = f"s p-{pal}" + (" dark" if pal in DARK else "")
    arrow = s.get("arrow", False)
    e = html.escape
    if s.get("mood"):
        cls += f" m-{s['mood']}"
    fx = _fx(s.get("mood", ""), pal in DARK, k)
    if k == "cover":
        line = s["line"]
        body = (f'<div class="ghost">{e(s["word"].rstrip("."))}</div>'
                '<div class="head">Daily Bible Verse</div>'
                f'<div class="tag">{e(lower_first(s["label"]))}</div>'
                f'<div class="cvbox"><div class="ctext" style="font-size:{cover_size(line)}px">'
                f'“{marked(line, cover_emph(line, s.get("emph", "")))}”</div>'
                f'<div class="cref">{e(s["ref"])}<span class="tr">WEB</span></div></div>')
    elif k == "verse":
        body = (f'<div class="vbox"><div class="lab">{e(lower_first(s["label"]))}</div>'
                f'<div class="vtext" style="font-size:{verse_size(s["text"])}px">{marked(s["text"], s.get("emph", ""))}</div>'
                f'<div class="vref">{e(s["ref"])}<span class="tr">WEB</span></div></div>')
    elif k == "note":
        body = (f'<div class="nbox"><div class="lab">{e(s["label"])}</div>'
                f'<p style="font-size:{note_size(s["body"])}px">{e(s["body"])}</p></div>'
                f'<div class="src">{e(s["source"])}</div>')
    elif k == "app":
        body = (f'<div class="cbox"><h2>{rich(s["headline"])}</h2>'
                + (f'<p>{rich(s["body"])}</p>' if s.get("body") else "")
                + '<div class="pill">Link in bio</div>'
                + (f'<div class="extra">{rich(s["extra"])}</div>' if s.get("extra") else "")
                + "</div>")
    else:
        raise ValueError(k)
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
           f'<body><div class="{cls}">{fx}{body}{_foot(arrow)}</div>{FIT_JS}</body></html>')
    return doc.replace("FONTS/", FONTS.as_uri() + "/")


def _shoot(html_path: Path, png_path: Path) -> None:
    # 헤드리스 창은 가끔 보이는 높이가 창보다 짧게 잡힌다(동시 실행 때). 넉넉한 창으로 찍고 위 1350 만 쓴다.
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1", f"--window-size={W},{H + 200}",
             "--virtual-time-budget=5000", f"--user-data-dir={profile}",
             "--allow-file-access-from-files", f"--screenshot={png_path}", html_path.as_uri()],
            check=True, capture_output=True, timeout=180,
        )


def render_slides(jobs: list[tuple[dict, Path]], workers: int = 6) -> list[Path]:
    """jobs: [(슬라이드, 저장할 .jpg 경로)] → 저장한 경로 목록."""
    from PIL import Image

    work = Path(tempfile.mkdtemp(prefix="ig-daily-"))

    def one(i_job: tuple[int, tuple[dict, Path]]) -> Path:
        i, (slide, jpg) = i_job
        html_path, png_path = work / f"{i}.html", work / f"{i}.png"
        html_path.write_text(slide_html(slide), encoding="utf-8")
        _shoot(html_path, png_path)
        im = Image.open(png_path).convert("RGB").crop((0, 0, W, H))
        bottom = [im.getpixel((x, H - 1)) for x in (5, W // 2, W - 5)]
        if any(px == (255, 255, 255) for px in bottom):
            raise RuntimeError(f"{jpg}: 아래가 비어 있다(창 높이)")
        jpg.parent.mkdir(parents=True, exist_ok=True)
        # 4:4:4(subsampling=0) — 4:2:0 이면 가는 글자 가장자리가 번진다.
        im.save(jpg, "JPEG", quality=JPEG_QUALITY, subsampling=0, optimize=True)
        return jpg

    try:
        with ThreadPoolExecutor(workers) as ex:
            return list(ex.map(one, enumerate(jobs)))
    finally:
        for f in work.iterdir():
            f.unlink()
        work.rmdir()


def grid_preview(images: list[Path], dst: Path, cols: int = 3) -> Path:
    """프로필 그리드처럼(4:5 를 가운데 3:4 로 잘라) 붙인 미리보기."""
    from PIL import Image

    tw, th, gap = 360, 480, 6
    rows = (len(images) + cols - 1) // cols
    grid = Image.new("RGB", (tw * cols + gap * (cols - 1), th * rows + gap * (rows - 1)), (255, 255, 255))
    cw = int(H * 3 / 4)
    x0 = (W - cw) // 2
    for i, path in enumerate(images):
        thumb = Image.open(path).crop((x0, 0, x0 + cw, H)).resize((tw, th), Image.LANCZOS)
        r, c = divmod(i, cols)
        grid.paste(thumb, (c * (tw + gap), r * (th + gap)))
    grid.save(dst)
    return dst


def sheet(images: list[Path], dst: Path, width: int = 360) -> Path:
    """캐러셀 한 게시물을 옆으로 이어 붙인 미리보기."""
    from PIL import Image

    h = round(width * H / W)
    gap = 12
    out = Image.new("RGB", (len(images) * (width + gap) - gap, h), (255, 255, 255))
    for i, p in enumerate(images):
        out.paste(Image.open(p).resize((width, h), Image.LANCZOS), (i * (width + gap), 0))
    out.save(dst)
    return dst
