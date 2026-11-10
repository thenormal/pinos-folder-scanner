"""Automated tests for the engine (scanning + exports). Run with:  python tests/test_core.py"""
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.exporters import FORMATS, ExportContext, export_all  # noqa: E402
from app.scanner import scan  # noqa: E402

DEPTH_LABEL = "All subfolders (No depth limit)"


def make_hidden(path):
    """On Windows hidden means 'has the hidden attribute'; elsewhere the name starts with a dot."""
    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetFileAttributesW(path, 0x2)


def make_tree(base):
    names = [
        "Photos/2024/Summer/August/RAW",
        "Photos/2024/Winter",
        "Photos/2023",
        "Documents/Work/Café & More",
        "Music/Zeta",
        "Music/alpha",
        "Empty",
    ]
    if os.name != "nt":  # these characters are not allowed in Windows folder names
        names.append("Documents/Taxes <2024>")
    for n in names:
        os.makedirs(os.path.join(base, *n.split("/")), exist_ok=True)
    hidden = os.path.join(base, ".hidden")
    os.makedirs(os.path.join(hidden, "secret"))
    make_hidden(hidden)
    open(os.path.join(base, "file.txt"), "w").close()


def rel(result):
    return [os.path.relpath(p, result.root) for p in result.folders]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "root")
        os.makedirs(root)
        make_tree(root)

        r1 = scan(root, 1, False)
        assert rel(r1) == ["Documents", "Empty", "Music", "Photos"], rel(r1)
        r2 = scan(root, 2, False)
        assert os.path.join("Photos", "2024") in rel(r2)
        assert not any("Summer" in p for p in rel(r2))
        r3 = scan(root, 3, False)
        assert any(p.endswith("Summer") for p in rel(r3)) and not any(p.endswith("August") for p in rel(r3))
        rall = scan(root, None, False)
        assert any(p.endswith("RAW") for p in rel(rall))
        assert not any(".hidden" in p for p in rel(rall)), "hidden folder must be excluded"
        rhid = scan(root, None, True)
        assert any(".hidden" in p for p in rel(rhid)), "hidden folder must be included"
        # alphabetical order: children right after their parent, case ignored
        order = rel(rall)
        assert order.index(os.path.join("Music", "alpha")) < order.index(os.path.join("Music", "Zeta"))
        assert order.index("Photos") < order.index(os.path.join("Photos", "2023")) < order.index(os.path.join("Photos", "2024"))
        print("scanning: depth, filters and order OK  (folders:", len(rall.folders), ")")

        # missing folder -> skipped and recorded
        rbad = scan(os.path.join(tmp, "does_not_exist"), None, False)
        assert rbad.skipped and rbad.skipped[0].code == "notfound"

        # symbolic links (even circular ones) are not followed
        if hasattr(os, "symlink"):
            loop = os.path.join(tmp, "with_links")
            os.makedirs(os.path.join(loop, "real", "inner"))
            try:
                os.symlink(loop, os.path.join(loop, "real", "cycle"), target_is_directory=True)
                os.symlink(os.path.join(loop, "real"), os.path.join(loop, "alias"), target_is_directory=True)
                rl = scan(loop, None, False)
                assert sorted(os.path.relpath(p, loop) for p in rl.folders) == ["real", os.path.join("real", "inner")], rl.folders
                print("symbolic links are not followed OK")
            except OSError:
                print("(symbolic links not tested: not allowed here)")

        # folder without permission -> skipped, recorded, and the scan goes on
        import app.scanner as scanner_mod

        real_scandir = scanner_mod.os.scandir
        blocked = os.path.join(root, "Documents", "Work")

        def fake_scandir(p):
            if os.path.normpath(p) == os.path.normpath(blocked):
                raise PermissionError(13, "Access denied")
            return real_scandir(p)

        scanner_mod.os.scandir = fake_scandir
        try:
            rden = scan(root, None, False)
        finally:
            scanner_mod.os.scandir = real_scandir
        assert [(s.path, s.code) for s in rden.skipped] == [(blocked, "denied")], rden.skipped
        assert blocked in rden.folders and not any("Café" in p for p in rden.folders)
        print("folder without permission: skipped, recorded, scan continues OK")

        # pause and cancel
        big = os.path.join(tmp, "big")
        for i in range(60):
            os.makedirs(os.path.join(big, f"a{i}", "b", "c"))
        run, cancel = threading.Event(), threading.Event()
        run.clear()
        out = {}
        t = threading.Thread(target=lambda: out.setdefault("r", scan(big, None, False, None, run, cancel)))
        t.start()
        time.sleep(0.4)
        assert t.is_alive(), "while paused it must stay still"
        run.set()
        t.join(5)
        assert not t.is_alive() and not out["r"].cancelled and len(out["r"].folders) == 180
        run.clear()
        cancel.clear()
        out.clear()
        t = threading.Thread(target=lambda: out.setdefault("r", scan(big, None, False, None, run, cancel)))
        t.start()
        time.sleep(0.2)
        cancel.set()
        t.join(5)
        assert not t.is_alive() and out["r"].cancelled
        print("pause / resume / cancel OK")

        # exports
        base = os.path.join(tmp, "export")
        ctx = ExportContext(rall, "en", datetime.now(), DEPTH_LABEL)
        created, errors = export_all(ctx, FORMATS, base)
        assert not errors, errors
        for f in created:
            assert os.path.getsize(f) > 100, f
        data = json.load(open(base + ".json", encoding="utf-8"))
        assert data["folder_count"] == len(rall.folders) and data["not_scanned"] == []
        html_text = open(base + ".html", encoding="utf-8").read()
        assert "Café &amp; More" in html_text
        if os.name != "nt":
            assert "&lt;2024&gt;" in html_text
        assert open(base + ".pdf", "rb").read(5) == b"%PDF-"
        from openpyxl import load_workbook

        wb = load_workbook(base + ".xlsx")
        assert wb.sheetnames[0] == "Folders" and wb["Folders"].max_row == len(rall.folders) + 1
        print("exports OK:", ", ".join(os.path.basename(c) for c in created))

        # the "not scanned" list is present when needed
        ctx = ExportContext(rbad, "en", datetime.now(), DEPTH_LABEL)
        base = os.path.join(tmp, "bad")
        created, errors = export_all(ctx, FORMATS, base)
        assert not errors, errors
        assert os.path.exists(base + "_not_scanned.csv")
        print("export with folders that could not be scanned OK")

        # very large PDF (chunked mode)
        many = type(rall)(rall.root, None, False, folders=[os.path.join(rall.root, f"folder_{i:06d}", "sub") for i in range(20000)])
        many.duration = 1
        t0 = time.time()
        export_all(ExportContext(many, "en", datetime.now(), "All"), ["pdf"], os.path.join(tmp, "large"))
        print(f"PDF with 20000 folders created in {time.time() - t0:.1f}s")
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
