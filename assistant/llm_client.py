"""LLM-Client: Chat über die GROQ API, Embeddings lokal über Ollama.

Dieses Modul kapselt:
- `chat_system_query`: Abfragen eines LLM über die GROQ API
- `embed_text`: Erzeugung von Embeddings über ein Ollama-Modell

Konfigurationshinweise:
- Die Datei `secrets.env` muss den Key `GROQ_API_KEY` enthalten.
- Ollama muss lokal installiert sein und ein Embedding-fähiges Modell
  verfügbar sein (z. B. `nomic-embed-text`).
"""

import os
from dotenv import load_dotenv
from groq import Groq
import requests
from ollama import embed

# --- API Keys / Umgebungsvariablen ---
load_dotenv("secrets.env")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("❌ Fehlender GROQ_API_KEY in secrets.env")

# --- Clients ---
client = Groq(api_key=GROQ_API_KEY)

# --- Funktionen ---

def chat_system_query(
    system_prompt: str,
    user_prompt: str,
    model: str = "moonshotai/kimi-k2-instruct-0905",
) -> str:
    """Chat-Abfrage an die GROQ API mit System- und User-Prompt.

    Args:
        system_prompt (str): System-Prompt zur Steuerung des LLM.
        user_prompt (str): Prompt des Nutzers.
        model (str): Modellname für die GROQ API (Default: moonshotai/kimi-k2-instruct-0905).

    Returns:
        str: Generierte Antwort des LLM.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=800,
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
        return content
    except Exception as e:
        print(f"[llm_client] ❌ Fehler bei GROQ Chat Query: {e}")
        raise


def embed_text(text: str, model: str = "nomic-embed-text"):
    """Erzeugt Embeddings mittels Ollama Python API.

    Args:
        text (str): Der Text, für den ein Embedding erzeugt werden soll.
        model (str): Ollama-Embedding-Modell, z. B. "nomic-embed-text".

    Returns:
        list[float]: Der Embedding-Vektor.

    Raises:
        RuntimeError: Wenn die Embedding-Antwort nicht wie erwartet ausfällt.
        Exception: Bei allen anderen Fehlern mit Debug-Ausgabe.
    """
    try:
        # Ollama muss installiert sein und das Modell gezogen (“pull”) worden sein
        resp = embed(model=model, input=text)
        # Das Ollama-embed gibt typischerweise ein Dict mit "embeddings" oder "embedding"
        # Checke Variante
        if "embeddings" in resp:
            emb = resp["embeddings"]
        elif "embedding" in resp:
            emb = resp["embedding"]
        else:
            raise RuntimeError(f"[embed_text] Kein Embedding Feld gefunden in Antwort: {resp!r}")
        # Falls mehrere Embeddings zurückgegeben wurden (z. B. Liste), nimm die erste
        if isinstance(emb, list) and len(emb) > 0 and isinstance(emb[0], list):
            return emb[0]
        return emb  # einzelner Vektor oder Liste
    except Exception as e:
        print(f"[embed_text] Fehler bei Ollama embed mit Modell '{model}': {e}")
        raise
