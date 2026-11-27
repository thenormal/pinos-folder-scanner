"""Settings remembered between runs (on Windows, in the per-user registry)."""
from __future__ import annotations

import os
from typing import List

from PySide6.QtCore import QLocale, QSettings

from .i18n import LANGUAGES

DEPTH_KEYS = ["0", "1", "2", "3", "all"]


def language_for_locale(name: str) -> str:
    """The program language for a locale name such as "it_IT", "en_US" or "zh_CN".

    Chinese is Simplified Chinese: it is chosen automatically only for the Simplified locales
    (China, Singapore); for Traditional Chinese (Taiwan, Hong Kong, Macau) English is used, instead
    of showing characters the person does not use.
    """
    name = name.lower().replace("-", "_")
    code = name.split("_")[0]
    if code == "zh":
        parts = name.split("_")[1:]
        simplified = "hans" in parts or any(part in ("cn", "sg") for part in parts)
        return "zh" if simplified and "hant" not in parts else "en"
    return code if code in LANGUAGES else "en"


def detect_system_language() -> str:
    return language_for_locale(QLocale.system().name())  # e.g. "it_IT", "en_US", "zh_CN"


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

    # folder names left out of the scan (the text as typed: "node_modules, .git")
    def exclude_text(self) -> str:
        return str(self._q.value("exclude", "") or "")

    def set_exclude_text(self, text: str) -> None:
        self._q.setValue("exclude", text)

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
