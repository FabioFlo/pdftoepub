# LeafPress project context

Date: 2026-10-01. Version: 0.2.0. Working name: LeafPress.

Flo wants local PDF-to-EPUB conversion with useful table/formula preservation and sensible memory use, particularly for Kindle. Standalone, independent of PlumePilot. Repository: https://github.com/FabioFlo/leafpress.

## User validation and release scope

On 2026-10-01 Flo reported reading v0.1 output on Kindle: satisfying quality/size, correctly preserved mathematical notation and usable table zoom. This is user-reported validation of the original baseline, not a device trial of the new features. Flo authorized v0.2 and its PR in the new public repository.

Keep Hybrid / Balanced / Auto as the default. v0.2 adds actual internal PDF links to nearby block anchors, HTTP/HTTPS/mailto links, adjacent links for visual content, nested bookmark navigation, manual region preservation and saved profiles/settings/folders. Existing note/reference links remain ordinary internal links; popup-note semantics are not inferred. Excluded targets and unsupported/invalid actions are omitted and reported.

Manual selections use normalized displayed-page bounds. Intersecting lines/tables/equations/figures are included whole; overlapping selections merge. The preview/report show final `region_bounds`. Document edits reset on opening another PDF and do not enter general profiles. CLI flags expose profiles, region JSON and link omission.

GitHub Actions verifies Linux/Windows/macOS and builds a portable Windows folder with a frozen-worker check, source archive and notices. Workflow results remain separate from interactive Windows GUI validation. Linux peak measurements use VmHWM to exclude pre-exec parent memory; large raster fixture generation runs separately from benchmark measurement launchers.

## Engine and verification

Python/PyMuPDF 1.26.x engine, PySide6 Essentials desktop and a separate QProcess worker with UTF-8 event files. Reflowable paragraphs/headings/simple ruled HTML tables, visual crops for difficult tables/notation/diagrams, whole-page fallbacks for scans/slides/rotated or failed reconstruction. Bounded 24-page sampling, one-page processing, capped output rasters, image reuse, disk staging and incremental ZIP writes. Cancellation and rollback retain the previous complete book.

The original seven-page fixture remains the established baseline. A new three-page navigation fixture covers v0.2. See `docs/BENCHMARKS.md` for measurements/checks. Local GUI tests are Linux/Qt offscreen; native platform and frozen-worker results are recorded by CI. Flo still needs to try new navigation/regions and the portable app on the actual Kindle/computer.

Reading order, reconstruction and crop expansion are heuristics. Raster caps do not impose a hard RAM quota on arbitrary PDF decoding. Link metadata grows with link count. Destinations map to blocks rather than exact PDF pixels; image targets point to the preserved image. One-page previews exclude cross-page targets. The desktop content preview is approximate.

OCR, inferred links from plain reference text, popup-note semantics, semantic footnote reconstruction, table editing, robust layouts beyond two columns and source-font embedding remain future work. Borderless-table detection is experimental. Local file/executable PDF link actions are omitted while source text remains.

## PlumePilot comparison

Flo asked whether the extension can benefit from the quality/size improvements. PlumePilot main uses PDF.js/JSZip and renders entire complex pages as visual blocks. It already selects PNG/JPEG and bounds canvases. LeafPress's region crops, adjustable surrounding prose, HTML grids and asset reuse explain much of the gap. See read-only `docs/PLUMEPILOT_COMPARISON.md` for source references and a feasible JavaScript improvement path. The native Python engine cannot simply be copied into the extension. No PlumePilot code/branch change is part of this PR.

## Next work

1. Flo trials navigation-lab, manual regions and the portable app on the device/computer.
2. Refine geometry/link placement using concrete problem pages.
3. A separate PlumePilot PR can start with conservative region crops/asset reuse, keeping whole-page fallback and browser/course-export checks.
4. Consider optional OCR and batch conversion after this baseline is stable.

AGPL v3 or later. Conversion performs no network requests; setup/CI download dependencies.
