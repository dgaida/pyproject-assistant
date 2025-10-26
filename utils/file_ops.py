"""Hilfsfunktionen für Dateioperationen und Diffs."""
from pathlib import Path
import difflib
import shutil


def read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def write_file_with_backup(path: Path, new_content: str) -> bool:
    try:
        if path.exists():
            backup = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup)
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception:
        return False


def unified_diff(old: str, new: str, filename: str = "file") -> str:
    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=f"{filename} (alt)",
        tofile=f"{filename} (neu)",
        lineterm=""
    )
    return "\n".join(diff)
