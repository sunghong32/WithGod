"""Daily Verse 캐러셀 슬라이드(1080×1350 JPEG) 렌더러 — 이 맥에서만 돈다 (이슈 #62).

디자인은 런칭 게시물(`docs/instagram/tools/make_launch_posts.py`)과 같은 틀이다 — 감정별 하늘빛 팔레트 +
필름 질감, Fraunces 본문, 핵심 구절 형광펜, 왼쪽 정렬, 아래 @withgod.app. 프로필 그리드가 런칭 9개와
한 계정으로 보여야 해서 팔레트·글꼴·여백 값을 그대로 옮겼다.

슬라이드 종류(한 게시물 = 2~4장 캐러셀):
- verse: 표지. 말씀 + 라벨 + 참조. 그리드에 보이는 장.
- scene: 그 말씀의 장면(복음서 이야기) 또는 그림(잠언 비유). 위에 그림, 아래 짧은 설명과 그림 출처.
  그림은 퍼블릭 도메인 성화이거나, 이 맥에서 로컬 오픈소스 모델(Z-Image-Turbo, Apache-2.0)로 만든 그림이다
  (`instagram/build/art/`, 출처 기록은 `instagram/art_sources.json`).
- today: 앱 풀이에서 줄인 오늘의 한마디 + 저장 권유.
- app: 앱 안내(수·일요일만).

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
ART = HERE / "build" / "art"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1080, 1350
JPEG_QUALITY = 92
ART_H = 800  # scene 장의 그림 높이

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

/* 장면 */
.art{position:absolute;left:0;top:0;width:1080px;height:ART_Hpx;overflow:hidden;background:#000}
.art img{width:100%;height:100%;object-fit:cover;display:block}
.art::after{content:"";position:absolute;left:0;right:0;bottom:0;height:3px;background:rgba(0,0,0,.08)}
.sc{position:absolute;left:100px;right:100px;top:calc(ART_Hpx + 54px);bottom:150px;display:flex;flex-direction:column}
.sc .lab{font-size:40px}
.sc p{margin:18px 0 0;font-size:42px;line-height:1.34;letter-spacing:-.004em;color:var(--ink);text-wrap:pretty}
.credit{margin-top:26px;font:500 22px/1.3 "WGSans";letter-spacing:.02em;color:var(--muted);opacity:.9}

/* 오늘의 한마디 */
.tbox{position:absolute;left:100px;right:100px;top:150px;bottom:230px;display:flex;flex-direction:column;
  justify-content:center}
.tbox p{margin:36px 0 0;font-size:66px;line-height:1.26;letter-spacing:-.012em;text-wrap:pretty}
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
""".replace("ART_H", str(ART_H))

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
document.fonts.ready.then(function(){
  fit('.vtext', '.vbox', 38); noOrphan('.vtext'); fit('.vtext', '.vbox', 38);
  fit('.sc p', '.sc', 34); noOrphan('.sc p'); fit('.sc p', '.sc', 34);
  fit('.tbox p', '.tbox', 44); noOrphan('.tbox p'); fit('.tbox p', '.tbox', 44);
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


def art_path(art: str) -> Path:
    """그림 경로 — 상대 경로면 instagram/art/ 기준."""
    p = Path(art)
    return p if p.is_absolute() else ART / p


def _foot(arrow: bool) -> str:
    return f'<div class="foot"><span>@withgod.app</span>{ARROW if arrow else ""}</div>'


def slide_html(s: dict) -> str:
    """슬라이드 하나의 HTML. s["kind"] 별 필드는 모듈 설명 참고."""
    k, pal = s["kind"], s["pal"]
    cls = f"s p-{pal}" + (" dark" if pal in DARK else "")
    arrow = s.get("arrow", False)
    e = html.escape
    if k == "verse":
        body = (f'<div class="vbox"><div class="lab">{e(lower_first(s["label"]))}</div>'
                f'<div class="vtext" style="font-size:{verse_size(s["text"])}px">{marked(s["text"], s.get("emph", ""))}</div>'
                f'<div class="vref">{e(s["ref"])}<span class="tr">WEB</span></div></div>')
    elif k == "scene":
        src = art_path(s["art"]).as_uri()
        body = (f'<div class="art"><img src="{src}" style="object-position:{e(s.get("focus", "50% 50%"))}"></div>'
                f'<div class="sc"><div class="lab">{e(s["label"])}</div><p>{rich(s["body"])}</p>'
                f'<div class="credit">{e(s["credit"])}</div></div>')
    elif k == "today":
        body = (f'<div class="tbox"><div class="lab">{e(s["label"])}</div>'
                f'<p>{marked(s["body"], s.get("emph", ""), "em")}</p>'
                + (f'<div class="extra">{e(s["extra"])}</div>' if s.get("extra") else "")
                + "</div>"
                + (f'<div class="src">{e(s["source"])}</div>' if s.get("source") else ""))
    elif k == "app":
        body = (f'<div class="cbox"><h2>{rich(s["headline"])}</h2>'
                + (f'<p>{rich(s["body"])}</p>' if s.get("body") else "")
                + '<div class="pill">Link in bio</div>'
                + (f'<div class="extra">{rich(s["extra"])}</div>' if s.get("extra") else "")
                + "</div>")
    else:
        raise ValueError(k)
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
           f'<body><div class="{cls}">{body}{_foot(arrow)}</div>{FIT_JS}</body></html>')
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
