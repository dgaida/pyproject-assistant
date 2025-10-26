"""FAISS-basierte Verwaltung von Embeddings.


Speichert Index in data/vector.index und eine separate JSON-Mapping
für ids -> filepath (data/embeddings_map.json).
"""
from pathlib import Path
import numpy as np
import faiss
import json


DATA_DIR = Path("data")
INDEX_FILE = DATA_DIR / "vector.index"
MAP_FILE = DATA_DIR / "embeddings_map.json"


class FaissStore:
    def __init__(self, dim: int = None):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.dim = dim
        self.index = None
        self.id_map = {}
        if MAP_FILE.exists():
            try:
                self.id_map = json.loads(MAP_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.id_map = {}
        if INDEX_FILE.exists():
            try:
                self.index = faiss.read_index(str(INDEX_FILE))
                self.dim = self.index.d
            except Exception:
                self.index = None

    def _init_index(self, dim: int):
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)

    def add(self, vector: list, filepath: str):
        vec = np.array(vector, dtype="float32").reshape(1, -1)
        if self.index is None:
            self._init_index(vec.shape[1])
        faiss.normalize_L2(vec)
        self.index.add(vec)
        new_id = len(self.id_map)
        self.id_map[str(new_id)] = filepath
        self._persist()

    def search(self, vector: list, k: int = 5):
        if self.index is None:
            return []
        vec = np.array(vector, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(vec)
        D, I = self.index.search(vec, k)
        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx == -1:
                continue
            fid = str(idx)
            filepath = self.id_map.get(fid)
            if filepath:
                results.append((float(dist), filepath))
        return results

    def _persist(self):
        if self.index is not None:
            faiss.write_index(self.index, str(INDEX_FILE))
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(self.id_map, f, indent=2, ensure_ascii=False)
