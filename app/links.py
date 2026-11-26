"""Web links used by the program.

The program never connects to the internet by itself: a link is opened in the default
browser only when the user clicks the matching button.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

KOFI_URL = "https://ko-fi.com/thenormal"


def open_support_page() -> bool:
    """Open the Ko-fi page in the default browser."""
    return QDesktopServices.openUrl(QUrl(KOFI_URL))
