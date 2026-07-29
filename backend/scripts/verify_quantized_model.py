"""양자화(int8 ONNX) 모델이 원본과 같은 검색 결과를 내는지 검증한다.

기준: 실제 verses.faiss 에 대해 한국어 감정 질의로
- 쿼리 임베딩 코사인 유사도 (원본 vs int8)
- Top-1 일치율 / Top-5 겹침율
품질 저하가 있으면 배포하면 안 된다.

    python scripts/verify_quantized_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "data" / "verses.faiss"
MODEL_DIR = ROOT / "models" / "e5-small-int8"
MODEL_ID = "intfloat/multilingual-e5-small"

QUERIES = [
    "요즘 너무 지치고 힘들어요", "불안해서 잠이 안 와요", "감사한 마음이 가득해요",
    "외로움을 느껴요", "미래가 두려워요", "가족 때문에 속상해요",
    "시험을 앞두고 긴장돼요", "위로가 필요해요", "화가 나서 참기 힘들어요",
    "슬픔에서 벗어나고 싶어요", "새로운 시작이 설레요", "죄책감이 들어요",
    "용서하고 싶은데 잘 안 돼요", "직장에서 스트레스를 받아요", "건강이 걱정돼요",
    "혼자라는 생각이 들어요", "기도해도 응답이 없는 것 같아요", "마음의 평안을 찾고 싶어요",
    "이별의 아픔이 커요", "인생의 방향을 모르겠어요", "돈 걱정이 많아요",
    "아이 걱정에 잠 못 들어요", "친구와 다퉈서 마음이 무거워요", "희망을 붙잡고 싶어요",
    "매일이 무기력해요", "하나님이 멀게 느껴져요", "감기몸살로 힘든 하루였어요",
    "결정을 앞두고 망설여져요", "부모님이 그리워요", "작은 일에도 짜증이 나요",
]


def onnx_encode(texts: list[str]) -> np.ndarray:
    import onnxruntime as ort
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    session = ort.InferenceSession(
        str(MODEL_DIR / "model_int8.onnx"), providers=["CPUExecutionProvider"]
    )
    enc = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="np")
    needed = {i.name for i in session.get_inputs()}
    inputs = {k: v for k, v in enc.items() if k in needed}
    # XLM-R 계열 토크나이저는 token_type_ids 를 안 내지만 export 그래프는 요구할
    # 수 있다 — 전부 0(단일 세그먼트)으로 채운다.
    if "token_type_ids" in needed and "token_type_ids" not in inputs:
        inputs["token_type_ids"] = np.zeros_like(enc["input_ids"])
    hidden = session.run(None, inputs)[0]  # (B, T, H)
    mask = enc["attention_mask"][..., None].astype(np.float32)
    pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    return pooled / np.linalg.norm(pooled, axis=1, keepdims=True)


def main() -> None:
    import faiss
    from sentence_transformers import SentenceTransformer

    index = faiss.read_index(str(INDEX_PATH))
    prefixed = [f"query: {q}" for q in QUERIES]

    print("[1/3] 원본(sentence-transformers) 임베딩...")
    baseline = SentenceTransformer(MODEL_ID).encode(
        prefixed, normalize_embeddings=True
    ).astype("float32")

    print("[2/3] int8 ONNX 임베딩...")
    quantized = onnx_encode(prefixed).astype("float32")

    print("[3/3] 비교")
    cosines = (baseline * quantized).sum(axis=1)
    _, base_ids = index.search(baseline, 5)
    _, quant_ids = index.search(quantized, 5)

    top1 = float(np.mean(base_ids[:, 0] == quant_ids[:, 0]))
    overlap5 = float(np.mean([
        len(set(b) & set(q)) / 5 for b, q in zip(base_ids, quant_ids)
    ]))

    print(f"  쿼리 임베딩 코사인: 평균 {cosines.mean():.4f} / 최소 {cosines.min():.4f}")
    print(f"  Top-1 일치율: {top1:.1%}")
    print(f"  Top-5 겹침율: {overlap5:.1%}")

    ok = cosines.min() >= 0.99 and top1 >= 0.90 and overlap5 >= 0.90
    print("✅ 통과 — 배포 가능" if ok else "❌ 실패 — 배포 금지, 원인 분석 필요")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
