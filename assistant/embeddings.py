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
    def __init__(self, dim: int | None = None) -> None:
        """Initialisiert den FAISS-Speicher für Embeddings.

        Lädt vorhandene FAISS-Indizes und das Mapping von Index-IDs zu Dateipfaden,
        falls entsprechende Dateien existieren. Erstellt das `data`-Verzeichnis bei Bedarf.

        Args:
            dim (int | None): Dimensionalität der Embeddings. Wird automatisch gesetzt,
                wenn ein gespeicherter Index geladen wird.
        """
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

    def _init_index(self, dim: int) -> None:
        """Initialisiert einen neuen FAISS-Index mit gegebener Dimensionalität.

        Args:
            dim (int): Anzahl der Dimensionen pro Embedding-Vektor.
        """
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)

    def add(self, vector: list[float], filepath: str) -> None:
        """Fügt einen neuen Embedding-Vektor in den FAISS-Index ein.

        Der Vektor wird normalisiert, in den Index eingefügt und
        die Zuordnung zwischen Index-ID und Dateipfad gespeichert.

        Args:
            vector (list[float]): Der einzufügende Embedding-Vektor.
            filepath (str): Der relative oder absolute Pfad zur zugehörigen Datei.
        """
        vec = np.array(vector, dtype="float32").reshape(1, -1)
        if self.index is None:
            self._init_index(vec.shape[1])
        faiss.normalize_L2(vec)
        self.index.add(vec)
        new_id = len(self.id_map)
        self.id_map[str(new_id)] = filepath
        self._persist()

    def search(self, vector: list[float], k: int = 5) -> list[tuple[float, str]]:
        """Sucht die `k` ähnlichsten Vektoren im FAISS-Index.

        Nutzt L2-Distanz und gibt eine Liste aus Distanzen und Dateipfaden zurück.

        Args:
            vector (list[float]): Der Abfrage-Vektor (Embedding).
            k (int, optional): Anzahl der ähnlichen Treffer. Standardmäßig 5.

        Returns:
            list[tuple[float, str]]: Liste von Tupeln bestehend aus
            (Distanzwert, Dateipfad) für jeden Treffer.
        """
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

    def _persist(self) -> None:
        """Speichert den aktuellen FAISS-Index und das ID-Mapping dauerhaft.

        Der Index wird in `data/vector.index` und das Mapping in
        `data/embeddings_map.json` geschrieben.
        """
        if self.index is not None:
            faiss.write_index(self.index, str(INDEX_FILE))
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(self.id_map, f, indent=2, ensure_ascii=False)
