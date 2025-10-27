"""Cache-Handling für Kurzbeschreibungen.


Speichert eine Hashmap in data/descriptions.json mit folgendem Schema:
{
"relative/path/to/file.py": {
"desc": "Kurzbeschreibung...",
"count": 1
},
...
}


Die Logik nutzt `count` um die LLM-Abfrage zu throtteln: standardmäßig
wird nur bei count % 5 == 0 das LLM erneut befragt.
"""
import json
from pathlib import Path
from typing import Optional


DATA_DIR = Path("data")
CACHE_FILE = DATA_DIR / "descriptions.json"


class DescriptionCache:
    def __init__(self) -> None:
        """Initialisiert den Cache für Kurzbeschreibungen.

        Lädt vorhandene Daten aus `data/descriptions.json`, falls die Datei existiert.
        Stellt sicher, dass das `data`-Verzeichnis existiert.
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def get(self, relpath: str) -> Optional[str]:
        """Gibt die gespeicherte Kurzbeschreibung einer Datei zurück.

        Args:
            relpath (str): Relativer Pfad zur Python-Datei im Projekt.

        Returns:
            Optional[str]: Die gespeicherte Kurzbeschreibung, falls vorhanden,
            sonst `None`.
        """
        entry = self._data.get(relpath)
        if not entry:
            return None
        return entry.get("desc")

    def should_query_llm(self, relpath: str) -> bool:
        """Entscheidet, ob das LLM erneut zur Beschreibung der Datei befragt werden soll.

        Das LLM wird nur befragt, wenn kein Eintrag existiert oder wenn der Zähler
        (`count`) ein Vielfaches von 5 ist (Throttling-Mechanismus).

        Args:
            relpath (str): Relativer Pfad zur Datei.

        Returns:
            bool: `True`, wenn das LLM befragt werden soll, sonst `False`.
        """
        entry = self._data.get(relpath)
        if not entry:
            return True
        # Wenn count % 5 == 0 -> aktualisieren
        count = entry.get("count", 1)
        return (count % 5) == 0

    def touch(self, relpath: str, description: str) -> None:
        """Aktualisiert oder erstellt den Cache-Eintrag für eine Datei.

        Erhöht den Zähler `count` und speichert die neue Kurzbeschreibung.
        Schreibt den aktualisierten Zustand in die JSON-Datei.

        Args:
            relpath (str): Relativer Pfad zur Datei.
            description (str): Die neue Kurzbeschreibung.
        """
        entry = self._data.get(relpath, {})
        entry["desc"] = description
        entry["count"] = entry.get("count", 0) + 1
        self._data[relpath] = entry
        self._persist()

    def _persist(self) -> None:
        """Persistiert den aktuellen Cache-Zustand in `data/descriptions.json`.

        Schreibt alle gespeicherten Beschreibungen und Zählerwerte dauerhaft in die JSON-Datei.
        """
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
