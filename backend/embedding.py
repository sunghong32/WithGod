"""쿼리 임베딩 — int8 ONNX 우선, sentence-transformers 폴백.

sentence-transformers 로 multilingual-e5-small 을 올리면 RSS ~560MB(25만 vocab
fp32 임베딩 테이블)를 차지해 1GB 서버에서 다국어 인덱스를 얹을 수 없다.
scripts/build_quantized_model.py 로 만든 int8 ONNX(~118MB)를 우선 사용한다.

품질은 scripts/verify_quantized_model.py 로 검증됨(2026-07-29: per-channel
int8, 코사인 ≥0.9992 / Top-1 100% / Top-5 92%). 모델 산출물이 없거나
onnxruntime 미설치면 기존 sentence-transformers 로 폴백한다(동작 동일, 메모리만
큼).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger("with-god.embedding")

ROOT = Path(__file__).resolve().parent
ONNX_DIR = ROOT / "models" / "e5-small-int8"
MODEL_ID = "intfloat/multilingual-e5-small"


class _OnnxEmbedder:
    def __init__(self, model_dir: Path) -> None:
        import onnxruntime as ort
        # transformers.AutoTokenizer 는 torch 를 끌고 들어와 RSS 를 ~300MB 이상
        # 잡아먹는다(실측). 경량 Rust 구현인 tokenizers 를 직접 쓴다.
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=512)
        pad_id = self.tokenizer.token_to_id("<pad>") or 0
        self.tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")
        self.session = ort.InferenceSession(
            str(model_dir / "model_int8.onnx"), providers=["CPUExecutionProvider"]
        )
        self._input_names = {i.name for i in self.session.get_inputs()}

    def encode(self, texts: list[str]) -> np.ndarray:
        encs = self.tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encs], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
        inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
        # XLM-R 토크나이저는 token_type_ids 를 안 주지만 그래프가 요구할 수 있다.
        if "token_type_ids" in self._input_names:
            inputs["token_type_ids"] = np.zeros_like(input_ids)
        inputs = {k: v for k, v in inputs.items() if k in self._input_names}
        hidden = self.session.run(None, inputs)[0]  # (B, T, H)
        mask = attention_mask[..., None].astype(np.float32)
        pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
        pooled = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
        return pooled.astype("float32")


class _SentenceTransformerEmbedder:
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        try:
            self.model = SentenceTransformer(MODEL_ID, device="mps")
            self.model.encode(["query: warmup"], normalize_embeddings=True)
        except Exception:
            self.model = SentenceTransformer(MODEL_ID)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True).astype("float32")


def load_query_embedder():
    """int8 ONNX 가 준비돼 있으면 그것을, 아니면 sentence-transformers 를 쓴다."""
    if (ONNX_DIR / "model_int8.onnx").exists():
        try:
            embedder = _OnnxEmbedder(ONNX_DIR)
            embedder.encode(["query: warmup"])  # 워밍업 겸 자가 점검
            log.info("query embedder: int8 ONNX (%s)", ONNX_DIR)
            return embedder
        except Exception:
            log.exception("int8 ONNX 로드 실패 — sentence-transformers 로 폴백")
    embedder = _SentenceTransformerEmbedder()
    log.info("query embedder: sentence-transformers (%s)", MODEL_ID)
    return embedder
