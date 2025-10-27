"""Gradio-basierter Chatbot, der RAG nutzt, um relevante Dateien in Prompts
aufzunehmen und Code-Vorschläge anzuzeigen. Optional kann generierter Code
in die Zieldateien übernommen werden; jede Änderung wird als Diff angezeigt.
"""
import gradio as gr
import json
from pathlib import Path
import os
from datetime import datetime

from assistant.rag import RAGSearcher
from assistant.llmclient import chat_system_query
from utils.file_ops import read_file, write_file_with_backup, unified_diff


# FIX: Verbesserter System-Prompt, der Modifikationen statt Überschreiben anweist
SYSTEM_PROMPT = """Du bist ein hilfreicher Python-Programmierassistent.
Deine Aufgabe ist es, Code-Änderungen basierend auf der Nutzeranfrage und dem bereitgestellten Kontext (Projektstruktur, Dateiinhalte) zu generieren.

ANTWORTFORMAT (JSON):
[
  {
    "file": "relativer/pfad/zur/datei.py",
    "new_content": "Der VOLLSTÄNDIGE, NEUE Inhalt dieser Datei als String"
  }
]

WICHTIGE REGELN:
1.  **JSON ONLY**: Antworte IMMER NUR mit einem gültigen JSON-Array. Kein Text davor oder danach.
2.  **VOLLSTÄNDIGER INHALT**: `new_content` MUSS den gesamten Dateiinhalt enthalten, nicht nur die geänderten Zeilen.
3.  **ÄNDERUNGEN VORNEHMEN**: Wenn eine Datei bereits Inhalt hat (im Kontext `### Datei: ...` gezeigt),
    BASIERE deine Antwort auf diesem Inhalt und nimm die vom Nutzer gewünschten Änderungen vor.
    Schreibe den Code nicht komplett neu, es sei denn, die Datei ist leer oder die Anfrage verlangt es explizit.
4.  **LOGIK BEIBEHALTEN**: Behalte bestehende Importe, Funktionen und Logik bei, die von der Anfrage nicht betroffen sind.
5.  **KEINE HALLUZINATIONEN**: Wenn eine Datei leer ist (z.B. `__init__.py`) und der Nutzer Inhalt dafür möchte, füge nur minimal notwendigen Code hinzu (z.B. einen Docstring oder relevante Importe), basierend auf dem Kontext der Projektstruktur. Erfinde keine komplexen Strukturen.
"""


def save_prompt_to_md(prompt: str, folder: str = "logs/prompts") -> Path:
    """Speichert den vollständigen Prompt als Markdown-Datei mit Zeitstempel.

    Erstellt das angegebene Zielverzeichnis (falls nicht vorhanden) und legt dort
    eine Markdown-Datei mit dem vollständigen Prompt-Inhalt ab. Der Dateiname
    enthält einen eindeutigen Zeitstempel.

    Args:
        prompt (str): Der vollständige Text des Prompts, der gespeichert werden soll.
        folder (str, optional): Zielverzeichnis für die gespeicherte Datei.
            Standardmäßig `"logs/prompts"`.

    Returns:
        Path: Der vollständige Pfad zur erstellten Markdown-Datei.
    """
    Path(folder).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = Path(folder) / f"prompt-{timestamp}.md"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# LLM Prompt ({timestamp})\n\n")
            f.write(prompt)
        print(f"[Chatbot] 💾 Prompt gespeichert: {filename}")
    except Exception as e:
        print(f"[Chatbot] ⚠️ Fehler beim Speichern des Prompts: {e}")
    return filename


def launch_gui(host: str = "127.0.0.1", port: int = 7860, project_root: str = ".") -> None:
    """Startet die Gradio-GUI für den Projekt-Assistenten mit RAG-Funktionalität.

    Die Anwendung bietet:
      - Einen Chatbereich zur Kommunikation mit dem LLM
      - Anzeige der Projektstruktur (Markdown)
      - Anzeige von vorgeschlagenen Dateiänderungen (Diffs)
      - Möglichkeit, generierte Änderungen in die Dateien zu übernehmen

    Args:
        host (str, optional): Hostname oder IP-Adresse, unter der die GUI erreichbar ist.
            Standardmäßig `"127.0.0.1"`.
        port (int, optional): Portnummer, auf dem der Gradio-Server läuft.
            Standardmäßig `7860`.
        project_root (str, optional): Pfad zum Projekt, das analysiert und bearbeitet werden soll.
            Standardmäßig `"."`.

    Raises:
        Exception: Wenn beim Laden der Projektstruktur oder bei der GUI-Initialisierung
        ein schwerwiegender Fehler auftritt.
    """
    project_root = Path(project_root)
    rag = RAGSearcher()

    structure_file = Path("data/structure.md")
    if structure_file.exists():
        structure_md = structure_file.read_text(encoding="utf-8")
    else:
        structure_md = "FEHLER: data/structure.md nicht gefunden. Bitte main.py erneut ausführen."
        print(f"[Chatbot] ❌ {structure_md}")

    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🧠 Project Assistant — Chatbot (RAG)")

        with gr.Row():
            with gr.Column(scale=3):
                user_input = gr.Textbox(label="Anfrage an das LLM / Chatbot", lines=4, placeholder="z.B. 'Füge eine Funktion hinzu, die ...' oder 'Optimiere die Imports in utils/helpers.py'")
                send_btn = gr.Button("Senden", variant="primary")
                llm_raw_output = gr.JSON(label="Rohantwort des LLM (JSON)")
            with gr.Column(scale=2):
                gr.Markdown("## Projektstruktur (wird in jeden Prompt eingefügt)")
                gr.Textbox(value=structure_md, interactive=False, lines=30, max_lines=40)

        # Bereich für Dateiänderungen
        gr.Markdown("## Vorgeschlagene Dateiänderungen")
        file_list = gr.Dropdown(
            label="Geänderte Dateien",
            choices=[],
            value=None,
            interactive=True
        )
        diff_output = gr.Code(label="Diff (Unterschiede)", lines=20)
        apply_btn = gr.Button("Ausgewählte Änderung übernehmen")
        status = gr.Label()

        # Session-State: Liste der Änderungen
        state_changes = gr.State([])

        def on_send(user_prompt):
            if not user_prompt:
                return "{}", [], gr.update(choices=[], value=None)

            print(f"[Chatbot] 💬 Neue Anfrage: {user_prompt}")

            # Relevante Dateien für Kontext
            files = rag.find_relevant_files(user_prompt)
            context_parts = []
            if not files:
                print("[Chatbot] ⚠️ RAG fand keine relevanten Dateien.")

            for f in files:
                p = Path(project_root) / f
                if p.exists():
                    try:
                        text = p.read_text(encoding="utf-8", errors="ignore")
                        context_parts.append(f"\n### Datei: {f}\n```python\n{text}\n```")
                    except Exception as e:
                        print(f"[Chatbot] ⚠️ Fehler beim Lesen der Kontext-Datei {f}: {e}")
                        context_parts.append(f"\n### Datei: {f}\n(Konnte nicht gelesen werden: {e})")
                else:
                    print(f"[Chatbot] ⚠️ RAG-Treffer {f} existiert nicht am Pfad {p}")

            user_message = (
                "## Projektstruktur\n"
                f"{structure_md}\n\n"
                "## Relevante Dateien (Kontext)\n"
                + ("\n".join(context_parts) if context_parts else "(Keine relevanten Dateien gefunden)")
                + "\n\n## Nutzeranfrage\n"
                + user_prompt
            )

            # Prompt speichern, bevor LLM aufgerufen wird
            save_prompt_to_md(user_message)

            try:
                print("[Chatbot] 🤖 Sende Anfrage an LLM...")
                raw = chat_system_query(SYSTEM_PROMPT, user_message)
                print("[Chatbot] 🤖 LLM-Antwort (Roh):", raw)

                # Versuche JSON zu parsen
                changes = json.loads(raw)
                if not isinstance(changes, list):
                    raise ValueError("JSON ist kein Array")

            except Exception as e:
                print(f"[Chatbot] ❌ Fehler bei LLM- oder JSON-Parsing: {e}")
                error_json = [{"error": f"Fehler bei LLM- oder JSON-Parsing: {e}", "raw_response": raw}]
                return error_json, [], gr.update(choices=[], value=None)

            file_choices = [c.get("file", "N/A") for c in changes if isinstance(c, dict)]

            # (Roh-JSON, State-Objekt, Dropdown-Update)
            return changes, changes, gr.update(choices=file_choices, value=(file_choices[0] if file_choices else None))

        def on_select_file(filename, changes):
            if not filename or not changes:
                return "(Datei auswählen)"

            for c in changes:
                if c.get("file") == filename:
                    new_content = c.get("new_content", "(Fehler: 'new_content' fehlt im JSON)")
                    orig = read_file(Path(project_root) / filename)
                    diff = unified_diff(orig, new_content, filename=filename)
                    return diff
            return f"(Fehler: Datei {filename} nicht in JSON-Antwort gefunden)"

        def on_apply(filename, changes):
            if not filename:
                return gr.update(value="Keine Datei ausgewählt ❌", variant="stop")

            for c in changes:
                if c.get("file") == filename:
                    target_path = Path(project_root) / filename
                    # Stelle sicher, dass das Verzeichnis existiert (für neue Dateien)
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    ok = write_file_with_backup(target_path, c["new_content"])
                    if ok:
                        print(f"[Chatbot] ✅ Änderung für {filename} übernommen.")
                        return gr.update(value=f"Änderung für {filename} übernommen ✅", variant="success")
                    else:
                        print(f"[Chatbot] ❌ Fehler beim Schreiben von {filename}.")
                        return gr.update(value=f"Fehler beim Schreiben von {filename} ❌", variant="stop")

            return gr.update(value="Datei nicht gefunden ❌", variant="stop")

        send_btn.click(
            on_send,
            inputs=[user_input],
            outputs=[llm_raw_output, state_changes, file_list],
        )
        file_list.change(
            on_select_file,
            inputs=[file_list, state_changes],
            outputs=[diff_output],
        )
        apply_btn.click(
            on_apply,
            inputs=[file_list, state_changes],
            outputs=[status],
        )

    print(f"[Chatbot] 🚀 Starte Gradio GUI auf http://{host}:{port}")
    demo.launch(server_name=host, server_port=port, inbrowser=True)
