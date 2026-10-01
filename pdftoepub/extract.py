from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import re
from statistics import median

import pymupdf

from .epub import EpubWriter, esc, xhtml_document
from .model import Options, PageResult
from .links import PageLinks


TEXT_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
MATH_FONT = re.compile(r"math|symbol|cmsy|cmex|cmmi|stix|msam|msbm", re.I)
MATH_SYMBOLS = set("∫∑∏√∞∂∇≈≠≤≥∈∉⊂⊆∪∩⇒⇔∀∃⊗⊕")


@dataclass
class Line:
    rect: pymupdf.Rect
    spans: list[dict]
    block: int
    direction: tuple

    @property
    def text(self) -> str:
        return "".join(span["text"] for span in self.spans).strip()

    @property
    def size(self) -> float:
        sizes = [span["size"] for span in self.spans if span["text"].strip()]
        return median(sizes) if sizes else 11.0


def lines_on(page: pymupdf.Page, with_characters: bool = False) -> list[Line]:
    data = page.get_text("rawdict" if with_characters else "dict", flags=TEXT_FLAGS, sort=False)
    if with_characters:
        for block in data["blocks"]:
            if block["type"] == 0:
                for line in block["lines"]:
                    for span in line["spans"]:
                        span["text"] = "".join(char["c"] for char in span["chars"])
    return [Line(pymupdf.Rect(line["bbox"]), line["spans"], block_index,
                 tuple(line.get("dir", (1, 0))))
            for block_index, block in enumerate(data["blocks"]) if block["type"] == 0
            for line in block["lines"] if any(span["text"].strip() for span in line["spans"])]


def normalize_margin(text: str) -> str:
    text = re.sub(r"\d+", "#", text.lower())
    return " ".join(text.split())


def is_margin(rect: pymupdf.Rect, height: float) -> bool:
    return rect.y1 < height * 0.095 or rect.y0 > height * 0.875


def margin_image_rects(page: pymupdf.Page, signatures: set[str] | None = None) -> list[tuple[str, pymupdf.Rect]]:
    """Fingerprint only small visible margin crops, including nested images.

    Resource lists can include unused images and get_image_bbox may decode all
    resources when images are nested in PDF forms. Placement metadata plus a
    small rendered crop avoids that behavior and compares visible mask content.
    """
    if signatures is not None and not signatures:
        return []
    found = []
    for info in page.get_image_info(hashes=False, xrefs=False):
        rect = pymupdf.Rect(info["bbox"]) & page.rect
        if (rect.is_empty or not is_margin(rect, page.rect.height) or
            info["width"] * info["height"] > 500_000):
            continue
        scale = min(1.0, 600 / max(rect.width, rect.height),
                    (120_000 / max(1, rect.get_area())) ** 0.5)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False)
        digest = hashlib.sha256(pixmap.tobytes("png")).hexdigest()
        del pixmap
        if signatures is None or digest in signatures:
            found.append((digest, rect))
    return found


def sample_document(doc: pymupdf.Document, selected: list[int], cancelled) -> tuple[set[str], float, set[str]]:
    # The preflight reads at most 24 pages without decoding image data.
    step = max(1, math.ceil(len(selected) / 24))
    sample = selected[::step][:24]
    counts = Counter()
    font_weights = Counter()
    image_counts = Counter()
    for index in sample:
        cancelled()
        page = doc[index]
        keys = set()
        for line in lines_on(page):
            if is_margin(line.rect, page.rect.height):
                keys.add(normalize_margin(line.text))
            else:
                for span in line.spans:
                    if not MATH_FONT.search(span["font"]):
                        font_weights[round(span["size"], 1)] += len(span["text"].strip())
        counts.update(keys)
        image_counts.update({signature for signature, _rect in margin_image_rects(page)})
        del page
        pymupdf.TOOLS.store_shrink(100)
    required = max(3, math.ceil(len(sample) * 0.5))
    repeated = {key for key, count in counts.items() if key and count >= required}
    body_size = font_weights.most_common(1)[0][0] if font_weights else 11.0
    repeated_images = {signature for signature, count in image_counts.items() if count >= required}
    return repeated, body_size, repeated_images


def overlap_fraction(rect: pymupdf.Rect, other: pymupdf.Rect) -> float:
    return (rect & other).get_area() / max(1, rect.get_area())


def inside(rect: pymupdf.Rect, region: pymupdf.Rect) -> bool:
    # MuPDF treats zero-height rules as empty rectangles. Compare coordinates
    # directly so a fraction bar or grid line still belongs to its region.
    return (region.x0 <= rect.x0 <= rect.x1 <= region.x1 and
            region.y0 <= rect.y0 <= rect.y1 <= region.y1)


def padded(rect: pymupdf.Rect, amount: float, bounds: pymupdf.Rect) -> pymupdf.Rect:
    return pymupdf.Rect(rect.x0 - amount, rect.y0 - amount,
                        rect.x1 + amount, rect.y1 + amount) & bounds


def merge_regions(regions: list[pymupdf.Rect], bounds: pymupdf.Rect) -> list[pymupdf.Rect]:
    merged = []
    for rect in regions:
        rect = pymupdf.Rect(rect) & bounds
        if rect.is_empty:
            continue
        changed = True
        while changed:
            changed = False
            for i, existing in enumerate(merged):
                if padded(rect, 2, bounds).intersects(existing):
                    rect |= merged.pop(i)
                    changed = True
                    break
        merged.append(rect)
    return merged


class PageExtractor:
    def __init__(self, writer: EpubWriter, options: Options, repeated: set[str], body_size: float,
                 repeated_images: set[str] | None = None, link_map=None):
        self.writer = writer
        self.options = options
        self.repeated = repeated
        self.body_size = body_size
        self.repeated_images = repeated_images or set()
        self.link_map = link_map
        self.links = PageLinks()

    def _keep_line(self, line: Line, page: pymupdf.Page) -> bool:
        if not self.options.remove_margins or not is_margin(line.rect, page.rect.height):
            return True
        key = normalize_margin(line.text)
        return key not in self.repeated and not re.fullmatch(
            r"(?:page |pagina )?#(?: (?:of|di|/) #)?", key)

    def _preserve(self, page: pymupdf.Page, result: PageResult, reason: str = "") -> PageResult:
        result.mode = "preserve"
        if reason:
            result.warnings.append(reason)
        # Alt text is deliberately short: a whole page in alt text is unusable.
        figure = self.writer.figure(page, page.rect, f"Original PDF page {result.label}", "preserved")
        result.images = 1
        result.text_characters = result.html_tables = result.table_images = result.equation_images = 0
        result.removed_margin_lines = result.removed_margin_images = 0
        result.manual_regions = 0
        result.region_bounds = []
        self.links.reset()
        items = self.links.decorate([(page.rect, figure)], result)
        result.xhtml = self._document(result, "\n".join(content for _, content in items))
        return result

    def _document(self, result: PageResult, body: str) -> str:
        marker = (f'<span class="pagebreak" id="source-{result.page}" '
                  f'epub:type="pagebreak" role="doc-pagebreak" aria-label="{esc(result.label)}"></span>')
        return xhtml_document(result.title, marker + body, self.options.language)

    def extract(self, page: pymupdf.Page, number: int) -> PageResult:
        label = page.get_label() or str(number)
        result = PageResult(number, label, f"Page {label}")
        self.links = self.link_map.for_page(number) if self.link_map else PageLinks()
        mode = self.options.page_modes.get(number, self.options.mode)
        if mode == "preserve":
            return self._preserve(page, result)
        if page.rotation:
            return self._preserve(page, result, "Rotated page preserved visually; review its reading orientation.")
        if page.rect.width / max(1, page.rect.height) > 1.25:
            return self._preserve(page, result, "Landscape/slide layout preserved visually.")
        all_lines = lines_on(page, with_characters=bool(self.links.links))
        manual = [pymupdf.Rect(page.rect.x0 + r[0] * page.rect.width,
                               page.rect.y0 + r[1] * page.rect.height,
                               page.rect.x0 + r[2] * page.rect.width,
                               page.rect.y0 + r[3] * page.rect.height)
                  for r in self.options.page_regions.get(number, [])]
        manual = self._expand_manual(manual, [line.rect for line in all_lines], page.rect)
        lines = [line for line in all_lines if self._keep_line(line, page)]
        result.removed_margin_lines = len(all_lines) - len(lines)
        image_info = page.get_image_info(hashes=False, xrefs=False)
        omitted_images = margin_image_rects(page, self.repeated_images) if self.options.remove_margins else []
        result.removed_margin_images = len(omitted_images)
        source_chars = sum(len(line.text) for line in all_lines)
        if source_chars < 25:
            return self._preserve(page, result, "Little or no extractable text. Preserved as an image; OCR is not included.")
        if sum(len(line.text) for line in lines) < 100 and any(
            overlap_fraction(page.rect, pymupdf.Rect(info["bbox"])) > 0.4 for info in image_info
        ):
            return self._preserve(page, result, "Large raster page with little body text; preserved visually. OCR is not included.")
        if any(overlap_fraction(page.rect, pymupdf.Rect(info["bbox"])) > 0.85 for info in image_info):
            return self._preserve(page, result, "Full-page image or scan detected; preserved visually to avoid duplicated OCR text.")
        if any(abs(line.direction[0] - 1) > 0.02 or abs(line.direction[1]) > 0.02 for line in lines):
            return self._preserve(page, result, "Text with multiple orientations preserved visually.")
        drawings = page.get_drawings()
        if len(drawings) > 3500:
            return self._preserve(page, result, "Very dense vector artwork preserved visually to limit extraction work.")
        try:
            table_regions, table_items = self._tables(page, drawings, result, manual)
        except Exception as exc:
            return self._preserve(page, result,
                                  f"Table detection could not complete ({type(exc).__name__}); page preserved visually.")
        equation_regions = self._equation_regions(
            [line for line in lines if not any(overlap_fraction(line.rect, table) > 0.3 for table in table_regions)],
            page.rect)
        for index, equation in enumerate(equation_regions):
            for drawing in drawings:
                stroke = pymupdf.Rect(drawing["rect"])
                if (max(stroke.width, stroke.height) < page.rect.width * 0.7 and
                    min(stroke.width, stroke.height) < self.body_size * 2 and
                    equation.intersects(padded(stroke, 2, page.rect))):
                    equation |= padded(stroke, 1.5, page.rect)
            equation_regions[index] = equation
        regions = []
        for info in image_info:
            rect = pymupdf.Rect(info["bbox"]) & page.rect
            if any(overlap_fraction(rect, margin_rect) > 0.98 for _signature, margin_rect in omitted_images):
                continue
            if rect.get_area() > 16 and not any(overlap_fraction(rect, table) > 0.2 for table in table_regions):
                regions.append(rect)
        # Cluster vector diagrams, omitting flat rules and page-sized backgrounds.
        useful = []
        for drawing in drawings:
            rect = pymupdf.Rect(drawing["rect"])
            if max(rect.width, rect.height) < 3 or overlap_fraction(page.rect, rect) > 0.8:
                continue
            if rect.height < 2 and rect.width > page.rect.width * 0.8:
                continue
            if any(inside(rect, region) or overlap_fraction(rect, region) > 0.4
                   for region in table_regions + equation_regions):
                continue
            useful.append(drawing)
        if useful:
            for rect in page.cluster_drawings(drawings=useful, x_tolerance=8, y_tolerance=8, final_filter=False):
                if rect.get_area() > 64 or rect.width > 12 or rect.height > 12:
                    regions.append(padded(pymupdf.Rect(rect), 1.5, page.rect))
        regions = merge_regions(regions, page.rect)
        # Include touching labels in diagram crops so they appear once, in place.
        for i, rect in enumerate(regions):
            for _ in range(3):
                before = tuple(rect)
                for line in lines:
                    if padded(rect, 4, page.rect).intersects(line.rect) and not any(
                        overlap_fraction(line.rect, region) > 0.5 for region in table_regions + equation_regions
                    ):
                        rect |= line.rect
                if tuple(rect) == before:
                    break
            regions[i] = padded(rect, 2, page.rect)
        regions = merge_regions(regions, page.rect)
        # If a figure overlaps a table after expanding labels, keep the whole
        # region visually and remove the competing table representation.
        for index, rect in enumerate(regions):
            for table in table_regions:
                if rect.intersects(table):
                    rect |= table
            regions[index] = rect
        regions = merge_regions(regions, page.rect)
        for table_rect, _ in list(table_items):
            if any(rect.intersects(table_rect) for rect in regions):
                table_items = [(r, content) for r, content in table_items if tuple(r) != tuple(table_rect)]
                # The original counts are recomputed below from rendered entries.
        manual = self._expand_manual(manual, table_regions + equation_regions + regions +
                                     [line.rect for line in all_lines], page.rect)
        table_items = [(r, content) for r, content in table_items if not any(r.intersects(m) for m in manual)]
        regions = [r for r in regions if not any(r.intersects(m) for m in manual)]
        equation_regions = [r for r in equation_regions if not any(r.intersects(m) for m in manual)]
        items: list[tuple[pymupdf.Rect, str]] = list(table_items)
        for rect in manual:
            items.append((rect, self.writer.figure(page, rect, f"Manually preserved region on PDF page {label}", "manual-region")))
            result.images += 1
        result.manual_regions = len(manual)
        result.region_bounds = [[(r.x0 - page.rect.x0) / page.rect.width,
                                 (r.y0 - page.rect.y0) / page.rect.height,
                                 (r.x1 - page.rect.x0) / page.rect.width,
                                 (r.y1 - page.rect.y0) / page.rect.height] for r in manual]
        if manual:
            result.warnings.append("Manual regions preserved visually; bounds expanded to include intersecting content. Compare the crop with the original.")
        for rect in regions:
            text = page.get_textbox(rect).strip()
            alt = text[:220] if text else f"Figure from PDF page {label}"
            items.append((rect, self.writer.figure(page, rect, alt)))
            result.images += 1
        exclusions = table_regions + regions + equation_regions + manual
        remaining = [line for line in lines if not any(
            overlap_fraction(line.rect, region) > 0.3 for region in exclusions)]
        for rect in equation_regions:
            items.append((rect, self.writer.figure(page, rect, page.get_textbox(rect)[:220], "equation")))
            result.equation_images += 1
        items.extend(self._paragraphs(page, remaining, result))
        if not items:
            return self._preserve(page, result, "No reliable reading content was reconstructed; page preserved visually.")
        items = self.links.decorate(items, result)
        ordered, columns = reading_order(items, page.rect.width)
        if columns:
            result.warnings.append("Two-column reading order inferred; compare it with the original.")
        body = "\n".join(content for _, content in ordered)
        result.html_tables = body.count('<table>')
        result.table_images = body.count('class="table-image"')
        if result.equation_images:
            result.warnings.append("Mathematical notation preserved with image crops; check their placement.")
        result.xhtml = self._document(result, body)
        return result

    def _expand_manual(self, manual, objects, bounds):
        if not manual:
            return []
        # Monotone unions terminate when no boundary moves. Any partially
        # intersected line/table/figure must be included whole before exclusion.
        manual = merge_regions(manual, bounds)
        while True:
            previous = [tuple(r) for r in manual]
            for index, rect in enumerate(manual):
                for other in objects:
                    if rect.intersects(other):
                        rect |= other
                manual[index] = rect
            manual = merge_regions(manual, bounds)
            if previous == [tuple(r) for r in manual]:
                return manual

    def _tables(self, page, drawings, result, manual=()):
        tables = page.find_tables(strategy="lines_strict", paths=drawings).tables
        borderless = False
        if not tables and self.options.detect_borderless:
            tables = page.find_tables(strategy="text", paths=drawings,
                                       min_words_vertical=3, min_words_horizontal=2).tables
            borderless = bool(tables)
        regions, items = [], []
        for table in tables:
            if table.row_count < 2 or table.col_count < 2:
                continue
            rows = table.extract()
            if sum(bool(cell and cell.strip()) for row in rows for cell in row) < 3:
                continue
            rect = padded(pymupdf.Rect(table.bbox), 1.5, page.rect)
            external = bool(table.header.external)
            if external:
                rect |= pymupdf.Rect(table.header.bbox)
            if any(rect.intersects(region) for region in manual):
                regions.append(rect)
                continue
            cell_data = page.get_text("dict", flags=TEXT_FLAGS, clip=rect)
            mathematical_cells = any(MATH_FONT.search(span["font"]) or span["flags"] & 1
                                     for block in cell_data["blocks"] if block["type"] == 0
                                     for line in block["lines"] for span in line["spans"])
            complex_table = (table.col_count > 6 or table.row_count * table.col_count > 160 or
                             any(cell is None for row in rows for cell in row) or borderless or mathematical_cells)
            if complex_table or self.options.table_mode == "image":
                content = self.writer.figure(page, rect, f"Table on PDF page {result.label}", "table-image")
                result.table_images += 1
                result.warnings.append("A wide, merged, or uncertain table was preserved as an image.")
            else:
                row_html = []
                if external:
                    row_html.append("<tr>" + "".join(f'<th scope="col">{esc(name or "")}</th>'
                                                    for name in table.header.names) + "</tr>")
                for index, row in enumerate(rows):
                    tag = "th" if index == 0 and not external else "td"
                    attrs = ' scope="col"' if tag == "th" else ""
                    cells = "".join(f'<{tag}{attrs}>{esc(cell or "").replace(chr(10), "<br/>")}</{tag}>'
                                    for cell in row)
                    row_html.append(f"<tr>{cells}</tr>")
                content = "<table>" + "".join(row_html) + "</table>"
                result.html_tables += 1
            regions.append(rect)
            items.append((rect, content))
        if borderless:
            result.warnings.append("Experimental borderless-table detection was used; review this page.")
        return regions, items

    def _math_line(self, line: Line) -> bool:
        text = line.text
        if all(span["flags"] & 8 for span in line.spans):
            return False
        math_chars = sum(len(span["text"].strip()) for span in line.spans
                         if MATH_FONT.search(span["font"]))
        operators = sum(c in MATH_SYMBOLS or c in "=^" for c in text)
        prose_words = [word for word in re.findall(r"[^\W\d_]+", text) if len(word) > 3]
        return (math_chars / max(1, len(text)) > 0.25 or
                (operators > 0 and len(prose_words) <= 2 and len(text) < 140) or
                "\ufffd" in text)

    def _equation_regions(self, lines: list[Line], bounds: pymupdf.Rect) -> list[pymupdf.Rect]:
        regions = [pymupdf.Rect(line.rect) for line in lines if self._math_line(line)]
        # PDF text can split an equation into separate lines/blocks for every
        # superscript, numerator, or denominator. Group by physical proximity.
        for _ in range(8):
            changed = False
            for i, rect in enumerate(regions):
                for line in lines:
                    text = line.text
                    words = [word for word in re.findall(r"[^\W\d_]+", text) if len(word) > 3]
                    if len(text) > 100 or len(words) > 1:
                        continue
                    candidate = line.rect
                    x_overlap = min(rect.x1, candidate.x1) - max(rect.x0, candidate.x0)
                    y_overlap = min(rect.y1, candidate.y1) - max(rect.y0, candidate.y0)
                    x_gap = max(rect.x0 - candidate.x1, candidate.x0 - rect.x1, 0)
                    y_gap = max(rect.y0 - candidate.y1, candidate.y0 - rect.y1, 0)
                    if ((y_overlap > 0 and x_gap < self.body_size * 6) or
                        (x_overlap > 0 and y_gap < self.body_size * 1.2)):
                        previous = tuple(rect)
                        rect |= candidate
                        changed |= previous != tuple(rect)
                regions[i] = rect
            combined = merge_regions(regions, bounds)
            changed |= len(combined) != len(regions)
            regions = combined
            if not changed:
                break
        return [padded(rect, 1.5, bounds) for rect in regions]

    def _line_html(self, page: pymupdf.Page, line: Line, result: PageResult) -> str:
        output = []
        spans = line.spans
        index = 0
        while index < len(spans):
            span = spans[index]
            if MATH_FONT.search(span["font"]) and span["text"].strip():
                rect = pymupdf.Rect(span["bbox"])
                alt = span["text"]
                # Adjacent mathematical spans form one crop; whitespace belongs
                # outside it to keep prose readable and adjustable.
                index += 1
                while index < len(spans) and MATH_FONT.search(spans[index]["font"]):
                    rect |= pymupdf.Rect(spans[index]["bbox"])
                    alt += spans[index]["text"]
                    index += 1
                asset = self.writer.render(page, rect & page.rect)
                width = max(1, round(rect.width * 16 / self.body_size))
                height = max(1, round(rect.height * 16 / self.body_size))
                output.append(f'<img src="../images/{asset.name}" width="{width}" height="{height}" '
                              f'style="width:{rect.width / self.body_size:.3f}em; '
                              f'height:{rect.height / self.body_size:.3f}em; vertical-align:-0.2em" '
                              f'alt="{esc(alt.strip())}"/>')
                result.equation_images += 1
                if alt.endswith(" "):
                    output.append(" ")
                continue
            def format_text(value):
                text = esc(value)
                if span["flags"] & 1:
                    text = f"<sup>{text}</sup>"
                if span["flags"] & 2:
                    text = f"<em>{text}</em>"
                if span["flags"] & 16:
                    text = f"<strong>{text}</strong>"
                return text
            text = self.links.inline(span, format_text)
            output.append(text)
            result.text_characters += len(span["text"])
            index += 1
        return "".join(output).strip()

    def _paragraphs(self, page: pymupdf.Page, lines: list[Line], result: PageResult):
        items = []
        pending: list[Line] = []

        def flush():
            if not pending:
                return
            rect = pymupdf.Rect(pending[0].rect)
            for line in pending[1:]:
                rect |= line.rect
            code = all(span["flags"] & 8 for line in pending for span in line.spans)
            if code:
                text = "\n".join(esc(line.text) for line in pending)
                result.text_characters += sum(len(line.text) for line in pending)
                items.append((rect, f"<pre>{text}</pre>"))
            else:
                parts = [self._line_html(page, line, result) for line in pending]
                text = parts[0]
                for part in parts[1:]:
                    # Join only plain-text hyphenation, never across an HTML tag.
                    if re.search(r"[a-zA-Z]-$", text) and re.match(r"^[a-z]", part):
                        text = text[:-1] + part
                    else:
                        text += " " + part
                items.append((rect, f"<p>{text}</p>"))
            pending.clear()

        for line in lines:
            if self._math_line(line):
                flush()
                rect = padded(line.rect, 1.5, page.rect)
                items.append((rect, self.writer.figure(page, rect, line.text[:220], "equation")))
                result.equation_images += 1
                continue
            heading = (line.size >= self.body_size * 1.2 and len(line.text) < 160 or
                       line.size >= self.body_size * 1.04 and len(line.text) < 100 and
                       all(span["flags"] & 16 for span in line.spans if span["text"].strip()))
            if heading:
                flush()
                tag = "h1" if line.size >= self.body_size * 1.6 else "h2"
                if result.title.startswith("Page "):
                    result.title = line.text
                items.append((line.rect, f"<{tag}>{self._line_html(page, line, result)}</{tag}>"))
                continue
            if pending:
                previous = pending[-1]
                # Word-generated PDFs often have ~9pt gaps between 11pt lines.
                # Keep that leading and a first-line indent inside a paragraph,
                # while blank lines, new indents, and column jumps separate it.
                x_change = line.rect.x0 - previous.rect.x0
                separate = (line.rect.y0 - previous.rect.y1 > self.body_size * 1.05 or
                            line.rect.y0 < previous.rect.y0 - 1 or
                            x_change > self.body_size * 2 or x_change < -self.body_size * 5 or
                            abs(line.size - previous.size) > self.body_size * 0.25 or
                            bool(all(span["flags"] & 8 for span in line.spans)) !=
                            bool(all(span["flags"] & 8 for span in previous.spans)) or
                            re.match(r"^(?:[•●▪]|\d+[.)])\s", line.text))
                if separate:
                    flush()
            pending.append(line)
        flush()
        return items


def reading_order(items: list[tuple[pymupdf.Rect, str]], page_width: float):
    """Handle one column or two clear columns, separated by spanning items."""
    mid = page_width / 2
    left = [item for item in items if item[0].x1 < mid - 6]
    right = [item for item in items if item[0].x0 > mid + 6]
    if len(left) < 2 or len(right) < 2:
        return sorted(items, key=lambda item: (round(item[0].y0 / 3), item[0].x0)), False
    left_top, left_bottom = min(i[0].y0 for i in left), max(i[0].y1 for i in left)
    right_top, right_bottom = min(i[0].y0 for i in right), max(i[0].y1 for i in right)
    if min(left_bottom, right_bottom) <= max(left_top, right_top):
        return sorted(items, key=lambda item: (item[0].y0, item[0].x0)), False
    spanning = [item for item in items if item not in left and item not in right]
    spans = sorted(spanning, key=lambda item: item[0].y0)
    output = []
    remaining = left + right
    for span in spans:
        band = [item for item in remaining if item[0].y0 < span[0].y0 - 2]
        output.extend(sorted([item for item in band if item[0].x1 < mid], key=lambda item: item[0].y0))
        output.extend(sorted([item for item in band if item[0].x0 > mid], key=lambda item: item[0].y0))
        remaining = [item for item in remaining if item not in band]
        output.append(span)
    output.extend(sorted([item for item in remaining if item[0].x1 < mid], key=lambda item: item[0].y0))
    output.extend(sorted([item for item in remaining if item[0].x0 > mid], key=lambda item: item[0].y0))
    return output, True
