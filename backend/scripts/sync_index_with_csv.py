# -*- coding: utf-8 -*-
"""verses.csv 에서 본문이 바뀐 행만 다시 임베딩해 검색 인덱스에 반영한다.

앱은 검색·추천·랜덤 말씀을 `verses.csv` 가 아니라 거기서 만든 산출물로 낸다
(`app.py`: `verses_meta.parquet` 가 있으면 그것을 먼저 읽는다). 그래서 CSV 본문만
고치면 **사용자에게는 반영되지 않는다.** 이슈 #31 에서 절 번호 밀림 161절을 CSV 에서
복구했을 때 실제로 그랬다.

본문은 두 곳에 들어 있다.
- `verses_meta.parquet` 의 text·clean — 사용자에게 보이는 글
- `verses.npy` / `verses.faiss` 의 벡터 — 검색이 **어느 행을 돌려줄지** 정하는 것
글만 바꾸고 벡터를 두면 161행의 벡터가 예전 본문을 가리킨다(시편 3:8 을 찾는
질문에 3:8 이 안 걸린다). 그래서 바뀐 행만 같은 모델로 다시 임베딩한다.
31,084절 전체를 다시 만들 필요는 없다.

**안전장치**: 쓰기 전에, 본문이 그대로인 행을 표본으로 다시 임베딩해 저장된 벡터와
코사인 유사도를 잰다. 원래 인덱스를 만든 방식(index.py)을 정확히 재현하지 못하면
(모델 판이 다르거나 전처리가 다르면) 아무것도 쓰지 않고 멈춘다.

    pip install sentence-transformers faiss-cpu pandas pyarrow
    python scripts/sync_index_with_csv.py            # 검사만
    python scripts/sync_index_with_csv.py --apply
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CSV = DATA / "verses.csv"
META = DATA / "verses_meta.parquet"
NPY = DATA / "verses.npy"
IDX = DATA / "verses.faiss"

MODEL = "intfloat/multilingual-e5-small"  # index.py 와 같아야 한다
GATE_SAMPLES = 200
GATE_MIN_COSINE = 0.999


def normalize(s: str) -> str:
    """index.py 의 전처리와 같다."""
    return " ".join(str(s).split())


def embed(model, texts: list[str]) -> np.ndarray:
    passages = [f"passage: {t}" for t in texts]  # E5 프리픽스 — index.py 와 같다
    out = model.encode(passages, batch_size=64, show_progress_bar=False,
                       normalize_embeddings=True)
    return np.asarray(out, dtype="float32")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    csv = pd.read_csv(CSV)
    meta = pd.read_parquet(META)
    if len(csv) != len(meta):
        raise SystemExit(f"행 수가 다르다: csv {len(csv)} / parquet {len(meta)} — 전체 재구축(index.py) 필요")
    keys = ["book", "chapter", "verse"]
    if not (csv[keys].astype(str).values == meta[keys].astype(str).values).all():
        raise SystemExit("행 순서나 절 키가 다르다 — 전체 재구축(index.py) 필요")

    changed = np.flatnonzero(csv["text"].values != meta["text"].values)
    print(f"본문이 바뀐 행: {len(changed)}개")
    if len(changed) == 0:
        return 0

    from sentence_transformers import SentenceTransformer

    stored = np.load(NPY)
    model = SentenceTransformer(MODEL, device="cpu")

    # ── 안전장치: 바뀌지 않은 행을 재현할 수 있어야 한다 ──
    rng = np.random.default_rng(31)
    untouched = np.setdiff1d(np.arange(len(csv)), changed)
    sample = rng.choice(untouched, size=min(GATE_SAMPLES, len(untouched)), replace=False)
    redo = embed(model, [normalize(t) for t in csv.loc[sample, "text"]])
    cos = (redo * stored[sample]).sum(axis=1)
    print(f"재현 검사 {len(sample)}행 — 코사인 최소 {cos.min():.6f} · 평균 {cos.mean():.6f}")
    if cos.min() < GATE_MIN_COSINE:
        raise SystemExit(f"저장된 벡터를 재현하지 못한다(최소 {cos.min():.4f} < {GATE_MIN_COSINE}). 쓰지 않는다.")

    new_vecs = embed(model, [normalize(t) for t in csv.loc[changed, "text"]])
    drift = (new_vecs * stored[changed]).sum(axis=1)
    print(f"바뀐 행의 옛 벡터와 새 벡터 코사인 — 평균 {drift.mean():.4f} (낮을수록 많이 달라진 것)")

    if not args.apply:
        print("\n(검사만 했다. 반영하려면 --apply)")
        return 0

    import faiss

    meta.loc[changed, "text"] = csv.loc[changed, "text"].values
    meta.loc[changed, "clean"] = [normalize(t) for t in csv.loc[changed, "text"]]
    stored[changed] = new_vecs

    index = faiss.IndexFlatIP(stored.shape[1])
    index.add(stored)

    meta.to_parquet(META, index=False)
    np.save(NPY, stored)
    faiss.write_index(index, str(IDX))
    print(f"\n반영 완료 — parquet·npy·faiss ({index.ntotal}행, {stored.shape[1]}차원)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
