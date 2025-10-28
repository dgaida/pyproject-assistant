#!/usr/bin/env python3
"""
Logging-Konfiguration für die PyProject-Assistant Anwendung

Zentralisierte Logging-Konfiguration für alle Module.
"""

import logging
import os
from datetime import datetime
from typing import Optional

# Logging-Verzeichnis
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Log-Datei mit Timestamp
LOG_FILE = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None, console_output: bool = True) -> None:
    """
    Konfiguriert das Logging-System für die gesamte Anwendung.

    Args:
        level: Logging-Level (default: INFO)
        log_file: Optionaler Pfad zur Log-Datei
        console_output: Ob auch auf Console geloggt werden soll
    """
    if log_file is None:
        log_file = LOG_FILE

    # Logging-Format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Root-Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Entferne existierende Handler
    root_logger.handlers.clear()

    # File Handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(file_handler)

    # Console Handler (optional)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Gibt einen konfigurierten Logger für ein Modul zurück.

    Args:
        name: Name des Loggers (üblicherweise __name__)

    Returns:
        Konfigurierter Logger

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    return logging.getLogger(name)


# Bei Import automatisch Setup durchführen
setup_logging()
