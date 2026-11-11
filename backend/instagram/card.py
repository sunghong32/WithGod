"""Daily Verse 카드 이미지(1080×1350 JPEG) 렌더러 — 이 맥에서만 돈다 (이슈 #62).

런칭 게시물의 말씀 카드(`docs/instagram/tools/make_launch_posts.py` 의 verse 슬라이드)를 그대로 옮겼다 —
크림 종이 바탕, 위에 파란 라벨(「WHEN YOU’RE AFRAID」)과 짧은 선, Noto Serif 본문, 참조 + WEB, 아래 앱 아이콘과
@withgod.app. 계정 그리드 톤이 런칭 9개와 같아야 해서 값(색·글꼴·여백·크기)을 바꾸지 않았다.

- HTML 을 Chrome 헤드리스로 찍고(글줄 균형 `text-wrap:pretty` 와 넘칠 때 글자 줄이기를 브라우저에 맡긴다)
  Pillow 로 JPEG 로 바꾼다(API 는 JPEG 만 받는다).
- 프로필 그리드는 4:5 를 가운데 3:4 로 잘라(양옆 34px씩) 보여 준다. 글자 상자는 좌우 104px 안쪽이라 안전하다.
- 운영 서버(1GB)는 렌더하지 않는다. 376장을 미리 찍어 S3 에 올려 두고 서버는 게시만 한다.
"""
from __future__ import annotations

import html
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
LOGO = HERE / "assets" / "logo.png"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1080, 1350
JPEG_QUALITY = 92

CSS = """
@font-face{font-family:Inter;src:url(FONTS/inter_medium.ttf);font-weight:500}
@font-face{font-family:Inter;src:url(FONTS/inter_semibold.ttf);font-weight:600}
@font-face{font-family:"WGSerif";src:url(FONTS/NotoSerif-Regular.ttf);font-weight:400;font-style:normal}
:root{--paper:#FBF7EF;--ink:#17223A;--ink2:#465068;--accent:#2D6EC3;--muted:#7B8091}
*{box-sizing:border-box}
html,body{margin:0;width:1080px;height:1350px;overflow:hidden}
body{font-family:Inter;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.slide{position:relative;width:1080px;height:1350px;overflow:hidden;background:var(--paper);color:var(--ink)}
.foot{position:absolute;left:104px;right:104px;bottom:76px;display:flex;align-items:center;
  justify-content:center;font-size:28px;font-weight:500;letter-spacing:.01em}
.brand{display:flex;align-items:center;gap:16px;color:var(--muted)}
.brand img{width:56px;height:56px;border-radius:50%}
.vbox{position:absolute;left:104px;right:104px;top:110px;bottom:200px;display:flex;
  flex-direction:column;justify-content:center;align-items:center;text-align:center}
.vlabel{font-size:28px;font-weight:600;letter-spacing:.15em;text-transform:uppercase;color:var(--accent)}
.rule{width:56px;height:3px;background:var(--accent);opacity:.55;margin:40px 0 48px;border-radius:2px}
.vtext{font-family:"WGSerif";font-weight:400;font-size:64px;line-height:1.44;color:var(--ink);
  text-wrap:pretty;max-width:872px}
.vref{margin-top:52px;font-size:32px;font-weight:500;color:var(--ink2);letter-spacing:.01em}
.vref .tr{margin-left:14px;font-size:22px;font-weight:600;letter-spacing:.12em;color:var(--muted)}
/* 파란 바탕(런칭 표지와 같은 그라데이션·원) */
.blue{background:linear-gradient(165deg,#5CA3FA 0%,#3A7ED6 100%);color:#FCF7EC}
.blob{position:absolute;border-radius:50%;background:rgba(255,255,255,.07)}
.blue .vlabel{color:rgba(252,247,236,.85)}
.blue .rule{background:#FCF7EC;opacity:.6}
.blue .vtext{color:#FCF7EC}
.blue .vref{color:rgba(252,247,236,.92)}
.blue .vref .tr{color:rgba(252,247,236,.7)}
.blue .brand{color:rgba(252,247,236,.9)}
.blue .brand img{box-shadow:0 0 0 3px rgba(252,247,236,.9)}
/* 명화 전면 — 그림 위에 옅은 어둠을 깔고 크림색 글자 */
.art{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.full .scrim{position:absolute;inset:0;background:
  linear-gradient(180deg, rgba(10,14,26,.18) 0%, rgba(10,14,26,.46) 26%, rgba(10,14,26,.52) 62%, rgba(10,14,26,.66) 100%)}
.full .vlabel{color:rgba(252,247,236,.92)}
.full .rule{background:#FCF7EC;opacity:.7}
.full .vtext{color:#FCF7EC;text-shadow:0 2px 24px rgba(0,0,0,.35)}
.full .vref{color:rgba(252,247,236,.95)}
.full .vref .tr{color:rgba(252,247,236,.72)}
.full .brand{color:rgba(252,247,236,.92)}
.full .brand img{box-shadow:0 0 0 3px rgba(252,247,236,.9)}
/* 명화 액자 — 위에 그림, 아래 종이에 말씀(도록 한 쪽처럼) */
.plate .frame{position:absolute;left:84px;right:84px;top:84px;height:600px;overflow:hidden;
  box-shadow:0 1px 2px rgba(23,34,58,.10),0 22px 46px rgba(23,34,58,.16)}
.plate .frame .art{position:absolute}
.plate .vbox{top:730px;bottom:170px}
.plate .rule{margin:26px 0 30px}
.plate .vref{margin-top:34px}
.plate .foot{bottom:64px}
"""

# 상자를 넘치면 본문 글자를 2px씩 줄인다(최소 38px). 다 되면 data-ready 를 단다.
FIT_JS = """
<script>
function overflows(box){
  var b = box.getBoundingClientRect(), kids = box.children;
  var top = kids[0].getBoundingClientRect().top;
  var bottom = kids[kids.length - 1].getBoundingClientRect().bottom;
  return top < b.top - 1 || bottom > b.bottom + 1;
}
document.fonts.ready.then(function(){
  var el = document.querySelector('.vtext'), box = el.closest('.vbox');
  var size = parseFloat(getComputedStyle(el).fontSize), guard = 0;
  while ((overflows(box) || el.scrollWidth > el.clientWidth + 1) && size > 38 && guard++ < 80) {
    size -= 2; el.style.fontSize = size + 'px';
  }
  document.body.setAttribute('data-ready', '1');
  document.body.setAttribute('data-size', String(size));
});
</script>
"""


def verse_size(text: str) -> int:
    """본문 길이별 시작 글자 크기(런칭 카드와 같은 계단)."""
    n = len(text)
    if n <= 80:
        return 74
    if n <= 130:
        return 66
    if n <= 190:
        return 60
    return 54


def card_html(*, kicker: str, text: str, ref: str, theme: str = "paper", art: str = "",
              focus: str = "50% 50%") -> str:
    """theme: paper(크림) · blue(파랑) · full(명화 전면) · plate(명화 액자). art 는 그림 파일 경로,
    focus 는 그림을 자를 때 남길 자리(CSS object-position)."""
    e = html.escape
    size = verse_size(text)
    deco = ""
    if theme == "blue":
        deco = ('<div class="blob" style="width:760px;height:760px;right:-300px;top:-260px"></div>'
                '<div class="blob" style="width:420px;height:420px;left:-170px;bottom:-120px"></div>')
    elif theme == "full":
        deco = f'<img class="art" src="{Path(art).as_uri()}" style="object-position:{focus}"><div class="scrim"></div>'
    elif theme == "plate":
        deco = (f'<div class="frame"><img class="art" src="{Path(art).as_uri()}" '
                f'style="object-position:{focus}"></div>')
        size = round(size * 0.78)  # 글자 상자가 절반쯤이라 시작 크기를 줄인다
    body = (
        f'<div class="slide {theme}">{deco}'
        f'<div class="vbox"><div class="vlabel">{e(kicker)}</div><div class="rule"></div>'
        f'<div class="vtext" style="font-size:{size}px">{e(text)}</div>'
        f'<div class="vref">{e(ref)}<span class="tr">WEB</span></div></div>'
        '<div class="foot"><div class="brand"><img src="LOGO"><span>@withgod.app</span></div></div>'
        '</div>'
    )
    doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}{FIT_JS}</body></html>"
    return doc.replace("FONTS/", FONTS.as_uri() + "/").replace("LOGO", LOGO.as_uri())


def _shoot(html_path: Path, png_path: Path) -> None:
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1", f"--window-size={W},{H}",
             "--virtual-time-budget=4000", f"--user-data-dir={profile}",
             "--allow-file-access-from-files", f"--screenshot={png_path}", html_path.as_uri()],
            check=True, capture_output=True, timeout=120,
        )


def render_cards(cards: list[dict], out_dir: Path, workers: int = 6) -> list[Path]:
    """cards: [{"name": 파일 이름(확장자 없이), "kicker", "text", "ref"}] → out_dir/<name>.jpg 목록."""
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="ig-daily-"))

    def one(card: dict) -> Path:
        html_path = work / f"{card['name']}.html"
        png_path = work / f"{card['name']}.png"
        html_path.write_text(card_html(kicker=card["kicker"], text=card["text"], ref=card["ref"],
                                       theme=card.get("theme", "paper"), art=card.get("art", ""),
                                       focus=card.get("focus", "50% 50%")),
                             encoding="utf-8")
        _shoot(html_path, png_path)
        im = Image.open(png_path).convert("RGB")
        if im.size != (W, H):
            raise RuntimeError(f"{card['name']}: 크기 {im.size}")
        jpg = out_dir / f"{card['name']}.jpg"
        # 4:4:4(subsampling=0) — 4:2:0 이면 파란 라벨·가는 글자 가장자리가 번진다.
        im.save(jpg, "JPEG", quality=JPEG_QUALITY, subsampling=0, optimize=True)
        return jpg

    try:
        with ThreadPoolExecutor(workers) as ex:
            return list(ex.map(one, cards))
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
