"""Translate PDF link annotations into portable XHTML links.

Only link/destination metadata is kept between pages. Raster content uses an
ordinary adjacent link list rather than reader-dependent clickable overlays.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import pymupdf

from .epub import esc


def allowed_uri(uri: str) -> bool:
    if not isinstance(uri, str) or any(ord(c) < 32 or c.isspace() for c in uri):
        return False
    try:
        parts = urlsplit(uri)
        return (parts.scheme.lower() in {"http", "https"} and bool(parts.hostname) or
                parts.scheme.lower() == "mailto" and bool(parts.path))
    except ValueError:
        return False


@dataclass
class SourceLink:
    rect: pymupdf.Rect
    href: str
    kind: str
    label: str


class LinkMap:
    def __init__(self, document, selected, cancelled):
        self.pages: dict[int, list[SourceLink]] = {}
        self.targets: dict[int, list[tuple[str, pymupdf.Point]]] = {}
        self.skipped: dict[int, int] = {}
        selected_set = set(selected)
        destinations = {}
        for index in selected:
            cancelled()
            page = document[index]
            links = []
            skipped = 0
            for annotation in page.get_links():
                rect = pymupdf.Rect(annotation["from"])
                kind = annotation["kind"]
                href = ""
                if kind == pymupdf.LINK_GOTO and annotation.get("page") in selected_set:
                    target_page = annotation["page"] + 1
                    point = pymupdf.Point(annotation.get("to", (0, 0)))
                    key = (target_page, round(point.x, 2), round(point.y, 2))
                    anchor = destinations.get(key)
                    if anchor is None:
                        anchor = f"destination-{len(destinations) + 1}"
                        destinations[key] = anchor
                        self.targets.setdefault(target_page, []).append((anchor, point))
                    href = f"page-{target_page:05d}.xhtml#{anchor}"
                    label = f"Go to source page {target_page}"
                    name = "internal"
                elif kind == pymupdf.LINK_URI and allowed_uri(annotation.get("uri", "")):
                    href = annotation["uri"]
                    label = href
                    name = "external"
                if not href:
                    skipped += 1
                    continue
                caption = page.get_textbox(rect).strip()
                links.append(SourceLink(rect, href, name, caption[:160] or label))
            if links:
                self.pages[index + 1] = links
            if skipped:
                self.skipped[index + 1] = skipped
            del page
            pymupdf.TOOLS.store_shrink(100)

    def for_page(self, number: int) -> PageLinks:
        return PageLinks(self.pages.get(number, []), self.targets.get(number, []),
                         self.skipped.get(number, 0))


class PageLinks:
    def __init__(self, links=(), targets=(), skipped=0):
        self.links = list(links)
        self.targets = list(targets)
        self.skipped = skipped
        self.used = set()

    def reset(self):
        self.used.clear()

    def inline(self, span: dict, format_text) -> str:
        chars = span.get("chars")
        if not self.links or not chars:
            return format_text(span["text"])
        groups = []
        for char in chars:
            rect = pymupdf.Rect(char["bbox"])
            center = (rect.tl + rect.br) / 2
            match = next((i for i, link in enumerate(self.links) if center in link.rect), None)
            if groups and groups[-1][0] == match:
                groups[-1][1] += char["c"]
            else:
                groups.append([match, char["c"]])
        output = []
        for index, text in groups:
            content = format_text(text)
            if index is not None and text.strip():
                self.used.add(index)
                content = f'<a href="{esc(self.links[index].href)}">{content}</a>'
            output.append(content)
        return "".join(output)

    def decorate(self, items: list, result) -> list:
        output = list(items)
        for anchor, point in self.targets:
            if not output:
                break
            def distance(item):
                rect = item[0]
                # Point-to-rectangle distance respects columns and image blocks.
                return max(rect.x0 - point.x, point.x - rect.x1, 0) ** 2 + max(
                    rect.y0 - point.y, point.y - rect.y1, 0) ** 2
            closest = min(range(len(output)), key=lambda i: distance(output[i]))
            rect, content = output[closest]
            output[closest] = (rect, f'<span id="{anchor}"></span>' + content)
        for index, link in enumerate(self.links):
            if index not in self.used:
                # Place unresolved sources at their source position. A table or
                # preserved image remains intact and has an adjacent link list.
                content = (f'<p class="source-link"><a href="{esc(link.href)}">'
                           f'{esc(link.label)}</a></p>')
                output.append((link.rect, content))
                self.used.add(index)
        result.internal_links = sum(link.kind == "internal" for link in self.links)
        result.external_links = sum(link.kind == "external" for link in self.links)
        result.skipped_links = self.skipped
        if self.skipped:
            result.warnings.append(f"{self.skipped} PDF links skipped: unsupported action, invalid destination, or target outside selected pages.")
        return output
