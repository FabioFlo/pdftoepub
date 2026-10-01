# Verification record - LeafPress 0.2.0

Date: 2026-10-01. Reference environment: Linux x86_64, Python 3.12, PyMuPDF 1.26.6, PySide6 Essentials 6.10.3. GUI checks use Qt offscreen.

## Conversion measurements

Fresh CLI process per input; Hybrid / Balanced / Auto, repeated-margin removal and existing-link preservation enabled. Timing covers the engine and local validation, excluding interpreter startup and GUI. MiB is 1,048,576 bytes. One reference run, not a performance guarantee.

| Input | Pages | PDF MiB | EPUB MiB | Engine seconds | Peak worker MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| conversion-lab.pdf | 7 | 0.05 | 0.19 | 0.361 | 64.08 |
| navigation-lab.pdf | 3 | 0.01 | 0.05 | 0.144 | 57.45 |
| RelIns_Pegaso.pdf | 19 | 0.87 | 1.84 | 7.401 | 97.21 |
| IntProSof_Pegaso.pdf | 24 | 1.18 | 1.82 | 3.591 | 93.08 |
| stress-350.pdf | 350 | 2.57 | 0.41 | 15.020 | 67.70 |
| unique-images-12.pdf | 12 | 42.99 | 31.89 | 13.437 | 87.41 |
| unique-images-60.pdf | 60 | 214.93 | 159.46 | 70.163 | 87.41 |

The 350-page case repeats the original seven-page fixture 50 times and benefits from duplicate asset reuse. The distinct-image cases contain 12 or 60 different 2100x2970 noisy RGB scan rasters (JPEG sources); every output image is unique. Their larger books demonstrate that bounded worker RAM does not imply small files for arbitrary photographic/scanned input. Output size and duration increase with page count while these observed peaks stay around 87.4 MiB. These synthetic scans are not a universal photo/scanner benchmark.

Fixture generation runs in separate processes. Linux VmHWM avoids retaining a fork parent's pre-exec high-water mark in the worker's figure; a regression check covers that case. Windows uses PeakWorkingSetSize and macOS ru_maxrss. Figures include the interpreter/native PDF engine and exclude GUI memory. Source-image decoding, fonts and pathological PDF structures can exceed these reference peaks; output raster caps are not a total RAM quota. Reports/resources/link metadata grow with content count. Staging/preview/ZIP consume disk space.

Exact measurements are in `benchmark-results.json`. Private study PDFs and large generated stress documents are not distributed with the source.

## Checks

- 38 automated checks pass locally, including the 24 original checks, existing-link source text/formatting and target blocks, excluded destinations, image-page links, nested navigation, manual region containment/merging, profiles, five real desktop worker/settings flows, and Linux pre-exec peak-memory accounting.
- Original sample content, real study PDFs and repeated stress output retain their v0.1 text/table/equation counts with default settings.
- The navigation sample restores four internal and two external links, including a return from a note and a web link on a preserved slide.
- EPUBCheck 5.3.0 results are recorded in `epubcheck-results.json`. Built-in validation separately checks package resources/fragments and permits outbound anchors while rejecting remote assets.
- Visual review includes all navigation PDF pages, source/EPUB desktop views, the full expanded manual table crop, and desktop layout at 1280x850 and 940x680.
- A wheel was built, installed outside the source tree, and used for a compact navigation conversion and GUI construction. The source bundle passes ZIP integrity/module checks.
- GitHub Actions checks native Linux/Windows/macOS and packages/verifies the frozen Windows worker. Consult the PR's checks and workflow run for their recorded outcome; the local figures above remain the Linux reference.

## Device/platform scope

Flo reported satisfactory v0.1 Kindle reading, formula preservation and table zoom on 2026-10-01. New v0.2 links/regions and interactive use of the portable Windows GUI still need that device/computer trial. Automated native/offscreen checks do not establish Amazon conversion behavior or physical-device presentation. OCR, inferred printed references and popup-note semantics are not implemented.

## Reproduce

```bash
python -m unittest discover -s tests -v
python tools/benchmark.py --stress-repeat 50
python tools/benchmark.py --unique-image-pages 12 60
python tools/benchmark.py /path/to/your-document.pdf
python tools/make_navigation_demo.py
java -jar /path/to/epubcheck.jar examples/navigation-lab.epub
```
