"""Generate distinct high-resolution noisy scan pages for memory measurements."""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("pages", type=int)
    args = parser.parse_args()
    if not 1 <= args.pages <= 1000:
        parser.error("Page count must be between 1 and 1000")
    with pymupdf.open() as document:
        for index in range(args.pages):
            image = Image.effect_noise((2100, 2970), 35).convert("RGB")
            ImageDraw.Draw(image).text((100, 100), f"Distinct scan page {index + 1}", fill="white", font_size=60)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=90)
            page = document.new_page(width=595, height=842)
            page.insert_image(page.rect, stream=buffer.getvalue())
            del page, buffer, image
            pymupdf.TOOLS.store_shrink(100)
        document.save(args.output, garbage=3, deflate=True)


if __name__ == "__main__":
    main()
