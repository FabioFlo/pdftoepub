# PdfToEpub converter and PlumePilot EPUB conversion

Reviewed 2026-10-01 against PlumePilot main `epub-core.mjs` blob `4fb453c79eebd88023088652dbd5d9fc7fa8b3ad` and `docs/epub-fidelity.md`. Read-only analysis: this PR changes PdfToEpub converter only.

## Why the outputs differ

| Behavior | PlumePilot | PdfToEpub converter |
| --- | --- | --- |
| Complex maths/tables/diagrams | Whole page becomes visual blocks | Difficult regions become crops; surrounding prose reflows |
| Simple ruled tables | Visual preservation | Reliable grids become HTML |
| Dense visual content | 1800-pixel page target; roughly five-million-pixel cap | Region-specific DPI, long-edge and roughly six-million-pixel caps |
| Image encoding | Already selects PNG/JPEG and avoids ZIP recompression | PNG crops with digest-based reuse |
| Long export | Browser memory and JSZip assembly | Incremental disk-backed assets and ZIP writes |

These are code-path differences in `pageNeedsVisual`, `renderVisualBlocks`, `pdfToXhtml` and packaging, not evidence that replacing PDF.js alone would produce PdfToEpub converter's result. Engine rendering and layout reconstruction both matter.

Recorded runs on the same named study PDFs illustrate the size difference. PlumePilot figures come from its September 22 fidelity record; PdfToEpub converter figures are the October 1 v0.2 Linux run. This is not a new side-by-side browser/device benchmark.

| Input | PlumePilot recorded EPUB bytes | PdfToEpub converter v0.2 EPUB bytes |
| --- | ---: | ---: |
| RelIns_Pegaso.pdf | 7,777,697 | 1,926,272 |
| IntProSof_Pegaso.pdf | 4,789,204 | 1,912,813 |

## Feasible improvements with the existing libraries

1. **Conservative region crops.** Use PDF.js text/operator coordinates to isolate maths, tables and figures and reflow adjacent prose. Keep whole-page fallback when grouping is ambiguous; fractions, superscripts, labels and arrows must stay complete.
2. **Reuse repeated assets.** Hash encoded crops and reuse manifest entries across pages/materials. Whole-page rasterization creates few identical images to reuse.
3. **Simple HTML grids.** Add a first-party geometric detector after regional behavior is reliable. The PyMuPDF table detector is not directly available in the existing PDF.js pipeline, so this requires implementation and tests.
4. **Measure course-export RAM.** Inspect intermediate canvases, assets and ZIP assembly. Encoded assets and final download bytes can coexist in browser memory. Matching PdfToEpub converter's disk-backed behavior would need a separate cross-browser streaming design.

PNG/JPEG selection and storing compressed images are already implemented. Lowering resolution alone sacrifices the formula detail protected by the previous fidelity update.

The native Python/PyMuPDF engine cannot simply be copied into an extension; a port or local companion would be needed. Transferring its reconstruction/crop strategies to PDF.js and JSZip is possible without requiring that change immediately.

## Checks for a separate PlumePilot PR

Use all four original study PDFs and synthetic fractions, superscripts, merged/wide grids, diagrams and prose. Check complete regions and reading order; measure bytes and browser memory. Test full-course export, inactive builder tabs, cancellation and downloads in Chrome/Edge/Firefox, followed by Kindle/phone review. Keep private study documents outside public source packages.
