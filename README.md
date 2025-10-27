# 🧠 Project Assistant — RAG-basierter Code-Assistent

Ein intelligenter **LLM-gestützter Projektassistent** für Python-Projekte.
Der Assistent durchsucht automatisch dein Repository, erzeugt Embeddings, fasst Dateien zusammen, und beantwortet Fragen zu deinem Code bzw. ergänzt neuen Code mit **RAG (Retrieval-Augmented Generation)**.
Zudem zeigt er über eine **Gradio-GUI** vorgeschlagene Dateiänderungen samt Diffs an.

---

## 🚀 Features

* 🔍 **Automatischer Projekt-Scan**

  * Erkennt Python-Dateien, ignoriert `.gitignore`-Einträge.
  * Erstellt eine visuelle **Projektstruktur** in `data/structure.md`.

* 💬 **LLM-Integration**

  * Erzeugt intelligente Kurzbeschreibungen jeder Datei.
  * Nutzt ein konfigurierbares Sprachmodell (z. B. `ollama`, `gpt-4`, `mistral`, …).
  * Speichert alle Prompts unter `logs/prompts/`.

* 🤩 **Vektorsuche mit FAISS**

  * Erzeugt Embeddings für jede Datei.
  * Kombination aus Keyword- und Vektorsuche zur Relevanzbewertung.

* 🧶 **GUI (Gradio)**

  * Einfacher Chat-Workflow: Eingabe deiner Frage → Anzeige der betroffenen Dateien → Vorschau & Anwendung der Änderungen.
  * Diff-Ansicht für jede vom LLM vorgeschlagene Änderung.
  * Automatische Backups bei Dateischreibvorgängen (`.bak`).

---

## 🧪 Projektstruktur

```plaintext
project-assistant/
├── assistant/           
├── data/
│   ├── structure.md           # Projektstruktur in Markdown
│   ├── descriptions.json      # Cache der Kurzbeschreibungen
│   ├── vector.index           # FAISS-Vektorindex
│   └── embeddings_map.json    # Mapping ID → Datei
├── gui/
│   ├── __init__.py           
│   └── chatbot.py             
├── logs/
│   └── prompts/               # Gespeicherte LLM-Prompts
├── utils/
│   ├── __init__.py           
│   └── file_ops.py      
├── .gitignore
├── environment.yml
├── LICENSE
├── main.py                    # CLI-Startpunkt / Scanner / App launcher
├── requirements.txt
└── README.md
```

---

## ⚙️ Installation

### 1️⃣ Voraussetzungen

* **Python 3.10+**
* **FAISS**, **Ollama** (lokales LLM) oder eine OpenAI-kompatible API
* **Gradio** für die Benutzeroberfläche

### 2️⃣ Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 3️⃣ Optional: Ollama installieren (für lokale LLMs)

[https://ollama.com/download](https://ollama.com/download)

Beispielmodell laden:

```bash
ollama pull llama3
```

---

## 🧠 Verwendung

### 🔹 Projekt scannen und GUI starten

Erzeugt Struktur, Metadaten, Embeddings und startet GUI:

```bash
python main.py
```

Die GUI öffnet sich im Browser unter:
🔗 [http://127.0.0.1:7860](http://127.0.0.1:7860)

---

## 🥉 Arbeitsweise (Kurzüberblick)

1. **ProjectScanner**

   * Lädt `.gitignore`-Regeln.
   * Liest und beschreibt alle `.py`-Dateien.
   * Speichert Kurzbeschreibungen im Cache.
   * Erstellt Vektorrepräsentationen (Embeddings) der Dateibeschreibungen.

2. **FAISSStore**

   * Speichert Embeddings und Datei-Mapping.
   * Ermöglicht schnelle semantische Suche nach relevanten Dateien.

3. **RAGSearcher**

   * Kombiniert Keyword-Suche und Embedding-Suche.
   * Ermittelt relevante Dateien für eine Nutzeranfrage.

4. **Gradio-GUI**

   * Interaktive Chatoberfläche für Nutzeranfragen.
   * Zeigt LLM-Antworten und vorgeschlagene Dateiänderungen.

---

## 🔒 Datenschutz & Sicherheit

* Lokale Speicherung aller Embeddings und Prompts.
* Keine Datenübertragung an Dritte ohne explizite API-Konfiguration.

---

## 💡 Tipps

* Scanne dein Projekt regelmäßig, um neue Dateien zu erfassen.
* Cache-Datei `data/descriptions.json` kann gefahrlos gelöscht werden, um neue Beschreibungen zu erzwingen.
* Bei LLM-Fehlern prüfe deine Umgebungsvariable (`OLLAMA_API_BASE` oder `OPENAI_API_KEY`).

---

## 👨‍💻 Autor

**Daniel Gaida**
Technische Hochschule Köln
✨ Open Source unter MIT-Lizenz
