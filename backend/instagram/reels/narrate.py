"""릴스 내레이션 녹음(로컬 Kokoro-82M, Apache-2.0). TTS 전용 venv 로 돌린다(torch·kokoro 가 그 안에만 있다):

    ~/.local/share/withgod-tts/venv/bin/python narrate.py <작업폴더>

<작업폴더>/narration.json:
  {"voice": "af_heart", "speed": 0.95, "lead": 0.35,
   "segments": [{"id": "title", "say": "읽을 문장", "pause": 0.4}, …]}
→ voice.wav(24kHz 모노) + timeline.json {"segments": [{"id", "t0", "t1"}…], "end": 마지막 쉼까지}.
문장마다 따로 읽혀 앞뒤 무음을 잘라 이어 붙이므로 자막·카메라를 문장 시작 시각에 정확히 맞출 수 있다.
발음이 이상한 이름은 say 에 [Nouwen](/nˈWən/) 처럼 misaki 음소를 적는다(W = aʊ, A = eɪ, I = aɪ, O = oʊ).

목소리: 계정의 화자 = Mia(20대 후반 여성, 수요일 시리즈) — af_heart(사용자 11/19 "미아의 목소리라고 생각하고").
설치(11/19): python3.12 -m venv ~/.local/share/withgod-tts/venv && pip install "kokoro>=0.9.4" soundfile
(모델은 처음 돌릴 때 허깅페이스 hexgrad/Kokoro-82M 에서 받는다, 약 330MB).
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf

warnings.filterwarnings('ignore')
from kokoro import KPipeline  # noqa: E402

SR = 24000


def trim(a, thr=0.008):
    idx = np.where(np.abs(a) > thr)[0]
    if not len(idx):
        return a
    return a[max(0, idx[0] - int(0.03 * SR)): idx[-1] + int(0.09 * SR)]


def main():
    w = Path(sys.argv[1])
    cfg = json.loads((w / 'narration.json').read_text())
    pipe = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
    lead = cfg.get('lead', 0.35)
    out, t, tl = [np.zeros(int(lead * SR), dtype=np.float32)], lead, []
    for s in cfg['segments']:
        parts = [np.asarray(a, dtype=np.float32) for _, _, a in pipe(s['say'], voice=cfg['voice'], speed=cfg.get('speed', 1.0))]
        a = trim(np.concatenate(parts))
        tl.append({'id': s['id'], 't0': round(t, 3), 't1': round(t + len(a) / SR, 3)})
        out.append(a)
        t += len(a) / SR
        p = s.get('pause', 0.3)
        out.append(np.zeros(int(p * SR), dtype=np.float32))
        t += p
        print(f"{s['id']:>10} {tl[-1]['t0']:6.2f}–{tl[-1]['t1']:6.2f}  {s['say'][:60]}")
    sf.write(w / 'voice.wav', np.concatenate(out), SR)
    (w / 'timeline.json').write_text(json.dumps({'segments': tl, 'end': round(t, 3)}, indent=1))
    print('end', round(t, 2))


if __name__ == '__main__':
    main()
