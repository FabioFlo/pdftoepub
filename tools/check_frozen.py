"""Exercise the frozen windowed conversion worker via its event file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from pdftoepub.epub import validate_epub
from pdftoepub.model import Options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pdftoepub-frozen-") as temporary:
        root = Path(temporary)
        output = root / "result.epub"
        events = root / "events.jsonl"
        config = root / "job.json"
        config.write_text(json.dumps({"source": str(args.pdf.resolve()), "output": str(output),
                                     "options": Options().to_dict(), "cancel_file": str(root / "cancel"),
                                     "events_file": str(events), "staging_parent": str(root)}), encoding="utf-8")
        run = subprocess.run([str(args.executable.resolve()), "worker", str(config)], timeout=90,
                             capture_output=True)
        emitted = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()] if events.exists() else []
        if run.returncode or not any(event.get("type") == "complete" for event in emitted):
            raise RuntimeError(f"Frozen worker failed ({run.returncode}): {emitted[-3:]} {run.stderr[-2000:]!r}")
        validation = validate_epub(output)
        print(json.dumps({"frozen_worker": "passed", "validation": validation}))


if __name__ == "__main__":
    main()
