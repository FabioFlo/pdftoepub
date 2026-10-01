from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import sys
import tempfile

from . import __version__
from .convert import ConversionCancelled, convert
from .epub import validate_epub
from .model import Options
from .profiles import PROFILES


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _worker(config_path: str) -> int:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    cancel_path = Path(config["cancel_file"])

    def stop(_signal, _frame):
        cancel_path.touch()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    events_file = config.get("events_file")
    event_stream = Path(events_file).open("a", encoding="utf-8") if events_file else None

    def send(event):
        if event_stream:
            event_stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            event_stream.flush()
        else:
            emit(event)

    try:
        convert(config["source"], config["output"], Options(**config["options"]),
                preview=True, overwrite=config.get("overwrite", False),
                cancel_file=cancel_path, progress=send,
                staging_parent=config.get("staging_parent"))
        return 0
    except ConversionCancelled:
        send({"type": "cancelled"})
        return 130
    except Exception as exc:
        send({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        return 1
    finally:
        if event_stream:
            event_stream.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PdfToEpub converter: offline PDF to EPUB conversion")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="Open the desktop app")
    converter = commands.add_parser("convert", help="Convert a PDF")
    converter.add_argument("input", type=Path)
    converter.add_argument("output", type=Path)
    converter.add_argument("--profile", choices=list(PROFILES), default="balanced")
    converter.add_argument("--mode", choices=["hybrid", "preserve"])
    converter.add_argument("--quality", choices=["compact", "balanced", "sharp"])
    converter.add_argument("--tables", choices=["auto", "image"])
    converter.add_argument("--language", default="en")
    converter.add_argument("--title", default="")
    converter.add_argument("--author", default="")
    converter.add_argument("--pages", default="", help="Source pages, for example 1-5,8")
    converter.add_argument("--keep-margins", action="store_true")
    converter.add_argument("--borderless-tables", action="store_true", help="Experimental: review all detections")
    converter.add_argument("--preserve-pages", default="", help="Page overrides, for example 2,7-9")
    converter.add_argument("--no-links", action="store_true", help="Omit PDF link reconstruction")
    converter.add_argument("--regions", type=Path, help="JSON map of source pages to normalized [x0,y0,x1,y1] crop lists")
    converter.add_argument("--preview", action="store_true", help="Keep XHTML and images beside the EPUB")
    converter.add_argument("--overwrite", action="store_true")
    checker = commands.add_parser("check", help="Check local EPUB package structure")
    checker.add_argument("epub", type=Path)
    worker = commands.add_parser("worker", help=argparse.SUPPRESS)
    worker.add_argument("config")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in (None, "gui"):
        try:
            from .gui import main as gui_main
        except ImportError:
            print('Desktop components are missing. Install with: python -m pip install -e ".[gui]"', file=sys.stderr)
            return 1
        return gui_main()
    if args.command == "worker":
        return _worker(args.config)
    if args.command == "check":
        try:
            print(json.dumps(validate_epub(args.epub), indent=2))
            return 0
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
    with tempfile.TemporaryDirectory(prefix="pdftoepub-cancel-") as temp:
        cancel_path = Path(temp) / "cancel"
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda _signal, _frame: cancel_path.touch())
        try:
            from .model import select_pages
            import pymupdf
            preset = PROFILES[args.profile]
            options = Options(mode=args.mode or preset["mode"], quality=args.quality or preset["quality"],
                              table_mode=args.tables or preset["table_mode"],
                              language=args.language, title=args.title, author=args.author, pages=args.pages,
                              remove_margins=not args.keep_margins, detect_borderless=args.borderless_tables,
                              preserve_links=not args.no_links)
            if args.regions:
                options.page_regions = json.loads(args.regions.read_text(encoding="utf-8"))
            if args.preserve_pages:
                with pymupdf.open(args.input) as doc:
                    options.page_modes = {index + 1: "preserve" for index in select_pages(args.preserve_pages, len(doc))}

            def progress(event):
                if event["type"] == "page":
                    print(f'Page {event["result"]["page"]}: {event["done"]}/{event["total"]}', file=sys.stderr)

            report = convert(args.input, args.output, options, preview=args.preview,
                             overwrite=args.overwrite, cancel_file=cancel_path, progress=progress)
            print(f'Created {args.output}\n{report["converted_pages"]} pages in {report["elapsed_seconds"]} s; '
                  f'peak conversion process RAM: {report["peak_process_mib"]} MiB\n'
                  f'{report["review_pages"]} pages marked for review. Report: {args.output.with_suffix(".report.json")}')
            return 0
        except ConversionCancelled:
            print("Cancelled. No partial EPUB was published.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"Conversion failed: {exc}", file=sys.stderr)
            return 1
        finally:
            signal.signal(signal.SIGINT, previous)
