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

## 1.2 – Released: diagnostics, languages, filters and clipboard

- **Diagnostics and feedback:** an **i** button next to the heart opens an info window (version, links, *Save diagnostic report*, *Report a problem*). The diagnostic report is a text file you save and share only if you want to; every folder name in it is replaced by a code, and there is no user name or computer name. At the end of a scan the report is offered only when something really went wrong. Issue forms for bug reports, ideas and translation fixes.
- **Eight languages:** Spanish, French, German, Dutch, Portuguese (neutral, close to Brazilian) and Chinese (Simplified) next to English and Italian, with a drop-down menu in the title bar. The new translations are not checked by native speakers yet: corrections are welcome. Numbers use the separator of each language.
- **Filters and clipboard:** exclude folders by name (with `*` and `?` wildcards); a **Copy list** button when a scan is complete; with no format ticked the program only scans, with no file.

## Ideas, no version yet

- Light theme.
- Code signing of the `.exe`, to avoid the SmartScreen warning.
- More languages on request.
- At the next start after an unexpected closing, offer to save the diagnostic report.

Ideas and bug reports are welcome in the [issues](../../issues).
