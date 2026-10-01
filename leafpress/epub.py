from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
from pathlib import Path
import re
import uuid
import zipfile

import pymupdf


CSS = """body { margin: 4%; line-height: 1.5; font-family: serif; }
h1, h2, h3 { line-height: 1.25; margin-top: 1.2em; }
p { margin: 0.65em 0; }
.illustration, .equation, .table-image { margin: 1em 0; text-align: center; }
img { max-width: 100%; height: auto; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #777; padding: 0.35em; vertical-align: top; }
th { font-weight: bold; }
pre { white-space: pre-wrap; font-family: monospace; }
.equation { text-align: center; }
.pagebreak { display: none; }
.preserved { margin: 0; }
.preserved img { width: 100%; }
"""


def clean_xml(text: str) -> str:
    return "".join(c for c in text if c in "\t\n\r" or
                   0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or
                   0x10000 <= ord(c) <= 0x10FFFF)


def esc(text: object) -> str:
    return html.escape(clean_xml(str(text)), quote=True)


def xhtml_document(title: str, body: str, language: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" '
            f'lang="{esc(language)}" xml:lang="{esc(language)}">'
            f'<head><title>{esc(title)}</title>'
            '<meta charset="utf-8"/>'
            '<link rel="stylesheet" type="text/css" href="../styles/book.css"/>'
            f'</head><body>{body}</body></html>')


@dataclass(frozen=True)
class Asset:
    name: str
    width: int
    height: int


class EpubWriter:
    """Write one page/asset at a time. Only small manifest records stay in RAM."""

    def __init__(self, path: Path, root: Path, quality: str):
        self.root = root
        self.quality = quality
        for directory in ("OEBPS/text", "OEBPS/images", "OEBPS/styles", "META-INF"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        self.archive = zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED,
                                       compresslevel=6, allowZip64=True)
        self.archive.writestr("mimetype", "application/epub+zip",
                             compress_type=zipfile.ZIP_STORED)
        self.assets: dict[str, Asset] = {}
        self.entries: list[dict] = []
        self._write("META-INF/container.xml", '<?xml version="1.0"?>'
                    '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                    '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                    'media-type="application/oebps-package+xml"/></rootfiles></container>')
        self._write("OEBPS/styles/book.css", CSS)

    def close(self) -> None:
        self.archive.close()

    def _write(self, name: str, content: str) -> None:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        self.archive.write(path, name)

    def render(self, page: pymupdf.Page, rect: pymupdf.Rect) -> Asset:
        rect = pymupdf.Rect(rect) & page.rect
        if rect.is_empty or rect.is_infinite:
            raise ValueError("A visual region has invalid bounds.")
        dpi, edge = {"compact": (120, 1600), "balanced": (160, 2400),
                     "sharp": (220, 3000)}[self.quality]
        scale = min(dpi / 72, edge / max(rect.width, rect.height),
                    (6_000_000 / max(1, rect.width * rect.height)) ** 0.5)
        colorspace = pymupdf.csGRAY if self.quality == "compact" else pymupdf.csRGB
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale),
                                 clip=rect, colorspace=colorspace, alpha=False, annots=True)
        data = pixmap.tobytes("png")
        digest = hashlib.sha256(data).hexdigest()
        existing = self.assets.get(digest)
        if existing:
            del pixmap, data
            return existing
        asset = Asset(f"img-{digest[:32]}.png", pixmap.width, pixmap.height)
        path = self.root / "OEBPS/images" / asset.name
        path.write_bytes(data)
        # PNG already has compressed pixels. Do not recompress it in the ZIP.
        self.archive.write(path, f"OEBPS/images/{asset.name}",
                           compress_type=zipfile.ZIP_STORED)
        self.assets[digest] = asset
        del pixmap, data
        return asset

    def figure(self, page: pymupdf.Page, rect: pymupdf.Rect, alt: str,
               css_class: str = "") -> str:
        asset = self.render(page, rect)
        display_width = max(1, round(rect.width * 96 / 72))
        return (f'<div class="{esc(css_class or "illustration")}"><img src="../images/{asset.name}" '
                f'width="{display_width}" alt="{esc(alt)}"/></div>')

    def add_page(self, number: int, label: str, title: str, xhtml: str) -> None:
        name = f"text/page-{number:05d}.xhtml"
        self._write(f"OEBPS/{name}", xhtml)
        self.entries.append({"page": number, "label": label, "title": title,
                             "href": name, "id": f"page-{number:05d}"})

    def finish(self, title: str, author: str, language: str, toc: list) -> None:
        by_page = {entry["page"]: entry for entry in self.entries}
        navigation = []
        seen = set()
        for level, caption, page in toc:
            if page in by_page and (page, caption) not in seen:
                navigation.append((by_page[page]["href"], caption))
                seen.add((page, caption))
        if not navigation:
            navigation = [(entry["href"], entry["title"]) for entry in self.entries]
        items = "".join(f'<li><a href="{esc(href)}">{esc(caption)}</a></li>'
                        for href, caption in navigation)
        page_items = "".join(
            f'<li><a href="{entry["href"]}#source-{entry["page"]}">{esc(entry["label"])}</a></li>'
            for entry in self.entries)
        nav = (f'<nav epub:type="toc" id="toc"><h1>{esc(title)}</h1><ol>{items}</ol></nav>'
               f'<nav epub:type="page-list" hidden="hidden"><h2>Source pages</h2><ol>{page_items}</ol></nav>')
        # nav.xhtml lives at the OEBPS root, so its stylesheet is one level nearer.
        nav_doc = xhtml_document(title, nav, language).replace("../styles/book.css", "styles/book.css")
        self._write("OEBPS/nav.xhtml", nav_doc)
        identifier = f"urn:uuid:{uuid.uuid4()}"
        ncx_items = "".join(
            f'<navPoint id="nav-{i}" playOrder="{i}"><navLabel><text>{esc(caption)}</text>'
            f'</navLabel><content src="{esc(href)}"/></navPoint>'
            for i, (href, caption) in enumerate(navigation, 1))
        self._write("OEBPS/toc.ncx", '<?xml version="1.0" encoding="utf-8"?>'
                    '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
                    f'<head><meta name="dtb:uid" content="{identifier}"/></head>'
                    f'<docTitle><text>{esc(title)}</text></docTitle><navMap>{ncx_items}</navMap></ncx>')
        pages = "".join(f'<item id="{entry["id"]}" href="{entry["href"]}" '
                        'media-type="application/xhtml+xml"/>' for entry in self.entries)
        assets = "".join(f'<item id="image-{i}" href="images/{asset.name}" media-type="image/png"/>'
                         for i, asset in enumerate(self.assets.values(), 1))
        spine = "".join(f'<itemref idref="{entry["id"]}"/>' for entry in self.entries)
        modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        creator = f'<dc:creator>{esc(author)}</dc:creator>' if author else ""
        self._write("OEBPS/content.opf", '<?xml version="1.0" encoding="utf-8"?>'
                    '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">'
                    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                    f'<dc:identifier id="book-id">{identifier}</dc:identifier>'
                    f'<dc:title>{esc(title)}</dc:title><dc:language>{esc(language)}</dc:language>{creator}'
                    f'<meta property="dcterms:modified">{modified}</meta></metadata><manifest>'
                    '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
                    '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
                    '<item id="css" href="styles/book.css" media-type="text/css"/>'
                    f'{pages}{assets}</manifest><spine toc="ncx">{spine}</spine></package>')
        (self.root / ".leafpress-preview").write_text("LeafPress preview v1\n", encoding="utf-8")


def validate_epub(path: Path) -> dict:
    """Local package sanity checks. For full conformance, also run EPUBCheck."""
    import posixpath
    import xml.etree.ElementTree as ET
    from urllib.parse import unquote, urlsplit

    with zipfile.ZipFile(path) as book:
        infos = book.infolist()
        if not infos or infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
            raise ValueError("EPUB mimetype must be the first entry, stored uncompressed.")
        if book.read("mimetype") != b"application/epub+zip" or infos[0].extra:
            raise ValueError("Invalid EPUB mimetype entry.")
        names = set(book.namelist())
        if len(names) != len(infos) or book.testzip() is not None:
            raise ValueError("Duplicate or damaged ZIP entries.")
        opf = ET.fromstring(book.read("OEBPS/content.opf"))
        ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
        manifest = opf.find("opf:manifest", ns)
        if manifest is None:
            raise ValueError("Missing EPUB manifest.")
        ids = {item.attrib["id"] for item in manifest}
        if len(ids) != len(manifest):
            raise ValueError("Duplicate EPUB manifest identifiers.")
        if not any("nav" in item.attrib.get("properties", "").split() for item in manifest):
            raise ValueError("Missing EPUB 3 navigation.")
        for item in manifest:
            if posixpath.normpath("OEBPS/" + item.attrib["href"]) not in names:
                raise ValueError("Missing EPUB resource: " + item.attrib["href"])
        spine = opf.find("opf:spine", ns)
        if spine is None or not len(spine) or any(item.attrib["idref"] not in ids for item in spine):
            raise ValueError("Invalid EPUB spine.")
        identifiers = {}
        for name in names:
            if name.endswith((".xhtml", ".opf", ".ncx", ".xml")):
                root = ET.fromstring(book.read(name))
                identifiers[name] = {item.attrib["id"] for item in root.iter() if "id" in item.attrib}
                del root
        for name in names:
            if not name.endswith(".xhtml"):
                continue
            root = ET.fromstring(book.read(name))
            for element in root.iter():
                for attribute in ("href", "src"):
                    reference = element.attrib.get(attribute)
                    if not reference:
                        continue
                    parts = urlsplit(reference)
                    if parts.scheme or parts.netloc:
                        raise ValueError("Unexpected external EPUB resource.")
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(parts.path))) if parts.path else name
                    if target not in names:
                        raise ValueError(f"Broken resource reference in {name}: {reference}")
                    if parts.fragment and target in identifiers and unquote(parts.fragment) not in identifiers[target]:
                        raise ValueError("Broken EPUB fragment: " + reference)
            del root
        return {"status": "passed", "kind": "local_structure_check", "entries": len(names),
                "spine_documents": len(spine), "full_epubcheck": False}
