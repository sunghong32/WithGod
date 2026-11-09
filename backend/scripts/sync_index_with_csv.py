# -*- coding: utf-8 -*-
"""verses.csv 에서 바뀐 행만 다시 임베딩해 검색 인덱스에 반영한다.

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

CSV 와 인덱스의 행은 절 키(책·장·절)로 맞춘다. 본문이 바뀐 절, CSV 에 새로 넣은 절
(아가 6:14 처럼 원본에서 통째로 빠졌던 절)은 다시 임베딩하고, CSV 에서 뺀 절은
인덱스에서도 뺀다. 그대로인 절은 저장된 벡터를 그대로 옮긴다. 산출물의 행 순서는
CSV 를 따른다 — 행이 하나 들어가면 그 뒤 행 번호가 모두 밀리므로 parquet·npy·faiss
셋을 함께 다시 쓴다.

**안전장치**: 쓰기 전에, 본문이 그대로인 행을 표본으로 다시 임베딩해 저장된 벡터와
코사인 유사도를 잰다. 원래 인덱스를 만든 방식(index.py)을 정확히 재현하지 못하면
(모델 판이 다르거나 전처리가 다르면) 아무것도 쓰지 않고 멈춘다.

    pip install sentence-transformers faiss-cpu pandas pyarrow
    python scripts/sync_index_with_csv.py            # 검사만
    python scripts/sync_index_with_csv.py --apply
    python scripts/sync_index_with_csv.py --lang es --index-dir /tmp/es --apply  # 외국어, 사본에 반영

외국어(`data/langs/<lang>/`)는 `build_language_index.py` 로 만든 같은 모델·같은 전처리다.
`--index-dir` 를 주면 그 폴더의 parquet·npy·faiss 를 읽고 고쳐 쓴다 — 서버에 올릴 사본을
만들 때 쓴다(이슈 #35, es 1,211행).

macOS 에서는 torch(sentence-transformers)와 faiss 를 한 프로세스에서 함께 쓰면 조용히
죽는다. 그래서 faiss 는 임베딩을 다 만든 뒤에야 import 한다.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

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


def verse_keys(df: pd.DataFrame, name: str) -> list[tuple[str, int, int]]:
    keys = list(zip(df["book"].astype(str), df["chapter"].astype(int), df["verse"].astype(int)))
    if len(set(keys)) != len(keys):
        raise SystemExit(f"{name} 에 같은 절이 두 번 있다 — 행을 절 키로 맞출 수 없다")
    return keys


def ref(k: tuple[str, int, int]) -> str:
    return f"{k[0]} {k[1]}:{k[2]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--lang", help="외국어 코드(es 등). 비우면 한국어 data/")
    ap.add_argument("--index-dir", type=Path, help="parquet·npy·faiss 폴더(기본: CSV 와 같은 폴더)")
    args = ap.parse_args()

    csv_dir = DATA / "langs" / args.lang if args.lang else DATA
    index_dir = args.index_dir or csv_dir
    CSV = csv_dir / "verses.csv"
    META, NPY, IDX = (index_dir / n for n in ("verses_meta.parquet", "verses.npy", "verses.faiss"))
    print(f"CSV {CSV}\n인덱스 {index_dir}")

    csv = pd.read_csv(CSV)
    meta = pd.read_parquet(META)
    csv_keys = verse_keys(csv, "verses.csv")
    meta_keys = verse_keys(meta, "verses_meta.parquet")

    # csv 행마다 인덱스의 같은 절 행 번호(-1 = 새로 넣은 절)
    old_row = {k: i for i, k in enumerate(meta_keys)}
    src = np.array([old_row.get(k, -1) for k in csv_keys])
    kept = np.flatnonzero(src >= 0)
    added = np.flatnonzero(src < 0)
    removed = sorted(set(meta_keys) - set(csv_keys), key=old_row.__getitem__)
    changed = kept[csv["text"].values[kept] != meta["text"].values[src[kept]]]
    redo = np.sort(np.concatenate([changed, added]))

    print(f"본문이 바뀐 행: {len(changed)}개 · 새로 넣은 행: {len(added)}개 · 뺀 행: {len(removed)}개")
    for i in added:
        print(f"  + {ref(csv_keys[i])}")
    for k in removed:
        print(f"  - {ref(k)}")
    if len(redo) == 0 and not removed:
        return 0

    from sentence_transformers import SentenceTransformer

    stored = np.load(NPY)
    if len(stored) != len(meta):
        raise SystemExit(f"npy {len(stored)}행 / parquet {len(meta)}행 — 인덱스가 이미 어긋나 있다. 전체 재구축(index.py) 필요")
    model = SentenceTransformer(MODEL, device="cpu")

    # ── 안전장치: 바뀌지 않은 행을 재현할 수 있어야 한다 ──
    rng = np.random.default_rng(31)
    untouched = np.setdiff1d(kept, changed)
    sample = rng.choice(untouched, size=min(GATE_SAMPLES, len(untouched)), replace=False)
    again = embed(model, [normalize(t) for t in csv.loc[sample, "text"]])
    cos = (again * stored[src[sample]]).sum(axis=1)
    print(f"재현 검사 {len(sample)}행 — 코사인 최소 {cos.min():.6f} · 평균 {cos.mean():.6f}")
    if cos.min() < GATE_MIN_COSINE:
        raise SystemExit(f"저장된 벡터를 재현하지 못한다(최소 {cos.min():.4f} < {GATE_MIN_COSINE}). 쓰지 않는다.")

    new_vecs = embed(model, [normalize(t) for t in csv.loc[redo, "text"]])
    if len(changed):
        drift = (new_vecs[np.searchsorted(redo, changed)] * stored[src[changed]]).sum(axis=1)
        print(f"바뀐 행의 옛 벡터와 새 벡터 코사인 — 평균 {drift.mean():.4f} (낮을수록 많이 달라진 것)")

    if not args.apply:
        print("\n(검사만 했다. 반영하려면 --apply)")
        return 0

    vecs = np.empty((len(csv), stored.shape[1]), dtype="float32")
    vecs[kept] = stored[src[kept]]
    vecs[redo] = new_vecs

    out = csv[["book", "chapter", "verse", "text"]].copy()
    out["clean"] = ""
    out.loc[kept, "clean"] = meta["clean"].values[src[kept]]
    out.loc[redo, "clean"] = [normalize(t) for t in csv.loc[redo, "text"]]
    out = out[list(meta.columns)].astype(meta.dtypes.to_dict())

    import faiss

    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)

    out.to_parquet(META, index=False)
    np.save(NPY, vecs)
    faiss.write_index(index, str(IDX))
    print(f"\n반영 완료 — parquet·npy·faiss ({index.ntotal}행, {vecs.shape[1]}차원)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
