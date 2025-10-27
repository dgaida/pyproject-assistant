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
        # FIX: Index vor jedem Scan löschen, um Konsistenz sicherzustellen
        self.faiss.clear()
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

        # Zuerst alle Dateien sammeln, um Baumstruktur korrekt abzubilden
        paths_to_process = []
        for root, dirs, files in os.walk(self.target, topdown=True):
            root_path = Path(root)

            # Verzeichnisse filtern
            dirs[:] = [d for d in sorted(dirs) if not self._is_ignored(root_path / d)]

            # Dateien filtern
            for f in sorted(files):
                if f.endswith(".py") and not self._is_ignored(root_path / f):
                    paths_to_process.append(root_path / f)

        # DEBUG:
        # print(f"[Scanner] Gefundene Python-Dateien: {len(paths_to_process)}")

        # Baumstruktur und Metadaten erstellen
        last_dir_in_parent = {}
        processed_dirs = set()

        for fpath in paths_to_process:
            relpath = fpath.relative_to(self.target)
            parts = list(relpath.parts)

            indent_str = ""
            current_path = self.target

            # 1. Ordner-Struktur aufbauen (nur einmal pro Ordner)
            for i, part in enumerate(parts[:-1]):
                current_path = current_path / part
                dir_rel_path = current_path.relative_to(self.target)

                if dir_rel_path not in processed_dirs:
                    # Prüfen, ob dieser Ordner der letzte in seinem Parent ist
                    parent_path = current_path.parent
                    try:
                        siblings = sorted([p.name for p in parent_path.iterdir() if p.is_dir() and not self._is_ignored(p)])
                        is_last = (part == siblings[-1])
                        last_dir_in_parent[dir_rel_path] = is_last
                    except Exception:
                        is_last = False
                        last_dir_in_parent[dir_rel_path] = False

                    # Einrückung für den Ordner
                    parent_indent = ""
                    temp_parent = dir_rel_path.parent
                    while str(temp_parent) != ".":
                        parent_indent = ("    " if last_dir_in_parent.get(temp_parent, False) else "│   ") + parent_indent
                        temp_parent = temp_parent.parent

                    branch = "└── " if is_last else "├── "
                    structure_lines.append(f"{parent_indent}{branch}{part}/")
                    processed_dirs.add(dir_rel_path)

            # 2. Datei-Zeile aufbauen
            # Einrückung für die Datei
            file_indent = ""
            temp_parent = relpath.parent
            while str(temp_parent) != ".":
                file_indent = ("    " if last_dir_in_parent.get(temp_parent, False) else "│   ") + file_indent
                temp_parent = temp_parent.parent

            # Prüfen, ob diese Datei die letzte in ihrem Ordner ist
            try:
                file_siblings = sorted([f.name for f in fpath.parent.iterdir() if f.name.endswith(".py") and not self._is_ignored(f)])
                is_last_file = (fpath.name == file_siblings[-1])
            except Exception:
                is_last_file = False

            file_branch = "└── " if is_last_file else "├── "

            # 3. Metadaten für die Datei generieren
            relpath_str = str(relpath).replace("\\", "/")
            try:
                code = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"[Scanner] ⚠️ Fehler beim Lesen von {relpath_str}: {e}")
                code = ""

            # Beschreibung holen
            use_llm = self.cache.should_query_llm(relpath_str)
            desc = self.cache.get(relpath_str)
            if use_llm or desc is None:
                system = "Du bist ein Python-Experte. Fasse die Aufgabe dieser Datei in einem Satz zusammen."
                user = f"Datei: {relpath_str}\n\nCode:\n{code[:2000]}"
                try:
                    desc = chat_system_query(system, user)
                except Exception as e:
                    print(f"[Scanner] ⚠️ LLM-Beschreibung fehlgeschlagen ({e})")
                    desc = (code.splitlines()[0].strip()[:120] + "...") if code else "(leer)"
                self.cache.touch(relpath_str, desc)

            structure_lines.append(f"{file_indent}{file_branch} {fpath.name:<30} # {desc}")

            # 4. Metadaten + Embeddings
            funcs, classes = extract_defs_from_code(code)
            metadata_items.append({"file": relpath_str, "functions": funcs, "classes": classes})
            try:
                emb = embed_text(f"{relpath_str}: {desc}") # Embedding mit Pfad-Kontext
                # FIX: Persist erst am Ende
                self.faiss.add(emb, relpath_str, persist_now=False)
            except Exception as e:
                print(f"[Scanner] ⚠️ Fehler bei Embedding für {relpath_str}: {e}")

        # Speichern
        # FIX: Persist Index/Map EINMAL am Ende des Scans
        self.faiss.persist()
        print(f"[Scanner] ✅ FAISS-Index mit {self.faiss.index.ntotal} Vektoren gespeichert.")

        write_metadata(metadata_items)
        structure_file = DATA_DIR / "structure.md"
        structure_file.write_text("\n".join(structure_lines), encoding="utf-8")

        print(f"[Scanner] ✅ Scan abgeschlossen. Struktur gespeichert unter {structure_file}")
