"""Automated tests for the engine (scanning + exports). Run with:  python tests/test_core.py"""
import html
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openpyxl import load_workbook  # noqa: E402

from app.exporters import FORMATS, ExportContext, export_all  # noqa: E402
from app.i18n import LANGUAGE_NAMES, LANGUAGES, STRINGS, format_int, tr  # noqa: E402
from app.settings import language_for_locale  # noqa: E402
from app.scanner import make_name_matcher, parse_exclude, scan  # noqa: E402

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


def check_texts():
    """Every language has all the texts, with the same {placeholders}, and a name for the menu."""
    import re

    en = STRINGS["en"]
    placeholders = lambda text: sorted(re.findall(r"\{(\w+)\}", text))  # noqa: E731
    assert LANGUAGES[:2] == ["en", "it"] and len(set(LANGUAGES)) == len(LANGUAGES)
    assert set(LANGUAGE_NAMES) == set(LANGUAGES) and all(LANGUAGE_NAMES.values())
    assert set(STRINGS) == set(LANGUAGES)
    for lang in LANGUAGES:
        table = STRINGS[lang]
        assert set(table) == set(en), (lang, set(table) ^ set(en))
        for key, text in table.items():
            assert isinstance(text, str) and text.strip(), (lang, key)
            assert placeholders(text) == placeholders(en[key]), (lang, key, text)
            assert text.startswith("\n") == en[key].startswith("\n"), (lang, key)
            text.format(**{name: "x" for name in placeholders(text)})  # no stray brace
    assert tr("xx", "btn_start") == en["btn_start"], "an unknown language falls back to English"
    assert STRINGS["de"]["btn_start"] != en["btn_start"] and STRINGS["fr"]["btn_start"] != en["btn_start"]
    print(f"texts OK: {len(LANGUAGES)} languages x {len(en)} texts, same placeholders")

    # numbers: the separator of each language
    assert format_int(12847, "en") == "12,847" and format_int(12847, "it") == "12.847"
    assert format_int(12847, "fr") == "12\u00a0847" and format_int(1234567, "de") == "1.234.567"
    assert format_int(999, "nl") == "999" and format_int(0, "zh") == "0" and format_int(12847, "xx") == "12,847"

    # the language chosen from the language of Windows
    for name, lang in (("it_IT", "it"), ("en_US", "en"), ("pt_BR", "pt"), ("pt_PT", "pt"), ("nl_BE", "nl"),
                       ("de-DE", "de"), ("zh_CN", "zh"), ("zh_SG", "zh"), ("zh_Hans_CN", "zh"),
                       ("zh_TW", "en"), ("zh_HK", "en"), ("zh_Hant_TW", "en"), ("ja_JP", "en"), ("", "en")):
        assert language_for_locale(name) == lang, (name, language_for_locale(name))
    print("numbers and language detection OK")


def check_exclude():
    """Folders left out by name: matching, wildcards, the starting folder, counts and the exported files."""
    assert parse_exclude("node_modules, .git;  Backup* ,,NODE_MODULES ; ") == ["node_modules", ".git", "Backup*"]
    assert parse_exclude("") == [] and parse_exclude(None) == [] and parse_exclude(" , ;; ") == []
    assert make_name_matcher([]) is None and make_name_matcher(["", "  "]) is None
    m = make_name_matcher(["Node_Modules", "back*", "a?", "[old]"])
    assert m("node_modules") and m("NODE_MODULES") and m("Backup2024") and m("BACK") and m("a1") and m("[old]")
    assert not m("node_modules2") and not m("my_node_modules") and not m("a") and not m("a12") and not m("old")
    assert not m("o") and not m("x[old]")

    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "root")
        for n in ("keep/a", "node_modules/pkg/x", "sub/Node_Modules/y", "sub/ok", "Backup2024/z", "backup_old/w",
                  "[old]/q", "a1/b", "a2/b", "node_modules_extra/k", ".git/objects"):
            os.makedirs(os.path.join(root, *n.split("/")))
        base = scan(root, None, True)
        assert base.exclude == [] and base.excluded == 0
        total = len(base.folders)

        def names(result):
            return sorted(os.path.relpath(f, root).replace(os.sep, "/") for f in result.folders)

        r = scan(root, None, True, exclude=["node_modules"])
        got = names(r)
        assert "node_modules" not in got and "sub/Node_Modules" not in got, got
        assert not any("pkg" in g or g.endswith("/y") for g in got), "the content of a folder left out is not listed"
        assert "node_modules_extra" in got and "keep/a" in got and "sub/ok" in got
        assert r.excluded == 2 and r.exclude == ["node_modules"]
        assert len(r.folders) == total - 5  # node_modules, pkg, x, Node_Modules, y

        r = scan(root, None, True, exclude=["backup*", "a?", "[old]", ".git"])
        got = names(r)
        assert not any(g.split("/")[0] in ("Backup2024", "backup_old", "a1", "a2", "[old]", ".git") for g in got), got
        assert r.excluded == 6 and "keep" in got and "keep/a" in got, (r.excluded, got)

        # the folder chosen to start from is never left out, even when its name matches
        inside = os.path.join(root, "node_modules")
        r = scan(inside, None, True, exclude=["node_modules", "pkg"])
        assert r.folders == [] and r.excluded == 1, "the starting folder is scanned; only 'pkg' inside it is left out"
        r = scan(inside, None, True, exclude=["x"])
        assert [os.path.basename(f) for f in r.folders] == ["pkg"] and r.excluded == 1

        # with a depth limit only the folders that are looked at are counted
        r = scan(root, 1, True, exclude=["node_modules"])
        assert r.excluded == 1 and "node_modules" not in names(r)
        r = scan(root, 0, True, exclude=["node_modules"])  # only the chosen folder: nothing to leave out
        assert r.exclude == [] and r.excluded == 0 and r.folders == [os.path.normpath(root)]

        # the exported files
        r = scan(root, None, True, exclude=["node_modules", "Backup*"])
        for lang in LANGUAGES:
            b = os.path.join(tmp, f"x_{lang}")
            created, errors = export_all(ExportContext(r, lang, datetime.now(), "All"), FORMATS, b)
            assert not errors, (lang, errors)
            txt = open(b + ".txt", encoding="utf-8").read()
            assert STRINGS[lang]["rep_excluded_names"] + ": node_modules, Backup*" in txt, lang
            assert STRINGS[lang]["rep_excluded_count"] + ": " + str(r.excluded) in txt, lang
        data = json.load(open(os.path.join(tmp, "x_en.json"), encoding="utf-8"))
        assert data["excluded_names"] == ["node_modules", "Backup*"] and data["excluded_count"] == r.excluded
        assert "node_modules, Backup*" in open(os.path.join(tmp, "x_en.html"), encoding="utf-8").read()
        plain = scan(root, None, True)
        b = os.path.join(tmp, "plain")
        export_all(ExportContext(plain, "en", datetime.now(), "All"), FORMATS, b)
        assert "Excluded" not in open(b + ".txt", encoding="utf-8").read(), "no exclusion: no extra lines"
        assert "excluded_names" not in json.load(open(b + ".json", encoding="utf-8"))
    print("exclusion by name OK")


def main():
    check_texts()
    check_exclude()
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

        # the same report in Italian
        base_it = os.path.join(tmp, "export_it")
        created_it, errors_it = export_all(ExportContext(rall, "it", datetime.now(), DEPTH_LABEL), FORMATS, base_it)
        assert not errors_it, errors_it
        txt_it = open(base_it + ".txt", encoding="utf-8").read()
        assert "ELENCO SOTTOCARTELLE" in txt_it and "SUBFOLDER LIST" not in txt_it
        assert open(base_it + ".pdf", "rb").read(5) == b"%PDF-"
        print("Italian exports OK")

        # every language: all the formats are created, the texts are those of the language
        for lang in LANGUAGES:
            base_l = os.path.join(tmp, f"export_{lang}")
            created_l, errors_l = export_all(ExportContext(rall, lang, datetime.now(), DEPTH_LABEL), FORMATS, base_l)
            assert not errors_l, (lang, errors_l)
            txt_l = open(base_l + ".txt", encoding="utf-8").read()
            assert STRINGS[lang]["rep_title"].upper() in txt_l, lang
            assert open(base_l + ".pdf", "rb").read(5) == b"%PDF-"
            assert STRINGS[lang]["rep_sheet_folders"] in load_workbook(base_l + ".xlsx").sheetnames
            html_l = open(base_l + ".html", encoding="utf-8").read()
            assert html.escape(STRINGS[lang]["html_search"]) in html_l, lang
        print("exports in every language OK")

        # Chinese in the PDF: the title, the summary and the page footer must use a font that has the characters.
        # (Needs a Chinese font on the computer, Microsoft YaHei on Windows, and the test-only tool pypdf;
        # without one of them the check is skipped.)
        from app.exporters import pdf_font_info

        try:
            from pypdf import PdfReader
        except ImportError:
            PdfReader = None

        if PdfReader is None:
            print("Chinese PDF check skipped: pypdf is not installed (pip install pypdf)")
        elif pdf_font_info()[1]:
            text_zh = "\n".join(page.extract_text() for page in PdfReader(os.path.join(tmp, "export_zh.pdf")).pages)
            assert STRINGS["zh"]["rep_title"] in text_zh and STRINGS["zh"]["rep_total"] in text_zh, "Chinese text in the PDF body"
            assert "第" in text_zh and "页，共" in text_zh, "Chinese page footer in the PDF (drawn with a fallback font)"
            print("Chinese PDF OK, fallback fonts:", ", ".join(pdf_font_info()[1]))
        else:
            print("Chinese PDF check skipped: no Chinese font found on this computer")
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
