#!/usr/bin/env python3
"""릴스 한 편 마무리: 무음 영상 + 음악 → reel.mp4, 표지 spec → cover.jpg. 결과 폴더는 reel_queue.py add 로 넣는다.

    python3 finish.py <작업폴더>      # 폴더에 spec.json · cover-spec.json · events.json(compose.py 결과)이 있어야 한다

순서: render.py spec.json(무음 1080×1920) → music.swift events.json(오프라인 렌더, 원음이 작다) → 소리 크기 맞춤
(엘리야 편과 같은 크기: loudnorm I=-18, 최고 -1.5dB) + 끝 2.4초 페이드 → AAC 192k 로 합침. 표지는 cover-spec 의
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
    dur = float(spec['dur'])
    silent = Path(spec['out']) if Path(spec['out']).is_absolute() else w / spec['out']
    run(sys.executable, HERE / 'render.py', w / 'spec.json', cwd=w)
    run('swift', HERE / 'music.swift', w / 'events.json', w / 'music.wav', dur + 0.6, cwd=w)
    fade_at = max(0.0, dur - 2.4)
    run('ffmpeg', '-y', '-loglevel', 'error', '-i', silent, '-i', w / 'music.wav', '-map', '0:v', '-map', '1:a',
        '-c:v', 'copy', '-af', f'loudnorm=I=-18:TP=-1.5:LRA=11,afade=t=out:st={fade_at}:d=2.4', '-ar', '44100',
        '-c:a', 'aac', '-b:a', '192k', '-t', str(dur), '-movflags', '+faststart', w / 'reel.mp4')
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
