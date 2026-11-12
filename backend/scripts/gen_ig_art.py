#!/usr/bin/env python3
"""캐러셀 장면 그림을 이 맥에서 로컬 오픈소스 모델로 만든다 (이슈 #62).

모델: Z-Image-Turbo(Tongyi-MAI, Apache-2.0 — 상업 이용 가능), 실행기: mflux(MIT, Apple Silicon MLX).
API·외부 서비스를 쓰지 않는다. 모델 가중치(약 33GB)는 처음 한 번 Hugging Face 캐시(~/.cache/huggingface)로 받는다.

    # mflux 는 따로 만든 venv 에 둔다(백엔드 venv 와 섞지 않는다)
    python3.12 -m venv ~/.local/share/withgod-imagegen/venv
    ~/.local/share/withgod-imagegen/venv/bin/pip install mflux==0.24.0
    # 8비트로 미리 줄여 저장해 둔다(한 번). 원본을 매번 올렸다 줄이면 메모리 32GB 맥에서 스왑이 차서
    # 장당 13분이 걸린다.
    ~/.local/share/withgod-imagegen/venv/bin/mflux-save --model z-image-turbo --quantize 8 \
        --path ~/.local/share/withgod-imagegen/z-image-turbo-q8

    python scripts/gen_ig_art.py pro-10-25              # art_sources.json 의 프롬프트·시드로 다시 만들기
    python scripts/gen_ig_art.py pro-10-25 --seeds 1 2 3  # 후보 여러 장(build/art/candidates/)

art_sources.json 의 generated 항목: {"kind": "generated", "model", "prompt", "seed", "steps"}.
결과는 build/art/<verse_id>.jpg(1344×992 → 슬라이드 그림 칸 비율에 맞춰 둔다).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

INSTAGRAM = Path(__file__).resolve().parent.parent / "instagram"
SOURCES = INSTAGRAM / "art_sources.json"
ART_DIR = INSTAGRAM / "build" / "art"
MFLUX = Path.home() / ".local/share/withgod-imagegen/venv/bin/mflux-generate-z-image"
MODEL_Q8 = Path.home() / ".local/share/withgod-imagegen/z-image-turbo-q8"
WIDTH, HEIGHT = 1344, 992  # 16의 배수, 슬라이드 그림 칸(1080×800)과 거의 같은 비율
# 모든 그림에 붙이는 화풍 — 그리드에서 한 계정처럼 보이게 고정한다. 특정 작가·스튜디오 이름은 쓰지 않는다.
# 미국 계정이라 서양 2D 손그림 장편 애니메이션 느낌(사용자 선택, 11/12). 일본 애니메이션풍은 인물이 동양적으로
# 나와서 negative 로 막는다.
STYLE = ("Still from a Western hand-drawn 2D animated feature film, classic American animation style, "
         "expressive characters with natural proportions, lush painted backgrounds, warm cinematic lighting.")
NEGATIVE = ("anime, manga, Japanese animation, East Asian features, text, letters, watermark, signature, logo, "
            "frame, border, modern buildings, cars")


def generate(prompt: str, seeds: list[int], steps: int, out_dir: Path, name: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(f"{STYLE}\n{prompt}")
        prompt_file = f.name
    model = (["--model", str(MODEL_Q8), "--base-model", "z-image-turbo"] if MODEL_Q8.exists()
             else ["--model", "z-image-turbo", "-q", "8"])
    paths = []
    for seed in seeds:  # 시드마다 따로 — 여러 시드를 한 번에 주면 mflux 가 파일 이름에 시드를 덧붙인다
        out = out_dir / f"{name}_{seed}.png"
        subprocess.run(
            [str(MFLUX), *model, "--prompt-file", prompt_file, "--negative-prompt", NEGATIVE,
             "--width", str(WIDTH), "--height", str(HEIGHT), "--steps", str(steps), "--seed", str(seed),
             "--output", str(out)],
            check=True,
        )
        paths.append(out)
    Path(prompt_file).unlink()
    return paths


def to_jpeg(png: Path, dst: Path) -> None:
    from PIL import Image

    Image.open(png).convert("RGB").save(dst, "JPEG", quality=93, subsampling=0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("verse_id")
    ap.add_argument("--pick", type=int, help="candidates/<verse_id>_<시드>.png 를 골라 build/art/ 에 두고 시드를 기록")
    ap.add_argument("--seeds", type=int, nargs="+", help="후보 시드(주면 candidates/ 에만 만든다)")
    args = ap.parse_args()

    src = json.loads(SOURCES.read_text(encoding="utf-8")).get(args.verse_id)
    if not src or src.get("kind") != "generated":
        raise SystemExit(f"{args.verse_id}: art_sources.json 에 generated 항목이 없다")
    if args.pick is not None:
        to_jpeg(ART_DIR / "candidates" / f"{args.verse_id}_{args.pick}.png", ART_DIR / f"{args.verse_id}.jpg")
        data = json.loads(SOURCES.read_text(encoding="utf-8"))
        data[args.verse_id].update(seed=args.pick, size=f"{WIDTH}x{HEIGHT}")
        SOURCES.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(ART_DIR / f"{args.verse_id}.jpg")
        return 0
    if args.seeds:
        paths = generate(src["prompt"], args.seeds, src.get("steps", 9), ART_DIR / "candidates", args.verse_id)
        print("\n".join(map(str, paths)))
        return 0
    png = generate(src["prompt"], [src["seed"]], src.get("steps", 9), ART_DIR / "candidates", args.verse_id)[0]
    to_jpeg(png, ART_DIR / f"{args.verse_id}.jpg")
    print(ART_DIR / f"{args.verse_id}.jpg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
