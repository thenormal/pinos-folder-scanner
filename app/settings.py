"""Settings remembered between runs (on Windows, in the per-user registry)."""
from __future__ import annotations

import os
from typing import List

from PySide6.QtCore import QLocale, QSettings

from .i18n import LANGUAGES

DEPTH_KEYS = ["0", "1", "2", "3", "all"]


def detect_system_language() -> str:
    name = QLocale.system().name().lower()  # e.g. "it_it", "en_us"
    code = name.split("_")[0]
    return code if code in LANGUAGES else "en"


class Settings:
    def __init__(self) -> None:
        self._q = QSettings("thenormal", "PinosFolderScanner")

    # language
    def language(self) -> str:
        value = str(self._q.value("language", "") or "")
        return value if value in LANGUAGES else detect_system_language()

    def set_language(self, lang: str) -> None:
        self._q.setValue("language", lang)

    # scan options
    def depth_key(self) -> str:
        value = str(self._q.value("depth", "2") or "2")
        return value if value in DEPTH_KEYS else "2"

    def set_depth_key(self, key: str) -> None:
        self._q.setValue("depth", key)

    def include_hidden(self) -> bool:
        return str(self._q.value("include_hidden", "false")).lower() == "true"

    def set_include_hidden(self, value: bool) -> None:
        self._q.setValue("include_hidden", "true" if value else "false")

    def formats(self, allowed: List[str]) -> List[str]:
        raw = str(self._q.value("formats", "pdf") or "")
        chosen = [f for f in raw.split(",") if f in allowed]
        return chosen or ["pdf"]

    def set_formats(self, formats: List[str]) -> None:
        self._q.setValue("formats", ",".join(formats))

    # folders used
    def last_folder(self) -> str:
        value = str(self._q.value("last_folder", "") or "")
        return value if value and os.path.isdir(value) else ""

    def set_last_folder(self, path: str) -> None:
        self._q.setValue("last_folder", path)

    def last_save_dir(self) -> str:
        value = str(self._q.value("last_save_dir", "") or "")
        return value if value and os.path.isdir(value) else ""

    def set_last_save_dir(self, path: str) -> None:
        self._q.setValue("last_save_dir", path)
