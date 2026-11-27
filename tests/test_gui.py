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

from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# temporary settings, so the real ones (registry on Windows) are never touched
_cfg = tempfile.mkdtemp(prefix="fs_cfg_")
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, _cfg)
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fs_log_")  # the diagnostic report reads errors.log from here

import app.scanner as scanner_mod  # noqa: E402
from app.dialogs import GlassDialog  # noqa: E402
from app.settings import Settings  # noqa: E402
import app.window as window_mod  # noqa: E402
from app.links import KOFI_URL  # noqa: E402
from app.window import MainWindow, dropped_folder  # noqa: E402

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

    settings = Settings()
    settings.set_language("en")  # the texts below are English, whatever the language of the system
    win = MainWindow(settings)
    win.show()
    qt.processEvents()
    assert win.titlebar.lang.isVisible(), "two languages: the language switch is shown"
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

    # --- diagnostic report of that scan: complete, and without any real folder name
    assert win.last_run is not None and win.last_run.status == "completed"
    report = win.diagnostic_report_text()
    assert "Status: completed" in report and "Folders found: " in report and "PDF: " in report and "CSV: " in report
    assert "Interface language: en" in report and "Program version: " in report
    assert os.path.basename(tmp) not in report and "tree" not in report.split("Scanned path:")[1].split("\n")[0]
    saved = os.path.join(tmp, "diag.txt")
    win.save_diagnostic_report(saved)
    assert os.path.getsize(saved) > 500
    print("diagnostic report of a finished scan OK")

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
    assert win.last_run.status == "cancelled" and "Status: cancelled" in win.diagnostic_report_text()

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

    # --- Italian: switch the window and back, the texts and the saved choice follow
    from app.i18n import LANGUAGES, STRINGS
    assert LANGUAGES == ["en", "it"]
    win.set_language("it")
    assert win.btn_start.text() == STRINGS["it"]["btn_start"] == "Avvia scansione"
    assert win.titlebar.support.toolTip() == STRINGS["it"]["support_tip"]
    assert win.settings.language() == "it"
    win.set_language("en")
    assert win.btn_start.text() == "Start scan" and win.settings.language() == "en"

    # a real click on the switch: the press must be accepted, otherwise the title bar takes it
    # (to move the window) and the release never reaches the switch
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QMouseEvent

    sw = win.titlebar.lang

    def mouse(kind, x):
        pos = QPointF(x, sw.height() / 2)
        ev = QMouseEvent(kind, pos, sw.mapToGlobal(pos), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        return ev

    right = sw.width() * 0.75  # the IT half
    press = mouse(QEvent.Type.MouseButtonPress, right)
    press.ignore()
    sw.mousePressEvent(press)
    assert press.isAccepted(), "the language switch must accept the mouse press"
    sw.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, right))
    assert win.lang == "it" and win.btn_start.text() == "Avvia scansione"
    left = sw.width() * 0.25
    sw.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, left))
    assert win.lang == "en" and win.btn_start.text() == "Start scan"
    print("Italian OK")

    # --- Ko-fi heart: the click opens the page, the tooltip is translated
    opened = []
    window_mod.open_support_page = lambda: opened.append(KOFI_URL) or True
    assert KOFI_URL == "https://ko-fi.com/thenormal"
    assert win.titlebar.support.toolTip() == "Support on Ko-fi"
    win.titlebar.support.click()
    assert opened == [KOFI_URL]
    print("Ko-fi button OK")

    # --- drag and drop of a folder, a drive or a file onto the window
    def make_mime(*paths):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        return mime

    def drop(*paths):
        mime = make_mime(*paths)  # the event does not own it: keep it alive
        event = QDropEvent(
            QPointF(50, 50), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
        )
        event.setDropAction(Qt.DropAction.CopyAction)
        win.dropEvent(event)
        return event.isAccepted()

    a00 = os.path.join(tree, "a00")
    some_file = os.path.join(out, "some.txt")
    open(some_file, "w").close()
    assert dropped_folder(make_mime(a00)) == os.path.normpath(a00)
    assert dropped_folder(make_mime(some_file)) == os.path.normpath(out)
    assert dropped_folder(QMimeData()) is None
    web = QMimeData()
    web.setUrls([QUrl("https://example.com")])
    assert dropped_folder(web) is None
    assert dropped_folder(make_mime(os.path.join(tmp, "does_not_exist"))) is None
    win.path_field.edit.setText("")
    assert drop(a00) and win.path_field.edit.text() == os.path.normpath(a00)
    assert drop(some_file) and win.path_field.edit.text() == os.path.normpath(out)
    assert not drop(os.path.join(tmp, "does_not_exist")) and win.path_field.edit.text() == os.path.normpath(out)
    win.state = "scanning"  # while a scan is running a drop is refused
    assert not drop(a00) and win.path_field.edit.text() == os.path.normpath(out)
    win.state = "cancelled"
    win.path_field.edit.setText(tree)  # back to the folder used by the following checks
    print("drag and drop OK")

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
