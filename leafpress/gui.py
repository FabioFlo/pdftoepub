from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

import pymupdf
from PySide6.QtCore import QProcess, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap, QFont, QImageReader
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QSplitter, QTextBrowser,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .model import Options, select_pages


STYLE = """
QMainWindow, QWidget#root { background: #f2f4f3; color: #1e3038; }
QLabel#brand { font-size: 26px; font-weight: 700; color: #183e40; }
QLabel#eyebrow { color: #36766a; font-size: 11px; font-weight: 600; }
QLabel#muted { color: #607278; }
QFrame#panel { background: white; border: 1px solid #dce3df; border-radius: 10px; }
QFrame#header { background: transparent; }
QLineEdit, QComboBox { padding: 7px; border: 1px solid #d2dcda; border-radius: 5px; background: white; color: #1e3038; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #237a6d; }
QPushButton { padding: 9px 14px; border: 1px solid #cbd8d4; border-radius: 6px; background: white; color: #22433f; font-weight: 600; }
QPushButton:hover { background: #edf6f1; }
QPushButton#primary { background: #216e62; color: white; border: 1px solid #216e62; }
QPushButton#primary:hover { background: #1b5c52; }
QPushButton:disabled { background: #ebefed; color: #899792; border-color: #dfe5e1; }
QProgressBar { border: 0; border-radius: 4px; background: #e4ebe7; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #2b8473; border-radius: 4px; }
QTreeWidget { border: 0; background: white; alternate-background-color: #f6f8f6; color: #273c42; }
QTreeWidget::item { padding: 5px; }
QTreeWidget::item:selected { background: #e0f0e9; color: #214d41; }
QHeaderView::section { background: #f4f7f5; padding: 6px; border: 0; color: #526762; }
QTextBrowser { border: 0; background: white; color: #223338; }
QScrollArea { border: 0; background: #e9eeeb; }
QCheckBox { color: #405853; spacing: 7px; }
QSplitter::handle { background: transparent; width: 10px; }
"""


def label(text, object_name=""):
    widget = QLabel(text)
    widget.setWordWrap(True)
    if object_name:
        widget.setObjectName(object_name)
    return widget


def panel():
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)
    return frame, layout


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LeafPress - PDF to EPUB")
        self.resize(1280, 850)
        self.setMinimumSize(940, 680)
        self.document = None
        self.source = None
        self.output_path = None
        self.preview_root = None
        self.current_page = 1
        self.page_modes = {}
        self.process = None
        self.job_dir = None
        self.buffer = b""
        self.job_kind = None
        self.cancel_requested = False
        self.job_error = ""
        self.job_complete = None
        self.closing = False
        self.event_offset = 0
        self.event_poll = QTimer(self)
        self.event_poll.setInterval(100)
        self.event_poll.timeout.connect(self._read_output)
        self._build()

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(24, 20, 24, 18)
        main.setSpacing(14)
        header = QHBoxLayout()
        names = QVBoxLayout()
        names.addWidget(label("LeafPress", "brand"))
        names.addWidget(label("PDF TO EPUB   /   LOCAL & OFFLINE", "eyebrow"))
        header.addLayout(names)
        header.addStretch()
        header.addWidget(label("Keep the text flexible.\nKeep the difficult parts intact.", "muted"))
        self.open_button = QPushButton("Open PDF")
        self.open_button.clicked.connect(self.open_pdf)
        header.addWidget(self.open_button)
        main.addLayout(header)
        self.file_label = label("Open a PDF to begin. A sample document is included in the examples folder.", "muted")
        main.addWidget(self.file_label)
        metadata = QHBoxLayout()
        self.title_edit = QLineEdit()
        self.author_edit = QLineEdit()
        metadata.addWidget(label("Title"))
        metadata.addWidget(self.title_edit, 2)
        metadata.addSpacing(12)
        metadata.addWidget(label("Author"))
        metadata.addWidget(self.author_edit, 1)
        main.addLayout(metadata)

        horizontal = QSplitter(Qt.Orientation.Horizontal)
        settings, settings_layout = panel()
        settings.setMaximumWidth(320)
        settings.setMinimumWidth(260)
        settings_layout.addWidget(label("Conversion settings", "eyebrow"))
        form = QFormLayout()
        form.setVerticalSpacing(9)
        self.mode = QComboBox()
        self.mode.addItem("Hybrid - adjustable text", "hybrid")
        self.mode.addItem("Preserve all pages as images", "preserve")
        self.mode.setToolTip("Hybrid reconstructs paragraphs and simple tables. Preserve keeps page appearance, with image-based text.")
        self.quality = QComboBox()
        self.quality.addItem("Balanced / colour", "balanced")
        self.quality.addItem("Compact / grayscale", "compact")
        self.quality.addItem("Sharp / colour", "sharp")
        self.quality.setToolTip("Controls cropped image resolution and file size. Adjustable text stays text at every quality.")
        self.tables = QComboBox()
        self.tables.addItem("Auto - HTML when reliable", "auto")
        self.tables.addItem("Preserve detected tables as images", "image")
        self.language = QComboBox()
        self.language.addItem("Italian", "it")
        self.language.addItem("English", "en")
        self.language.addItem("French", "fr")
        self.language.addItem("German", "de")
        self.language.addItem("Spanish", "es")
        self.pages = QLineEdit()
        self.pages.setPlaceholderText("All pages, or e.g. 1-5,8")
        for text, widget in [("Layout", self.mode), ("Images", self.quality), ("Tables", self.tables),
                             ("Language", self.language), ("Pages", self.pages)]:
            form.addRow(text, widget)
        settings_layout.addLayout(form)
        self.remove_margins = QCheckBox("Remove repeated headers / footers")
        self.remove_margins.setChecked(True)
        self.remove_margins.setToolTip("Repeated margin text and page counters are omitted from hybrid pages. Disable to retain them.")
        self.borderless = QCheckBox("Borderless tables (experimental)")
        self.borderless.setToolTip("May mistake aligned prose for a table. Review detected pages.")
        settings_layout.addWidget(self.remove_margins)
        settings_layout.addWidget(self.borderless)
        settings_layout.addWidget(label("Scans and complex layouts use image fallbacks. Image text keeps its appearance and cannot resize independently.", "muted"))
        settings_layout.addWidget(label("Source pages", "eyebrow"))
        self.page_list = QTreeWidget()
        self.page_list.setColumnCount(2)
        self.page_list.setHeaderLabels(["Page", "Result / review"])
        self.page_list.setColumnWidth(0, 50)
        self.page_list.setAlternatingRowColors(True)
        self.page_list.currentItemChanged.connect(self.select_page)
        settings_layout.addWidget(self.page_list, 1)
        horizontal.addWidget(settings)

        comparison, compare_layout = panel()
        row = QHBoxLayout()
        row.addWidget(label("Compare a page", "eyebrow"))
        row.addStretch()
        self.override = QComboBox()
        self.override.addItem("This page: follow global layout", None)
        self.override.addItem("This page: hybrid", "hybrid")
        self.override.addItem("This page: preserve appearance", "preserve")
        self.override.currentIndexChanged.connect(self.change_override)
        row.addWidget(self.override)
        self.preview_button = QPushButton("Preview page")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self.preview_page)
        row.addWidget(self.preview_button)
        compare_layout.addLayout(row)
        columns = QSplitter(Qt.Orientation.Horizontal)
        original = QWidget()
        original_layout = QVBoxLayout(original)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.addWidget(label("ORIGINAL PDF", "muted"))
        self.source_view = QLabel("PDF preview")
        self.source_view.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.source_view.setStyleSheet("background: #e9eeeb; padding: 8px;")
        self.source_scroll = QScrollArea()
        self.source_scroll.setWidget(self.source_view)
        self.source_scroll.setWidgetResizable(True)
        original_layout.addWidget(self.source_scroll)
        columns.addWidget(original)
        converted = QWidget()
        converted_layout = QVBoxLayout(converted)
        converted_layout.setContentsMargins(0, 0, 0, 0)
        converted_layout.addWidget(label("EPUB CONTENT / APPROXIMATE DESKTOP VIEW", "muted"))
        self.book_view = QTextBrowser()
        self.book_view.setOpenLinks(False)
        self.book_view.setOpenExternalLinks(False)
        self.book_view.setFont(QFont("Georgia", 12))
        self.book_view.setHtml("<h2>A smaller screen, a readable document.</h2><p>Open a PDF, select a page, and click <b>Preview page</b>.</p><p>Compare tables, equations, and reading order before exporting.</p>")
        converted_layout.addWidget(self.book_view)
        columns.addWidget(converted)
        columns.setSizes([420, 420])
        compare_layout.addWidget(columns, 1)
        self.review_label = label("Preview is an approximation. Check the delivered book on Kindle for final layout.", "muted")
        compare_layout.addWidget(self.review_label)
        horizontal.addWidget(comparison)
        horizontal.setSizes([285, 930])
        main.addWidget(horizontal, 1)

        bottom, bottom_layout = panel()
        destination = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Destination EPUB")
        destination.addWidget(self.output_edit, 1)
        self.browse_output = QPushButton("Save to...")
        self.browse_output.clicked.connect(self.choose_output)
        destination.addWidget(self.browse_output)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        destination.addWidget(self.cancel_button)
        self.convert_button = QPushButton("Create EPUB")
        self.convert_button.setObjectName("primary")
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(self.export)
        destination.addWidget(self.convert_button)
        bottom_layout.addLayout(destination)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        bottom_layout.addWidget(self.progress)
        status_row = QHBoxLayout()
        self.status = label("Ready. Your documents stay on this computer.", "muted")
        status_row.addWidget(self.status, 1)
        self.folder_button = QPushButton("Open output folder")
        self.folder_button.setEnabled(False)
        self.folder_button.clicked.connect(self.open_output_folder)
        status_row.addWidget(self.folder_button)
        bottom_layout.addLayout(status_row)
        main.addWidget(bottom)
        self.settings_widgets = [self.title_edit, self.author_edit, self.mode, self.quality, self.tables,
                                 self.language, self.pages, self.remove_margins, self.borderless,
                                 self.override, self.output_edit, self.browse_output, self.open_button]

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open a PDF", "", "PDF documents (*.pdf)")
        if path:
            try:
                self.load_pdf(path)
            except Exception as exc:
                QMessageBox.warning(self, "Cannot open PDF", str(exc))

    def load_pdf(self, path):
        document = pymupdf.open(path)
        if not document.is_pdf or document.needs_pass or not len(document):
            document.close()
            raise ValueError("Open a readable, unlocked PDF with at least one page.")
        if self.document is not None:
            self.document.close()
        self.document = document
        self.source = Path(path).resolve()
        self.page_modes = {}
        self.preview_root = None
        self.page_list.clear()
        self.title_edit.setText(document.metadata.get("title", "") or self.source.stem)
        self.author_edit.setText(document.metadata.get("author", ""))
        self.output_edit.setText(str(self.source.with_suffix(".epub")))
        self.file_label.setText(f"{self.source.name}  /  {len(document)} source pages  /  {self.source.stat().st_size / 1024**2:.1f} MiB")
        for index in range(len(document)):
            item = QTreeWidgetItem([str(index + 1), "Not previewed"])
            item.setData(0, Qt.ItemDataRole.UserRole, index + 1)
            self.page_list.addTopLevelItem(item)
        self.page_list.setCurrentItem(self.page_list.topLevelItem(0))
        self.preview_button.setEnabled(True)
        self.convert_button.setEnabled(True)
        self.folder_button.setEnabled(False)
        self.status.setText("Choose a page to preview, or create the complete EPUB.")

    def select_page(self, current, _previous):
        if current is None or self.document is None:
            return
        self.current_page = current.data(0, Qt.ItemDataRole.UserRole)
        self.override.blockSignals(True)
        self.override.setCurrentIndex(self.override.findData(self.page_modes.get(self.current_page)))
        self.override.blockSignals(False)
        page = self.document[self.current_page - 1]
        width = max(300, self.source_scroll.viewport().width() - 25)
        scale = min(1.8, width / max(1, page.rect.width),
                    (2_000_000 / max(1, page.rect.get_area())) ** 0.5)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        image = QPixmap()
        image.loadFromData(pix.tobytes("png"))
        self.source_view.setPixmap(image)
        del pix, page
        pymupdf.TOOLS.store_shrink(100)
        self._show_converted_page()

    def _show_converted_page(self):
        if self.preview_root:
            path = self.preview_root / "OEBPS/text" / f"page-{self.current_page:05d}.xhtml"
            if path.is_file():
                # QTextBrowser supports a smaller CSS subset than EPUB readers.
                # Scale preview images to this panel without changing the EPUB.
                markup = ET.fromstring(path.read_text(encoding="utf-8"))
                available = max(200, self.book_view.viewport().width() - 25)
                for img in markup.iter("{http://www.w3.org/1999/xhtml}img"):
                    asset_path = (path.parent / img.attrib["src"]).resolve()
                    size = QImageReader(str(asset_path)).size()
                    width = min(available, int(img.attrib.get("width", available)))
                    if size.width() > 0:
                        img.set("width", str(width))
                        img.set("height", str(round(width * size.height() / size.width())))
                ET.register_namespace("", "http://www.w3.org/1999/xhtml")
                ET.register_namespace("epub", "http://www.idpf.org/2007/ops")
                self.book_view.document().setBaseUrl(QUrl.fromLocalFile(str(path.parent) + os.sep))
                self.book_view.setHtml(ET.tostring(markup, encoding="unicode"))
                self.book_view.verticalScrollBar().setValue(0)
                item = self.page_list.topLevelItem(self.current_page - 1)
                self.review_label.setText(item.toolTip(1) or "No automatic review flags. Compare content before sending to Kindle.")
                return
        self.book_view.setHtml("<p>Click <b>Preview page</b> to convert this page with the current settings.</p>")
        self.review_label.setText("The EPUB content will appear here after a preview or conversion.")

    def change_override(self):
        value = self.override.currentData()
        if value:
            self.page_modes[self.current_page] = value
        else:
            self.page_modes.pop(self.current_page, None)
        if self.source:
            self.review_label.setText("Page setting changed. Preview or export again to apply it.")

    def options(self, preview=False):
        options = Options(mode=self.mode.currentData(), quality=self.quality.currentData(),
                          table_mode=self.tables.currentData(), language=self.language.currentData(),
                          title=self.title_edit.text(), author=self.author_edit.text(),
                          pages=str(self.current_page) if preview else self.pages.text(),
                          remove_margins=self.remove_margins.isChecked(), detect_borderless=self.borderless.isChecked(),
                          page_modes=self.page_modes.copy())
        options.validate()
        select_pages(options.pages, len(self.document))
        return options

    def choose_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save EPUB", self.output_edit.text(), "EPUB books (*.epub)")
        if path:
            self.output_edit.setText(path if Path(path).suffix.lower() == ".epub" else path + ".epub")

    def preview_page(self):
        self._launch(True)

    def export(self):
        self._launch(False)

    def _launch(self, preview):
        if not self.source or self.process:
            return
        try:
            options = self.options(preview)
            if preview:
                job = tempfile.TemporaryDirectory(prefix="leafpress-preview-")
                output = Path(job.name) / "preview.epub"
                overwrite = False
            else:
                if not self.output_edit.text().strip():
                    raise ValueError("Choose an EPUB destination.")
                output = Path(self.output_edit.text()).resolve()
                if output.suffix.lower() != ".epub":
                    raise ValueError("The destination must end in .epub.")
                if output == self.source:
                    raise ValueError("Input and output must be different files.")
                overwrite = any(path.exists() for path in [output, output.with_suffix(".report.json"), output.with_suffix(".preview")])
                if overwrite and QMessageBox.question(self, "Replace conversion?",
                        "Replace the existing EPUB and its LeafPress report/preview?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
                output.parent.mkdir(parents=True, exist_ok=True)
                job = tempfile.TemporaryDirectory(prefix=".leafpress-job-", dir=output.parent)
            # Keep only the most recent preview; no accumulating raster cache.
            self.preview_root = None
            self.book_view.clear()
            if self.job_dir:
                self.job_dir.cleanup()
            self.job_dir = job
            root = Path(job.name)
            self.cancel_path = root / "cancel"
            config = {"source": str(self.source), "output": str(output), "options": options.to_dict(),
                      "overwrite": overwrite, "cancel_file": str(self.cancel_path), "staging_parent": str(root),
                      "events_file": str(root / "events.jsonl")}
            self.events_path = root / "events.jsonl"
            config_path = root / "job.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            self.process = QProcess(self)
            self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            if getattr(sys, "frozen", False):
                program = sys.executable
                arguments = ["worker", str(config_path)]
            else:
                program = sys.executable
                arguments = ["-m", "leafpress", "worker", str(config_path)]
                self.process.setWorkingDirectory(str(Path(__file__).resolve().parent.parent))
            self.process.setProgram(program)
            self.process.setArguments(arguments)
            self.process.readyReadStandardOutput.connect(self._read_output)
            self.process.finished.connect(self._finished)
            self.process.errorOccurred.connect(self._process_error)
            self.buffer = b""
            self.event_offset = 0
            self.job_kind = "preview" if preview else "export"
            self.job_complete = None
            self.job_error = ""
            self.cancel_requested = False
            self._busy(True)
            self.progress.setValue(0)
            self.status.setText("Preparing page preview..." if preview else "Preparing conversion...")
            self.process.start()
            self.event_poll.start()
        except Exception as exc:
            QMessageBox.warning(self, "Cannot start conversion", str(exc))

    def _busy(self, busy):
        for widget in self.settings_widgets:
            widget.setEnabled(not busy)
        self.preview_button.setEnabled(not busy and bool(self.source))
        self.convert_button.setEnabled(not busy and bool(self.source))
        self.cancel_button.setEnabled(busy)

    def _read_output(self):
        if not self.process:
            return
        # Event files also work in a PyInstaller windowed executable where
        # sys.stdout can be None. Worker diagnostics remain on its stderr pipe.
        diagnostics = bytes(self.process.readAllStandardOutput())
        if diagnostics and b"Traceback" in diagnostics:
            self.job_error = diagnostics.decode("utf-8", errors="replace")[-2000:]
        if hasattr(self, "events_path") and self.events_path.is_file():
            with self.events_path.open("rb") as events:
                events.seek(self.event_offset)
                self.buffer += events.read()
                self.event_offset = events.tell()
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                event = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            kind = event.get("type")
            if kind == "status":
                self.status.setText(event["message"])
            elif kind == "page":
                result = event["result"]
                item = self.page_list.topLevelItem(result["page"] - 1)
                detail = "Image" if result["mode"] == "preserve" else "Hybrid"
                if result["warnings"]:
                    detail += " / review"
                item.setText(1, detail)
                item.setToolTip(1, "\n".join(result["warnings"]))
                self.progress.setValue(round(event["done"] * 100 / event["total"]))
                self.status.setText(f'Page {result["page"]}: {event["done"]}/{event["total"]}  /  worker peak {event["peak_process_mib"]} MiB')
            elif kind == "complete":
                self.job_complete = event
            elif kind == "error":
                self.job_error = event["message"]

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.job_error = "The conversion worker could not start. Check the Python environment."
            self._finished(1, QProcess.ExitStatus.CrashExit)

    def _finished(self, code, _status):
        process = self.process
        if process is None:
            return
        self._read_output()
        self.event_poll.stop()
        self.process = None
        process.deleteLater()
        self._busy(False)
        if self.job_complete:
            event = self.job_complete
            self.preview_root = Path(event["preview"])
            report = event["summary"]
            self.progress.setValue(100)
            if self.job_kind == "export":
                self.output_path = Path(event["output"])
                self.folder_button.setEnabled(True)
                self.status.setText(f'EPUB created  /  {report["output_bytes"] / 1024**2:.2f} MiB  /  '
                                    f'{report["elapsed_seconds"]:.1f} s  /  {report["review_pages"]} pages to review')
            else:
                self.status.setText(f'Preview ready  /  worker peak {report["peak_process_mib"]} MiB. Change settings and preview again if needed.')
            self._show_converted_page()
        elif self.cancel_requested or code == 130:
            self.progress.setValue(0)
            self.status.setText("Cancelled. The previous EPUB was kept.")
            if self.job_dir:
                self.job_dir.cleanup()
                self.job_dir = None
        else:
            self.status.setText("Conversion failed. The previous EPUB was kept.")
            QMessageBox.warning(self, "Conversion failed", self.job_error or f"Worker exited with code {code}.")
            if self.job_dir:
                self.job_dir.cleanup()
                self.job_dir = None
        if self.closing:
            self.close()

    def cancel(self):
        if self.process:
            self.cancel_requested = True
            self.cancel_path.touch()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling after the current page operation...")
            process = self.process
            # A malformed PDF cannot leave a worker running indefinitely.
            QTimer.singleShot(5000, lambda: self._stop_if_current(process))

    def _stop_if_current(self, process):
        if self.process is process:
            process.kill()

    def open_output_folder(self):
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_path.parent)))

    def closeEvent(self, event):
        if self.process:
            self.closing = True
            self.cancel()
            event.ignore()
            return
        if self.document:
            self.document.close()
            self.document = None
        if self.job_dir:
            self.job_dir.cleanup()
        event.accept()


def main():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("LeafPress")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
