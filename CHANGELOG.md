# Changes

## Unreleased

- Reject borderless-table candidates that cut through prose or lack clear column gutters, keeping ordinary paragraphs adjustable.
- Recover separate ruled-table headings when only the header separators are missing; keep genuinely merged tables visual.
- Let HTML table cells rewrap naturally and avoid treating an incomplete continuation row as a header. Table fragments remain on their original source pages.
- Keep separately encoded Symbol-font list markers with their prose instead of rendering them as mathematical images.
- Preserve local Fit/FitH PDF destinations that MuPDF exposes as named links, including page selection and finite-coordinate handling.

## 0.2.0 - 2026-10-01

- Rename the personal tool to PdfToEpub converter, including package/CLI, portable executable, sample content, screenshots and build artifacts. New-name application settings start with defaults.

- Add remembered System / Light / Dark appearance, live system changes, consistent menu/control contrast, clearer layout guidance and completion status. Document previews retain original colours.

- Restore existing internal PDF links and HTTP/HTTPS/mailto links, retaining text formatting and nearby block destinations. Visual content has adjacent clickable entries.
- Retain nested bookmark navigation; report excluded/unsupported link targets.
- Preserve selected regions, expanding intersecting content whole and showing/reporting final crop bounds.
- Add built-in/named profiles, remembered settings/folders, and CLI profile/region/link switches.
- Fit the source preview after window resizing and keep settings accessible through a scrollable panel.
- Measure Linux worker peaks independently of GUI pre-exec memory; benchmark distinct large images with separate fixture generation.
- Add native platform CI and a Windows portable build/frozen-worker check.
- Include an original navigation sample and keep the Kindle-tested default conversion behavior.

## 0.1.0 - 2026-09-30

Initial offline converter: reflowable text/simple tables, visual fallbacks, comparison preview, page overrides, bounded raster buffers and incremental EPUB packaging.
