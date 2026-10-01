# Verification record - LeafPress 0.1.0

Date: 2026-09-30. Reference environment: Linux x86_64, Python 3.12, PyMuPDF 1.26.6, PySide6 Essentials 6.10.3. Desktop flow tests use the offscreen Qt platform.

## Conversion measurements

Each case ran in a fresh CLI process with Hybrid / Balanced / automatic ruled tables / margin removal. Timing covers the engine pipeline through local EPUB validation; it excludes interpreter startup and the desktop UI. MiB means 1,048,576 bytes. Results are one reference run, not performance guarantees.

| Input | Pages | PDF MiB | EPUB MiB | Engine seconds | Peak worker MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| conversion-lab.pdf | 7 | 0.05 | 0.19 | 0.291 | 63.95 |
| RelIns_Pegaso.pdf | 19 | 0.87 | 1.84 | 5.823 | 97.70 |
| IntProSof_Pegaso.pdf | 24 | 1.18 | 1.82 | 2.652 | 94.20 |
| stress-350.pdf | 350 | 2.57 | 0.41 | 12.157 | 67.60 |

The 350-page test repeats the original seven-page fixture 50 times. It checks memory growth with document length and exercises image reuse. It does not represent 350 distinct high-resolution photographic pages. Its compact output benefits from repeated images. The two study PDFs contain different real-world layouts; the math document uses many small inline notation crops.

Peak RAM includes the interpreter and native PDF engine. GUI memory is additional. Python/native allocator behavior, fonts, source image decoding, and pathological PDF structures can change peak usage. The raster caps are not a hard process memory limit. Disk requirements include the source, staged resources, ZIP, report, and optional retained preview.

Exact machine-readable measurements: `benchmark-results.json`.

## Correctness checks

- 24 automated checks passed: exact table cell mapping; merged-cell fallback; complete equation groups; connected diagram arrows; column ordering; reflow with Word-style line spacing and indents; scans and slides; metadata escaping; page ranges and overrides; image reuse; repeated versus distinct footer images; resource validation; overwrite refusal; cancellation and sidecar rollback; rotated pages; and three desktop worker flows.
- The shipped sample EPUB, both full study conversions, and the 350-page stress conversion pass the built-in structural validator.
- EPUBCheck 5.3.0 validation results are recorded in `epubcheck-results.json`.
- Visual review covered all seven original sample PDF pages, the desktop table/merged-cell/equation views, and representative mathematical and software study pages.
- A wheel was built and installation was checked outside the source tree.

## What has not been established

Native Windows and macOS operation, a Windows PyInstaller executable, Amazon conversion behavior, and rendering on a physical Kindle have not been verified in this environment. EPUB conformance does not guarantee perfect reading order or device rendering. OCR is not implemented.

## Reproduce

```bash
python -m unittest discover -s tests -v
python tools/benchmark.py --stress-repeat 50
python tools/benchmark.py /path/to/your-document.pdf
java -jar /path/to/epubcheck.jar output.epub
```
