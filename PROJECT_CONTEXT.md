# LeafPress project context

Date: 2026-09-30. Version: 0.1.0. Working name: LeafPress.

Flo wants a local PDF-to-EPUB converter with useful table/formula preservation and sensible memory use, particularly for Kindle reading. This is a standalone project, independent of PlumePilot.

## Current implementation

- Python conversion engine with PyMuPDF, using the tested 1.26.x API.
- PySide6 Essentials GUI, using a lightweight QTextBrowser comparison view.
- Separate conversion worker with UTF-8 JSON events on disk, so a windowed frozen executable does not depend on stdout.
- Adjustable XHTML paragraphs, inferred headings, and simple ruled HTML tables.
- Image preservation for merged/wide/mathematical/uncertain tables, grouped equations, inline mathematical spans, and connected vector diagrams.
- Automatic page-image fallbacks for scans, sparse raster pages, slides, rotated text, and reconstruction failures.
- Bounded 24-page preflight, one-page extraction, incremental ZIP writes, duplicate image reuse, raster caps, and MuPDF cache clearing.
- Global mode plus source-page overrides; page range selection; metadata editing; language selection.
- Reports with page decisions, warnings, timing, output size, and peak worker RAM.
- Staged publication and sidecar rollback; cooperative cancellation plus GUI worker timeout.
- Windows setup/start/build scripts and a source launcher for macOS/Linux.
- Original seven-page PDF/EPUB fixture, source generator, meaningful conversion tests, and desktop worker smoke checks.

## Verification and present limits

See `docs/BENCHMARKS.md` for exact final metrics and validation. Desktop checks use Linux/Qt offscreen. A native Windows executable is not included or claimed to have been tested. No device-level Kindle result has been verified yet.

The memory design reduces growth with document length; it does not enforce a total RAM quota for arbitrary source PDF decoding. Reading order, paragraph reconstruction, table boundaries, and equation detection are heuristics. The desktop preview approximates EPUB rendering. Repeated margins are optional; page images always retain the original page.

OCR, internal/external hyperlink reconstruction, semantic footnotes, table editing, region-level manual overrides, and reliable layouts beyond two columns remain future work. Borderless table detection is experimental. Ordinary text uses reader fonts; source font embedding is not implemented.

## Next useful work

1. Test the shipped EPUB and a few representative conversions on Flo's Kindle through Send to Kindle.
2. Try `setup-windows.bat` / `start-windows.bat` on Windows; verify file dialogs, worker cancellation, and a native PyInstaller build.
3. Record concrete problem pages before adjusting heuristics. Prefer page-specific or region-specific corrections over broad guesses.
4. Add region-level table/equation overrides and an explicit visual-fidelity profile for math-heavy documents if needed.
5. Add optional OCR after baseline layout behavior is stable; make its extra dependencies and memory costs explicit.

Source is delivered under AGPL v3 or later, consistent with the selected PDF engine's open-source route. The application performs no network requests during conversion.
