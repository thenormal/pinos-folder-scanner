"""Development tool: saves images of the window in its various states (without showing it on screen).

Usage:  python tools/render_states.py [output_folder]
Used to check the look after a visual change and to refresh the screenshots in docs/.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# temporary settings, separate from the real ones
_cfg = tempfile.mkdtemp(prefix="fs_cfg_")
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, _cfg)

from app.settings import Settings  # noqa: E402
from app.window import MainWindow  # noqa: E402


def pump(app: QApplication, n: int = 6) -> None:
    for _ in range(n):
        app.processEvents()


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(tempfile.gettempdir(), "fs_render")
    os.makedirs(out, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    settings = Settings()
    settings.set_formats(["pdf", "xlsx"])
    win = MainWindow(settings)
    win.path_field.edit.setText(r"D:\Photos")
    win.resize(1100, 720)
    win.show()
    pump(app)

    def shot(name: str) -> None:
        pump(app)
        win._t = 3.0  # fixed position of the glows, for repeatable images
        win.update()
        pump(app)
        path = os.path.join(out, name + ".png")
        win.grab().save(path)
        print("saved", path)

    shot("1_ready")

    win._count, win._skipped = 12847, 14
    win._scan_started = time.monotonic() - 102
    win._set_state("scanning")
    win.ticker.set_text(r"D:\Photos\2024\Summer\August\RAW")
    win.ring.set_count("12,847")
    shot("2_scanning")

    win._pause_started = time.monotonic()
    win._set_state("paused")
    shot("3_paused")

    win._last_duration = 102
    win._set_state("exporting")
    shot("4_creating_files")

    win._set_state("done")
    shot("5_finished")

    win._set_state("cancelled")
    shot("6_cancelled")

    win._pause_started = None
    win._set_state("idle")
    win.resize(1000, 680)
    shot("7_small_window")


if __name__ == "__main__":
    main()
