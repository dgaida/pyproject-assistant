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
from assistant.llmclient import embed_text
import re


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

    def _get_keywords(self, query: str) -> set[str]:
        """Extrahiert relevante Keywords (Token) aus einer Suchanfrage."""
        # Bereinigen: Kleinbuchstaben, nur alphanumerische Zeichen + wichtige Trennzeichen
        q_cleaned = query.lower()
        q_cleaned = re.sub(r"[^a-z0-9_./\\]+", " ", q_cleaned)

        # Trennen bei Leerzeichen, Slashes, Punkten
        tokens = set(re.split(r"[\s./\\]+", q_cleaned))

        # Rauschwörter filtern
        noise_words = {
            "schreibe", "inhalt", "für", "die", "das", "package", "ein", "eine",
            "und", "oder", "mit", "von", "zu", "py", "datei", "file", "function",
            "klasse", "class", "methode", "method", "in", "der", "relativer", "pfad"
        }
        keywords = {t for t in tokens if t and t not in noise_words}
        return keywords

    def find_relevant_files(self, query: str, top_k: int = 5):
        """Findet relevante Dateien für eine Nutzeranfrage.

        Args:
            query (str): Nutzeranfrage in Textform.
            top_k (int): Maximale Anzahl Treffer aus der Vektor-Suche.

        Returns:
            list[str]: Liste relativer Dateipfade, die relevant erscheinen.
        """
        results = set()
        q_lower = query.lower()
        q_keywords = self._get_keywords(query)
        print(f"[RAGSearcher] 🔑 Keywords: {q_keywords}")

        # --- 1. Keyword-basierte Suche ---
        try:
            for item in self.metadata:
                filepath = item.get("file", "")
                if not filepath.endswith(".py"):
                    continue

                # A. Direkter Pfad-Match (wenn Nutzer Pfad angibt)
                if filepath in q_lower:
                    results.add(filepath)
                    continue

                # B. Token-basierte Suche
                # Erstelle Tokens aus Pfad, Funktionen und Klassen
                path_tokens = set(re.split(r"[\s./\\]+", filepath.lower().replace(".py", "")))
                functions = {f.lower() for f in item.get("functions", [])}
                classes = {c.lower() for c in item.get("classes", [])}

                all_tokens = path_tokens.union(functions).union(classes)

                # Prüfe auf Schnittmenge
                if q_keywords.intersection(all_tokens):
                    results.add(filepath)

            print(f"[RAGSearcher] 🔎 Keyword-Suche ergab {len(results)} Treffer")
        except Exception as e:
            print(f"[RAGSearcher] ❌ Fehler bei Keyword-Suche: {e}")

        # --- 2. Embedding-basierte Suche ---
        try:
            emb = embed_text(query)
            vector_hits = self.faiss.search(emb, k=top_k)
            print(f"[RAGSearcher] 🔎 Vektor-Suche ergab {len(vector_hits)} Treffer")
            for score, fname in vector_hits:
                results.add(fname)
                print(f"[RAGSearcher]    → {fname} (score={score:.4f})")
        except Exception as e:
            print(f"[RAGSearcher] ❌ Fehler bei Vektor-Suche: {e}")

        result_list = sorted(results)
        print(f"[RAGSearcher] ✅ Gesamttreffer: {len(result_list)} Dateien")
        return result_list
