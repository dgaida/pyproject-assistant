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
        if MAP_FILE.exists() and INDEX_FILE.exists():
            try:
                self.id_map = json.loads(MAP_FILE.read_text(encoding="utf-8"))
                self.index = faiss.read_index(str(INDEX_FILE))
                self.dim = self.index.d
                print(f"[FaissStore] ✅ Index ({self.index.ntotal} Vektoren) und Map ({len(self.id_map)} Einträge) geladen.")
            except Exception as e:
                print(f"[FaissStore] ⚠️ Fehler beim Laden des Index, starte neu: {e}")
                self.index = None
                self.id_map = {}
        else:
            print("[FaissStore] ℹ️ Kein Index/Map gefunden, starte neu.")

    def _init_index(self, dim: int) -> None:
        """Initialisiert einen neuen FAISS-Index mit gegebener Dimensionalität.

        Args:
            dim (int): Anzahl der Dimensionen pro Embedding-Vektor.
        """
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)

    def clear(self) -> None:
        """Löscht den Index und das Mapping (Datei und Speicher)."""
        self.index = None
        self.id_map = {}
        if INDEX_FILE.exists():
            try:
                INDEX_FILE.unlink()
            except OSError as e:
                print(f"[FaissStore] ⚠️ Fehler beim Löschen von {INDEX_FILE}: {e}")
        if MAP_FILE.exists():
            try:
                MAP_FILE.unlink()
            except OSError as e:
                print(f"[FaissStore] ⚠️ Fehler beim Löschen von {MAP_FILE}: {e}")
        print("[FaissStore] 🧹 Index und Map gelöscht.")

    def add(self, vector: list[float], filepath: str, persist_now: bool = True) -> None:
        """Fügt einen neuen Embedding-Vektor in den FAISS-Index ein.

        Der Vektor wird normalisiert, in den Index eingefügt und
        die Zuordnung zwischen Index-ID und Dateipfad gespeichert.

        Args:
            vector (list[float]): Der einzufügende Embedding-Vektor.
            filepath (str): Der relative oder absolute Pfad zur zugehörigen Datei.
            persist_now (bool): Ob der Index sofort gespeichert werden soll.
        """
        vec = np.array(vector, dtype="float32").reshape(1, -1)
        if self.index is None:
            self._init_index(vec.shape[1])
        faiss.normalize_L2(vec)
        self.index.add(vec)

        # WICHTIGER FIX: Die ID muss die FAISS-Index-ID sein (ntotal - 1)
        new_id = self.index.ntotal - 1
        self.id_map[str(new_id)] = filepath

        if persist_now:
            self.persist()

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
        if self.index is None or self.index.ntotal == 0:
            print("[FaissStore] ⚠️ Suche abgebrochen, Index ist leer.")
            return []

        # Stelle sicher, dass k nicht größer ist als die Anzahl der Elemente im Index
        k = min(k, self.index.ntotal)

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
            else:
                print(f"[FaissStore] ⚠️ Index {fid} nicht in Map gefunden!")
        return results

    def persist(self) -> None:
        """Speichert den aktuellen FAISS-Index und das ID-Mapping dauerhaft."""
        if self.index is not None:
            faiss.write_index(self.index, str(INDEX_FILE))
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(self.id_map, f, indent=2, ensure_ascii=False)
        # print(f"[FaissStore] 💾 Index ({self.index.ntotal}) und Map ({len(self.id_map)}) gespeichert.")
