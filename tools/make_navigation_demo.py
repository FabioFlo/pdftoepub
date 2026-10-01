"""Create an original PDF fixture with real link annotations and bookmarks."""
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


def build(path):
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    c.setTitle("LeafPress - Navigation lab")
    c.setAuthor("LeafPress")
    width, height = A4
    ink, accent = HexColor("#243b43"), HexColor("#216e62")

    def heading(title, number, size=A4):
        c.setPageSize(size)
        w, h = size
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(48, h - 42, "LEAFPRESS / NAVIGATION LAB")
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 24)
        c.drawString(48, h - 88, title)
        c.setFont("Helvetica", 10)
        c.drawString(48, 32, f"Original test document / source page {number}")

    def text(value, y, x=48):
        c.setFillColor(ink)
        c.setFont("Helvetica", 12)
        c.drawString(x, y, value)

    def internal(value, target, y):
        c.setFont("Helvetica", 12)
        c.setFillColor(accent)
        c.drawString(48, y, value)
        c.linkAbsolute(value, target, Rect=(48, y - 3, 48 + c.stringWidth(value, "Helvetica", 12), y + 13), thickness=0)

    def external(value, y):
        c.setFont("Helvetica", 12)
        c.setFillColor(accent)
        c.drawString(48, y, value)
        c.linkURL("https://github.com/FabioFlo/leafpress", (48, y - 3, 48 + c.stringWidth(value, "Helvetica", 12), y + 13), thickness=0)

    heading("Follow the original PDF links", 1)
    c.bookmarkPage("start", fit="XYZ", left=48, top=height - 88, zoom=0)
    c.addOutlineEntry("Reading and navigation", "start", 0)
    text("This PDF contains clickable internal references and a website link.", height - 140)
    text("LeafPress v0.2 should preserve these links in the converted EPUB.", height - 162)
    internal("Read the linked section on source page 2", "section-two", height - 218)
    internal("Read note 1 near the bottom of source page 2", "note-one", height - 256)
    external("Visit the LeafPress project website", height - 294)
    text("Use the contents menu to check the nested chapter outline.", height - 358)
    text("If you export only this page, missing internal targets are reported.", height - 380)
    c.showPage()

    heading("The linked section", 2)
    c.bookmarkPage("section-two", fit="XYZ", left=48, top=height - 88, zoom=0)
    c.addOutlineEntry("Linked section", "section-two", 1)
    text("This paragraph is the destination of the first internal reference.", height - 140)
    text("Text stays adjustable. Navigation points to a reconstructed block.", height - 162)
    internal("Return to the reference on source page 1", "start", height - 218)
    c.setStrokeColor(HexColor("#ccd9d3"))
    c.line(48, 214, width - 48, 214)
    c.bookmarkPage("note-one", fit="XYZ", left=48, top=190, zoom=0)
    text("NOTE 1: Existing PDF links to notes are restored as ordinary links.", 188)
    text("Popup notes are reader features; LeafPress does not infer them.", 166)
    internal("Return from note 1 to the reference", "start", 130)
    c.showPage()

    heading("Links on a preserved slide", 3, landscape(A4))
    c.bookmarkPage("slide")
    c.addOutlineEntry("Preserved slide", "slide", 0)
    slide_height = landscape(A4)[1]
    text("The landscape page is kept as an image in the EPUB.", slide_height - 150)
    text("Its website link remains available as a separate clickable entry.", slide_height - 177)
    external("Open the LeafPress project website", slide_height - 235)
    c.save()


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "examples/navigation-lab.pdf"
    build(destination)
    print(destination)
