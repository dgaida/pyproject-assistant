"""Extrahiert Funktionen und Klassen aus Python-Dateien und speichert metadata.json


Schema:
[
{
"file": "rel/path.py",
"functions": ["foo", "bar"],
"classes": ["Baz"]
},
...
]
"""
import ast
import json
from pathlib import Path

DATA_DIR = Path("data")
META_FILE = DATA_DIR / "metadata.json"


def extract_defs_from_code(code: str) -> tuple[list[str], list[str]]:
    """Extrahiert Funktions- und Klassennamen aus Python-Quelltext.

    Nutzt das `ast`-Modul, um den Quelltext zu parsen und alle
    Vorkommen von `FunctionDef` und `ClassDef` zu extrahieren.

    Args:
        code (str): Der Python-Quelltext, aus dem Definitionen extrahiert werden sollen.

    Returns:
        tuple[list[str], list[str]]: Ein Tupel mit zwei Listen:
            - Liste der Funktionsnamen
            - Liste der Klassennamen
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [], []
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    return funcs, classes


def write_metadata(items: list[dict]) -> None:
    """Schreibt Metadaten zu Dateien, Funktionen und Klassen in eine JSON-Datei.

    Erstellt das Zielverzeichnis, falls es nicht existiert, und speichert
    die übergebenen Metadaten formatiert in `META_FILE`.

    Args:
        items (list[dict]): Liste von Dictionaries, die Metadaten zu Projektdateien enthalten.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
