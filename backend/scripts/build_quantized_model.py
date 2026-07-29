"""multilingual-e5-small 을 ONNX int8 로 양자화해 서버 메모리를 줄인다.

sentence-transformers 로 로드하면 RSS ~560MB(대부분 25만 vocab 임베딩 테이블의
fp32) 를 차지한다. ONNX 로 내보내고 가중치를 int8 동적 양자화하면 파일·메모리가
~1/4 로 줄고 CPU 추론도 빨라진다. 검색 품질 영향은 verify_quantized_model.py 로
반드시 확인할 것.

로컬(개발 맥)에서 실행해 산출물을 서버로 업로드한다(서버 1GB 램에선 torch
export 가 부담). 산출물은 git 에 넣지 않는다(~120MB).

    python scripts/build_quantized_model.py --out models/e5-small-int8
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

MODEL_ID = "intfloat/multilingual-e5-small"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="models/e5-small-int8")
    args = parser.parse_args()
    out_dir = Path(args.out)
    tmp_dir = out_dir.parent / (out_dir.name + "-fp32-tmp")

    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoTokenizer

    print(f"[1/3] ONNX export: {MODEL_ID}")
    model = ORTModelForFeatureExtraction.from_pretrained(MODEL_ID, export=True)
    model.save_pretrained(tmp_dir)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.save_pretrained(out_dir)

    fp32_path = tmp_dir / "model.onnx"
    int8_path = out_dir / "model_int8.onnx"
    print(f"[2/3] int8 동적 양자화 → {int8_path}")
    # MatMul 뿐 아니라 Gather(= 25만 vocab 임베딩 테이블)까지 양자화해야
    # 메모리 절감이 실제로 일어난다.
    # per_channel: 채널별 스케일로 양자화 오차를 크게 줄인다. per-tensor 로는
    # 25만 vocab 임베딩 테이블의 정밀도 손실이 검색 순위를 흔들었다
    # (Top-5 겹침 79% → 검증 실패). per-channel 로 재빌드해 통과시킨다.
    quantize_dynamic(
        model_input=str(fp32_path),
        model_output=str(int8_path),
        weight_type=QuantType.QInt8,
        op_types_to_quantize=["MatMul", "Gather"],
        per_channel=True,
    )
    shutil.rmtree(tmp_dir)

    fp32_mb = 0.0  # tmp 삭제됨 — 크기 로그용으로 미리 계산하려면 위에서
    int8_mb = int8_path.stat().st_size / 1e6
    print(f"[3/3] 완료: {int8_path} ({int8_mb:.0f}MB)")
    print("다음: python scripts/verify_quantized_model.py 로 품질을 검증할 것")


if __name__ == "__main__":
    main()
