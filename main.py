"""Startpunkt für die Anwendung.


usage:
python main.py --target /path/to/python/package
"""
import argparse
from gui.chatbot import launch_gui
from assistant.scanner import ProjectScanner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="Pfad zum zu durchsuchenden Python-Package")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    # Scan das Ziel (strukturiert erstellen, caches updaten)
    scanner = ProjectScanner(target_dir=args.target)
    scanner.scan()

    # Gradio GUI starten
    launch_gui(host=args.host, port=args.port, project_root=args.target)


if __name__ == "__main__":
    main()
