"""Projekt-Scanner: rekursiv Dateien lesen, Kurzbeschreibungen beschaffen,
Metadata + Embeddings erzeugen und structure.md schreiben.
"""
from pathlib import Path
import os
from pathspec import PathSpec
from .cache import DescriptionCache
from .llmclient import chat_system_query, embed_text
from .embeddings import FaissStore
from .metadata import extract_defs_from_code, write_metadata

DATA_DIR = Path("data")


class ProjectScanner:
    """Rekursiver Projekt-Scanner für Python-Packages.

    Durchsucht ein Zielverzeichnis rekursiv nach `.py`-Dateien, analysiert deren
    Inhalte, generiert Kurzbeschreibungen über ein LLM, extrahiert Funktionen und
    Klassen, und schreibt die komplette Projektstruktur in eine Markdown-Datei.

    Zusätzlich werden Metadaten in JSON gespeichert und Embeddings in einer
    FAISS-Datenbank abgelegt.
    """

    def __init__(self, target_dir: str) -> None:
        """Initialisiert den Projekt-Scanner.

        Lädt den Cache, initialisiert FAISS, erstellt das `data`-Verzeichnis
        und lädt optional eine `.gitignore`-Spezifikation.

        Args:
            target_dir (str): Pfad zum Zielverzeichnis (Python-Projekt oder Package).
        """
        self.target = Path(target_dir).resolve()
        self.cache = DescriptionCache()
        self.faiss = FaissStore()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.ignore_spec = self._load_gitignore()

    # --------------------------------------------------------
    # .gitignore mit pathspec
    # --------------------------------------------------------
    def _load_gitignore(self) -> "PathSpec | None":
        """Lädt eine `.gitignore`-Datei und erstellt eine PathSpec-Matching-Regel.

        Gibt `None` zurück, falls keine `.gitignore` vorhanden oder lesbar ist.

        Returns:
            PathSpec | None: Eine `PathSpec`-Instanz zur Filterung ignorierter Pfade
            oder `None`, falls keine Datei geladen werden konnte.
        """
        gitignore_path = self.target / ".gitignore"
        if not gitignore_path.exists():
            print("[Scanner] ℹ️ Keine .gitignore-Datei gefunden.")
            return None
        try:
            lines = gitignore_path.read_text(encoding="utf-8").splitlines()
            spec = PathSpec.from_lines("gitwildmatch", lines)
            print(f"[Scanner] 📜 .gitignore geladen mit {len(lines)} Einträgen")
            return spec
        except Exception as e:
            print(f"[Scanner] ⚠️ Fehler beim Laden der .gitignore: {e}")
            return None

    def _is_ignored(self, path: Path) -> bool:
        """Prüft, ob ein gegebener Pfad laut `.gitignore` ignoriert werden soll.

        Args:
            path (Path): Absoluter Pfad zu einer Datei oder einem Ordner.

        Returns:
            bool: `True`, wenn der Pfad laut `.gitignore` ignoriert werden soll,
            sonst `False`.
        """
        """Prüft, ob Datei oder Ordner laut .gitignore ignoriert werden soll."""
        if not self.ignore_spec:
            return False
        try:
            rel_path = str(path.relative_to(self.target)).replace("\\", "/")
            # für Ordner: trailing slash erzwingen, damit z. B. "__pycache__/" matched
            if path.is_dir() and not rel_path.endswith("/"):
                rel_path += "/"
            return self.ignore_spec.match_file(rel_path)
        except Exception as e:
            print(f"[Scanner] ⚠️ Fehler bei _is_ignored({path}): {e}")
            return False

    # --------------------------------------------------------
    # Hauptlogik
    # --------------------------------------------------------
    def scan(self) -> None:
        """Führt den vollständigen Scan des Zielprojekts durch.

        Rekursiv werden alle Python-Dateien im Zielordner durchsucht, Kurzbeschreibungen
        generiert, Funktionen und Klassen extrahiert und die Ergebnisse als:

        - Markdown-Struktur (`data/structure.md`)
        - Metadaten (`data/meta.json`)
        - Embeddings in FAISS (`data/vector.index`)

        gespeichert.

        Raises:
            Exception: Wenn beim Zugriff auf Dateien oder beim Schreiben der Ergebnisse
            ein schwerwiegender Fehler auftritt.
        """
        print(f"[Scanner] 🚀 Starte Scan von {self.target}")
        structure_lines = [f"{self.target.name}/"]
        metadata_items = []

        for root, dirs, files in os.walk(self.target):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.target)

            # Nur relevante Inhalte
            dirs[:] = [d for d in sorted(dirs) if not self._is_ignored(root_path / d)]
            files = [f for f in sorted(files) if f.endswith(".py") and not self._is_ignored(root_path / f)]

            # ├── oder └── für Ordner
            if rel_root.parts:
                depth = len(rel_root.parts) - 1
                parent = rel_root.parent
                parent_path = self.target / parent
                try:
                    siblings = sorted([p for p in parent_path.iterdir() if p.is_dir() and not self._is_ignored(p)])
                    is_last_dir = (rel_root.name == siblings[-1].name) if siblings else False
                except FileNotFoundError:
                    is_last_dir = False

                # Einrückung aufbauen
                indent_parts = []
                for i, part in enumerate(rel_root.parts[:-1]):
                    partial = self.target.joinpath(*rel_root.parts[:i + 1])
                    try:
                        parent_dirs = sorted([p for p in partial.parent.iterdir() if p.is_dir() and not self._is_ignored(p)])
                        if partial.name == parent_dirs[-1].name:
                            indent_parts.append("    ")
                        else:
                            indent_parts.append("│   ")
                    except FileNotFoundError:
                        indent_parts.append("│   ")

                branch = "└── " if is_last_dir else "├── "
                structure_lines.append("".join(indent_parts) + branch + rel_root.name + "/")

            # Dateien
            for i, fname in enumerate(files):
                fpath = root_path / fname
                relpath = str(fpath.relative_to(self.target))
                connector = "└──" if i == len(files) - 1 else "├──"

                # Einrückung für Datei
                indent_parts = []
                for j, part in enumerate(rel_root.parts):
                    partial = self.target.joinpath(*rel_root.parts[:j + 1])
                    try:
                        parent_dirs = sorted([p for p in partial.parent.iterdir() if p.is_dir() and not self._is_ignored(p)])
                        if partial.name == parent_dirs[-1].name:
                            indent_parts.append("    ")
                        else:
                            indent_parts.append("│   ")
                    except FileNotFoundError:
                        indent_parts.append("│   ")
                subindent = "".join(indent_parts)

                # Datei lesen
                try:
                    code = fpath.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    print(f"[Scanner] ⚠️ Fehler beim Lesen von {relpath}: {e}")
                    code = ""

                # Beschreibung holen
                use_llm = self.cache.should_query_llm(relpath)
                desc = self.cache.get(relpath)
                if use_llm or desc is None:
                    system = "Du bist ein Python-Experte. Fasse die Aufgabe dieser Datei in einem Satz zusammen."
                    user = f"Datei: {relpath}\n\nCode:\n{code[:2000]}"
                    try:
                        desc = chat_system_query(system, user)
                    except Exception as e:
                        print(f"[Scanner] ⚠️ LLM-Beschreibung fehlgeschlagen ({e})")
                        desc = (code.splitlines()[0].strip()[:120] + "...") if code else "(leer)"
                    self.cache.touch(relpath, desc)

                structure_lines.append(f"{subindent}{connector} {fname:<30} # {desc}")

                # Metadaten + Embeddings
                funcs, classes = extract_defs_from_code(code)
                metadata_items.append({"file": relpath, "functions": funcs, "classes": classes})
                try:
                    emb = embed_text(desc)
                    self.faiss.add(emb, relpath)
                except Exception as e:
                    print(f"[Scanner] ⚠️ Fehler bei Embedding für {relpath}: {e}")

        # Speichern
        write_metadata(metadata_items)
        structure_file = DATA_DIR / "structure.md"
        structure_file.write_text("\n".join(structure_lines), encoding="utf-8")

        print(f"[Scanner] ✅ Scan abgeschlossen. Struktur gespeichert unter {structure_file}")
