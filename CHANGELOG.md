# Changelog

All notable changes to Pino's Folder Scanner. See also the [roadmap](ROADMAP.md).

## 1.1 – ready, not yet released

### Added
- Ko-fi support: a small heart button in the title bar that opens the Ko-fi page in your browser when you click it. The program still never connects to the internet by itself.
- Italian interface and reports. A language switch (EN | IT) appears in the title bar; the language of Windows is used on the first start.
- Drag a folder or a drive onto the window to choose it (dragging a file uses the folder that contains it).
- Automatic build on GitHub Actions: tests on every pull request, and the `.exe` with its SHA256 attached to each release.

### Changed
- The version number is defined in one place (`app/__init__.py`).
- `build_exe.bat` skips its pauses and the Explorer window when run by the automatic build.

## 1.0 – 2026-11-10

First public release: scan a drive or folder and export its subfolder list to PDF, TXT, CSV, XLSX, HTML or JSON.
