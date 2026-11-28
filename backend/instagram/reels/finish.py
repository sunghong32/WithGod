#!/usr/bin/env python3
"""릴스 한 편 마무리: 무음 영상 + 음악 → reel.mp4, 표지 spec → cover.jpg. 결과 폴더는 reel_queue.py add 로 넣는다.

    python3 finish.py <작업폴더>      # 폴더에 spec.json · cover-spec.json · events.json(compose.py 결과)이 있어야 한다
    python3 finish.py <작업폴더> --skip-open-check   # 첫 장면 검사(render.opening_problems)를 건너뛴다 — 이유가 있을 때만

순서: render.py spec.json(무음 1080×1920) → music.swift events.json(오프라인 렌더, 원음이 작다) → 소리 크기 맞춤
(엘리야 편과 같은 크기: loudnorm I=-18, 최고 -1.5dB) + 끝 2.4초 페이드 → AAC 192k 로 합침(spec 의 "lofi": true 면 로파이 거르기·잡음).
spec 에 "voice"(narrate.py 가 만든 voice.wav)가 있으면 내레이션을 앞에 세운다 — 목소리 -17 LUFS, 음악은 "music_lufs"(기본 -30)로 깔고
목소리가 나올 때 더 눌러(sidechain) 말 사이에만 살짝 올라오게. 표지는 cover-spec 의
0초 장면을 JPEG 로 저장한다(인스타 릴스 표지 1080×1920).
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(*cmd, cwd=None):
    subprocess.run([str(c) for c in cmd], check=True, cwd=cwd)


def main() -> int:
    w = Path(sys.argv[1]).resolve()
    spec = json.loads((w / 'spec.json').read_text())
    sys.path.insert(0, str(HERE))
    from render import opening_problems
    found = opening_problems(spec)
    if found and '--skip-open-check' not in sys.argv[2:]:
        print('\n'.join(f'⚠ 첫 장면: {p}' for p in found), file=sys.stderr)
        print('README 「첫 3초」 규칙대로 spec 을 고치거나, 이유가 있으면 --skip-open-check', file=sys.stderr)
        return 2
    dur = float(spec['dur'])
    silent = Path(spec['out']) if Path(spec['out']).is_absolute() else w / spec['out']
    run(sys.executable, HERE / 'render.py', w / 'spec.json', cwd=w)
    run('swift', HERE / 'music.swift', w / 'events.json', w / 'music.wav', dur + 0.6, cwd=w)
    fade_at = max(0.0, dur - 2.4)
    tail = f'loudnorm=I=-18:TP=-1.5:LRA=11,afade=t=out:st={fade_at}:d=2.4'
    if spec.get('voice'):  # 내레이션 편: 목소리 앞, 음악은 뒤에 깔고 말할 때 더 눌러 둔다
        voice = Path(spec['voice']) if Path(spec['voice']).is_absolute() else w / spec['voice']
        fmt = 'aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo'
        audio = ['-i', voice, '-filter_complex',
                 f"[1]{fmt},loudnorm=I={spec.get('music_lufs', -30)}:TP=-6[m0];"
                 f"[2]{fmt},loudnorm=I=-17:TP=-2:LRA=9,apad[v];[v]asplit[v1][v2];"
                 "[m0][v1]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=600[m];"
                 f"[m][v2]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.75:level=false,afade=t=out:st={fade_at}:d=2.4[a]",
                 '-map', '0:v', '-map', '[a]']
    elif spec.get('lofi'):  # 수요일 Mia: 고음을 깎고 살짝 눌러 + 아주 작은 테이프 잡음(분홍 잡음)
        audio = ['-f', 'lavfi', '-i', f'anoisesrc=color=pink:amplitude=0.02:seed=7:duration={dur + 1}',
                 '-filter_complex', '[1]lowpass=f=4200,acompressor=threshold=-20dB:ratio=3[m];'
                 f'[2]highpass=f=900,lowpass=f=7000,volume=0.35[h];[m][h]amix=inputs=2:normalize=0,{tail}[a]',
                 '-map', '0:v', '-map', '[a]']
    else:
        audio = ['-map', '0:v', '-map', '1:a', '-af', tail]
    run('ffmpeg', '-y', '-loglevel', 'error', '-i', silent, '-i', w / 'music.wav', *audio,
        '-c:v', 'copy', '-ar', '44100', '-c:a', 'aac', '-b:a', '192k', '-t', str(dur), '-movflags', '+faststart',
        w / 'reel.mp4')
    if (w / 'cover-spec.json').exists():
        cover = json.loads((w / 'cover-spec.json').read_text())
        run(sys.executable, HERE / 'render.py', w / 'cover-spec.json', cwd=w)
        out = Path(cover['out']) if Path(cover['out']).is_absolute() else w / cover['out']
        snap = out.parent / f'{out.stem}-at0.0.jpg'
        snap.replace(w / 'cover.jpg')
    print('done', w / 'reel.mp4', w / 'cover.jpg')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
