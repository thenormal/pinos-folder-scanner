"""Scan engine: lists the subfolders of a drive or a folder.

This module does NOT depend on Qt: it can be tried and changed on its own.
Pause and cancel are supported through two threading.Event objects.
"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # junction
IO_REPARSE_TAG_SYMLINK = 0xA000000C

# System folders found in the root of a drive (they are skipped only there).
SYSTEM_ROOT_NAMES = {
    "$recycle.bin",
    "system volume information",
    "$winreagent",
    "$sysreset",
    "$windows.~bt",
    "$windows.~ws",
    "config.msi",
    "recovery",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "documents and settings",
}


@dataclass
class SkippedFolder:
    path: str
    code: str  # "denied" | "notfound" | "error"
    detail: str = ""


@dataclass
class ScanResult:
    root: str
    max_depth: Optional[int]  # None = no limit
    include_hidden: bool
    folders: List[str] = field(default_factory=list)
    skipped: List[SkippedFolder] = field(default_factory=list)
    duration: float = 0.0
    cancelled: bool = False
    paused: float = 0.0  # seconds spent in pause (not counted in `duration`)
    dirs_read: int = 0  # folders opened to read their content
    slowest: List[Tuple[str, float]] = field(default_factory=list)  # (folder, seconds), slowest first
    exclude: List[str] = field(default_factory=list)  # folder names the person asked to leave out
    excluded: int = 0  # folders left out because of their name (their content is not opened)


SLOWEST_KEEP = 5


def _remember_slowest(slowest: List[Tuple[str, float]], path: str, seconds: float) -> None:
    """Keep the SLOWEST_KEEP folders that took longest to read (used by the diagnostic report)."""
    if len(slowest) < SLOWEST_KEEP or seconds > slowest[-1][1]:
        slowest.append((path, seconds))
        slowest.sort(key=lambda item: item[1], reverse=True)
        del slowest[SLOWEST_KEEP:]


# ---------------------------------------------------------------- long paths
def to_long(path: str) -> str:
    """On Windows, add the \\\\?\\ prefix to very long paths (over ~260 characters)."""
    if os.name != "nt" or path.startswith("\\\\?\\") or len(path) < 240:
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def from_long(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def normalize_root(path: str) -> str:
    """Clean up the path chosen by the user (e.g. 'D:' becomes 'D:\\')."""
    path = path.strip().strip('"')
    if len(path) == 2 and path[1] == ":":
        path += "\\"
    path = os.path.normpath(path)
    if len(path) == 2 and path[1] == ":":
        path += "\\"
    return path


def is_drive_root(path: str) -> bool:
    return os.path.splitdrive(path)[1] in ("\\", "/")


# ---------------------------------------------------------------- filters
def _is_link_or_junction(entry: "os.DirEntry") -> bool:
    try:
        if entry.is_symlink():
            return True
        if os.name == "nt":
            st = entry.stat(follow_symlinks=False)
            attrs = getattr(st, "st_file_attributes", 0)
            if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                tag = getattr(st, "st_reparse_tag", 0)
                return tag in (IO_REPARSE_TAG_MOUNT_POINT, IO_REPARSE_TAG_SYMLINK)
    except OSError:
        return False
    return False


def _is_hidden_or_system(entry: "os.DirEntry", parent_is_root: bool) -> bool:
    name = entry.name
    if os.name == "nt":
        try:
            attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        except OSError:
            attrs = 0
        if attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM):
            return True
        if parent_is_root and (name.casefold() in SYSTEM_ROOT_NAMES or name.startswith("$")):
            return True
        return False
    return name.startswith(".")


def sort_key(path: str):
    """Alphabetical order that keeps subfolders right after their parent folder."""
    drive, rest = os.path.splitdrive(path)
    parts = [p for p in rest.replace("/", "\\").split("\\") if p]
    return (drive.casefold(), tuple(p.casefold() for p in parts), path)


# ---------------------------------------------------------------- exclusion by name
def parse_exclude(text: str) -> List[str]:
    """The folder names to leave out, from a text like "node_modules, .git; Backup*".

    Names are separated by a comma or a semicolon; empty ones are dropped and a name written twice
    (in any case) is kept once.
    """
    names: List[str] = []
    seen = set()
    for piece in re.split(r"[;,]", text or ""):
        name = piece.strip()
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            names.append(name)
    return names


def make_name_matcher(patterns: Sequence[str]) -> Optional[Callable[[str], bool]]:
    """A function that says if a folder name is one to leave out; None when there is nothing to leave out.

    The whole name must match, upper and lower case do not matter, and `*` (any characters) and
    `?` (one character) are the only wildcards: everything else, brackets included, is taken
    literally (folders like "[2024]" are common).
    """
    plain = set()
    wild = []
    for pattern in patterns:
        folded = pattern.strip().casefold()
        if not folded:
            continue
        if "*" in folded or "?" in folded:
            regex = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in folded)
            wild.append(re.compile(regex, re.DOTALL))
        else:
            plain.add(folded)
    if not plain and not wild:
        return None

    def matches(name: str) -> bool:
        folded = name.casefold()
        return folded in plain or any(rx.fullmatch(folded) for rx in wild)

    return matches


# ---------------------------------------------------------------- scanning
ProgressCb = Callable[[int, str, int], None]


def scan(
    root: str,
    max_depth: Optional[int],
    include_hidden: bool,
    on_progress: Optional[ProgressCb] = None,
    run_event: Optional[threading.Event] = None,
    cancel_event: Optional[threading.Event] = None,
    exclude: Optional[Sequence[str]] = None,
) -> ScanResult:
    """Scan `root` and return the sorted list of subfolders.

    max_depth: 0 = only the chosen folder, 1 = main folders only, 2 = down to the second
    level, ... None = all.
    run_event: if given, the scan proceeds only while it is "set" (cleared = paused).
    cancel_event: if "set", the scan stops.
    exclude: folder names to leave out (see make_name_matcher). A folder left out is not listed and
    is not opened, so nothing inside it is listed either. The folder chosen to start from is never left out.
    """
    root = normalize_root(root)
    result = ScanResult(root=root, max_depth=max_depth, include_hidden=include_hidden)
    matcher = make_name_matcher(exclude or []) if max_depth != 0 else None
    if matcher is not None:
        result.exclude = [name for name in (exclude or []) if name.strip()]
    started = time.monotonic()
    paused_total = 0.0
    last_emit = 0.0
    last_path = ""

    def emit(force: bool = False) -> None:
        nonlocal last_emit
        if on_progress is None:
            return
        now = time.monotonic()
        if force or now - last_emit >= 0.08:
            last_emit = now
            on_progress(len(result.folders), last_path, len(result.skipped))

    if max_depth == 0:
        if os.path.isdir(to_long(root)):
            result.folders.append(root)
            last_path = root
        else:
            result.skipped.append(SkippedFolder(root, "notfound"))
        result.duration = time.monotonic() - started
        emit(force=True)
        return result

    stack = [(root, 0)]
    while stack:
        if cancel_event is not None and cancel_event.is_set():
            result.cancelled = True
            break
        if run_event is not None and not run_event.is_set():
            pause_started = time.monotonic()
            while not run_event.is_set():
                if cancel_event is not None and cancel_event.is_set():
                    break
                run_event.wait(0.1)
            paused_total += time.monotonic() - pause_started
            if cancel_event is not None and cancel_event.is_set():
                result.cancelled = True
                break

        path, depth = stack.pop()
        parent_is_root = is_drive_root(path)
        read_started = time.perf_counter()
        try:
            with os.scandir(to_long(path)) as it:
                for entry in it:
                    try:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    if _is_link_or_junction(entry):
                        continue
                    if not include_hidden and _is_hidden_or_system(entry, parent_is_root):
                        continue
                    if matcher is not None and matcher(entry.name):
                        result.excluded += 1
                        continue
                    full = from_long(entry.path)
                    result.folders.append(full)
                    last_path = full
                    if max_depth is None or depth + 1 < max_depth:
                        stack.append((full, depth + 1))
                    emit()
        except PermissionError:
            result.skipped.append(SkippedFolder(path, "denied"))
        except FileNotFoundError:
            result.skipped.append(SkippedFolder(path, "notfound"))
        except OSError as exc:
            result.skipped.append(SkippedFolder(path, "error", str(exc)))
        result.dirs_read += 1
        _remember_slowest(result.slowest, path, time.perf_counter() - read_started)
        emit()

    result.folders.sort(key=sort_key)
    result.skipped.sort(key=lambda s: sort_key(s.path))
    result.paused = paused_total
    result.duration = time.monotonic() - started - paused_total
    emit(force=True)
    return result
