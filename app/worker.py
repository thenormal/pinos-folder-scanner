"""Worker thread: runs the scan and then creates the files, without freezing the window."""
from __future__ import annotations

import threading
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from .exporters import ExportContext, export_all
from .scanner import scan


class ScanWorker(QThread):
    progress = Signal(int, str, int)  # folders found, last folder, folders skipped
    exporting = Signal()
    finished_ok = Signal(object, list, list)  # ScanResult, files created, errors [(format, message)]
    failed = Signal(str)

    def __init__(
        self,
        root: str,
        max_depth: Optional[int],
        include_hidden: bool,
        formats: List[str],
        base: str,
        lang: str,
        depth_label: str,
        parent=None,
    ):
        super().__init__(parent)
        self.root = root
        self.max_depth = max_depth
        self.include_hidden = include_hidden
        self.formats = formats
        self.base = base
        self.lang = lang
        self.depth_label = depth_label
        self._run_event = threading.Event()  # "set" = running, "clear" = paused
        self._run_event.set()
        self._cancel_event = threading.Event()

    # commands from the window
    def pause(self) -> None:
        self._run_event.clear()

    def resume(self) -> None:
        self._run_event.set()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._run_event.set()  # wake up a pause, if any

    def run(self) -> None:  # noqa: D401 - metodo di QThread
        started_at = datetime.now()
        try:
            result = scan(
                self.root,
                self.max_depth,
                self.include_hidden,
                on_progress=lambda count, path, skipped: self.progress.emit(count, path, skipped),
                run_event=self._run_event,
                cancel_event=self._cancel_event,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        if result.cancelled:
            self.finished_ok.emit(result, [], [])
            return
        self.exporting.emit()
        ctx = ExportContext(result, self.lang, started_at, self.depth_label)
        files, errors = export_all(ctx, self.formats, self.base)
        self.finished_ok.emit(result, files, errors)
