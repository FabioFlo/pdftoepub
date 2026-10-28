"""Synthetic regressions for prose false positives and split ruled tables."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import pymupdf

from pdftoepub.convert import convert
from pdftoepub.model import Options


XHTML = "{http://www.w3.org/1999/xhtml}"


class TableDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.pdf"
        self.output = self.root / "output.epub"

    def tearDown(self):
        self.temp.cleanup()

    def markup(self, number=1):
        with zipfile.ZipFile(self.output) as book:
            return ET.fromstring(book.read(f"OEBPS/text/page-{number:05d}.xhtml"))

    def test_borderless_detection_keeps_aligned_prose_adjustable(self):
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((72, 90), "Adjustable prose", fontsize=18)
            for row in range(12):
                page.insert_text((72, 135 + row * 20),
                                 "Ordinary paragraphs contain words with regular spaces between them.", fontsize=11)
            # Confirm this exercises the text detector, rather than a page on
            # which the underlying engine never finds a phantom table.
            self.assertTrue(page.find_tables(strategy="text").tables)
            doc.save(self.source)
        report = convert(self.source, self.output, Options(detect_borderless=True))
        body = self.markup().find(XHTML + "body")
        self.assertEqual("".join(body.itertext()).count("Ordinary paragraphs"), 12)
        self.assertFalse(list(body.iter(XHTML + "img")))
        self.assertEqual(report["totals"]["table_images"], 0)
        self.assertFalse(any("borderless" in w for w in report["pages"][0]["warnings"]))

    def test_genuine_borderless_columns_still_get_visual_fallback(self):
        with pymupdf.open() as doc:
            page = doc.new_page()
            for row, values in enumerate([("Material", "Quantity", "Unit"),
                                           ("Notebook", "12", "pieces"),
                                           ("Pencil", "24", "pieces"),
                                           ("Paper", "3", "packs")]):
                for x, text in zip((60, 260, 420), values):
                    page.insert_text((x, 140 + 30 * row), text, fontsize=11)
            doc.save(self.source)
        report = convert(self.source, self.output, Options(detect_borderless=True))
        self.assertEqual(report["totals"]["table_images"], 1)
        self.assertTrue(any("borderless" in w for w in report["pages"][0]["warnings"]))

    def test_separate_symbol_bullets_stay_with_adjustable_list_text(self):
        from reportlab.pdfgen import canvas
        document = canvas.Canvas(str(self.source), pagesize=(595, 842))
        document.setFont("Helvetica", 11)
        document.drawString(72, 702, "A paragraph before the list of ordinary prose items.")
        document.drawString(92, 662, "FIRST_ITEM remains adjustable, including its list marker.")
        document.drawString(92, 622, "SECOND_ITEM remains below the first one.")
        # Both markers occur after the paragraph blocks in PDF order. ReportLab
        # supplies the Symbol bullet's Unicode map, as in the source document.
        document.setFont("Symbol", 11)
        document.drawString(75, 662, "•")
        document.drawString(75, 622, "•")
        document.save()
        report = convert(self.source, self.output, Options(detect_borderless=True))
        body = self.markup().find(XHTML + "body")
        text = " ".join(body.itertext())
        self.assertIn("•FIRST_ITEM", text)
        self.assertIn("•SECOND_ITEM", text)
        self.assertEqual(report["totals"]["equation_images"], 0)
        self.assertFalse(list(body.iter(XHTML + "img")))

    def test_split_table_header_and_continuation_both_reflow(self):
        with pymupdf.open() as doc:
            page = doc.new_page()
            for y in (200, 230, 270, 310):
                page.draw_line((50, y), (540, y))
            for x in (50, 540):
                page.draw_line((x, 200), (x, 310))
            # The middle rule is missing only from the header, as in a
            # Word-exported table. The two headings are clearly separated.
            page.draw_line((200, 230), (200, 310))
            for x, y, text in [(65, 220, "Question"), (215, 220, "Answer"),
                                (65, 250, "FIRST_QUESTION"), (215, 250, "FIRST_ANSWER"),
                                (65, 290, "SPLIT_QUESTION"), (215, 290, "COMPLETE_ANSWER")]:
                page.insert_text((x, y), text, fontsize=11)
            page = doc.new_page()
            for y in (70, 110, 160):
                page.draw_line((50, y), (540, y))
            for x in (50, 200, 540):
                page.draw_line((x, 70), (x, 160))
            page.insert_text((65, 90), "REMAINDER", fontsize=10)
            page.insert_text((65, 130), "NEXT_QUESTION", fontsize=11)
            page.insert_text((215, 130), "Wrapped answer continues", fontsize=11)
            page.insert_text((215, 150), "on its next source line.", fontsize=11)
            doc.save(self.source)
        report = convert(self.source, self.output, Options(detect_borderless=True))
        self.assertEqual([p["html_tables"] for p in report["pages"]], [1, 1])
        self.assertEqual(report["totals"]["table_images"], 0)
        first = self.markup(1).find(".//" + XHTML + "table")
        self.assertEqual(["".join(cell.itertext()) for cell in first[0]], ["Question", "Answer"])
        second = self.markup(2).find(".//" + XHTML + "table")
        self.assertEqual([cell.tag for cell in second[0]], [XHTML + "td", XHTML + "td"])
        self.assertEqual(["".join(cell.itertext()) for cell in second[0]], ["REMAINDER", ""])
        self.assertEqual("".join(second[1][1].itertext()), "Wrapped answer continues on its next source line.")
        self.assertFalse(list(second.iter(XHTML + "br")))


if __name__ == "__main__":
    unittest.main()
