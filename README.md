# LeafPress 0.1

An offline PDF-to-EPUB prototype for reading on small screens. LeafPress is a working name.

Ordinary text becomes adjustable XHTML. Reliable tables become HTML tables. Complex tables, mathematical notation, diagrams, scans, and slides use visual fallbacks where necessary. A desktop comparison view and page overrides let you inspect the result before sending it to a reader.

![Desktop comparison](docs/desktop-table.png)

## Start on Windows

1. Extract the ZIP to a normal folder, such as `Documents\LeafPress`. Do not launch files inside the ZIP.
2. Install **Python 3.12 or 3.13** if needed, enabling the Python launcher or adding Python to PATH.
3. Double-click **`setup-windows.bat`** once. Setup downloads the dependencies into a local `.venv`.
4. Double-click **`start-windows.bat`**.
5. Open `examples\conversion-lab.pdf`, select page 2, and click **Preview page**.
6. Choose the output filename and click **Create EPUB**.

Python 3.10+ is supported by the source configuration. Setup requires Internet access; preview and conversion run locally without a network service or API key.

This bundle contains runnable source, launch scripts, and examples. It does not include a prebuilt Windows executable. `build-windows.bat` builds a portable application folder **on a Windows computer** using PyInstaller. Copy the entire `dist\LeafPress` folder, including its dependencies. The executable build and native Windows/macOS behavior still need platform testing; the engine and desktop flows were tested on Linux with Qt's offscreen renderer.

Italian instructions: [START_HERE_IT.md](START_HERE_IT.md).

## First conversion

- **Hybrid** keeps paragraphs adjustable and uses image crops for content that is difficult to reconstruct.
- **Preserve all pages** renders complete PDF pages inside a regular EPUB. Appearance is retained, while text on those pages remains image-based.
- **Tables / Auto** reconstructs ruled tables with up to six columns when cell geometry is simple. Merged cells, mathematical cells, very large tables, and uncertain detections use images.
- **Tables / Images** preserves all detected tables as crops. Undetected borderless tables still need inspection.
- **Compact** uses grayscale crops at up to 120 DPI / 1600 pixels on the long edge. **Balanced** uses colour at 160 DPI / 2400 pixels. **Sharp** uses colour at 220 DPI / 3000 pixels. Individual output rasters are capped at approximately six million pixels.
- **Remove repeated headers / footers** removes repeated margin text, page counters, and shared margin images. Disable it to retain that material. Preserved pages always retain the full page.
- **Borderless tables** is experimental. Aligned prose can look like a table; inspect every detection.
- **Pages** accepts original PDF numbers, for example `1-5,8`. The EPUB preserves those source page references.
- **This page / Preserve appearance** overrides the global mode for a problem page. Preview or export again after changing settings.

The desktop preview approximates EPUB content using Qt's text renderer. It is not a Kindle emulator. Send the completed EPUB through Send to Kindle and inspect tables, equations, and images on the actual device.

Each export creates:

| Output | Purpose |
| --- | --- |
| `book.epub` | The reading file |
| `book.report.json` | Page decisions, review flags, timing, size, and peak process RAM |
| `book.preview/` | XHTML, CSS, and images used for desktop comparison |

Keep the preview folder while reviewing the book. It can be removed afterward; the EPUB contains its own resources. Reusing an output name replaces its LeafPress sidecars together with the book after conversion completes. Cancellation or a failed conversion keeps the previous complete EPUB. Cancellation is checked between page operations; the GUI stops an unresponsive worker after five seconds.

## What v0.1 handles, and what to inspect

The shipped seven-page fixture covers paragraphs, an exact cell mapping test, merged cells, superscripts and a stacked fraction, a connected vector diagram, two columns, a simulated scan, and a landscape slide. Its expected behavior is described in [examples/EXPECTED_RESULTS.md](examples/EXPECTED_RESULTS.md).

Reading order and document structure are inferred. Arbitrary PDFs do not guarantee reliable table boundaries, headings, equation grouping, or paragraph separation. Multi-column pages and mathematical crops receive review flags. More than two columns, unusually positioned annotations, nested tables, and complex forms need manual inspection or a page override. An automatic review flag cannot identify every conversion error.

Scanned pages are preserved visually. **OCR is not implemented in this version.** Image text does not provide ordinary text selection or independent font resizing. Inline mathematical crops use relative CSS dimensions where the reader supports them. Wide table images may still require zooming on a small device.

PDF bookmarks become navigation entries; without bookmarks, reconstructed page titles provide navigation. Source-page navigation is also included. Internal hyperlinks, external hyperlinks, footnote semantics, and a full editable document tree are not reconstructed yet. Encrypted PDFs require an unlocked local copy.

## Memory design

Conversion runs in a separate process. It samples up to 24 pages for font and margin heuristics, processes one page at a time, stores assets and preview content on disk, writes the ZIP incrementally, and clears MuPDF's native cache between pages. Small repeated margin images are compared using bounded visible crops, including image masks. Identical output images are reused. Only page reports and EPUB resource metadata accumulate in memory. The structural validator also parses one content document at a time.

Output raster caps constrain our own image buffers, **not all memory used to decode an unusually large source image or parse a pathological PDF**. This is not a hard RAM quota. Preview files consume temporary disk space; retaining a preview also duplicates EPUB assets on disk.

Measurements and their limits are in [docs/BENCHMARKS.md](docs/BENCHMARKS.md). Peak process RAM includes the interpreter and native PDF engine; GUI memory is measured separately by the operating system and is not included in that number.

## Command line / macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[gui]"
.venv/bin/python -m leafpress gui
```

On Linux, Qt may need the distribution's XCB/XKB libraries for an interactive desktop. After installation, `start.sh` launches the app. The CLI requires only the base dependency:

```bash
python -m pip install -e .
python -m leafpress convert input.pdf output.epub --language it --preview
python -m leafpress convert input.pdf output.epub --pages 1-12 --preserve-pages 4,8-9
python -m leafpress convert input.pdf output.epub --tables image --quality compact
python -m leafpress check output.epub
```

Use `--overwrite` to replace an existing conversion, and Ctrl+C to cancel. `check` performs local ZIP, XML, manifest, spine, resource, and fragment checks. It is not a full conformance checker.

## Verification and development

```bash
python -m unittest discover -s tests -v
python tools/benchmark.py --stress-repeat 50
python -m pip install -e ".[demo]"
python tools/make_demo.py
```

GUI checks run with Qt's offscreen platform. With the `gui` extra omitted, they are explicitly skipped. Full publication validation can be run separately with [EPUBCheck](https://github.com/w3c/epubcheck):

```bash
java -jar /path/to/epubcheck.jar output.epub
```

The verification record in [docs/BENCHMARKS.md](docs/BENCHMARKS.md) distinguishes local checks, EPUBCheck conformance, and device testing. Real study PDFs used for private verification are not bundled with the application.

## Source layout

| File | Role |
| --- | --- |
| `leafpress/extract.py` | Layout, paragraphs, tables, equation and figure crops |
| `leafpress/epub.py` | Incremental assets, EPUB packaging, structural validation |
| `leafpress/convert.py` | Bounded preflight, page loop, reports, cancellation and final writes |
| `leafpress/gui.py` | Desktop settings, comparison preview, page overrides, worker lifecycle |
| `leafpress/cli.py` | CLI and worker protocol |
| `tests/` | Content preservation, package integrity, rollback, and desktop flow checks |
| `tools/` | Original fixture generator and reproducible benchmarks |

Source is provided under GNU AGPL v3 or later; see [LICENSE](LICENSE). Dependency licensing is listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
