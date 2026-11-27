"""Test of the diagnostic report (no Qt, no screen needed).

Run with:  python tests/test_diagnostics.py
The most important check is about privacy: no real folder name, user name or computer name
may appear in the report.
"""
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.diagnostics import (  # noqa: E402
    Masker,
    RunRecord,
    build_report,
    environment_info,
    path_kind,
    read_log_tail,
    save_report,
)
from app.exporters import ExportContext, export_all  # noqa: E402
from app.scanner import ScanResult, SkippedFolder, scan  # noqa: E402

SECRETS = [
    "SecretFamilyPhotos",
    "Mario Rossi tax 2026",
    "Café ünïcode",
    "AnnaBianchi",
    "Rossi",
    "PC-DI-MARIO",
    "Documenti segreti",
]


def assert_no_secret(text: str, where: str) -> None:
    low = text.casefold()
    for secret in SECRETS:
        assert secret.casefold() not in low, f"{where}: found {secret!r}"


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="fs_diag_")

    # --- the scanner measures what the report needs
    tree = os.path.join(tmp, "SecretFamilyPhotos")
    for name in ("Mario Rossi tax 2026", "Café ünïcode", "plain"):
        os.makedirs(os.path.join(tree, name, "sub"))
    res = scan(tree, None, False)
    assert res.dirs_read >= 7 and 1 <= len(res.slowest) <= 5, (res.dirs_read, res.slowest)
    assert all(a[1] >= b[1] for a, b in zip(res.slowest, res.slowest[1:])), "slowest folders in order"
    assert res.paused == 0.0
    print("scanner measures OK")

    # --- export timings
    base = os.path.join(tmp, "out")
    stats = {}
    created, errors = export_all(ExportContext(res, "en", datetime.now(), "All"), ["txt", "csv", "pdf"], base, stats)
    assert not errors and set(stats) == {"txt", "csv", "pdf"}
    assert all(stats[f]["seconds"] >= 0 and stats[f]["bytes"] > 0 and stats[f]["error"] is None for f in stats)
    print("export timings OK")

    # --- masker: same name, same code; different report, different codes
    m1, m2 = Masker(salt=b"a" * 16), Masker(salt=b"b" * 16)
    assert m1.code("Photos") == m1.code("photos") and m1.code("Photos") != m1.code("Videos")
    assert m1.code("Photos") != m2.code("Photos")
    p = m1.path("D:\\Photos\\2024\\Photos")
    assert p.startswith("<drive>\\") and p.count("\\") == 3 and "Photos" not in p
    assert p.split("\\")[1] == p.split("\\")[3], "same name, same code"
    assert m1.path("D:\\") == "<drive>\\"
    assert m1.path("\\\\server\\share\\x").startswith("<network>\\")
    assert m1.path("/home/mario/x").startswith("<root>\\")
    assert m1.path("C:\\app\\window.py", keep_py=True).endswith("\\window.py")
    assert not m1.path("C:\\app\\window.py").endswith("window.py")
    print("masker OK")

    # --- kind of path (the drive type is injected: it works on any system)
    assert path_kind("\\\\srv\\share\\x") == "network share (UNC)"
    assert path_kind("D:\\x", lambda root: 3) == "local drive"
    assert path_kind("E:\\", lambda root: 2) == "removable drive"
    assert path_kind("Z:\\", lambda root: 4) == "network drive"
    assert path_kind("Z:\\", lambda root: 0) == "unknown"
    print("path kind OK")

    # --- free text: paths with spaces, quotes, doubled backslashes, user and computer name
    masker = Masker(user="AnnaBianchi", computer="PC-DI-MARIO")
    masker.register_path(os.path.join(tmp, "SecretFamilyPhotos", "Mario Rossi tax 2026"))
    messy = (
        "Traceback (most recent call last):\n"
        '  File "C:\\Users\\AnnaBianchi\\AppData\\Local\\Temp\\_MEI123\\app\\window.py", line 10, in run\n'
        "PermissionError: [WinError 5] Access is denied: 'D:\\\\Documenti segreti\\\\Mario Rossi tax 2026\\\\x'\n"
        "OSError: cannot read D:\\Documenti segreti\\Café ünïcode because AnnaBianchi on PC-DI-MARIO said no\n"
        f"OSError: [Errno 5] input/output error: '{os.path.join(tmp, 'SecretFamilyPhotos', 'Mario Rossi tax 2026', 'sub', 'file')}'\n"
    )
    cleaned = masker.text(messy)
    assert_no_secret(cleaned, "free text")
    assert "AnnaBianchi" not in cleaned and "PC-DI-MARIO" not in cleaned
    assert "window.py" in cleaned and "line 10" in cleaned, "the program file name and line stay"
    assert "Traceback (most recent call last)" in cleaned and "PermissionError" in cleaned
    print("free text masking OK")

    # --- a complete report, with everything that can contain names
    run = RunRecord(
        started_at=datetime(2026, 11, 27, 10, 0, 0),
        root=tree,
        depth_key="all",
        include_hidden=False,
        formats=["pdf", "txt", "html"],
        save_base=os.path.join(tmp, "Documenti segreti", "report"),
    )
    skipped_path = os.path.join(tree, "Mario Rossi tax 2026", "sub")
    res.skipped = [
        SkippedFolder(os.path.join(tree, "Café ünïcode"), "denied"),
        SkippedFolder(os.path.join(tree, "gone"), "notfound"),
        SkippedFolder(skipped_path, "error", f"[Errno 5] Input/output error: '{skipped_path}'"),
    ]
    res.paused = 2.5
    run.result, run.status = res, "completed"
    run.export_stats = {"pdf": {"seconds": 1.234, "bytes": 123456, "error": None}, "txt": {"seconds": 0.01, "bytes": 800, "error": None}}
    run.errors = [("HTML", f"Permission denied: '{os.path.join(tmp, 'Documenti segreti', 'report.html')}'")]
    log = tempfile.mktemp(dir=tmp)
    with open(log, "w", encoding="utf-8") as fh:
        for i in range(100):
            fh.write(f"old line {i}\n")
        fh.write("Traceback (most recent call last):\n")
        fh.write('  File "C:\\Users\\AnnaBianchi\\Documenti segreti\\Mario Rossi tax 2026\\x.py", line 3, in f\n')
        fh.write("ValueError: bad value in 'D:\\Mario Rossi tax 2026\\SecretFamilyPhotos'\n")
    tail = read_log_tail(log)
    assert "old line 0\n" not in tail and "old line 99" in tail, "only the last lines"
    env = environment_info("it", 1.25)
    assert ("Program version", __import__("app").__version__) in env and ("Screen scale", "1.25") in env
    report = build_report(
        run, env, tail, Masker(user="AnnaBianchi", computer="PC-DI-MARIO"), datetime(2026, 11, 27, 10, 5, 0), lambda root: 3
    )
    assert_no_secret(report, "report")
    for text in (
        "Folders found: 6",
        "Folders skipped: 3 (access denied 1, not found 1, unexpected error 1)",
        "Time in pause: 2.50 s",
        "Kind of path: ",
        "Status: completed",
        "Depth: All subfolders",
        "PDF: 1.23 s, 120.6 KB",
        "HTML: FAILED - Permission denied",
        "Slowest folders to read:",
        "Unexpected errors while reading folders",
        "errors.log (last lines)",
        "does not send this file anywhere",
    ):
        assert text in report, f"missing: {text!r}\n{report}"
    assert "Scanned path: <root>\\f_" in report or "Scanned path: <drive>\\f_" in report
    print("complete report OK, and it contains no real name")

    # --- no scan yet, a failed scan, a cancelled one
    nothing = build_report(None, env, "", Masker(), datetime.now())
    assert "No scan has been done" in nothing and "(empty or missing" in nothing
    failed = RunRecord(datetime.now(), os.path.join(tmp, "SecretFamilyPhotos"), "1", True, ["txt"])
    failed.status, failed.fail_message = "failed", f"boom in {os.path.join(tmp, 'SecretFamilyPhotos')}"
    failed.fail_trace = f'Traceback\n  File "{os.path.join(tmp, "SecretFamilyPhotos", "x.py")}", line 1\nRuntimeError: boom\n'
    text = build_report(failed, env, "", Masker(), datetime.now())
    assert "Status: failed" in text and "RuntimeError: boom" in text
    assert_no_secret(text, "failed report")
    cancelled = RunRecord(datetime.now(), tree, "2", False, ["pdf"])
    cancelled.status, cancelled.result = "cancelled", ScanResult(tree, 2, False)
    assert "Status: cancelled" in build_report(cancelled, env, "", Masker(), datetime.now())
    print("no scan / failed / cancelled OK")

    # --- saving: UTF-8 with BOM, Windows line ends
    out = os.path.join(tmp, "report.txt")
    save_report(report, out)
    raw = open(out, "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    print("saving OK")
    print("ALL DIAGNOSTIC TESTS PASSED")


if __name__ == "__main__":
    main()
