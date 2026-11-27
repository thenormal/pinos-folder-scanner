"""Diagnostic report: what the program knows about the last scan, ready to be attached to a bug report.

This module does NOT depend on Qt. It only builds text; saving it and showing it are done by the window.

Privacy rules (checked by tests/test_diagnostics.py):
  * every folder name is replaced by a code, always; the same name always gets the same code;
  * the user name, the computer name and the home folder never appear;
  * free text (error messages, the end of errors.log) is cleaned the same way;
  * nothing is sent anywhere: the user decides what to do with the file.
"""
from __future__ import annotations

import getpass
import hashlib
import os
import platform
import re
import secrets
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from . import __version__
from .i18n import STRINGS
from .scanner import ScanResult

REPORT_TITLE = "Pino's Folder Scanner - diagnostic report"

# Windows drive types (GetDriveTypeW) -> text
_DRIVE_KINDS = {
    2: "removable drive",
    3: "local drive",
    4: "network drive",
    5: "optical drive",
    6: "RAM disk",
}


def error_log_path(create: bool = True) -> str:
    """Where unexpected errors are written (see main.py). With create=False no folder is made."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "PinosFolderScanner")
    if create:
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            folder = os.path.expanduser("~")
    return os.path.join(folder, "errors.log")


# ---------------------------------------------------------------- masking
_SEPARATORS = re.compile(r"[\\/]+")
_PY_FILE = re.compile(r"^[A-Za-z0-9_.\-]+\.py$")
# start of a Windows path inside free text: "C:\" / "C:/" or "\\" (network)
_PATH_START = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\")


class Masker:
    """Replaces folder names (and other personal details) with codes.

    The codes are made with a random value chosen for each report and never written in it, so
    they cannot be turned back into names, but the same name always gets the same code inside
    one report (so you can still see which folders are the same and how deep they are).
    """

    def __init__(self, salt: Optional[bytes] = None, user: Optional[str] = None, computer: Optional[str] = None) -> None:
        self._salt = salt if salt is not None else secrets.token_bytes(16)
        self._literals: Dict[str, str] = {}
        self._literal_re: Optional["re.Pattern[str]"] = None
        self._words: Dict[str, str] = {}
        self._word_re: Optional["re.Pattern[str]"] = None
        if user is None:
            try:
                user = getpass.getuser()
            except Exception:  # noqa: BLE001
                user = ""
        if computer is None:
            computer = platform.node()
        for word, label in ((user, "<user>"), (computer, "<computer>")):
            if word and len(word) >= 2:
                self._words[word.casefold()] = label

    # -- single pieces
    def code(self, name: str) -> str:
        digest = hashlib.sha256(self._salt + name.casefold().encode("utf-8", "surrogatepass")).hexdigest()
        return "f_" + digest[:6]

    def path(self, path: str, keep_py: bool = False) -> str:
        """A full path with every folder name replaced by a code.

        The kind of start is kept in words: <drive> (D:), <network> (\\\\server\\share), <root> (/).
        With keep_py the name of a final .py file is kept: it is a program file, useful in a
        traceback and not a personal name.
        """
        rest = path.strip()
        if not rest:
            return ""
        if rest.startswith("\\\\?\\UNC\\"):
            rest = "\\\\" + rest[8:]
        elif rest.startswith("\\\\?\\"):
            rest = rest[4:]
        prefix = ""
        if rest.startswith("\\\\") or rest.startswith("//"):
            prefix, rest = "<network>", rest.lstrip("\\/")
        elif re.match(r"^[A-Za-z]:", rest):
            prefix, rest = "<drive>", rest[2:]
        elif rest[:1] in ("\\", "/"):
            prefix = "<root>"
        parts = [p for p in _SEPARATORS.split(rest) if p]
        coded = []
        for i, part in enumerate(parts):
            if keep_py and i == len(parts) - 1 and _PY_FILE.match(part):
                coded.append(part)
            else:
                coded.append(self.code(part))
        if prefix:
            return prefix + ("\\" + "\\".join(coded) if coded else "\\")
        return "\\".join(coded)

    # -- text
    def _add_literal(self, real: str, replacement: str) -> None:
        if real:
            self._literals[real] = replacement
            self._literal_re = None

    def register_path(self, path: str) -> None:
        """Make sure this path is recognised in free text wherever it appears (even with spaces)."""
        if not path or len(path.strip()) < 3:
            return
        variants = {path, path.replace("/", "\\"), path.replace("\\", "/"), path.replace("\\", "\\\\")}
        for variant in variants:
            self._add_literal(variant, "")

    @staticmethod
    def _segment_end(text: str, start: int) -> int:
        """Where the path that begins at `start` ends: at the closing quote, or at the end of the line.

        Being generous is intentional: a path with spaces must not leak its second half.
        """
        eol = text.find("\n", start)
        eol = len(text) if eol < 0 else eol
        if start > 0 and text[start - 1] in "'\"":
            closing = text.find(text[start - 1], start, eol)
            if closing >= 0:
                return closing
        return eol

    def _mask_literals(self, text: str) -> str:
        if not self._literals:
            return text
        if self._literal_re is None:
            ordered = sorted(self._literals, key=len, reverse=True)
            self._literal_re = re.compile("|".join(re.escape(x) for x in ordered), re.IGNORECASE)
        out: List[str] = []
        pos = 0
        while True:
            match = self._literal_re.search(text, pos)
            if match is None:
                out.append(text[pos:])
                break
            start = match.start()
            out.append(text[pos:start])
            end = max(match.end(), self._segment_end(text, start))
            out.append(self.path(text[start:end], keep_py=True))
            pos = end
        return "".join(out)

    def _mask_windows_paths(self, text: str) -> str:
        """Any "C:\\..." or "\\\\server\\..." left in the text."""
        out: List[str] = []
        pos = 0
        while True:
            match = _PATH_START.search(text, pos)
            if match is None:
                out.append(text[pos:])
                break
            start = match.start()
            out.append(text[pos:start])
            end = self._segment_end(text, start)
            out.append(self.path(text[start:end], keep_py=True))
            pos = end
        return "".join(out)

    def _mask_words(self, text: str) -> str:
        if not self._words:
            return text
        if self._word_re is None:
            ordered = sorted(self._words, key=len, reverse=True)
            self._word_re = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(x) for x in ordered) + r")(?![A-Za-z0-9])", re.IGNORECASE)
        return self._word_re.sub(lambda m: self._words.get(m.group(0).casefold(), "<name>"), text)

    def text(self, text: str) -> str:
        """Free text (an error message, a traceback...) with the personal details removed."""
        text = self._mask_literals(text)
        text = self._mask_windows_paths(text)
        return self._mask_words(text)


# ---------------------------------------------------------------- what kind of path is it
def _drive_type_windows(root: str) -> int:
    if os.name != "nt":
        return 0
    try:
        import ctypes

        return int(ctypes.windll.kernel32.GetDriveTypeW(root))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return 0


def path_kind(path: str, drive_type: Optional[Callable[[str], int]] = None) -> str:
    """local drive / network drive / network share / removable drive ... (never the path itself)."""
    p = path.strip()
    if p.startswith("\\\\?\\UNC\\") or (p.startswith("\\\\") and not p.startswith("\\\\?\\")):
        return "network share (UNC)"
    if p.startswith("\\\\?\\"):
        p = p[4:]
    if re.match(r"^[A-Za-z]:", p):
        kind = (drive_type or _drive_type_windows)(p[:2] + "\\")
        return _DRIVE_KINDS.get(kind, "unknown")
    return "unknown (not a drive letter)"


# ---------------------------------------------------------------- the data of the last run
@dataclass
class RunRecord:
    """What happened in the last scan: filled by the window, read by build_report."""

    started_at: datetime
    root: str
    depth_key: str
    include_hidden: bool
    formats: List[str]
    language: str = "en"
    save_base: str = ""
    status: str = "running"  # running | completed | cancelled | failed
    result: Optional[ScanResult] = None
    export_stats: Dict[str, Dict[str, object]] = field(default_factory=dict)
    errors: List[Tuple[str, str]] = field(default_factory=list)  # [(format, message)]
    fail_message: str = ""
    fail_trace: str = ""


def needs_attention(run: Optional["RunRecord"]) -> bool:
    """True when something really went wrong in the last scan (so the report is worth offering).

    Really wrong means: a format could not be created, the scan failed with an unexpected
    error, or folders were skipped because of an unexpected system error. "Access denied" and
    "not found" are normal and do not count.
    """
    if run is None:
        return False
    if run.status == "failed" or run.errors:
        return True
    if any(stat.get("error") for stat in run.export_stats.values()):
        return True
    if run.result is not None and any(item.code == "error" for item in run.result.skipped):
        return True
    return False


def system_summary() -> str:
    """Windows version in one short line (no user name, no computer name)."""
    return platform.platform()


def environment_info(language: str, pixel_ratio: Optional[float] = None) -> List[Tuple[str, str]]:
    """Program and system details (no user name, no computer name)."""
    rows: List[Tuple[str, str]] = [
        ("Program version", __version__),
        ("Build", "single-file executable" if getattr(sys, "frozen", False) else "run from source"),
        ("System", platform.platform()),
        ("Architecture", platform.machine() or "unknown"),
        ("Python", platform.python_version()),
    ]
    try:
        import PySide6
        from PySide6.QtCore import qVersion

        rows.append(("PySide6 / Qt", f"{PySide6.__version__} / {qVersion()}"))
    except Exception:  # noqa: BLE001
        rows.append(("PySide6 / Qt", "not available"))
    rows.append(("Interface language", language))
    if pixel_ratio is not None:
        rows.append(("Screen scale", f"{pixel_ratio:g}"))
    return rows


# ---------------------------------------------------------------- reading errors.log
def read_log_tail(path: Optional[str] = None, max_lines: int = 40, max_chars: int = 6000) -> str:
    """The last lines of errors.log, or "" if there is none."""
    path = path or error_log_path(create=False)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    text = "\n".join(lines[-max_lines:])
    return text[-max_chars:]


# ---------------------------------------------------------------- formatting helpers
def _seconds(value: float) -> str:
    return f"{value:.2f} s" if value < 60 else f"{int(value // 60)} min {value % 60:.0f} s"


def _size(n: int) -> str:
    size = float(n)
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} bytes" if unit == "bytes" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} bytes"


def _depth_text(key: str) -> str:
    en = STRINGS["en"]
    title = en.get(f"depth_{key}_title")
    return f"{title} (setting {key})" if title else f"setting {key}"


# ---------------------------------------------------------------- the report
def build_report(
    run: Optional[RunRecord],
    env: List[Tuple[str, str]],
    log_text: str,
    masker: Masker,
    now: Optional[datetime] = None,
    drive_type: Optional[Callable[[str], int]] = None,
) -> str:
    """The text of the diagnostic report (English, whatever the language of the program)."""
    now = now or datetime.now()
    if run is not None:
        masker.register_path(run.root)
        if run.save_base:
            masker.register_path(run.save_base)
            masker.register_path(os.path.dirname(run.save_base))
        if run.result is not None:
            for item in run.result.skipped:
                masker.register_path(item.path)
            for path, _sec in run.result.slowest:
                masker.register_path(path)

    lines: List[str] = []
    add = lines.append

    def section(title: str) -> None:
        add("")
        add(f"== {title} ==")

    add(REPORT_TITLE)
    add(f"Created: {now:%Y-%m-%d %H:%M:%S}")
    add("Folder names are replaced by codes: the same name always gets the same code in this report.")
    add("The program does not send this file anywhere: you decide whether to share it.")

    section("Program and system")
    for key, value in env:
        add(f"{key}: {value}")

    section("Last scan")
    if run is None:
        add("No scan has been done since the program was started.")
    else:
        add(f"Started: {run.started_at:%Y-%m-%d %H:%M:%S}")
        add(f"Status: {run.status}")
        add(f"Scanned path: {masker.path(run.root)}")
        add(f"Kind of path: {path_kind(run.root, drive_type)}")
        add(f"Depth: {_depth_text(run.depth_key)}")
        add(f"System and hidden folders: {'included' if run.include_hidden else 'excluded'}")
        add(f"Formats requested: {', '.join(f.upper() for f in run.formats) or 'none'}")
        result = run.result
        if result is not None:
            counts: Dict[str, int] = {}
            for item in result.skipped:
                counts[item.code] = counts.get(item.code, 0) + 1
            add(f"Folders found: {len(result.folders):,}")
            add(
                f"Folders skipped: {len(result.skipped):,} (access denied {counts.get('denied', 0)}, "
                f"not found {counts.get('notfound', 0)}, unexpected error {counts.get('error', 0)})"
            )
            add(f"Scan time, pauses excluded: {_seconds(result.duration)}")
            add(f"Time in pause: {_seconds(result.paused)}")
            add(f"Folders opened to read them: {result.dirs_read:,}")
            if result.duration >= 0.05:
                add(f"Speed: {len(result.folders) / result.duration:,.0f} folders found per second")
            if result.slowest:
                add("Slowest folders to read:")
                for i, (path, seconds) in enumerate(result.slowest, 1):
                    add(f"  {i}. {_seconds(seconds)}  {masker.path(path)}")
            unexpected = [item for item in result.skipped if item.code == "error"]
            if unexpected:
                add(f"Unexpected errors while reading folders (first {min(len(unexpected), 10)}):")
                for item in unexpected[:10]:
                    add(f"  {masker.path(item.path)}  {masker.text(item.detail)}")
        if run.status == "failed":
            add(f"Error: {masker.text(run.fail_message)}")
            if run.fail_trace:
                add("Details:")
                for line in masker.text(run.fail_trace).rstrip().splitlines():
                    add("  " + line)

        if run.status == "completed" or run.export_stats or run.errors:
            section("Export")
            failures = {fmt.lower(): msg for fmt, msg in run.errors}
            for fmt in run.formats:
                stat = run.export_stats.get(fmt)
                if fmt in failures:
                    add(f"{fmt.upper()}: FAILED - {masker.text(failures[fmt])}")
                elif stat:
                    add(f"{fmt.upper()}: {_seconds(float(stat.get('seconds', 0)))}, {_size(int(stat.get('bytes', 0)))}")
                else:
                    add(f"{fmt.upper()}: no data")
            try:
                from .exporters import pdf_font_info

                main_font, fallbacks = pdf_font_info()
            except Exception:  # noqa: BLE001
                main_font, fallbacks = None, []
            if main_font:
                add(f"PDF main font: {main_font}")
                add(f"PDF fallback fonts found: {', '.join(fallbacks) if fallbacks else 'none'}")

    section("errors.log (last lines)")
    cleaned = masker.text(log_text).strip()
    add(cleaned if cleaned else "(empty or missing: no unexpected error recorded)")
    add("")
    return "\n".join(lines)


def save_report(text: str, path: str) -> None:
    """Write the report as a text file that Notepad shows correctly (UTF-8 with BOM, Windows line ends)."""
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as fh:
        fh.write(text)
