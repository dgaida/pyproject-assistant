"""RAG-Suche: kombiniert Vektor- und Schlüsselwortsuche über Projektdateien.

Dieses Modul implementiert die Klasse `RAGSearcher`, die zur semantischen und
keyword-basierten Suche in einem Python-Projekt dient. Grundlage sind:
- Metadaten über Dateien, Funktionen und Klassen (JSON-Datei META_FILE)
- Vektorsuche über Embeddings (FaissStore)

Die Methode `find_relevant_files` liefert eine Liste relativer Dateipfade zurück,
die thematisch zur Nutzeranfrage passen.
"""

import json
from pathlib import Path
from assistant.embeddings import FaissStore
from assistant.metadata import META_FILE


class RAGSearcher:
    """Kombiniert Keyword-Suche (Dateiname/Funktions-/Klassennamen)
    und Vektor-Suche (Embeddings) zur Auffindung relevanter Dateien."""

    def __init__(self):
        """Initialisiert den RAGSearcher.

        Lädt die Metadaten-Datei (falls vorhanden) und
        initialisiert die Vektor-Datenbank.
        """
        self.faiss = FaissStore()
        self.metadata = {}

        try:
            if Path(META_FILE).exists():
                self.metadata = json.loads(Path(META_FILE).read_text(encoding="utf-8"))
                print(f"[RAGSearcher] ✅ Metadaten geladen: {len(self.metadata)} Einträge")
            else:
                print(f"[RAGSearcher] ⚠️ Keine Metadaten-Datei gefunden: {META_FILE}")
        except Exception as e:
            print(f"[RAGSearcher] ❌ Fehler beim Laden der Metadaten aus {META_FILE}: {e}")
            self.metadata = {}

    def find_relevant_files(self, query: str, top_k: int = 10):
        """Findet relevante Dateien für eine Nutzeranfrage.

        Args:
            query (str): Nutzeranfrage in Textform.
            top_k (int): Maximale Anzahl Treffer aus der Vektor-Suche.

        Returns:
            list[str]: Liste relativer Dateipfade, die relevant erscheinen.
        """
        results = set()
        q = query.lower()

        # --- 1. Keyword-basierte Suche ---
        try:
            for item in self.metadata:
                fname = item.get("file", "").lower()
                if not fname.endswith(".py"):
                    continue
                functions = item.get("functions", [])
                classes = item.get("classes", [])
                # Prüfen, ob Dateiname oder Funktion/Klasse im Query vorkommt
                if fname in q or any(fn.lower() in q for fn in functions + classes):
                    results.add(item["file"])
            print(f"[RAGSearcher] 🔎 Keyword-Suche ergab {len(results)} Treffer")
        except Exception as e:
            print(f"[RAGSearcher] ❌ Fehler bei Keyword-Suche: {e}")

        # --- 2. Embedding-basierte Suche ---
        try:
            from assistant.llm_client import embed_text
            emb = embed_text(query)
            vector_hits = self.faiss.search(emb, k=top_k)
            print(f"[RAGSearcher] 🔎 Vektor-Suche ergab {len(vector_hits)} Treffer")
            for hit in vector_hits:
                print(f"[RAGSearcher]    → {hit}")
            for score, fname in vector_hits:
                results.add(fname)
                print(f"[RAGSearcher]    → {fname} (score={score:.4f})")
        except Exception as e:
            print(f"[RAGSearcher] ❌ Fehler bei Vektor-Suche: {e}")

        result_list = sorted(results)
        print(f"[RAGSearcher] ✅ Gesamttreffer: {len(result_list)} Dateien")
        return result_list
