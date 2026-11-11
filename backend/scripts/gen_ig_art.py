#!/usr/bin/env python3
"""캐러셀 장면 그림을 이 맥에서 로컬 오픈소스 모델로 만든다 (이슈 #62).

모델: Z-Image-Turbo(Tongyi-MAI, Apache-2.0 — 상업 이용 가능), 실행기: mflux(MIT, Apple Silicon MLX).
API·외부 서비스를 쓰지 않는다. 모델 가중치(약 33GB)는 처음 한 번 Hugging Face 캐시(~/.cache/huggingface)로 받는다.

    # mflux 는 따로 만든 venv 에 둔다(백엔드 venv 와 섞지 않는다)
    python3.12 -m venv ~/.local/share/withgod-imagegen/venv
    ~/.local/share/withgod-imagegen/venv/bin/pip install mflux==0.24.0

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
WIDTH, HEIGHT = 1344, 992  # 16의 배수, 슬라이드 그림 칸(1080×800)과 거의 같은 비율
# 모든 그림에 붙이는 화풍 — 그리드에서 한 계정처럼 보이게 고정한다. 특정 작가·스튜디오 이름은 쓰지 않는다.
STYLE = ("Hand-painted animated film background art, soft painterly brushwork, rich atmospheric light, "
         "cinematic wide shot.")
NEGATIVE = "text, letters, watermark, signature, logo, frame, border, modern buildings, cars"


def generate(prompt: str, seeds: list[int], steps: int, out_dir: Path, name: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(f"{STYLE}\n{prompt}")
        prompt_file = f.name
    subprocess.run(
        [str(MFLUX), "--model", "z-image-turbo", "-q", "8", "--prompt-file", prompt_file,
         "--negative-prompt", NEGATIVE, "--width", str(WIDTH), "--height", str(HEIGHT),
         "--steps", str(steps), "--seed", *map(str, seeds), "--output", str(out_dir / f"{name}_{{seed}}.png")],
        check=True,
    )
    Path(prompt_file).unlink()
    return [out_dir / f"{name}_{s}.png" for s in seeds]


def to_jpeg(png: Path, dst: Path) -> None:
    from PIL import Image

    Image.open(png).convert("RGB").save(dst, "JPEG", quality=93, subsampling=0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("verse_id")
    ap.add_argument("--seeds", type=int, nargs="+", help="후보 시드(주면 candidates/ 에만 만든다)")
    args = ap.parse_args()

    src = json.loads(SOURCES.read_text(encoding="utf-8")).get(args.verse_id)
    if not src or src.get("kind") != "generated":
        raise SystemExit(f"{args.verse_id}: art_sources.json 에 generated 항목이 없다")
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
