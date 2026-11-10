"""Headless test of the window (no screen needed): start, pause, resume, cancel, scan finished.

Run with:  python tests/test_gui.py
Message boxes are replaced by test functions, and the settings are temporary.
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# temporary settings, so the real ones (registry on Windows) are never touched
_cfg = tempfile.mkdtemp(prefix="fs_cfg_")
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, _cfg)

import app.scanner as scanner_mod  # noqa: E402
from app.dialogs import GlassDialog  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.window import MainWindow  # noqa: E402

qt = QApplication(sys.argv)
messages = []
GlassDialog.message = staticmethod(lambda parent, title, text, ok, tone="info": messages.append((title, text, tone)))
GlassDialog.ask = staticmethod(lambda *a, **k: True)

_real_scandir = os.scandir


def slow_scandir(path):
    time.sleep(0.01)  # slow the scan down so there is time to press Pause/Cancel
    return _real_scandir(path)


scanner_mod.os.scandir = slow_scandir


def wait_for(predicate, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        qt.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def main():
    tmp = tempfile.mkdtemp(prefix="fs_gui_")
    tree = os.path.join(tmp, "tree")
    for i in range(40):
        os.makedirs(os.path.join(tree, f"a{i:02d}", "b", "c"))
    out = os.path.join(tmp, "output")
    os.makedirs(out)

    win = MainWindow(Settings())
    win.show()
    qt.processEvents()
    assert not win.titlebar.lang.isVisible(), "no language switch while there is only one language"
    win.path_field.edit.setText(tree)
    win.depth.set_current("all")
    for fmt, chip in win.chips.items():
        chip.setChecked(fmt in ("pdf", "csv"))

    # --- full scan
    base1 = os.path.join(out, "one")
    win._ask_base = lambda formats, root: base1
    win._on_start()
    assert win.state == "scanning"
    assert wait_for(lambda: win.state == "done"), f"final state: {win.state}"
    assert os.path.exists(base1 + ".pdf") and os.path.exists(base1 + ".csv")
    assert messages and messages[-1][0] == "Scan complete" and messages[-1][2] == "success", messages[-1]
    assert win._count == 40 * 3, win._count
    print("start -> scan -> files created -> final message OK")

    # --- pause and resume
    messages.clear()
    base2 = os.path.join(out, "two")
    win._ask_base = lambda formats, root: base2
    win._on_start()
    assert wait_for(lambda: win._count > 5)
    win._on_pause()
    assert win.state == "paused"
    qt.processEvents()
    time.sleep(0.3)
    qt.processEvents()
    frozen = win._count
    time.sleep(0.5)
    qt.processEvents()
    assert win._count - frozen <= 3, "while paused the counter must stop"
    t_paused = win._elapsed()
    time.sleep(0.4)
    assert abs(win._elapsed() - t_paused) < 0.05, "while paused the timer must not advance"
    assert win.btn_pause.text() == "Resume"
    win._on_pause()
    assert win.state == "scanning"
    assert wait_for(lambda: win.state == "done")
    assert os.path.exists(base2 + ".pdf")
    print("pause / resume OK (counter and timer stand still while paused)")

    # --- cancel
    messages.clear()
    base3 = os.path.join(out, "three")
    win._ask_base = lambda formats, root: base3
    win._on_start()
    assert wait_for(lambda: win._count > 5)
    win._on_cancel()
    assert wait_for(lambda: win.state == "cancelled")
    assert not os.path.exists(base3 + ".pdf") and not os.path.exists(base3 + ".csv")
    assert messages and messages[-1][0] == "Scan cancelled"
    print("cancel OK (no file created)")

    # --- cancel while paused
    messages.clear()
    win._on_start()
    assert wait_for(lambda: win._count > 5)
    win._on_pause()
    win._on_cancel()
    assert wait_for(lambda: win.state == "cancelled")
    print("cancel from pause OK")

    # --- checks on the input
    messages.clear()
    win.path_field.edit.setText("")
    win._on_start()
    assert messages and messages[-1][0] == "Warning"
    win.path_field.edit.setText(os.path.join(tmp, "does_not_exist"))
    win._on_start()
    assert len(messages) == 2
    win.path_field.edit.setText(tree)
    for chip in win.chips.values():
        chip.setChecked(False)
    win._on_start()
    assert len(messages) == 3 and win.state == "cancelled"
    print("checks on path and formats OK")

    assert win.btn_start.text() == "Start scan" and win.cap_depth.text() == "SCAN DEPTH"
    print("texts OK")

    # --- closing during a scan
    win.chips["pdf"].setChecked(True)
    base4 = os.path.join(out, "four")
    win._ask_base = lambda formats, root: base4
    win._on_start()
    assert wait_for(lambda: win._count > 5)
    win.close()
    qt.processEvents()
    assert win.worker is None or not win.worker.isRunning()
    print("closing during a scan OK")
    print("ALL WINDOW TESTS PASSED")


if __name__ == "__main__":
    main()
