from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

import pymupdf

from . import __version__
from .epub import EpubWriter, validate_epub
from .extract import PageExtractor, sample_document
from .model import Options, PageResult, select_pages, validate_paths
from .links import LinkMap


class ConversionCancelled(Exception):
    pass


def peak_memory_mib() -> float | None:
    """Peak resident memory: Win32, Linux VmHWM, macOS resource counters."""
    try:
        if sys.platform.startswith("linux"):
            try:
                with open("/proc/self/status", encoding="ascii") as status:
                    for line in status:
                        if line.startswith("VmHWM:"):
                            return round(int(line.split()[1]) / 1024, 2)
            except OSError:
                pass
            # Unlike ru_maxrss, VmHWM resets after exec. This avoids attributing
            # a Qt parent's pre-exec RSS to its much smaller conversion worker.
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return None
            return round(counters.PeakWorkingSetSize / 1024 ** 2, 2)
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak / (1024 ** 2 if sys.platform == "darwin" else 1024), 2)
    except (ImportError, OSError, AttributeError):
        return None


def convert(source: str | Path, output: str | Path, options: Options | None = None,
            *, preview: bool = False, overwrite: bool = False, cancel_file: str | Path | None = None,
            progress=None, staging_parent: str | Path | None = None) -> dict:
    source, output = Path(source).resolve(), Path(output).resolve()
    options = options or Options()
    options.validate()
    validate_paths(source, output)
    report_path = output.with_suffix(".report.json")
    preview_path = output.with_suffix(".preview")
    if not overwrite and (output.exists() or report_path.exists() or (preview and preview_path.exists())):
        raise FileExistsError("Output artifacts already exist. Choose another name or enable overwrite.")
    if preview and preview_path.exists() and not (preview_path / ".pdftoepub-preview").is_file():
        raise ValueError("The preview destination is not a PdfToEpub converter preview. Choose another output name.")
    output.parent.mkdir(parents=True, exist_ok=True)
    if staging_parent is not None:
        staging_parent = Path(staging_parent).resolve()
        staging_parent.mkdir(parents=True, exist_ok=True)
        if os.stat(staging_parent).st_dev != os.stat(output.parent).st_dev:
            raise ValueError("Temporary output and final output must be on the same drive.")
    started = time.perf_counter()
    notify = progress or (lambda _event: None)

    def cancelled():
        if cancel_file and Path(cancel_file).exists():
            raise ConversionCancelled("Conversion cancelled. The previous EPUB was kept.")

    cancelled()
    with pymupdf.open(source) as document:
        if not document.is_pdf:
            raise ValueError("The input is not a PDF document.")
        if document.needs_pass:
            raise ValueError("This PDF is encrypted. Save an unlocked copy before converting it.")
        if not document.page_count:
            raise ValueError("This PDF has no pages.")
        selected = select_pages(options.pages, document.page_count)
        if any(page > document.page_count for page in options.page_modes.keys() | options.page_regions.keys()):
            raise ValueError("A page override is outside this PDF.")
        metadata = document.metadata or {}
        title = options.title.strip() or metadata.get("title", "").strip() or source.stem
        author = options.author.strip() or metadata.get("author", "").strip()
        notify({"type": "start", "total": len(selected), "title": title})
        notify({"type": "status", "message": "Sampling text styles and repeated margins..."})
        # Previewing one page must use the same style/margin preflight as a full
        # conversion. Sampling is bounded even when only a few pages are selected.
        repeated, body_size, repeated_images = sample_document(document, list(range(document.page_count)), cancelled)
        link_map = None
        if options.preserve_links:
            notify({"type": "status", "message": "Mapping PDF links to EPUB destinations..."})
            link_map = LinkMap(document, selected, cancelled)
        page_summaries = []
        with tempfile.TemporaryDirectory(prefix=".pdftoepub-", dir=staging_parent or output.parent) as temporary:
            temporary = Path(temporary)
            epub_temp = temporary / "book.epub"
            root = temporary / "preview"
            writer = EpubWriter(epub_temp, root, options.quality)
            extractor = PageExtractor(writer, options, repeated, body_size, repeated_images, link_map)
            try:
                for position, index in enumerate(selected, 1):
                    cancelled()
                    page = document[index]
                    try:
                        result = extractor.extract(page, index + 1)
                    except (MemoryError, ConversionCancelled):
                        raise
                    except Exception as exc:
                        result = PageResult(index + 1, page.get_label() or str(index + 1), f"Page {index + 1}")
                        result = extractor._preserve(page, result,
                                                     f"Automatic reconstruction failed ({type(exc).__name__}); original page preserved.")
                    cancelled()
                    writer.add_page(result.page, result.label, result.title, result.xhtml)
                    summary = result.summary()
                    page_summaries.append(summary)
                    del result, page
                    # Empty MuPDF's native object/image cache between pages.
                    pymupdf.TOOLS.store_shrink(100)
                    notify({"type": "page", "done": position, "total": len(selected),
                            "result": summary, "peak_process_mib": peak_memory_mib()})
                writer.finish(title, author, options.language, document.get_toc())
                asset_count = len(writer.assets)
            finally:
                writer.close()
            cancelled()
            notify({"type": "status", "message": "Checking EPUB resources and navigation..."})
            validation = validate_epub(epub_temp)
            elapsed = round(time.perf_counter() - started, 3)
            report = {
                "application": "PdfToEpub converter", "version": __version__,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "input": source.name, "input_bytes": source.stat().st_size,
                "output": output.name, "output_bytes": epub_temp.stat().st_size,
                "title": title, "author": author, "source_pages": document.page_count,
                "converted_pages": len(selected), "options": asdict(options),
                "elapsed_seconds": elapsed, "peak_process_mib": peak_memory_mib(),
                "memory_scope": "conversion process including Python/native PDF engine; GUI excluded",
                "platform": sys.platform, "pymupdf_version": pymupdf.VersionBind,
                "unique_images": asset_count, "validation": validation,
                "totals": {key: sum(page[key] for page in page_summaries) for key in
                           ("text_characters", "html_tables", "table_images", "images",
                            "equation_images", "removed_margin_lines", "removed_margin_images",
                            "manual_regions", "internal_links", "external_links", "skipped_links")},
                "preserved_pages": sum(page["mode"] == "preserve" for page in page_summaries),
                "review_pages": sum(bool(page["warnings"]) for page in page_summaries),
                "pages": page_summaries,
            }
            staged_report = temporary / "report.json"
            staged_report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            cancelled()
            # Stage sidecars with rollback. Install the EPUB last, so a cancelled
            # or failed job cannot replace a previously complete book.
            backups = []
            installed = []
            try:
                for staged, destination in [(staged_report, report_path)] + ([(root, preview_path)] if preview else []):
                    if destination.exists():
                        if not overwrite:
                            raise FileExistsError("An output sidecar appeared during conversion; it was kept.")
                        backup = temporary / (destination.name + ".previous")
                        os.replace(destination, backup)
                        backups.append((backup, destination))
                    os.replace(staged, destination)
                    installed.append(destination)
                cancelled()
                if not overwrite and output.exists():
                    raise FileExistsError("The output appeared during conversion; it was not overwritten.")
                os.replace(epub_temp, output)
            except BaseException:
                for destination in reversed(installed):
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    elif destination.exists():
                        destination.unlink()
                for backup, destination in reversed(backups):
                    os.replace(backup, destination)
                raise
    notify({"type": "complete", "output": str(output), "report": str(report_path),
            "preview": str(preview_path) if preview else None, "summary": report})
    return report
