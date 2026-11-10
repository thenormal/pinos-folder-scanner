"""Create assets/icon.ico (the .exe icon) by drawing it with the program's own code.

Usage:  python tools/make_icon.py
build_exe.bat runs it automatically if the file is missing.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.icon import write_ico  # noqa: E402

if __name__ == "__main__":
    _app = QGuiApplication(sys.argv)
    target = os.path.join(ROOT, "assets", "icon.ico")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    write_ico(target)
    print("Creato", os.path.normpath(target))
