# Changelog

All notable changes to Pino's Folder Scanner. See also the [roadmap](ROADMAP.md).

## 1.2 – ready, not yet released

### Added
- **Info window** (the **i** button next to the heart): version, links (GitHub, Issues, Ko-fi, README), **Save diagnostic report** and **Report a problem**.
- **Diagnostic report** of the last scan, saved as a text file wherever you choose. It has the version, Windows, Python and Qt versions, the scan options and results, the kind of path (local, network or removable), time and size of each export, the fonts used in the PDF, the five slowest folders to read and the end of `errors.log`. Every folder name in it is replaced by a code, and there is no user name or computer name. The program never sends it anywhere: you decide what to share.
- **Report a problem** opens the GitHub new-issue page with the version and Windows already filled in; nothing is sent by the program.
- At the end of a scan the message offers the report only when something really went wrong (a format could not be created, the scan failed, or folders were skipped because of an unexpected system error). "Access denied" and "not found" are normal and do not trigger it.
- Issue forms for a bug report, an idea and a translation to fix.
- Six new languages: **German, Spanish, French, Dutch, Portuguese and Chinese (Simplified)**. The translations have not been checked by native speakers yet; corrections are welcome.
- **Exclude folders by name** (for example `node_modules, .git, backup*`): upper and lower case do not matter, `*` and `?` work as wildcards, a folder left out is not opened and the starting folder is never left out. The exported files and the final message say what was left out.
- **Copy list** button when a scan is complete: copies the full paths, one per line, to the clipboard.
- With no export format ticked the program only scans: no "Save as" window and no file.

### Changed
- The language switch is now a drop-down menu with the name of each language. The language of Windows is used on the first start (Chinese only for Simplified Chinese locales).
- Numbers use the thousands separator of the language (12,847 / 12.847 / 12 847).
- "Nothing ticked" in the export formats is remembered between runs. The warning "select at least one format" is gone.
- Message windows are always wide enough for their buttons and tall enough for their text.

### Fixed
- Non-Latin text (for example Chinese) in the page footer of the PDF showed as empty boxes: it now uses the fallback fonts like the rest of the document.

## 1.1 – 2026-11-26

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
