"""Measure conversion in fresh processes, optionally with repeated test pages."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import pymupdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="*", type=Path)
    parser.add_argument("--stress-repeat", type=int, default=0)
    parser.add_argument("--unique-image-pages", type=int, nargs="*", default=[],
                        help="Generate distinct 2100x2970 noisy scan images, e.g. 12 60")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks"))
    args = parser.parse_args()
    if args.stress_repeat < 0:
        parser.error("--stress-repeat cannot be negative")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    project = Path(__file__).resolve().parents[1]
    pdfs = args.pdfs or [project / "examples/conversion-lab.pdf"]
    if args.stress_repeat:
        path = args.output_dir / f"stress-{args.stress_repeat * 7}.pdf"
        with pymupdf.open(project / "examples/conversion-lab.pdf") as fixture, pymupdf.open() as document:
            for _ in range(args.stress_repeat):
                document.insert_pdf(fixture)
            document.save(path, garbage=3, deflate=True)
        pdfs.append(path)
    for count in args.unique_image_pages:
        if not 1 <= count <= 1000:
            parser.error("Unique-image page counts must be between 1 and 1000")
        path = args.output_dir / f"unique-images-{count}.pdf"
        # Linux can retain a fork child's pre-exec high-water mark. Generating
        # many source images in THIS launcher therefore inflates every later
        # ru_maxrss measurement. Keep the generator in its own process too.
        subprocess.run([sys.executable, str(project / "tools/make_image_stress.py"),
                        str(path.resolve()), str(count)], check=True)
        pdfs.append(path)
    summaries = []
    for position, pdf in enumerate(pdfs, 1):
        output = args.output_dir / f"{position:02d}-{pdf.stem}.epub"
        run = subprocess.run([sys.executable, "-m", "pdftoepub", "convert", str(pdf.resolve()),
                              str(output.resolve()), "--overwrite"], cwd=project,
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        if run.returncode:
            print(run.stderr, file=sys.stderr)
            return run.returncode
        report = json.loads(output.with_suffix(".report.json").read_text(encoding="utf-8"))
        summaries.append({key: report[key] for key in ["input", "input_bytes", "converted_pages",
                         "output_bytes", "elapsed_seconds", "peak_process_mib", "preserved_pages",
                         "review_pages", "unique_images", "totals", "platform", "pymupdf_version", "memory_scope"]})
        print(f'{pdf.name}: {report["converted_pages"]} pages, {report["elapsed_seconds"]} s, '
              f'{report["peak_process_mib"]} MiB peak conversion RAM')
    result = args.output_dir / "benchmark-results.json"
    result.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"Results: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
