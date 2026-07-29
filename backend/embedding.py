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


class _SplitOnnxEmbedder:
    """임베딩 테이블 분리형 — 테이블은 memmap, 트랜스포머만 ONNX.

    통짜 int8 ONNX 는 ORT 세션이 ~370MB 를 상주시킨다(실측). 96MB 테이블을
    numpy memmap 으로 빼면 파일 기반 페이지라 익명 RSS 가 거의 0 이고, ONNX
    세션은 22MB 트랜스포머만 든다. 역양자화 (x-zp)*scale 을 numpy 로 동일
    재현하므로 결과는 통짜 모델과 일치한다(scripts/split_onnx_embedding.py).
    """

    EMBEDS_INPUT = "/embeddings/word_embeddings/Gather_output_0"

    # XLM-R(fairseq) 특수 토큰: <s>=0, <pad>=1, </s>=2, <unk>=3, 일반 = sp_id+1.
    # HF tokenizers(tokenizer.json)와의 ID 완전 일치는 다국어 14종 샘플로 검증됨
    # — tokenizers 는 25만 vocab 로드에 ~286MB 를 쓰지만 sentencepiece 는 ~수십MB.
    BOS, PAD, EOS, UNK, OFFSET = 0, 1, 2, 3, 1

    def __init__(self, model_dir: Path) -> None:
        import json

        import onnxruntime as ort
        import sentencepiece as spm

        self.sp = spm.SentencePieceProcessor(
            model_file=str(model_dir / "sentencepiece.bpe.model")
        )

        meta = json.loads((model_dir / "word_embeddings_meta.json").read_text())
        self.scale = float(meta["scale"])
        self.zero_point = float(meta["zero_point"])
        self.table = np.load(model_dir / "word_embeddings_uint8.npy", mmap_mode="r")

        self.session = ort.InferenceSession(
            str(model_dir / "model_int8_noemb.onnx"), providers=["CPUExecutionProvider"]
        )
        self._input_names = {i.name for i in self.session.get_inputs()}

    def _tokenize(self, text: str) -> list[int]:
        raw = self.sp.encode(text, out_type=int)
        mapped = [self.UNK if i == self.sp.unk_id() else i + self.OFFSET for i in raw]
        return [self.BOS] + mapped[:510] + [self.EOS]

    def encode(self, texts: list[str]) -> np.ndarray:
        seqs = [self._tokenize(t) for t in texts]
        longest = max(len(s) for s in seqs)
        input_ids = np.full((len(seqs), longest), self.PAD, dtype=np.int64)
        attention_mask = np.zeros((len(seqs), longest), dtype=np.int64)
        for row, seq in enumerate(seqs):
            input_ids[row, : len(seq)] = seq
            attention_mask[row, : len(seq)] = 1
        # DequantizeLinear 재현: (uint8 - zero_point) * scale
        embeds = (self.table[input_ids].astype(np.float32) - self.zero_point) * self.scale
        inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            self.EMBEDS_INPUT: embeds,
        }
        if "token_type_ids" in self._input_names:
            inputs["token_type_ids"] = np.zeros_like(input_ids)
        inputs = {k: v for k, v in inputs.items() if k in self._input_names}
        hidden = self.session.run(None, inputs)[0]
        mask = attention_mask[..., None].astype(np.float32)
        pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
        pooled = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
        return pooled.astype("float32")


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
    """분리형 int8 → 통짜 int8 → sentence-transformers 순으로 시도한다."""
    if (ONNX_DIR / "model_int8_noemb.onnx").exists() and (
        ONNX_DIR / "word_embeddings_uint8.npy"
    ).exists():
        try:
            embedder = _SplitOnnxEmbedder(ONNX_DIR)
            embedder.encode(["query: warmup"])  # 워밍업 겸 자가 점검
            log.info("query embedder: int8 ONNX 분리형(memmap 테이블) (%s)", ONNX_DIR)
            return embedder
        except Exception:
            log.exception("분리형 ONNX 로드 실패 — 통짜 int8 로 폴백")
    if (ONNX_DIR / "model_int8.onnx").exists():
        try:
            embedder = _OnnxEmbedder(ONNX_DIR)
            embedder.encode(["query: warmup"])
            log.info("query embedder: int8 ONNX (%s)", ONNX_DIR)
            return embedder
        except Exception:
            log.exception("int8 ONNX 로드 실패 — sentence-transformers 로 폴백")
    embedder = _SentenceTransformerEmbedder()
    log.info("query embedder: sentence-transformers (%s)", MODEL_ID)
    return embedder
