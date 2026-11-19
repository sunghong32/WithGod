"""릴스 렌더러. spec JSON: 장면(그림 + 카메라 키프레임) + 자막(시간·위치) → 1080×1920 MP4(무음 트랙).

    python3 render.py spec.json        # Pillow·ffmpeg·Google Chrome 필요(이 맥 전용)
    python3 render.py spec.json --only 1.0,7.5   # 그 시각의 스냅 jpg 만(영상 없이) — 자리 잡을 때 빠르게

음악은 music.swift 로 따로 만들어 ffmpeg 로 입힌다. 다 만든 편은 reel_queue.py add 로 월·수·금 예약에 넣는다.

카메라는 [시각, 중심x, 중심y, 폭](원본 픽셀) 키프레임 사이를 부드럽게(smoothstep) 움직인다. 9:16 창이 원본 밖으로
나가면 bg 색으로 채운다. 장면이 바뀔 때 fade 초 동안 앞 장면과 섞는다. 자막은 Chrome 으로 투명 PNG 를 찍어 얹는다.

장면 종류: img(그림 + cam) · video(영상 + cam) · screen(앱 녹화를 둥근 카드로 배경 위에 띄움 — 그림 없는 앱 시연용):
  {"screen": 녹화.mp4, "bgimg": 1080×1920 배경, "rect": [[시각, 카드 중심x, 중심y, 카드 폭(출력 픽셀)]…],
   "scroll": [[시각, 보여 줄 원본 첫 줄]…], "src_h": 보여 줄 원본 높이, "radius": 모서리(카드 폭 820 기준)}
  · panels(그림 두 곳을 나란히 — 성화 읽기의 비교): {"panels": [{"img", "box": [x, y, 폭, 높이](출력 픽셀),
   "cam": [[시각, 중심x, 중심y, 폭]…](원본 픽셀), "from": [dx, dy](들어올 때 밀려 들어오는 거리)}…],
   "under": [중심x, 중심y, 폭](흐리고 어둡게 깔 그림 창), "under_img"}
img 장면의 "marks"(성화 읽기 표시 — 그림 좌표라 카메라를 따라 움직인다):
  {"t0", "t1", "ring": [x, y, rx, ry], "draw": 0.45}    금색 동그라미가 draw 초 동안 그려진다
  {"t0", "t1", "spot": [x, y, rx, ry], "dim": 0.62}     그 타원 밖을 어둡게(조명)
  {"t0", "t1", "tag": html, "at": [x, y], "off": [dx, dy]}  번호(.num)·이름표(.lbl)를 그 점(+화면 픽셀 off)에 톡 띄운다
spec 의 "css" 는 자막 HTML 에 덧붙는다(편·시리즈마다 다른 글꼴·상자).
spec 의 "crf"(기본 18)는 화질 — 큰 PD 성화는 캔버스 결 때문에 18 이면 30Mbps 를 넘는다(인스타 상한 25Mbps), 22~24 로.
"""
import html, json, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

FONTS = Path(__file__).resolve().parent.parent / 'fonts'
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1080, 1920
CSS = f"""
@font-face{{font-family:"D";src:url({FONTS.as_uri()}/Fraunces-Variable.ttf);font-weight:100 900}}
@font-face{{font-family:"D";src:url({FONTS.as_uri()}/Fraunces-Italic-Variable.ttf);font-weight:100 900;font-style:italic}}
@font-face{{font-family:"S";src:url({FONTS.as_uri()}/inter_medium.ttf);font-weight:500}}
@font-face{{font-family:"I";src:url({FONTS.as_uri()}/inter_medium.ttf);font-weight:500}}
@font-face{{font-family:"I";src:url({FONTS.as_uri()}/inter_semibold.ttf);font-weight:600}}
@font-face{{font-family:"I";src:url({FONTS.as_uri()}/inter_bold.ttf);font-weight:700}}
html,body{{margin:0;width:{W}px;height:{H}px;background:transparent;overflow:hidden}}
body{{position:relative}}  /* low·hd(bottom 기준)를 창(H+200)이 아니라 1920 화면 기준으로 */
.b{{position:absolute;left:90px;right:150px;color:#FFF8EC;font-family:"D";font-variation-settings:"SOFT" 50;
  text-shadow:0 2px 24px rgba(0,0,0,.55),0 1px 3px rgba(0,0,0,.45)}}
.top{{top:300px}} .low{{bottom:520px}}
.h1{{font-size:70px;line-height:1.14;font-weight:500;letter-spacing:-.01em;text-wrap:balance}}
/* 첫 문장(훅) — 0초에 바로, 피드에서 넘기기 전에 읽히게 크고 굵게(11/19: 평균 시청 7~10초, 첫 화면 글씨가 작았다) */
.hook{{font-size:88px;line-height:1.06;font-weight:600;letter-spacing:-.018em;text-wrap:balance}}
.t{{font-size:60px;line-height:1.24;text-wrap:pretty}}
.it{{font-style:italic}}
.sub{{margin-top:22px;font:500 30px/1.35 "S";letter-spacing:.02em;color:rgba(255,248,236,.86)}}
.v{{font-size:60px;line-height:1.3;font-style:italic;color:#FFE2AE;text-wrap:pretty}}
.r{{margin-top:30px;font:500 32px "S";letter-spacing:.03em;color:rgba(255,248,236,.9)}}
.hd{{position:absolute;left:90px;bottom:470px;font:500 30px "S";color:rgba(255,248,236,.88);
  text-shadow:0 1px 10px rgba(0,0,0,.5)}}
p{{margin:0}} p+p{{margin-top:26px}}
/* 앱 화면처럼 밝은 바탕 위 자막: 어두운 둥근 상자(raw 로 쓴다) — 그림자 띠로는 흰 화면에서 안 읽힌다 */
.card{{position:absolute;left:70px;right:70px;padding:30px 40px;border-radius:30px;background:#120F18;
  color:#FFF8EC;font-family:"D";font-variation-settings:"SOFT" 50;font-size:54px;line-height:1.22;text-wrap:pretty;
  box-shadow:0 10px 40px rgba(0,0,0,.25)}}
.card.top{{top:250px}} .card.low{{bottom:500px}}
.card .q{{font-style:italic}}
/* 성화 읽기(11/19): 디테일 번호 띠 · 그림 위 번호/이름표 · 「성경에서는」 카드(위로의 말씀 금색 이탤릭과 다르게 바로 선 글씨) */
.tag{{display:inline-block;margin-bottom:20px;padding:9px 18px 10px;border-radius:999px;background:#F4C76A;color:#1A1208;
  font:700 27px/1 "I";letter-spacing:.09em;text-transform:uppercase;text-shadow:none}}
.num{{display:inline-block;width:86px;height:86px;border-radius:50%;background:#F4C76A;color:#1A1208;font:700 48px/86px "I";
  text-align:center;box-shadow:0 0 0 5px rgba(14,11,9,.55),0 6px 22px rgba(0,0,0,.55)}}
.lbl{{display:inline-block;padding:10px 20px 12px;border-radius:14px;background:rgba(14,11,9,.84);color:#FFF8EC;
  font:600 32px/1.15 "I";border:2px solid #F4C76A}}
.vc{{position:absolute;left:70px;right:110px;padding:26px 34px 30px;border-radius:22px;background:rgba(14,11,9,.86);
  border-left:7px solid #F4C76A;box-shadow:0 10px 40px rgba(0,0,0,.4)}}
.vc .ref{{font:700 26px "I";letter-spacing:.13em;color:#F4C76A;text-transform:uppercase;margin-bottom:14px}}
.vc .q{{font-family:"D";font-variation-settings:"SOFT" 50;font-size:46px;line-height:1.24;color:#FFF8EC;text-wrap:pretty}}
"""

def shoot(body: str, out: Path, css: str = '') -> Image.Image:
    h = out.with_suffix('.html')
    h.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}{css}</style></head><body>{body}</body></html>", encoding='utf-8')
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                        f'--window-size={W},{H+200}', '--default-background-color=00000000', '--virtual-time-budget=4000',
                        f'--user-data-dir={prof}', '--allow-file-access-from-files', f'--screenshot={out}', h.as_uri()],
                       check=True, capture_output=True, timeout=120)
    return Image.open(out).convert('RGBA').crop((0, 0, W, H))

def ease(t): return t * t * (3 - 2 * t)

# ── 첫 장면 검사 (11/19) ─────────────────────────────────────────
# 올린 세 편의 평균 시청이 6.9~10.5초(42~60초 영상)였다. 첫 3~4초가 거의 멈춘 그림 + 작은 글씨였고, 3초 무렵
# 첫 문장이 사라진 뒤 다음 자막까지 빈 틈이 있었다. 릴스는 첫 몇 초에 넘기면 더 퍼지지 않으니 그 구간을 기계로 막는다.
OPEN_CHANGE_BY = 2.5   # 이 시각까지 컷이 있거나 카메라가 눈에 띄게(줌 1.2배·이동 폭의 20%) 움직여야 한다
OPEN_MIN_ZOOM, OPEN_MIN_PAN = 1.2, 0.2
OPEN_TEXT_UNTIL = 8.0  # 이 시각까지는 자막 사이 빈 틈을 OPEN_MAX_GAP 초 넘게 두지 않는다
OPEN_MAX_GAP = 0.2
HOOK_MAX_WORDS = 12

def opening_problems(spec) -> list[str]:
    """spec 의 첫 장면 규칙 위반(없으면 빈 목록). 표지 spec 은 검사하지 않는다."""
    import re
    problems = []
    texts = sorted(spec.get('texts', []), key=lambda t: t['t0'])
    hooks = [t for t in texts if t['t0'] <= 0.05 and re.search(r"class=['\"][^'\"]*\bhook\b", t['html'])]
    if not hooks:
        problems.append("0초에 hook 클래스 첫 문장이 없다(<div class='hook'>…, Mia 는 <p class='m hook'>…)")
    for h in hooks:
        if h.get('fi', 0.6) > 0:
            problems.append("첫 문장은 fi: 0 — 0초 첫 프레임부터 보여야 한다")
        words = len(re.sub(r'<[^>]+>', ' ', h['html']).split())
        if words > HOOK_MAX_WORDS:
            problems.append(f"첫 문장 {words}단어(최대 {HOOK_MAX_WORDS})")
        if h['t1'] < 2.0:
            problems.append(f"첫 문장이 {h['t1']}초에 사라진다(2초 이상 머물게)")
    shots = sorted(spec['shots'], key=lambda s: s['t0'])
    s0 = shots[0]
    if s0['t1'] > OPEN_CHANGE_BY and 'cam' in s0:
        cams = [cam_at(s0['cam'], OPEN_CHANGE_BY * i / 25) for i in range(26)]
        ws = [c[2] for c in cams]
        zoom = max(ws) / min(ws)
        pan = max(((c[0] - cams[0][0]) ** 2 + (c[1] - cams[0][1]) ** 2) ** .5 for c in cams) / min(ws)
        if zoom < OPEN_MIN_ZOOM and pan < OPEN_MIN_PAN:
            problems.append(f"첫 {OPEN_CHANGE_BY}초에 컷이 없고 카메라도 거의 안 움직인다(줌 {zoom:.2f}배·이동 {pan:.0%}) — "
                            f"{OPEN_CHANGE_BY}초 안에 컷하거나 {OPEN_MIN_ZOOM}배 이상 밀고 들어가기")
    end, until = 0.0, min(OPEN_TEXT_UNTIL, spec['dur'])
    for t in texts + [{'t0': until, 't1': until}]:  # 끝 표지 — 마지막 자막 뒤 빈 틈도 본다
        start = min(t['t0'], until)
        if start - end > OPEN_MAX_GAP + 1e-6:
            problems.append(f"{end:.1f}~{start:.1f}초 자막 빈 틈({start - end:.1f}초) — 첫 {until:.0f}초는 이어 붙인다")
        if t['t0'] >= until:
            break
        end = max(end, t['t1'])
    return problems

class Video:
    """영상 장면의 프레임을 앞에서부터 차례로 읽는다(통째로 올리면 휴대폰 녹화 1206×2622 는 30초에 수 GB).
    장면마다 따로 연다 — 앞 장면과 섞이는 동안 두 장면이 서로 다른 위치를 번갈아 달라고 하기 때문이다.
    고정 프레임레이트로 바꿔 둔 파일을 준다(시뮬레이터 녹화는 가변이라 ffmpeg -vf fps=30 으로)."""

    def __init__(self, path):
        info = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                          'stream=width,height', '-of', 'json', path],
                                         capture_output=True, text=True, check=True).stdout)
        self.size = (info['streams'][0]['width'], info['streams'][0]['height'])
        self.path, self.proc, self.i, self.cur = path, None, -1, None

    def frame(self, i):
        n = self.size[0] * self.size[1] * 3
        if self.proc is None or i < self.i:
            self.close()
            self.proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', self.path, '-f', 'rawvideo',
                                          '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
            self.i = -1
        raw = None
        while self.i < i:
            b = self.proc.stdout.read(n)
            if len(b) < n:  # 끝이면 마지막 프레임에 머문다
                break
            raw, self.i = b, self.i + 1
        if raw is not None:
            self.cur = Image.frombytes('RGB', self.size, raw)
        return self.cur

    def close(self):
        if self.proc:
            self.proc.kill(); self.proc.wait(); self.proc = None

def cam_at(keys, t):
    """[시각, 값…] 키프레임 사이를 smoothstep 으로 잇는다(카메라·카드 위치·스크롤 모두)."""
    if t <= keys[0][0]: return keys[0][1:]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            p = ease((t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 1)
            return [a[i] + (b[i] - a[i]) * p for i in range(1, len(a))]
    return keys[-1][1:]

def rounded(size, r):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], r, fill=255)
    return m

SHADOW = None
def shadow(size):
    """카드 그림자 — 한 번 흐리게 만든 것을 크기만 바꿔 쓴다(매 프레임 흐리기는 느리다)."""
    global SHADOW
    if SHADOW is None:
        pad, base = 120, Image.new('L', (820 + 240, 1292 + 240), 0)
        ImageDraw.Draw(base).rounded_rectangle([pad, pad + 24, pad + 820, pad + 24 + 1292], 60, fill=110)
        SHADOW = base.filter(ImageFilter.GaussianBlur(40))
    k = size[0] / 820
    return SHADOW.resize((int(SHADOW.width * k), int(size[1] / 1292 * SHADOW.height))), int(120 * k), int(120 * size[1] / 1292)

def put(fr, lay, x, y):
    """RGBA 층을 (x, y)에 얹는다 — 화면 밖으로 나간 부분은 잘라 낸다(alpha_composite 는 음수 위치를 못 받는다)."""
    x, y = int(round(x)), int(round(y))
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(lay.width, W - x), min(lay.height, H - y)
    if ex > sx and ey > sy:
        fr.alpha_composite(lay, dest=(x + sx, y + sy), source=(sx, sy, ex, ey))

RING = (244, 199, 106)
def ring(fr, cx, cy, rx, ry, p, al, sw=7):
    """금색 동그라미(타원) — 위(12시)에서 시계 방향으로 p(0~1)만큼 그린다. 2배로 그려 줄여서 매끈하게."""
    if p <= 0.003 or al <= 0: return
    pad, ss = sw + 10, 2
    bw, bh = int(2 * rx + 2 * pad), int(2 * ry + 2 * pad)
    if bw > 3 * W or bh > 3 * H: return
    lay = Image.new('RGBA', (bw * ss, bh * ss), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    box = [pad * ss, pad * ss, (bw - pad) * ss, (bh - pad) * ss]
    end = -90 + 360 * min(1.0, p)
    d.arc(box, -90, end, fill=(10, 8, 6, 120), width=(sw + 6) * ss)  # 밝은 옷 위에서도 보이게 어두운 테
    d.arc(box, -90, end, fill=RING + (255,), width=sw * ss)
    lay = lay.resize((bw, bh), Image.LANCZOS)
    if al < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * al)))
    put(fr, lay, cx - bw / 2, cy - bh / 2)

SPOT = None
def spot(fr, cx, cy, rx, ry, dim):
    """조명 — 타원 안은 그대로, 밖은 dim 만큼 어둡게(가장자리는 부드럽게 번진다)."""
    global SPOT
    if SPOT is None:
        n = 256; g = Image.new('L', (n, n))
        g.putdata([int(255 * ease(min(1.0, max(0.0, ((((x - n / 2 + .5) ** 2 + (y - n / 2 + .5) ** 2) ** .5) / (n / 2) - .6) / .4))))
                   for y in range(n) for x in range(n)])
        SPOT = g
    k = 1 / .6  # 그라데이션 0.6 지점이 타원 가장자리
    gw, gh = max(2, int(2 * rx * k)), max(2, int(2 * ry * k))
    m = Image.new('L', (W, H), 255)
    m.paste(SPOT.resize((gw, gh), Image.BILINEAR), (int(cx - gw / 2), int(cy - gh / 2)))
    dark = Image.new('RGBA', (W, H), (8, 6, 4, 0))
    dark.putalpha(m.point(lambda v: int(v * dim)))
    fr.alpha_composite(dark)

def back(t):  # 톡 튀어나오기(살짝 넘쳤다 돌아옴)
    c = 1.7; t -= 1
    return 1 + (c + 1) * t ** 3 + c * t ** 2

def shade(pos):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    mid = 560 if pos == 'top' else 1180
    for y in range(H):
        a = int(170 * max(0.0, 1 - abs(y - mid) / 560) ** 1.3)
        if a: d.line([(0, y), (W, y)], fill=(10, 8, 6, a))
    return im

def main():
    spec = json.loads(Path(sys.argv[1]).read_text()); out = Path(spec['out'])
    fps, dur = spec.get('fps', 30), spec['dur']
    bg = tuple(int(spec.get('bg', '#0e0b09')[i:i + 2], 16) for i in (1, 3, 5))
    paths = {s['img'] for s in spec['shots'] if 'img' in s}
    paths |= {p['img'] for s in spec['shots'] for p in s.get('panels', [])}
    paths |= {s['under_img'] for s in spec['shots'] if 'under_img' in s}
    imgs = {p: Image.open(p).convert('RGB') for p in paths}
    vids = {}
    for k, s in enumerate(spec['shots']):
        if 'video' in s:
            vids[k] = Video(s['video'])
            s['_k'] = k
        if 'video' in s and 'cam' not in s:
            vw, vh = vids[k].size
            s['cam'] = [[s['t0'], vw / 2, vh / 2, vw]]
    work = Path(tempfile.mkdtemp())
    texts = []
    bgs = {p: Image.open(p).convert('RGB').resize((W, H)) for p in {s['bgimg'] for s in spec['shots'] if 'bgimg' in s}}
    for k, s in enumerate(spec['shots']):
        if 'screen' in s:
            vids[k] = Video(s['screen'])
            s['_k'] = k
    for i, t in enumerate(spec['texts']):
        cls = t.get('pos', 'top')
        body = t['html'] if t.get('raw') else f'<div class="b {cls}">{t["html"]}</div>'
        texts.append((t['t0'], t['t1'], shoot(body, work / f't{i}.png', spec.get('css', '')), cls if not t.get('raw') else None, t.get('fi', 0.6), t.get('fo', 0.6)))  # fo: 사라지는 시간
    shades = {'top': shade('top'), 'low': shade('low')}
    for si, s in enumerate(spec['shots']):
        for mi, m in enumerate(s.get('marks', [])):
            if 'tag' in m:  # 번호·이름표는 한 번 찍어 둔다(테두리만 남기고 잘라서)
                im = shoot(f"<div style='position:absolute;left:40px;top:40px'>{m['tag']}</div>", work / f'm{si}_{mi}.png',
                           spec.get('css', ''))
                m['_lay'] = im.crop(im.getbbox())
        if 'panels' in s and 'under' in s:  # 나란히 보기 밑에 깔 그림 — 흐리고 어둡게, 한 번만
            cx, cy, w = s['under']; k = w / W; h = w * H / W
            u = imgs[s.get('under_img', s['panels'][0]['img'])].transform(
                (W, H), Image.AFFINE, (k, 0, cx - w / 2, 0, k, cy - h / 2), Image.BICUBIC, fillcolor=bg)
            s['_under'] = ImageEnhance.Brightness(u.filter(ImageFilter.GaussianBlur(26))).enhance(0.36)
    only = [float(x) for x in sys.argv[sys.argv.index('--only') + 1].split(',')] if '--only' in sys.argv else None
    ff = None if only else subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(fps), '-i', '-', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-shortest',
                           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', str(spec.get('crf', 18)), '-preset', 'medium',
                           '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart', str(out)], stdin=subprocess.PIPE)
    def source(s, t):
        if 'img' in s:
            return imgs[s['img']]
        i = int((t - s['t0']) * s.get('src_fps', 24) * s.get('speed', 1.0)) + s.get('start_frame', 0)
        return vids[s['_k']].frame(max(0, i))
    def render_screen(s, t):
        fr = source(s, t)
        cx, cy, w = cam_at(s['rect'], t)
        y0 = cam_at(s.get('scroll', [[0, 0]]), t)[0]
        sh = s.get('src_h', fr.height)
        y0 = max(0, min(fr.height - sh, y0))
        h = w * sh / fr.width
        size = (int(round(w)), int(round(h)))
        card = fr.crop((0, int(y0), fr.width, int(y0 + sh))).resize(size, Image.LANCZOS)
        out = bgs[s['bgimg']].copy()
        x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
        sd, px, py = shadow(size)
        out.paste((0, 0, 0), (x - px, y - py), sd)
        out.paste(card, (x, y), rounded(size, int(s.get('radius', 56) * w / 820)))
        return out
    def render_panels(s, t):
        out = s['_under'].copy() if '_under' in s else Image.new('RGB', (W, H), bg)
        d = ImageDraw.Draw(out)
        q = ease(min(1.0, max(0.0, (t - s['t0']) / 0.45)))
        for p in s['panels']:
            bx, by, bw, bh = p['box']
            dx, dy = p.get('from', [0, 0])
            bx, by = int(round(bx + dx * (1 - q))), int(round(by + dy * (1 - q)))
            cx, cy, w = cam_at(p['cam'], t); k = w / bw; h = bh * k
            crop = imgs[p['img']].transform((bw, bh), Image.AFFINE, (k, 0, cx - w / 2, 0, k, cy - h / 2), Image.BICUBIC,
                                            fillcolor=bg)
            r = p.get('radius', 26)
            out.paste(crop, (bx, by), rounded((bw, bh), r))
            d.rounded_rectangle([bx, by, bx + bw - 1, by + bh - 1], r, outline=RING, width=3)
        return out
    def draw_marks(fr, s, t):
        """img 장면의 표시를 RGBA 프레임에 그린다 — 자막 그림자 띠 위에 그려야 이름표가 흐려지지 않는다."""
        live = [m for m in s.get('marks', []) if m['t0'] <= t <= m['t1']]
        if not live or 'cam' not in s: return
        cx, cy, w = cam_at(s['cam'], t); k = w / W
        x0, y0 = cx - w / 2, cy - w * H / W / 2
        sx, sy = (lambda x: (x - x0) / k), (lambda y: (y - y0) / k)
        for m in sorted(live, key=lambda m: 0 if 'spot' in m else 1):  # 조명 먼저, 그 위에 동그라미·이름표
            if 'spot' in m:
                x, y, rx, ry = m['spot']
                spot(fr, sx(x), sy(y), rx / k, ry / k, m.get('dim', 0.62) * fade(t, m['t0'], m['t1'], m.get('fo', 0.4), m.get('fi', 0.4)))
            elif 'ring' in m:
                x, y, rx, ry = m['ring']
                ring(fr, sx(x), sy(y), rx / k, ry / k, ease(min(1.0, (t - m['t0']) / m.get('draw', 0.45))),
                     fade(t, m['t0'], m['t1'], m.get('fo', 0.3), 0))
            else:
                lay, q = m['_lay'], min(1.0, (t - m['t0']) / 0.3)
                if q < 1:
                    sc = 0.55 + 0.45 * back(q)
                    lay = lay.resize((max(1, int(lay.width * sc)), max(1, int(lay.height * sc))), Image.BICUBIC)
                al = fade(t, m['t0'], m['t1'], m.get('fo', 0.3), 0.15)
                if al < 1:
                    lay = lay.copy(); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * al)))
                dx, dy = m.get('off', [0, 0])
                put(fr, lay, sx(m['at'][0]) + dx - lay.width / 2, sy(m['at'][1]) + dy - lay.height / 2)
    def render_shot(s, t):
        if 'screen' in s:
            return render_screen(s, t)
        if 'panels' in s:
            return render_panels(s, t)
        cx, cy, w = cam_at(s['cam'], t); h = w * H / W
        x0, y0 = cx - w / 2, cy - h / 2; k = w / W
        return source(s, t).transform((W, H), Image.AFFINE, (k, 0, x0, 0, k, y0), Image.BICUBIC, fillcolor=bg)
    def fade(t, a, b, f=0.6, fi=0.6):
        if t < a or t > b: return 0.0
        return min(1.0, (t - a) / fi if fi > 0 else 1.0, (b - t) / f if f > 0 else 1.0)
    snaps = set(only or spec.get('snaps', []))
    for i in (sorted({round(x * fps) for x in only}) if only else range(int(dur * fps))):
        t = i / fps
        cur = [s for s in spec['shots'] if s['t0'] <= t < s['t1']] or [spec['shots'][-1]]
        s = cur[-1]
        fr = render_shot(s, t)
        prev = [p for p in spec['shots'] if p['t1'] == s['t0']]
        f = s.get('fade', 0.8)
        if prev and t < s['t0'] + f:
            fr = Image.blend(render_shot(prev[0], t), fr, ease((t - s['t0']) / f))
        fr = fr.convert('RGBA')
        for pos in ('top', 'low'):
            a = max([fade(t, a0, b0, fo, fi) for a0, b0, _, c, fi, fo in texts if c == pos] or [0])
            if a: fr.alpha_composite(Image.blend(Image.new('RGBA', (W, H), (0, 0, 0, 0)), shades[pos], a))
        draw_marks(fr, s, t)
        for a0, b0, lay, _, fi, fo in texts:
            al = fade(t, a0, b0, fo, fi)
            if al > 0:
                l = lay.copy(); l.putalpha(l.getchannel('A').point(lambda v: int(v * al)))
                rising = fi > 0 and t < a0 + fi  # 들어올 때만 아래에서 살짝 올라온다
                dy = int(round((1 - ease(min(1.0, (t - a0) / fi))) * 28)) if rising else 0
                fr.alpha_composite(l, dest=(0, dy), source=(0, 0, W, H - dy))
        rgb = fr.convert('RGB')
        if ff: ff.stdin.write(rgb.tobytes())
        if any(i == round(x * fps) for x in snaps):
            rgb.save(out.parent / f'{out.stem}-at{t:.1f}.jpg', quality=82)
    if ff: ff.stdin.close(); ff.wait()
    for v in vids.values():
        v.close()
    print('done', out)

if __name__ == '__main__':
    if sys.argv[1] == '--check':  # python3 render.py --check spec.json — 첫 장면 규칙만 본다
        found = opening_problems(json.loads(Path(sys.argv[2]).read_text()))
        print('\n'.join(f'⚠ 첫 장면: {p}' for p in found) or '첫 장면 OK')
        sys.exit(1 if found else 0)
    main()
