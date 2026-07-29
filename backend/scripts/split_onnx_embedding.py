"""int8 ONNX 에서 단어 임베딩 테이블을 분리해 메모리를 줄인다.

ONNX Runtime 은 96MB uint8 임베딩 테이블이 든 모델을 세션에 올릴 때 실측
~370MB 를 상주시킨다(초기화 사본·내부 변환). 테이블 조회(Gather + 역양자화)는
numpy 로 대체 가능하므로:

- 테이블을 .npy 로 추출해 **memmap(파일 기반)** 으로 조회 — 익명 RSS 거의 0,
  메모리 압박 시 OS 가 페이지 회수 가능
- ONNX 그래프에서 해당 Gather/DequantizeLinear 노드를 제거하고, 역양자화된
  단어 임베딩(fp32)을 그래프 입력으로 승격

역양자화 공식 (x - zero_point) * scale 을 numpy 로 그대로 재현하므로 결과는
비트 수준에서 동일하다(검증 스크립트로 확인할 것).

    python scripts/split_onnx_embedding.py --model-dir models/e5-small-int8
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

TABLE_INIT = "embeddings.word_embeddings.weight_quantized"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="models/e5-small-int8")
    args = parser.parse_args()
    model_dir = Path(args.model_dir)

    model = onnx.load(str(model_dir / "model_int8.onnx"))
    graph = model.graph
    inits = {i.name: i for i in graph.initializer}

    # 1) 테이블·스케일·영점 추출
    table = numpy_helper.to_array(inits[TABLE_INIT])
    gather = next(n for n in graph.node if n.op_type == "Gather" and TABLE_INIT in n.input)
    dq = next(n for n in graph.node if n.op_type == "DequantizeLinear" and gather.output[0] in n.input)
    scale = float(numpy_helper.to_array(inits[dq.input[1]]))
    zero_point = int(numpy_helper.to_array(inits[dq.input[2]]))
    embeds_name = dq.output[0]
    hidden = int(table.shape[1])

    np.save(model_dir / "word_embeddings_uint8.npy", table)
    (model_dir / "word_embeddings_meta.json").write_text(
        json.dumps({"scale": scale, "zero_point": zero_point, "vocab": int(table.shape[0]), "hidden": hidden})
    )

    # 2) 그래프 수술: Gather·DQ 제거, DQ 출력(fp32 단어 임베딩)을 입력으로 승격
    graph.node.remove(gather)
    graph.node.remove(dq)
    graph.initializer.remove(inits[TABLE_INIT])
    graph.input.append(
        helper.make_tensor_value_info(
            embeds_name, TensorProto.FLOAT, ["batch_size", "sequence_length", hidden]
        )
    )

    onnx.checker.check_model(model, full_check=False)
    out_path = model_dir / "model_int8_noemb.onnx"
    onnx.save(model, str(out_path))
    print(f"완료: {out_path} ({out_path.stat().st_size/1e6:.0f}MB)")
    print(f"  테이블: word_embeddings_uint8.npy ({table.nbytes/1e6:.0f}MB, memmap 용)")
    print(f"  임베딩 입력명: {embeds_name}")


if __name__ == "__main__":
    main()
