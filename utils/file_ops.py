"""Hilfsfunktionen für Dateioperationen und Diffs."""
from pathlib import Path
import difflib
import shutil


def read_file(path: Path) -> str:
    """Liest den Inhalt einer Textdatei ein.

    Öffnet die angegebene Datei im UTF-8-Encoding und gibt deren Inhalt zurück.
    Falls die Datei nicht existiert, wird ein leerer String zurückgegeben.

    Args:
        path (Path): Pfad zur Datei, die gelesen werden soll.

    Returns:
        str: Der Inhalt der Datei oder ein leerer String, wenn die Datei nicht existiert.
    """
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def write_file_with_backup(path: Path, new_content: str) -> bool:
    """Schreibt neuen Inhalt in eine Datei und erstellt zuvor ein Backup.

    Wenn die Datei bereits existiert, wird eine Sicherheitskopie mit der Endung
    `.bak` erstellt, bevor der neue Inhalt geschrieben wird.

    Args:
        path (Path): Pfad zur Zieldatei.
        new_content (str): Neuer Textinhalt, der in die Datei geschrieben wird.

    Returns:
        bool: `True`, wenn das Schreiben erfolgreich war, sonst `False`.
    """
    try:
        if path.exists():
            backup = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup)
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception:
        return False


def unified_diff(old: str, new: str, filename: str = "file") -> str:
    """Erzeugt ein Unified Diff zwischen zwei Textversionen.

    Erstellt ein Diff im Standard-Unified-Format, um Unterschiede zwischen
    zwei Textinhalten (`old` und `new`) zu visualisieren. Wird typischerweise
    zur Anzeige von Codeänderungen genutzt.

    Args:
        old (str): Ursprünglicher Textinhalt.
        new (str): Neuer Textinhalt.
        filename (str, optional): Anzeigename der Datei im Diff-Header.
            Standardmäßig `"file"`.

    Returns:
        str: Der erzeugte Unified-Diff-Text.
    """
    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=f"{filename} (alt)",
        tofile=f"{filename} (neu)",
        lineterm=""
    )
    return "\n".join(diff)
