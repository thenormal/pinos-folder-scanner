"""Web links used by the program.

The program never connects to the internet by itself: a link is opened in the default
browser only when the user clicks the matching button.
"""
from __future__ import annotations

from urllib.parse import quote, urlencode

KOFI_URL = "https://ko-fi.com/thenormal"
REPO_URL = "https://github.com/thenormal/pinos-folder-scanner"
ISSUES_URL = REPO_URL + "/issues"
README_URL = REPO_URL + "#readme"
BUG_FORM = "bug_report.yml"


def new_issue_url(version: str, system: str) -> str:
    """The "new bug report" page of GitHub with the version and Windows already filled in.

    Nothing is sent: the person sees the page in the browser, can read and change every field,
    and decides whether to send it.
    """
    query = urlencode({"template": BUG_FORM, "version": version, "windows": system}, quote_via=quote)
    return f"{ISSUES_URL}/new?{query}"


def open_url(url: str) -> bool:
    """Open a link in the default browser."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    return QDesktopServices.openUrl(QUrl(url))


def open_support_page() -> bool:
    """Open the Ko-fi page in the default browser."""
    return open_url(KOFI_URL)
