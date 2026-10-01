from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile

import pymupdf

from leafpress.convert import convert
from leafpress.epub import validate_epub
from leafpress.model import Options
from leafpress.profiles import checked_preferences, preferences


XHTML = "{http://www.w3.org/1999/xhtml}"
PROJECT = Path(__file__).resolve().parents[1]


def make_link_fixture(path):
    with pymupdf.open() as doc:
        for _ in range(3):
            doc.new_page()
        page = doc[0]
        page.insert_text((50, 100), "Before CLICK_SECTION after this linked phrase.", fontsize=12)
        page.insert_text((50, 160), "Read WEBSITE and continue normally.", fontsize=12)
        page.insert_text((50, 220), "Go to EXCLUDED_SECTION on the third source page.", fontsize=12)
        page.insert_link({"kind": pymupdf.LINK_GOTO, "from": page.search_for("CLICK_SECTION")[0],
                         "page": 1, "to": pymupdf.Point(50, 250)})
        page.insert_link({"kind": pymupdf.LINK_URI, "from": page.search_for("WEBSITE")[0],
                         "uri": "https://example.org/guide?a=1&b=2#details"})
        page.insert_link({"kind": pymupdf.LINK_GOTO, "from": page.search_for("EXCLUDED_SECTION")[0],
                         "page": 2, "to": pymupdf.Point(50, 100)})
        page = doc[1]
        page.insert_text((50, 100), "FIRST_BLOCK stays above the actual target paragraph.", fontsize=12)
        page.insert_text((50, 250), "TARGET_BLOCK is the linked destination in this document.", fontsize=12)
        page.insert_text((50, 310), "RETURN_LINK goes back to the source reference.", fontsize=12)
        page.insert_link({"kind": pymupdf.LINK_GOTO, "from": page.search_for("RETURN_LINK")[0],
                         "page": 0, "to": pymupdf.Point(50, 100)})
        doc[2].insert_text((50, 100), "THIRD_BLOCK has enough extractable text for a reflowable page.", fontsize=12)
        doc.set_toc([[1, "Part One", 1], [2, "Linked section", 2], [1, "Part Two", 3]])
        doc.save(path)


class NavigationRegionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "links.pdf"
        self.output = self.root / "links.epub"
        make_link_fixture(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def markup(self, number):
        with zipfile.ZipFile(self.output) as book:
            return ET.fromstring(book.read(f"OEBPS/text/page-{number:05d}.xhtml"))

    def test_partial_text_links_and_precise_block_destination(self):
        report = convert(self.source, self.output)
        root = self.markup(1)
        anchors = list(root.iter(XHTML + "a"))
        self.assertEqual(["".join(a.itertext()) for a in anchors], ["CLICK_SECTION", "WEBSITE", "EXCLUDED_SECTION"])
        self.assertEqual(anchors[1].attrib["href"], "https://example.org/guide?a=1&b=2#details")
        target_id = anchors[0].attrib["href"].split("#")[1]
        body = self.markup(2).find(XHTML + "body")
        destination_index = next(i for i, element in enumerate(body) if element.attrib.get("id") == target_id)
        self.assertIn("TARGET_BLOCK", "".join(body[destination_index + 1].itertext()))
        self.assertEqual(report["totals"]["internal_links"], 3)
        self.assertEqual(report["totals"]["external_links"], 1)
        self.assertEqual(validate_epub(self.output)["status"], "passed")

    def test_page_selection_reports_omitted_destinations(self):
        report = convert(self.source, self.output, Options(pages="1-2"))
        anchors = list(self.markup(1).iter(XHTML + "a"))
        self.assertEqual(len(anchors), 2)
        self.assertEqual(report["totals"]["skipped_links"], 1)
        self.assertIn("outside selected pages", " ".join(report["pages"][0]["warnings"]))
        validate_epub(self.output)

    def test_preserved_page_links_remain_available(self):
        report = convert(self.source, self.output, Options(mode="preserve"))
        self.assertEqual(report["totals"]["internal_links"], 3)
        self.assertEqual(report["totals"]["external_links"], 1)
        root = self.markup(1)
        self.assertEqual(len(list(root.iter(XHTML + "img"))), 1)
        self.assertEqual(len(list(root.iter(XHTML + "a"))), 3)
        validate_epub(self.output)

    def test_disable_link_preservation(self):
        report = convert(self.source, self.output, Options(preserve_links=False))
        self.assertFalse(list(self.markup(1).iter(XHTML + "a")))
        self.assertEqual(report["totals"]["internal_links"], 0)
        self.assertIn("CLICK_SECTION", "".join(self.markup(1).itertext()))

    def test_bookmark_hierarchy_is_retained(self):
        convert(self.source, self.output)
        with zipfile.ZipFile(self.output) as book:
            nav = ET.fromstring(book.read("OEBPS/nav.xhtml"))
            first = nav.find(f"{XHTML}body/{XHTML}nav/{XHTML}ol/{XHTML}li")
            child = first.find(f"{XHTML}ol/{XHTML}li/{XHTML}a")
            self.assertEqual(child.text, "Linked section")
            ncx = ET.fromstring(book.read("OEBPS/toc.ncx"))
            ns = "{http://www.daisy.org/z3986/2005/ncx/}"
            self.assertIsNotNone(ncx.find(f"{ns}navMap/{ns}navPoint/{ns}navPoint"))

    def test_manual_region_keeps_partial_text_lines_whole(self):
        # Select a small part of a line; all intersected characters belong to
        # the crop, and the next paragraph still reflows once.
        region = [0.14, 0.1, .30, .125]
        report = convert(self.source, self.output, Options(page_regions={1: [region]}))
        root = self.markup(1)
        body = "".join(root.find(XHTML + "body").itertext())
        self.assertNotIn("Before", body)
        self.assertEqual(body.count("Read"), 1)
        self.assertEqual(report["pages"][0]["manual_regions"], 1)
        with pymupdf.open(self.source) as document:
            page = document[0]
            r = report["pages"][0]["region_bounds"][0]
            crop = pymupdf.Rect(r[0] * page.rect.width, r[1] * page.rect.height,
                               r[2] * page.rect.width, r[3] * page.rect.height)
            original_line = page.search_for("Before CLICK_SECTION after this linked phrase.")[0]
            self.assertLessEqual(crop.x0, original_line.x0 + 1e-5)
            self.assertGreaterEqual(crop.x1, original_line.x1 - 1e-5)
            self.assertLessEqual(crop.y0, original_line.y0 + 1e-5)
            self.assertGreaterEqual(crop.y1, original_line.y1 - 1e-5)
        self.assertEqual(len([e for e in root.iter() if e.attrib.get("class") == "manual-region"]), 1)
        self.assertEqual(report["totals"]["internal_links"], 3)
        validate_epub(self.output)

    def test_manual_table_crop_preserves_grid_without_duplicate_content(self):
        report = convert(PROJECT / "examples/conversion-lab.pdf", self.output,
                         Options(page_regions={2: [[.15, .29, .7, .45]]}))
        root = self.markup(2)
        self.assertFalse(list(root.iter(XHTML + "table")))
        self.assertEqual(report["pages"][1]["manual_regions"], 1)
        self.assertIn("TABLE_END_MARKER", "".join(root.itertext()))
        self.assertNotIn("Notebook", "".join(root.itertext()))
        with pymupdf.open(PROJECT / "examples/conversion-lab.pdf") as document:
            page = document[1]
            table = pymupdf.Rect(page.find_tables(strategy="lines_strict").tables[0].bbox)
            r = report["pages"][1]["region_bounds"][0]
            self.assertLessEqual(r[0] * page.rect.width, table.x0)
            self.assertGreaterEqual(r[2] * page.rect.width, table.x1)
            self.assertLessEqual(r[1] * page.rect.height, table.y0)
            self.assertGreaterEqual(r[3] * page.rect.height, table.y1)

    def test_overlapping_regions_merge(self):
        report = convert(self.source, self.output,
                         Options(page_regions={1: [[.1, .1, .4, .125], [.2, .11, .5, .13]]}))
        self.assertEqual(report["pages"][0]["manual_regions"], 1)

    def test_invalid_regions_are_rejected_before_publication(self):
        for region in ([0, 0, 2, 1], [.5, 0, .2, 1], [0, 0, float("nan"), 1], [0, 0, True, 1]):
            with self.subTest(region=region), self.assertRaises(ValueError):
                convert(self.source, self.output, Options(page_regions={1: [region]}))
            self.assertFalse(self.output.exists())
        with self.assertRaises(ValueError):
            convert(self.source, self.output, Options(page_regions={5: [[0, 0, 1, 1]]}))

    def test_external_anchors_allowed_but_remote_assets_rejected(self):
        convert(self.source, self.output)
        with zipfile.ZipFile(self.output) as book:
            entries = [(info, book.read(info.filename)) for info in book.infolist()]
        bad = self.root / "bad.epub"
        for replacement in ('<img src="https://example.org/image.png" alt="remote"/>',
                            '<a href="javascript:alert(1)">Invalid</a>'):
            with zipfile.ZipFile(bad, "w") as book:
                for info, content in entries:
                    if info.filename == "OEBPS/text/page-00001.xhtml":
                        content = content.replace(b"</body>", replacement.encode() + b"</body>")
                    book.writestr(info, content)
            with self.assertRaisesRegex(ValueError, "external EPUB resource"):
                validate_epub(bad)

    def test_profiles_do_not_include_document_specific_edits(self):
        values = preferences(Options(title="Private title", pages="2", page_modes={2: "preserve"},
                                     page_regions={2: [[0, 0, 1, 1]]}, quality="compact"))
        self.assertEqual(values["quality"], "compact")
        self.assertNotIn("title", values)
        self.assertNotIn("page_regions", values)
        self.assertEqual(checked_preferences(values), values)
        with self.assertRaises(ValueError):
            checked_preferences({"quality": "wrong"})


if __name__ == "__main__":
    unittest.main()
