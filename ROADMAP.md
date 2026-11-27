# Roadmap

What is planned for Pino's Folder Scanner. Plans can change; nothing here is a promise or a date.
The program stays free, and no feature is ever locked behind a donation.

## 1.0 – Released

First public release: scan a drive or folder and export its subfolder list to PDF, TXT, CSV, XLSX, HTML or JSON.

## 1.1 – Released: support and Italian

- Ko-fi support: a small heart button in the program (opens the Ko-fi page in your browser, only when you click it; the program never connects to the internet by itself), a badge in the README and the **Sponsor** button of this repository.
- Italian interface.
- Drag a folder onto the window to choose it.
- Automatic build on GitHub Actions: the `.exe` attached to each release is built from the public source.

## 1.2 – Diagnostics, languages, filters and clipboard (planned)

One release with all of this. The work is done in small steps, each one tried on Windows before it is merged; the release is published when everything is in and no problem is open.

### Diagnostics and feedback

- **Diagnostic report** of the last scan, saved as a text file wherever you choose with *Save as*. It contains the version, Windows, Python and Qt versions, the language and the screen scale; the scan options and results (folders found, folders skipped by reason, duration, time in pause, folders per second); the kind of path (local, network or removable); time and size of each export, and the fonts used in the PDF; the five slowest folders to read; the last lines of `errors.log`. *Progress: the report itself is written and tested, it has no button yet.*
- **Privacy:** every folder name in the report is replaced by a code (for example `D:\Photos` becomes `<drive>\f_3a9c1e`), always, with no option to show the real names. No user name, no computer name. Nothing is ever sent by the program: you decide what to attach to a report. Tests check that no real name appears in the report.
- **Info window** (an "i" button next to the heart): version, links (GitHub, issues, Ko-fi, README), *Save diagnostic report* and *Report a problem* (opens the GitHub new-issue page already filled with the version and Windows, which you can read before sending).
- **Offer to save the report** in the window shown at the end of a scan, only when something really went wrong: a format could not be created, the scan failed because of an unexpected error, or folders were skipped because of an unexpected system error. Folders skipped for "access denied" or "not found" are normal and do not trigger it.
- Issue forms in the repository (bug report, idea) and a README note on what the report contains.

### More languages

- Spanish, French, German, Portuguese, Dutch and Chinese.
- The language switch becomes a drop-down menu; the language of Windows is used by default.
- Issue form to report a translation to fix. Translations are not checked by native speakers yet: corrections are welcome.

### Filters and clipboard

- Exclude folders by name (for example `node_modules` or `.git`).
- Copy the list to the clipboard without saving a file.

## Ideas, no version yet

- Light theme.
- Code signing of the `.exe`, to avoid the SmartScreen warning.
- More languages on request.
- At the next start after an unexpected closing, offer to save the diagnostic report.

Ideas and bug reports are welcome in the [issues](../../issues).
