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
from assistant.llm_client import chat_system_query
from utils.file_ops import read_file, write_file_with_backup, unified_diff


SYSTEM_PROMPT = """Du bist ein hilfreicher Python-Programmierassistent.
Wenn du Änderungen an Dateien vorschlägst, antworte im JSON-Format mit folgender Struktur:

[
  {
    "file": "relativer/pfad/zur/datei.py",
    "new_content": "Kompletter neuer Inhalt dieser Datei als String"
  },
  ...
]

Wichtig:
- Immer nur gültiges JSON zurückgeben.
- Alle Dateien, die du ändern willst, müssen vollständig in `new_content` enthalten sein.
- Schreibe keine zusätzlichen Erklärungen oder Text außerhalb des JSON.
"""


def save_prompt_to_md(prompt: str, folder: str = "logs/prompts") -> Path:
    """
    Speichert den vollständigen Prompt als Markdown-Datei.
    Der Dateiname enthält einen Zeitstempel.
    """
    Path(folder).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = Path(folder) / f"prompt-{timestamp}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# LLM Prompt\n\n")
        f.write(prompt)
    return filename


def launch_gui(host: str = "127.0.0.1", port: int = 7860, project_root: str = "."):
    project_root = Path(project_root)
    rag = RAGSearcher()
    structure_md = Path("data/structure.md").read_text(encoding="utf-8") if Path("data/structure.md").exists() else ""

    with gr.Blocks() as demo:
        gr.Markdown("# Project Assistant — Chatbot (RAG)")

        with gr.Row():
            with gr.Column(scale=3):
                user_input = gr.Textbox(label="Anfrage an das LLM / Chatbot", lines=4)
                send_btn = gr.Button("Senden")
                llm_raw_output = gr.Textbox(label="Rohantwort des LLM (JSON)", lines=15)
            with gr.Column(scale=2):
                gr.Markdown("## Projektstruktur (wird in jeden Prompt eingefügt)")
                gr.Textbox(value=structure_md, interactive=False, lines=30)

        # Bereich für Dateiänderungen
        gr.Markdown("## Vorgeschlagene Dateiänderungen")
        file_list = gr.Dropdown(
            label="Geänderte Dateien",
            choices=[],
            value=None,
            interactive=True
        )
        diff_output = gr.Textbox(label="Diff", lines=20)
        apply_btn = gr.Button("Ausgewählte Änderung übernehmen")
        status = gr.Label()

        # Session-State: Liste der Änderungen
        state_changes = gr.State([])

        def on_send(user_prompt):
            # Relevante Dateien für Kontext
            files = rag.find_relevant_files(user_prompt)
            context_parts = []
            for f in files:  # [:6]:
                p = Path(project_root) / f
                if p.exists():
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    context_parts.append(f"\n### Datei: {f}\n```python\n{text}\n```")  # [:2000]

            user_message = (
                "## Projektstruktur\n"
                f"{structure_md}\n\n"
                "## Relevante Dateien\n"
                + "\n".join(context_parts)
                + "\n\n## Nutzeranfrage\n"
                + user_prompt
            )

            # Prompt speichern, bevor LLM aufgerufen wird
            save_prompt_to_md(user_message)

            return ""

            try:
                raw = chat_system_query(SYSTEM_PROMPT, user_message)
                changes = json.loads(raw)
            except Exception as e:
                return f"(Fehler bei LLM- oder JSON-Parsing: {e})", []

            file_choices = [c["file"] for c in changes]
            return json.dumps(changes, indent=2, ensure_ascii=False), changes, gr.update(choices=file_choices, value=(file_choices[0] if file_choices else None))

        def on_select_file(filename, changes):
            for c in changes:
                if c["file"] == filename:
                    new_content = c["new_content"]
                    orig = read_file(Path(project_root) / filename)
                    return unified_diff(orig, new_content)
            return "(keine Änderung gefunden)"

        def on_apply(filename, changes):
            for c in changes:
                if c["file"] == filename:
                    ok = write_file_with_backup(Path(project_root) / filename, c["new_content"])
                    return "Änderung übernommen ✅" if ok else "Fehler beim Schreiben ❌"
            return "Datei nicht gefunden in Änderungen."

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

    demo.launch(server_name=host, server_port=port, inbrowser=True)
