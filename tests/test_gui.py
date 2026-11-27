"""Headless test of the window (no screen needed): start, pause, resume, cancel, scan finished.

Run with:  python tests/test_gui.py
Message boxes are replaced by test functions, and the settings are temporary.
"""
import os
import sys
import tempfile
import time
from datetime import datetime

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
from app.i18n import LANGUAGES, STRINGS  # noqa: E402
from app.settings import Settings  # noqa: E402
import app.window as window_mod  # noqa: E402
from app.links import ISSUES_URL, KOFI_URL, README_URL, REPO_URL  # noqa: E402
from app.diagnostics import RunRecord  # noqa: E402
from app.scanner import ScanResult, SkippedFolder  # noqa: E402
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
    settings.set_exclude_text("")  # nothing left out unless a test asks for it, whatever an earlier run saved
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

    # --- folders left out by name: the field, the scan, the final message, the report, the settings
    assert win.exclude_field.edit.text() == "" and win.exclude_field.edit.placeholderText().startswith("For example")
    win.exclude_field.edit.setText("B, nothing*")  # not case sensitive: every folder called "b" is left out
    messages.clear()
    base_x = os.path.join(out, "excluded")
    win._ask_base = lambda formats, root: base_x
    win._on_start()
    assert wait_for(lambda: win.state == "done"), win.state
    assert win._count == 40, win._count  # the 40 "aNN" folders; the "b" folders and what is in them are left out
    res = win.last_run.result
    assert res.exclude == ["B", "nothing*"] and res.excluded == 40
    assert "40 folders left out by name" in messages[-1][1], messages[-1][1]
    report = win.diagnostic_report_text()
    assert "Exclusion by name: 2 name(s), 40 folders left out" in report
    assert "nothing" not in report and "B, " not in report, "the names typed by the person are not in the report"
    win._save_settings()
    assert win.settings.exclude_text() == "B, nothing*"
    win.set_language("it")
    assert win.cap_exclude.text().upper() == STRINGS["it"]["exclude_title"].upper()
    assert win.exclude_field.edit.placeholderText() == STRINGS["it"]["exclude_placeholder"]
    win.set_language("en")
    win.exclude_field.edit.setText("")
    messages.clear()
    win._ask_base = lambda formats, root: os.path.join(out, "not_excluded")
    win._on_start()
    assert wait_for(lambda: win.state == "done") and win._count == 40 * 3
    assert "left out" not in messages[-1][1], "no exclusion: no line about it"
    win._save_settings()
    assert win.settings.exclude_text() == ""
    win._set_state("cancelled")  # back to the state the following checks expect
    print("exclusion by name in the window OK")

    # --- checks on the input
    messages.clear()
    win.path_field.edit.setText("")
    win._on_start()
    assert messages and messages[-1][0] == "Warning"
    win.path_field.edit.setText(os.path.join(tmp, "does_not_exist"))
    win._on_start()
    assert len(messages) == 2
    win.path_field.edit.setText(tree)
    print("checks on the path OK")

    # --- scan only (no format ticked): no "Save as", no file; then "Copy list" puts the folders on the clipboard
    for chip in win.chips.values():
        chip.setChecked(False)
    asked = []
    win._ask_base = lambda formats, root: asked.append(formats) or ""
    messages.clear()
    win._on_start()
    assert win.state == "scanning" and win.btn_pause.isVisible() and not win.btn_copy.isVisible()
    assert wait_for(lambda: win.state == "done"), win.state
    assert not asked, "no format: the Save as window is not shown"
    win._save_settings()
    assert win.settings.formats(list(win.chips)) == [], "nothing ticked is remembered as nothing ticked"
    win.settings._q.setValue("formats", "garbage")
    assert win.settings.formats(list(win.chips)) == ["pdf"], "unreadable saved text: back to the default"
    win._save_settings()
    assert messages[-1][0] == "Scan complete" and "No file was created" in messages[-1][1] and "Copy list" in messages[-1][1]
    assert win._count == 40 * 3
    assert win.btn_copy.isVisible() and win.btn_copy.isEnabled() and win.btn_copy.text() == "Copy list"
    assert not win.btn_pause.isVisible() and not win.btn_cancel.isVisible(), "Copy list replaces Pause and Cancel"

    class FakeClipboard:
        def __init__(self, works=True):
            self.value, self.works = "", works

        def setText(self, text):  # noqa: N802
            if self.works:
                self.value = text

        def text(self):
            return self.value

    clip = FakeClipboard()
    win._clipboard = lambda: clip
    win.btn_copy.click()
    expected = "\n".join(win.last_run.result.folders)
    assert clip.value == expected and len(clip.value.splitlines()) == 120
    assert clip.value.splitlines() == sorted(clip.value.splitlines(), key=lambda p: [x.casefold() for x in p.split(os.sep)])
    assert not clip.value.endswith("\n") and "\r" not in clip.value
    assert win.btn_copy.text() == "Copied (120 folders)" and win.last_run.clipboard_lines == 120
    win._reset_copy_button()
    assert win.btn_copy.text() == "Copy list"
    report = win.diagnostic_report_text()
    assert "Clipboard: 120 folders copied (paths only)" in report and "Formats requested: none (scan only)" in report
    broken = FakeClipboard(works=False)  # another program holds the clipboard: the person is told
    win._clipboard = lambda: broken
    before = len(messages)
    win.btn_copy.click()
    assert len(messages) == before + 1 and messages[-1][2] == "error" and "could not be copied" in messages[-1][1]
    win._clipboard = lambda: clip
    win.set_language("it")
    assert win.btn_copy.text() == "Copia elenco"
    win.btn_copy.click()
    assert win.btn_copy.text() == "Copiato (120 cartelle)"
    win.set_language("en")
    # a new scan brings Pause and Cancel back; a cancelled scan has nothing to copy
    win.chips["csv"].setChecked(True)
    base_c = os.path.join(out, "after_copy")
    win._ask_base = lambda formats, root: base_c
    win._on_start()
    assert win.btn_pause.isVisible() and not win.btn_copy.isVisible()
    assert wait_for(lambda: win.state == "done") and os.path.exists(base_c + ".csv")
    assert win.btn_copy.isVisible() and "Files created in" in messages[-1][1]
    win.last_run.result.folders = []
    win._set_state("done")
    assert win.btn_copy.isVisible() and not win.btn_copy.isEnabled(), "an empty list: nothing to copy"
    win.btn_copy.click()
    assert clip.value != "", "an empty list does not overwrite the clipboard"
    win.chips["csv"].setChecked(False)
    win._set_state("cancelled")
    assert not win.btn_copy.isVisible() and win.btn_pause.isVisible()
    print("scan only and Copy list OK")

    assert win.btn_start.text() == "Start scan" and win.cap_depth.text() == "SCAN DEPTH"
    print("texts OK")

    # --- Italian: switch the window and back, the texts and the saved choice follow
    assert LANGUAGES == ["en", "it", "de", "es", "fr", "nl", "pt", "zh"]
    win.set_language("it")
    assert win.btn_start.text() == STRINGS["it"]["btn_start"] == "Avvia scansione"
    assert win.titlebar.support.toolTip() == STRINGS["it"]["support_tip"]
    assert win.settings.language() == "it"
    # the folder count uses the separator of the language
    win._count = 12847
    for lang, expected in (("en", "12,847"), ("it", "12.847"), ("fr", "12\u00a0847"), ("zh", "12,847")):
        win.set_language(lang)
        assert win._num(win._count) == expected, lang
    win.set_language("en")
    assert win.btn_start.text() == "Start scan" and win.settings.language() == "en"

    # a real click on the language menu: the press must be accepted, otherwise the title bar takes
    # it (to move the window) and the release never reaches the menu
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QMouseEvent

    menu_btn = win.titlebar.lang
    assert menu_btn.width() < 100 and menu_btn.current() == "en"

    def mouse(kind, x=None):
        pos = QPointF(menu_btn.width() / 2 if x is None else x, menu_btn.height() / 2)
        return QMouseEvent(
            kind, pos, menu_btn.mapToGlobal(pos), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
        )

    press = mouse(QEvent.Type.MouseButtonPress)
    press.ignore()
    menu_btn.mousePressEvent(press)
    assert press.isAccepted(), "the language menu must accept the mouse press"

    listed = []
    pick = {"lang": "it"}

    def fake_run(menu):  # replaces menu.exec: records the entries and "clicks" one
        entries = [(a.data(), a.text(), a.isChecked()) for a in menu.actions()]
        listed.append(entries)
        return next(a for a in menu.actions() if a.data() == pick["lang"])

    menu_btn._run_menu = fake_run
    menu_btn.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease))  # a click on the pill opens the menu
    assert [e[0] for e in listed[0]] == LANGUAGES
    assert [e[1] for e in listed[0]] == ["English", "Italiano", "Deutsch", "Español", "Français", "Nederlands", "Português", "中文 (简体)"]
    assert [e[0] for e in listed[0] if e[2]] == ["en"], "the current language is ticked"
    assert win.lang == "it" and win.btn_start.text() == "Avvia scansione" and menu_btn.current() == "it"
    pick["lang"] = "en"
    menu_btn.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease))
    assert win.lang == "en" and win.btn_start.text() == "Start scan"
    n = len(listed)
    menu_btn.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, -5))  # released outside: nothing
    assert len(listed) == n
    pick["lang"] = "en"
    menu_btn.open_menu()  # choosing the language already in use changes nothing
    assert win.lang == "en"

    # every language: the window and the final message work, texts change, the language is remembered
    for lang in LANGUAGES:
        win.set_language(lang)
        assert win.btn_start.text() == STRINGS[lang]["btn_start"] and win.settings.language() == lang
        assert win.titlebar.info.toolTip() == STRINGS[lang]["info_tip"]
    from app.i18n import UNVERIFIED_LANGUAGES

    shown_text = []
    GlassDialog.info_window = staticmethod(lambda parent, title, text, *a: shown_text.append(text))
    for lang in LANGUAGES:
        win.set_language(lang)
        win._open_info()
        has_note = STRINGS[lang]["info_unverified"] in shown_text[-1]
        assert has_note == (lang in UNVERIFIED_LANGUAGES), lang
    assert UNVERIFIED_LANGUAGES == {"de", "es", "fr", "nl", "pt", "zh"}
    win.set_language("en")
    print("Italian OK")

    # --- Ko-fi heart: the click opens the page, the tooltip is translated
    opened = []
    window_mod.open_support_page = lambda: opened.append(KOFI_URL) or True
    assert KOFI_URL == "https://ko-fi.com/thenormal"
    assert win.titlebar.support.toolTip() == "Support on Ko-fi"
    win.titlebar.support.click()
    assert opened == [KOFI_URL]
    print("Ko-fi button OK")

    # --- "i" button: info window, links, saving the report, report a problem
    from PySide6.QtWidgets import QFileDialog

    opened_urls = []
    window_mod.open_url = lambda url: opened_urls.append(url) or True
    shown = {}

    def fake_info_window(parent, title, text, links, actions, close_text):
        shown.update(title=title, text=text, links=dict(links), actions=dict(actions), close=close_text)

    GlassDialog.info_window = staticmethod(fake_info_window)
    assert win.titlebar.info.toolTip() == "About and diagnostics"
    win.titlebar.info.click()
    assert shown["title"] == "Pino's Folder Scanner" and shown["text"].startswith("Version ")
    assert "never sends anything" in shown["text"] and shown["close"] == "Close"
    assert list(shown["links"]) == ["GitHub", "Issues", "Ko-fi", "README"]
    for name, url in (("GitHub", REPO_URL), ("Issues", ISSUES_URL), ("Ko-fi", KOFI_URL), ("README", README_URL)):
        shown["links"][name]()
        assert opened_urls[-1] == url
    shown["actions"]["Report a problem"]()
    assert "/issues/new?template=bug_report.yml" in opened_urls[-1] and "version=" in opened_urls[-1]
    assert "windows=" in opened_urls[-1]
    report_path = os.path.join(tmp, "info_report.txt")
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (report_path, ""))
    before = len(messages)
    shown["actions"]["Save diagnostic report"]()
    assert os.path.isfile(report_path) and open(report_path, encoding="utf-8-sig").read().startswith("Pino")
    assert messages[before][0] == "Report saved" and report_path in messages[before][1]
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
    os.remove(report_path)
    shown["actions"]["Save diagnostic report"]()  # cancelled: nothing is written
    assert not os.path.exists(report_path)
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (os.path.join(tmp, "no_such_folder", "r.txt"), ""))
    before = len(messages)
    shown["actions"]["Save diagnostic report"]()  # cannot be written: an error message, no crash
    assert messages[before][2] == "error" and "could not be saved" in messages[before][1]
    print("info window OK")

    # --- the offer at the end of a scan: only when something really went wrong
    offers = []
    answers = []

    def fake_choose(parent, title, text, buttons, tone="info"):
        offers.append((title, text, [b[0] for b in buttons], tone))
        return answers.pop(0) if answers else 1

    GlassDialog.choose = staticmethod(fake_choose)
    win.last_run = RunRecord(datetime.now(), tree, "all", False, ["txt"])
    normal = ScanResult(tree, 99, False)
    normal.skipped = [SkippedFolder("X:\\a", "denied"), SkippedFolder("X:\\b", "notfound")]
    before = len(messages)
    win._on_finished(normal, [os.path.join(out, "ok.txt")], [])
    assert not offers and len(messages) == before + 1 and "diagnostic" not in messages[-1][1]
    bad = ScanResult(tree, 99, False)
    bad.skipped = [SkippedFolder("X:\\c", "error", "disk error")]
    win.last_run = RunRecord(datetime.now(), tree, "all", False, ["txt"])
    answers[:] = [3, 2, 1]  # Report a problem, Save the report, OK
    saved_to = os.path.join(tmp, "offer_report.txt")
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (saved_to, ""))
    n_urls = len(opened_urls)
    win._on_finished(bad, [os.path.join(out, "ok.txt")], [])
    assert len(offers) == 3 and offers[0][2] == ["Report a problem", "Save diagnostic report", "OK"]
    assert "Something did not work as expected" in offers[0][1] and offers[0][3] == "warn"
    assert len(opened_urls) == n_urls + 1 and os.path.isfile(saved_to)
    offers.clear()
    win.last_run = RunRecord(datetime.now(), tree, "all", False, ["pdf"])
    win._on_finished(normal, [], [("pdf", "no space left")])  # a format could not be created
    assert len(offers) == 1 and "no space left" in offers[0][1]
    offers.clear()
    win.last_run = RunRecord(datetime.now(), tree, "all", False, ["pdf"])
    win._on_failed("boom")
    assert len(offers) == 1 and offers[0][3] == "error" and "boom" in offers[0][1]
    GlassDialog.choose = staticmethod(lambda *a, **k: 1)
    win.last_run = None
    print("offer at the end of a scan OK")

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
