# index.py
import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

CSV  = "data/verses.csv"
IDX  = "data/verses.faiss"
NPY  = "data/verses.npy"
META = "data/verses_meta.parquet"

# 1) 데이터 로드
df = pd.read_csv(CSV)

# 2) 텍스트 전처리 (불필요한 공백/기호 정리 등)
def normalize(s: str) -> str:
    return " ".join(str(s).split())

df["clean"] = df["text"].map(normalize)

# 3) 임베딩
model = SentenceTransformer("intfloat/multilingual-e5-small", device="mps")  # MIT, 무료
# E5 계열은 프리픽스 권장
passages = [f"passage: {t}" for t in df["clean"].tolist()]
emb = model.encode(passages, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
emb = emb.astype("float32")

# 4) FAISS 인덱스
d = emb.shape[1]
index = faiss.IndexFlatIP(d)
index.add(emb)

faiss.write_index(index, IDX)
np.save(NPY, emb)
df[["book","chapter","verse","clean","text"]].to_parquet(META, index=False)
print("indexed", emb.shape)
