"""언어별 인덱스 검색 스모크용 개발 도구 (이슈 #10).

서버 배포 전에 언어별 FAISS 인덱스의 검색 품질을 로컬에서 확인한다.
ML venv 필요 (sentence-transformers, faiss-cpu, pandas).

    python scripts/search_language_index.py --lang en \
        --query "I feel so tired and need comfort" \
        --query "I'm anxious about my future"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import faiss
import pandas as pd
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
MODEL_ID = "intfloat/multilingual-e5-small"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True)
    ap.add_argument("--query", action="append", required=True)
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    lang_dir = ROOT / "data" / "langs" / args.lang
    df = pd.read_parquet(lang_dir / "verses_meta.parquet")
    index = faiss.read_index(str(lang_dir / "verses.faiss"))
    model = SentenceTransformer(MODEL_ID)

    q = model.encode(
        [f"query: {t}" for t in args.query], normalize_embeddings=True
    ).astype("float32")
    scores, ids = index.search(q, args.top)

    for qi, query in enumerate(args.query):
        print(f"\n### {query}")
        for rank, (i, s) in enumerate(zip(ids[qi], scores[qi]), 1):
            row = df.iloc[int(i)]
            print(f"{rank}. [{s:.4f}] {row['book']} {row['chapter']}:{row['verse']} — {row['text']}")


if __name__ == "__main__":
    main()
