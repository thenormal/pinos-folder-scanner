"""Pino's Folder Scanner - program entry point."""
from __future__ import annotations

import os
import sys
import traceback


def _log_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "PinosFolderScanner")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        folder = os.path.expanduser("~")
    return os.path.join(folder, "errors.log")


def _install_error_hook() -> None:
    """If something goes wrong, write the details to a text file and tell the user."""

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(_log_path(), "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "Pino's Folder Scanner",
                    f"An unexpected error occurred.\nDetails were saved to:\n{_log_path()}\n\n{exc}",
                )
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = hook


def main() -> int:
    _install_error_hook()
    if os.name == "nt":
        try:  # group the icon correctly in the taskbar
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("thenormal.PinosFolderScanner.1")
        except Exception:  # noqa: BLE001
            pass

    from PySide6.QtWidgets import QApplication

    from app.icon import app_icon
    from app.settings import Settings
    from app.window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Pino's Folder Scanner")
    app.setOrganizationName("thenormal")
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())

    window = MainWindow(Settings())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
