"""Build an original, redistributable conversion fixture. Requires .[demo]."""
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle


def build_demo(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    c.setTitle("LeafPress conversion lab")
    c.setAuthor("LeafPress")
    width, height = A4
    # Symbol cannot encode ordinary Latin x reliably. A regular font is a safe
    # fallback; Cambria Math is used if the optional font is available locally.
    math_font = "Helvetica"
    candidates = [Path("/usr/share/fonts/truetype/dejavu/DejaVuMathTeXGyre.ttf"),
                  Path("C:/Windows/Fonts/cambria.ttc")]
    for font_path in candidates:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont("DemoMath", str(font_path)))
                math_font = "DemoMath"
                break
            except Exception:
                pass

    def frame(number, title, page_size=A4):
        c.setPageSize(page_size)
        w, h = page_size
        c.setFillColor(colors.HexColor("#486663"))
        c.setFont("Helvetica", 9)
        c.drawString(48, h - 33, "LEAFPRESS / CONVERSION LAB")
        c.drawRightString(w - 48, 30, f"Page {number} of 7")
        c.setFillColor(colors.HexColor("#1e4740"))
        c.setFont("Helvetica-Bold", 23)
        c.drawString(48, h - 92, title)
        c.bookmarkPage(f"page{number}")
        c.addOutlineEntry(title, f"page{number}", 0)
        c.setFillColor(colors.HexColor("#233b41"))

    def paragraph(text, x=48, y=height - 135, chars=83, font="Helvetica", size=11):
        text_object = c.beginText(x, y)
        text_object.setFont(font, size)
        text_object.setLeading(17)
        for line in textwrap.wrap(text, width=chars):
            text_object.textLine(line)
        c.drawText(text_object)
        return y - 17 * len(textwrap.wrap(text, width=chars))

    def table(data, widths, y, spans=()):
        t = Table(data, colWidths=widths, rowHeights=[34] * len(data))
        styles = [("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#6b827b")),
                  ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e1eee7")),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                  ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                  ("FONTSIZE", (0, 0), (-1, -1), 10),
                  ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#223d35")),
                  ("LEFTPADDING", (0, 0), (-1, -1), 10),
                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
        styles.extend(("SPAN", start, end) for start, end in spans)
        t.setStyle(TableStyle(styles))
        _, th = t.wrap(500, 500)
        t.drawOn(c, 48, y - th)
        return y - th

    frame(1, "A readable page")
    y = paragraph("This document is an original test fixture for LeafPress. The paragraphs on this page should remain adjustable text in the EPUB. Change the reader font size to check that sentences wrap naturally.")
    y = paragraph("The following pages exercise simple tables, merged cells, mathematical notation, vector diagrams, columns, a scanned page, and a slide. This is a controlled sample; real PDFs will have more varied layouts.", y=y - 28)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(48, y - 38, "What to inspect")
    paragraph("Check the order of paragraphs, table rows and columns, equation shapes, diagram labels, and the distinction between image text and adjustable text. No content in this fixture depends on an online service.", y=y - 65)
    c.showPage()

    frame(2, "A simple table")
    paragraph("A reliable grid should become an HTML table. Each value must stay in the correct row and column. The paragraph below the table must follow it in reading order.")
    bottom = table([["Material", "Quantity", "Unit"], ["Notebook", "12", "pieces"],
                    ["Pencil", "24", "pieces"], ["Paper", "3", "packs"], ["Ink", "2", "bottles"]],
                   [210, 130, 155], height - 230)
    paragraph("TABLE_END_MARKER. The table is complete; this paragraph follows all five rows. The EPUB should contain each product name only once.", y=bottom - 45)
    c.showPage()

    frame(3, "Merged cells need care")
    paragraph("A merged header should keep its original appearance. In the first prototype this table uses a cropped image rather than guessing a grid that could lose the merge.")
    bottom = table([["Quarterly allocation", "", ""], ["Department", "Budget", "Owner"],
                    ["Research", "12000", "Ada"], ["Operations", "18000", "Lin"]],
                   [210, 130, 155], height - 225, spans=[((0, 0), (2, 0))])
    paragraph("MERGED_END_MARKER. Text around the complex table should still be adjustable.", y=bottom - 45)
    c.showPage()

    frame(4, "Equations and diagrams")
    paragraph("Mathematical notation should preserve baselines, superscripts, and fraction bars. The process diagram below must retain its arrows and labels.")
    c.setFillColor(colors.HexColor("#213e37"))
    c.setFont("Helvetica", 20)
    c.drawString(175, height - 245, "x")
    c.setFont("Helvetica", 12)
    c.drawString(186, height - 235, "2")
    c.setFont("Helvetica", 20)
    c.drawString(198, height - 245, "+ y")
    c.setFont("Helvetica", 12)
    c.drawString(235, height - 235, "2")
    c.setFont("Helvetica", 20)
    c.drawString(247, height - 245, "= r")
    c.setFont("Helvetica", 12)
    c.drawString(281, height - 235, "2")
    c.setFont("Helvetica", 20)
    c.drawString(153, height - 326, "f(x) =")
    c.setFont(math_font, 18)
    c.drawString(251, height - 309, "x + 1")
    c.drawString(249, height - 339, "2x + 3")
    c.setStrokeColor(colors.HexColor("#294d42"))
    c.setLineWidth(1.2)
    c.line(239, height - 316, 326, height - 316)
    boxes = [(70, "Read PDF"), (242, "Reconstruct"), (414, "Write EPUB")]
    y = height - 540
    for x, caption in boxes:
        c.setFillColor(colors.HexColor("#e5f2eb"))
        c.roundRect(x, y, 114, 60, 7, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#294d42"))
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x + 57, y + 27, caption)
    for start, end in [(184, 242), (356, 414)]:
        c.line(start, y + 30, end - 6, y + 30)
        arrow = c.beginPath()
        arrow.moveTo(end, y + 30)
        arrow.lineTo(end - 9, y + 35)
        arrow.lineTo(end - 9, y + 25)
        arrow.close()
        c.drawPath(arrow, stroke=1, fill=1)
    paragraph("DIAGRAM_END_MARKER. The diagram and formulas should appear once, with normal text continuing here.", y=y - 55)
    c.showPage()

    frame(5, "Two columns, one reading order")
    for x, prefix in [(48, "LEFT"), (322, "RIGHT")]:
        y = height - 145
        for number in range(1, 5):
            y = paragraph(f"{prefix}_{number}. This paragraph belongs to the {prefix.lower()} column. Read every paragraph in the left column before starting the right column.",
                          x=x, y=y, chars=34)
            y -= 20
    c.showPage()

    frame(6, "A scanned page")
    image = Image.new("RGB", (1100, 1260), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 34)
        heading = ImageFont.truetype("DejaVuSans.ttf", 46)
    except OSError:
        font = ImageFont.load_default()
        heading = font
    draw.text((60, 60), "A simulated scan", fill="#23483f", font=heading)
    for line_number, text in enumerate(["These words exist only inside an image.",
                                       "Version 0.1 preserves this page visually.",
                                       "OCR can be added after the layout engine", "has been tested on real documents."]):
        draw.text((60, 170 + line_number * 62), text, fill="#2b3634", font=font)
    draw.rectangle((60, 500, 1040, 850), outline="#6d827b", width=3)
    draw.line((60, 610, 1040, 610), fill="#6d827b", width=3)
    draw.line((600, 500, 600, 850), fill="#6d827b", width=3)
    draw.text((85, 530), "Original shapes", fill="#2b3634", font=font)
    draw.text((625, 530), "Stay in place", fill="#2b3634", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    c.drawImage(ImageReader(buffer), 48, 85, width=495, height=565)
    c.showPage()

    page_size = landscape(A4)
    frame(7, "A slide should remain a slide", page_size)
    w, h = page_size
    for x, caption, text in [(48, "TEXT", "Adjustable paragraphs"),
                              (306, "TABLES", "Grid or visual fallback"),
                              (564, "IMAGES", "Bounded resolution")]:
        c.setFillColor(colors.HexColor("#e2efe7"))
        c.roundRect(x, 180, 228, 220, 8, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#23574b"))
        c.setFont("Helvetica-Bold", 19)
        c.drawString(x + 22, 337, caption)
        c.setFont("Helvetica", 14)
        c.drawString(x + 22, 285, text)
    c.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=Path("examples/conversion-lab.pdf"))
    build_demo(parser.parse_args().output)
