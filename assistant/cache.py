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
    def __init__(self):
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
        entry = self._data.get(relpath)
        if not entry:
            return None
        return entry.get("desc")

    def should_query_llm(self, relpath: str) -> bool:
        entry = self._data.get(relpath)
        if not entry:
            return True
        # Wenn count % 5 == 0 -> aktualisieren
        count = entry.get("count", 1)
        return (count % 5) == 0

    def touch(self, relpath: str, description: str):
        entry = self._data.get(relpath, {})
        entry["desc"] = description
        entry["count"] = entry.get("count", 0) + 1
        self._data[relpath] = entry
        self._persist()

    def _persist(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
