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


def extract_defs_from_code(code: str):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [], []
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    return funcs, classes


def write_metadata(items: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
