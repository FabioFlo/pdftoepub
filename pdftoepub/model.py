from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import re
from pathlib import Path


@dataclass
class Options:
    mode: str = "hybrid"
    quality: str = "balanced"
    table_mode: str = "auto"
    language: str = "en"
    title: str = ""
    author: str = ""
    pages: str = ""
    remove_margins: bool = True
    detect_borderless: bool = False
    page_modes: dict[int, str] = field(default_factory=dict)
    preserve_links: bool = True
    # Fractions of the displayed source-page bounds: x0, y0, x1, y1.
    page_regions: dict[int, list[list[float]]] = field(default_factory=dict)

    def validate(self) -> None:
        for value, choices in [
            (self.mode, {"hybrid", "preserve"}),
            (self.quality, {"compact", "balanced", "sharp"}),
            (self.table_mode, {"auto", "image"}),
        ]:
            if value not in choices:
                raise ValueError(f"Invalid option: {value}")
        if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", self.language):
            raise ValueError("Use a language code such as en, it, or en-GB.")
        self.page_modes = {int(k): v for k, v in self.page_modes.items()}
        if any(k < 1 or v not in {"hybrid", "preserve"} for k, v in self.page_modes.items()):
            raise ValueError("Page overrides must use positive page numbers and hybrid/preserve.")
        self.page_regions = {int(k): v for k, v in self.page_regions.items()}
        for page, regions in self.page_regions.items():
            if page < 1 or not isinstance(regions, list):
                raise ValueError("Regions must map positive page numbers to lists of rectangles.")
            for region in regions:
                if (not isinstance(region, (list, tuple)) or len(region) != 4 or
                    any(not isinstance(v, (int, float)) or isinstance(v, bool) or
                        not math.isfinite(v) or not 0 <= v <= 1 for v in region) or
                    region[0] >= region[2] or region[1] >= region[3]):
                    raise ValueError("Each region must be [x0, y0, x1, y1] with increasing coordinates between 0 and 1.")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PageResult:
    page: int
    label: str
    title: str
    mode: str = "hybrid"
    text_characters: int = 0
    html_tables: int = 0
    table_images: int = 0
    images: int = 0
    equation_images: int = 0
    removed_margin_lines: int = 0
    removed_margin_images: int = 0
    manual_regions: int = 0
    region_bounds: list[list[float]] = field(default_factory=list)
    internal_links: int = 0
    external_links: int = 0
    skipped_links: int = 0
    warnings: list[str] = field(default_factory=list)
    xhtml: str = ""

    def summary(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "xhtml"}


def select_pages(expression: str, count: int) -> list[int]:
    """Return zero-based pages, in source order. Ranges are inclusive."""
    if not expression.strip():
        return list(range(count))
    selected: set[int] = set()
    for part in expression.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", part)
        if not match:
            raise ValueError("Pages must look like 1-5,8,12-14.")
        first = int(match[1])
        last = int(match[2] or first)
        if not 1 <= first <= last <= count:
            raise ValueError(f"Page range {part.strip()} is outside 1-{count}.")
        selected.update(range(first - 1, last))
    return sorted(selected)


def validate_paths(source: Path, output: Path) -> None:
    if not source.is_file():
        raise ValueError("The input PDF does not exist.")
    if source.resolve() == output.resolve():
        raise ValueError("Input and output must be different files.")
    if output.suffix.lower() != ".epub":
        raise ValueError("The output filename must end in .epub.")
