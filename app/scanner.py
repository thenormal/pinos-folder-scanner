"""Scan engine: lists the subfolders of a drive or a folder.

This module does NOT depend on Qt: it can be tried and changed on its own.
Pause and cancel are supported through two threading.Event objects.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

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


# ---------------------------------------------------------------- scanning
ProgressCb = Callable[[int, str, int], None]


def scan(
    root: str,
    max_depth: Optional[int],
    include_hidden: bool,
    on_progress: Optional[ProgressCb] = None,
    run_event: Optional[threading.Event] = None,
    cancel_event: Optional[threading.Event] = None,
) -> ScanResult:
    """Scan `root` and return the sorted list of subfolders.

    max_depth: 0 = only the chosen folder, 1 = main folders only, 2 = down to the second
    level, ... None = all.
    run_event: if given, the scan proceeds only while it is "set" (cleared = paused).
    cancel_event: if "set", the scan stops.
    """
    root = normalize_root(root)
    result = ScanResult(root=root, max_depth=max_depth, include_hidden=include_hidden)
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
        emit()

    result.folders.sort(key=sort_key)
    result.skipped.sort(key=lambda s: sort_key(s.path))
    result.duration = time.monotonic() - started - paused_total
    emit(force=True)
    return result
