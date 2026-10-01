from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

import pymupdf

from leafpress.convert import ConversionCancelled, convert
from leafpress.epub import validate_epub
from leafpress.model import Options, select_pages


PROJECT = Path(__file__).resolve().parents[1]
DEMO = PROJECT / "examples/conversion-lab.pdf"
XHTML = "{http://www.w3.org/1999/xhtml}"


def body_text(path: Path, page: int) -> str:
    with zipfile.ZipFile(path) as book:
        root = ET.fromstring(book.read(f"OEBPS/text/page-{page:05d}.xhtml"))
        return " ".join(root.find(XHTML + "body").itertext())


class ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.book = cls.root / "lab.epub"
        cls.report = convert(DEMO, cls.book, Options(language="en"), preview=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_epub_package_and_navigation(self):
        result = validate_epub(self.book)
        self.assertEqual(result["spine_documents"], 7)
        with zipfile.ZipFile(self.book) as book:
            nav = ET.fromstring(book.read("OEBPS/nav.xhtml"))
            links = [e.attrib["href"] for e in nav.iter(XHTML + "a")]
            self.assertIn("text/page-00007.xhtml#source-7", links)

    def test_simple_table_retains_exact_cell_mapping(self):
        with zipfile.ZipFile(self.book) as book:
            root = ET.fromstring(book.read("OEBPS/text/page-00002.xhtml"))
            table = root.find(".//" + XHTML + "table")
            self.assertIsNotNone(table)
            rows = [["".join(cell.itertext()) for cell in row] for row in table]
            self.assertEqual(rows, [["Material", "Quantity", "Unit"],
                                    ["Notebook", "12", "pieces"], ["Pencil", "24", "pieces"],
                                    ["Paper", "3", "packs"], ["Ink", "2", "bottles"]])
            body = " ".join(root.find(XHTML + "body").itertext())
            self.assertEqual(body.count("Notebook"), 1)
            self.assertLess(body.index("bottles"), body.index("TABLE_END_MARKER"))

    def test_merged_table_preserves_visual_layout(self):
        result = self.report["pages"][2]
        self.assertEqual(result["html_tables"], 0)
        self.assertEqual(result["table_images"], 1)
        self.assertIn("MERGED_END_MARKER", body_text(self.book, 3))

    def test_equations_and_arrows_appear_once(self):
        result = self.report["pages"][3]
        self.assertEqual(result["equation_images"], 2)
        self.assertEqual(result["images"], 1)  # One connected diagram, including arrows.
        with zipfile.ZipFile(self.book) as book:
            root = ET.fromstring(book.read("OEBPS/text/page-00004.xhtml"))
            equation_blocks = [element for element in root.iter() if element.attrib.get("class") == "equation"]
            fraction = equation_blocks[1].find(XHTML + "img")
            self.assertIn("f(x) =", fraction.attrib["alt"])
            self.assertIn("x + 1", fraction.attrib["alt"])
            self.assertIn("2x + 3", fraction.attrib["alt"])
            self.assertNotIn("x + 1", body_text(self.book, 4))

    def test_column_order_is_left_then_right(self):
        text = body_text(self.book, 5)
        labels = [f"LEFT_{i}" for i in range(1, 5)] + [f"RIGHT_{i}" for i in range(1, 5)]
        positions = [text.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertTrue(self.report["pages"][4]["warnings"])

    def test_scan_and_slide_are_preserved_and_flagged(self):
        for index in [5, 6]:
            self.assertEqual(self.report["pages"][index]["mode"], "preserve")
            self.assertTrue(self.report["pages"][index]["warnings"])

    def test_wrapped_lines_are_one_paragraph(self):
        with zipfile.ZipFile(self.book) as book:
            root = ET.fromstring(book.read("OEBPS/text/page-00002.xhtml"))
            paragraphs = list(root.iter(XHTML + "p"))
            self.assertIn("row and column", " ".join(paragraphs[0].itertext()))

    def test_word_style_leading_and_first_line_indent_reflow(self):
        source = self.root / "spaced-paragraph.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((72, 120), "LONG_PARAGRAPH_MARKER. This sentence continues onto the next line without", fontsize=11)
            page.insert_text((48, 144), "losing its flow when converted into an EPUB.", fontsize=11)
            page.insert_text((72, 182), "NEXT_PARAGRAPH_MARKER. A blank line separates this paragraph.", fontsize=11)
            document.save(source)
        output = self.root / "spaced-paragraph.epub"
        convert(source, output)
        with zipfile.ZipFile(output) as book:
            root = ET.fromstring(book.read("OEBPS/text/page-00001.xhtml"))
            paragraphs = list(root.iter(XHTML + "p"))
            self.assertEqual(len(paragraphs), 2)
            self.assertIn("losing its flow", " ".join(paragraphs[0].itertext()))
            self.assertIn("NEXT_PARAGRAPH_MARKER", " ".join(paragraphs[1].itertext()))

    def test_preview_and_full_conversion_use_same_margin_rules(self):
        output = self.root / "single.epub"
        report = convert(DEMO, output, Options(pages="2"))
        self.assertEqual(report["converted_pages"], 1)
        self.assertNotIn("LEAFPRESS / CONVERSION LAB", body_text(output, 2))
        self.assertEqual(report["pages"][0]["removed_margin_lines"], self.report["pages"][1]["removed_margin_lines"])

    def test_page_override_and_original_page_numbers(self):
        output = self.root / "override.epub"
        report = convert(DEMO, output, Options(pages="2,5", page_modes={2: "preserve"}))
        self.assertEqual([p["page"] for p in report["pages"]], [2, 5])
        self.assertEqual(report["pages"][0]["mode"], "preserve")
        self.assertEqual(report["pages"][1]["mode"], "hybrid")
        self.assertEqual(validate_epub(output)["spine_documents"], 2)

    def test_image_tables_option(self):
        report = convert(DEMO, self.root / "tables.epub", Options(pages="2", table_mode="image"))
        self.assertEqual(report["totals"]["html_tables"], 0)
        self.assertEqual(report["totals"]["table_images"], 1)

    def test_keep_margins_option(self):
        output = self.root / "margins.epub"
        convert(DEMO, output, Options(pages="2", remove_margins=False))
        self.assertIn("LEAFPRESS / CONVERSION LAB", body_text(output, 2))

    def test_repeated_footer_image_removed_but_distinct_image_kept(self):
        source = self.root / "footer-images.pdf"
        with pymupdf.open() as document:
            for index in range(4):
                page = document.new_page(width=595, height=842)
                page.insert_text((48, 120), "An ordinary paragraph with enough adjustable text for this test.")
                icon = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 12, 12), False)
                icon.clear_with(80 if index < 3 else 160)
                page.insert_image(pymupdf.Rect(48, 770, 72, 794), stream=icon.tobytes("png"))
            document.save(source)
        report = convert(source, self.root / "footer-images.epub")
        self.assertEqual([p["removed_margin_images"] for p in report["pages"]], [1, 1, 1, 0])
        self.assertEqual(report["pages"][3]["images"], 1)
        kept = convert(source, self.root / "footer-images-kept.epub", Options(remove_margins=False))
        self.assertEqual(kept["totals"]["removed_margin_images"], 0)
        self.assertEqual(kept["totals"]["images"], 4)

    def test_repeated_images_are_reused(self):
        source = self.root / "repeated.pdf"
        with pymupdf.open(DEMO) as original, pymupdf.open() as repeat:
            for _ in range(3):
                repeat.insert_pdf(original, from_page=0, to_page=0)
            repeat.save(source)
        report = convert(source, self.root / "repeated.epub", Options(mode="preserve"))
        self.assertEqual(report["unique_images"], 1)
        self.assertEqual(report["preserved_pages"], 3)

    def test_metadata_is_escaped_and_invalid_xml_characters_removed(self):
        output = self.root / "metadata.epub"
        convert(DEMO, output, Options(pages="1", title="A & B <tag>\x01", author="An <Author>"))
        with zipfile.ZipFile(output) as book:
            root = ET.fromstring(book.read("OEBPS/content.opf"))
            title = root.find(".//{http://purl.org/dc/elements/1.1/}title")
            self.assertEqual(title.text, "A & B <tag>")

    def test_cancel_keeps_existing_book_and_sidecars(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "kept.epub"
            convert(DEMO, output, Options(pages="1"), preview=True)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            cancel = root / "cancel"

            def progress(event):
                if event["type"] == "page":
                    cancel.touch()

            with self.assertRaises(ConversionCancelled):
                convert(DEMO, output, overwrite=True, preview=True, cancel_file=cancel, progress=progress)
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and p != cancel}
            self.assertEqual(before, after)
            self.assertFalse(list(root.glob(".leafpress-*")))

    def test_cancel_during_sidecar_install_rolls_back(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "transaction.epub"
            convert(DEMO, output, Options(pages="1"), preview=True)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            cancel = root / "cancel"
            real_replace = os.replace

            def replace(source, destination):
                result = real_replace(source, destination)
                if Path(source).name == "report.json":
                    cancel.touch()
                return result

            with patch("leafpress.convert.os.replace", side_effect=replace):
                with self.assertRaises(ConversionCancelled):
                    convert(DEMO, output, Options(pages="2"), overwrite=True, preview=True, cancel_file=cancel)
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and p != cancel}
            self.assertEqual(before, after)

    def test_refuse_overwrite_and_unowned_preview(self):
        with self.assertRaises(FileExistsError):
            convert(DEMO, self.book)
        output = self.root / "unowned.epub"
        output.with_suffix(".preview").mkdir()
        with self.assertRaises(ValueError):
            convert(DEMO, output, preview=True, overwrite=True)

    def test_rotated_page_keeps_visual_orientation(self):
        source = self.root / "rotated.pdf"
        with pymupdf.open(DEMO) as original, pymupdf.open() as document:
            document.insert_pdf(original, from_page=1, to_page=1)
            document[0].set_rotation(90)
            document.save(source)
        report = convert(source, self.root / "rotated.epub")
        self.assertEqual(report["pages"][0]["mode"], "preserve")

    def test_invalid_ranges_and_inputs_do_not_create_output(self):
        for value in ["0", "8", "5-2", "a", "2,", "1-20"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                select_pages(value, 7)
        self.assertEqual(select_pages("3,1-3,7", 7), [0, 1, 2, 6])
        output = self.root / "invalid.epub"
        with self.assertRaises(ValueError):
            convert(DEMO, output, Options(pages="999"))
        self.assertFalse(output.exists())

    def test_validator_rejects_broken_image_reference(self):
        output = self.root / "broken.epub"
        with zipfile.ZipFile(self.book) as source, zipfile.ZipFile(output, "w") as target:
            for entry in source.infolist():
                data = source.read(entry.filename)
                if entry.filename == "OEBPS/text/page-00004.xhtml":
                    data = data.replace(b"../images/img-", b"../images/missing-", 1)
                target.writestr(entry, data)
        with self.assertRaises(ValueError):
            validate_epub(output)


if __name__ == "__main__":
    unittest.main()
