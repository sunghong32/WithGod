r"""언어별 FAISS 인덱스 구축 (다국어 파이프라인 2단계, 이슈 #10).

data/langs/{lang}/verses.csv 를 multilingual-e5-small(fp32)로 임베딩해
언어별 검색 인덱스를 만든다. 한국어 index.py 와 같은 방식(passage: 프리픽스,
정규화, IndexFlatIP)이라 서버의 int8 쿼리 임베더와 그대로 호환된다.

무거운 산출물(faiss/npy/parquet)은 git 에 넣지 않는다 — 서버에는 scp 로
올리고, 재현은 이 스크립트로 한다. (ML 의존성이 있어 별도 venv 필요:
torch, sentence-transformers, faiss-cpu, pandas, pyarrow)

    python scripts/build_language_index.py --all
    python scripts/build_language_index.py --lang en
"""

from __future__ import annotations

import argparse
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
LANG_DIR = ROOT / "data" / "langs"
MODEL_ID = "intfloat/multilingual-e5-small"


def build(model: SentenceTransformer, lang_dir: Path) -> None:
    df = pd.read_csv(lang_dir / "verses.csv")
    df["clean"] = df["text"].astype(str).str.split().str.join(" ")

    passages = [f"passage: {t}" for t in df["clean"].tolist()]
    emb = model.encode(
        passages, batch_size=128, show_progress_bar=True, normalize_embeddings=True
    ).astype("float32")

    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)

    faiss.write_index(index, str(lang_dir / "verses.faiss"))
    np.save(lang_dir / "verses.npy", emb)  # 재인덱싱용 로컬 캐시(업로드 불필요)
    df[["book_code", "book", "chapter", "verse", "clean", "text"]].to_parquet(
        lang_dir / "verses_meta.parquet", index=False
    )
    print(f"[{lang_dir.name}] {emb.shape[0]}절 인덱싱 완료")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    langs = (
        sorted(d.name for d in LANG_DIR.iterdir() if (d / "verses.csv").exists())
        if args.all
        else [args.lang]
        if args.lang
        else []
    )
    if not langs:
        ap.error("--lang 또는 --all 이 필요합니다")

    try:
        model = SentenceTransformer(MODEL_ID, device="mps")
        model.encode(["passage: warmup"])
    except Exception:
        model = SentenceTransformer(MODEL_ID)

    for lang in langs:
        build(model, LANG_DIR / lang)


if __name__ == "__main__":
    main()
