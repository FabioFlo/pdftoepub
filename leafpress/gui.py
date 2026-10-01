from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

import pymupdf
from PySide6.QtCore import QProcess, QSettings, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap, QFont, QImageReader
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QInputDialog, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter, QTextBrowser,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .model import Options, select_pages
from .page_canvas import PageCanvas
from .profiles import PROFILES, checked_preferences, preferences


from .themes import COLOURS, palette_for, resolve_theme, stylesheet


STYLE = stylesheet("light")


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
    def __init__(self, settings=None):
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
        self.page_regions = {}
        self.resolved_regions = {}
        self.settings = settings if settings is not None else QSettings("LeafPress", "LeafPress")
        self.saved_profiles = {}
        self.open_folder = str(self.settings.value("open_folder", ""))
        self.save_folder = str(self.settings.value("save_folder", ""))
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
        self._restore_settings()
        self.theme.currentIndexChanged.connect(self._theme_changed)
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self._apply_theme()
        self._update_layout_help()

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
        header.addWidget(label("Appearance", "muted"))
        self.theme = QComboBox()
        for text, value in (("System", "system"), ("Light", "light"), ("Dark", "dark")):
            self.theme.addItem(text, value)
        self.theme.setAccessibleName("Appearance")
        self.theme.setToolTip("Follow system appearance, or always use Light or Dark. Document colours stay unchanged.")
        header.addWidget(self.theme)
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
        settings.setMaximumWidth(390)
        settings.setMinimumWidth(300)
        settings_layout.addWidget(label("Conversion settings", "eyebrow"))
        preference_content = QWidget()
        preference_content.setObjectName("preferences")
        preference_layout = QVBoxLayout(preference_content)
        preference_layout.setContentsMargins(0, 0, 0, 0)
        preference_layout.setSpacing(10)
        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.profile = QComboBox()
        self.profile.addItem("Balanced", "balanced")
        self.profile.addItem("Technical", "technical")
        self.profile.addItem("Compact", "compact")
        self.profile.addItem("Custom settings", None)
        self.profile.currentIndexChanged.connect(self.apply_profile)
        form.addRow("Profile", self.profile)
        self.mode = QComboBox()
        self.mode.addItem("Reflow text + complex content", "hybrid")
        self.mode.addItem("Preserve pages as images", "preserve")
        self.mode.setToolTip("Hybrid reconstructs paragraphs and simple tables. Preserve keeps page appearance, with image-based text.")
        self.quality = QComboBox()
        self.quality.addItem("Balanced / colour", "balanced")
        self.quality.addItem("Compact / grayscale", "compact")
        self.quality.addItem("Sharp / colour", "sharp")
        self.quality.setToolTip("Controls cropped image resolution and file size. Adjustable text stays text at every quality.")
        self.tables = QComboBox()
        self.tables.addItem("Auto / HTML", "auto")
        self.tables.addItem("As images", "image")
        self.tables.setToolTip("Auto reconstructs reliable simple grids as HTML. As images preserves the appearance of detected tables.")
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
        for widget in (self.profile, self.mode, self.quality, self.tables, self.language, self.pages):
            widget.setMinimumHeight(32)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        preference_layout.addLayout(form)
        self.layout_help = label("", "muted")
        preference_layout.addWidget(self.layout_help)
        self.mode.currentIndexChanged.connect(self._update_layout_help)
        self._update_layout_help()
        self.save_profile_button = QPushButton("Save profile...")
        self.save_profile_button.clicked.connect(self.save_profile)
        preference_layout.addWidget(self.save_profile_button)
        self.remove_margins = QCheckBox("Remove repeated margins")
        self.remove_margins.setChecked(True)
        self.remove_margins.setToolTip("Repeated margin text and page counters are omitted from hybrid pages. Disable to retain them.")
        self.borderless = QCheckBox("Borderless tables (experimental)")
        self.borderless.setToolTip("May mistake aligned prose for a table. Review detected pages.")
        preference_layout.addWidget(self.remove_margins)
        preference_layout.addWidget(self.borderless)
        self.preserve_links = QCheckBox("Preserve PDF and web links")
        self.preserve_links.setChecked(True)
        self.preserve_links.setToolTip("Internal links jump to the nearest reconstructed block. Image content gets an adjacent link list. Targets outside the chosen pages are reported.")
        preference_layout.addWidget(self.preserve_links)
        preference_layout.addWidget(label("Scans and complex layouts use image fallbacks. Image text keeps its appearance and cannot resize independently.", "muted"))
        preference_scroll = QScrollArea()
        preference_scroll.setWidgetResizable(True)
        preference_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preference_scroll.setWidget(preference_content)
        preference_scroll.setMinimumHeight(155)
        settings_layout.addWidget(preference_scroll, 3)
        settings_layout.addWidget(label("Source pages", "eyebrow"))
        self.page_list = QTreeWidget()
        self.page_list.setColumnCount(2)
        self.page_list.setHeaderLabels(["Page", "Result / review"])
        self.page_list.setColumnWidth(0, 50)
        self.page_list.setAlternatingRowColors(True)
        self.page_list.setMinimumHeight(100)
        self.page_list.currentItemChanged.connect(self.select_page)
        settings_layout.addWidget(self.page_list, 2)
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
        region_row = QHBoxLayout()
        self.region_button = QPushButton("Select area to preserve")
        self.region_button.setCheckable(True)
        self.region_button.setEnabled(False)
        self.region_button.toggled.connect(self.toggle_region_selection)
        region_row.addWidget(self.region_button)
        self.undo_region_button = QPushButton("Undo area")
        self.undo_region_button.clicked.connect(self.undo_region)
        region_row.addWidget(self.undo_region_button)
        self.clear_regions_button = QPushButton("Clear page areas")
        self.clear_regions_button.clicked.connect(self.clear_regions)
        region_row.addWidget(self.clear_regions_button)
        self.regions_label = label("0 selected areas", "muted")
        region_row.addWidget(self.regions_label, 1)
        compare_layout.addLayout(region_row)
        columns = QSplitter(Qt.Orientation.Horizontal)
        original = QWidget()
        original_layout = QVBoxLayout(original)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.addWidget(label("ORIGINAL PDF", "muted"))
        self.source_view = PageCanvas()
        self.source_view.regionSelected.connect(self.add_region)
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
        self.book_view.setObjectName("document")
        self.book_view.setPalette(palette_for("light"))
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
        horizontal.setSizes([340, 890])
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
                                 self.override, self.output_edit, self.browse_output, self.open_button,
                                 self.profile, self.save_profile_button, self.preserve_links,
                                 self.region_button, self.undo_region_button, self.clear_regions_button]
        self._update_region_controls()
        for widget in (self.mode, self.quality, self.tables, self.language):
            widget.currentIndexChanged.connect(self.settings_changed)
        for widget in (self.remove_margins, self.borderless, self.preserve_links):
            widget.toggled.connect(self.settings_changed)

    def _update_layout_help(self):
        self.layout_help.setText("Adjustable text, with tables and formulas preserved where needed."
                                 if self.mode.currentData() == "hybrid" else
                                 "Exact page appearance. Text cannot resize; files can be much larger.")

    def _apply_theme(self):
        choice = self.theme.currentData()
        self.effective_theme = resolve_theme(choice, QApplication.instance().styleHints().colorScheme())
        self.setPalette(palette_for(self.effective_theme))
        self.setStyleSheet(stylesheet(self.effective_theme))
        self.source_view.set_background(COLOURS[self.effective_theme]["canvas"])

    def _theme_changed(self):
        self._apply_theme()
        self.settings.setValue("appearance", self.theme.currentData())
        self.settings.sync()

    def _system_theme_changed(self, _scheme):
        if self.theme.currentData() == "system":
            self._apply_theme()

    def _preference_values(self):
        return preferences(Options(mode=self.mode.currentData(), quality=self.quality.currentData(),
                                   table_mode=self.tables.currentData(), language=self.language.currentData(),
                                   remove_margins=self.remove_margins.isChecked(),
                                   detect_borderless=self.borderless.isChecked(),
                                   preserve_links=self.preserve_links.isChecked()))

    def _set_preferences(self, values):
        fields = {"mode": self.mode, "quality": self.quality, "table_mode": self.tables, "language": self.language,
                  "remove_margins": self.remove_margins, "detect_borderless": self.borderless,
                  "preserve_links": self.preserve_links}
        for key, value in values.items():
            widget = fields.get(key)
            if widget is None:
                continue
            widget.blockSignals(True)
            if isinstance(widget, QComboBox):
                if widget.findData(value) < 0:
                    widget.addItem(value, value)
                widget.setCurrentIndex(widget.findData(value))
            else:
                widget.setChecked(value)
            widget.blockSignals(False)

    def settings_changed(self):
        self.profile.blockSignals(True)
        self.profile.setCurrentIndex(self.profile.findData(None))
        self.profile.blockSignals(False)
        self._update_region_controls()
        self._update_layout_help()
        if self.source:
            self.review_label.setText("Settings changed. Preview or export again to apply them.")

    def apply_profile(self):
        key = self.profile.currentData()
        values = PROFILES.get(key) or self.saved_profiles.get(key)
        if values:
            self._set_preferences(values)
            self._update_region_controls()
            self._update_layout_help()
            if self.source:
                self.review_label.setText("Profile applied. Preview or export again to apply it.")

    def save_profile(self):
        name, accepted = QInputDialog.getText(self, "Save conversion profile", "Profile name:")
        if accepted and name.strip():
            key = "saved:" + name.strip()[:60]
            self.saved_profiles[key] = self._preference_values()
            if self.profile.findData(key) < 0:
                self.profile.addItem(name.strip()[:60], key)
            self.profile.setCurrentIndex(self.profile.findData(key))
            self._save_settings()

    def _restore_settings(self):
        appearance = self.settings.value("appearance", "system")
        index = self.theme.findData(appearance)
        self.theme.setCurrentIndex(index if index >= 0 else 0)
        try:
            values = json.loads(str(self.settings.value("preferences", "{}")))
            if values:
                self._set_preferences(checked_preferences(values))
            saved = json.loads(str(self.settings.value("saved_profiles", "{}")))
            for key, values in saved.items():
                if isinstance(key, str) and key.startswith("saved:"):
                    self.saved_profiles[key] = checked_preferences(values)
                    self.profile.addItem(key[6:], key)
            self.profile.blockSignals(True)
            key = self.settings.value("selected_profile", "balanced")
            index = self.profile.findData(key)
            self.profile.setCurrentIndex(index if index >= 0 else self.profile.findData(None))
            self.profile.blockSignals(False)
        except (TypeError, ValueError, AttributeError):
            self.status.setText("Some saved preferences could not be restored.")

    def _save_settings(self):
        self.settings.setValue("appearance", self.theme.currentData())
        self.settings.setValue("preferences", json.dumps(self._preference_values()))
        self.settings.setValue("saved_profiles", json.dumps(self.saved_profiles))
        self.settings.setValue("selected_profile", self.profile.currentData() or "")
        self.settings.setValue("open_folder", self.open_folder)
        self.settings.setValue("save_folder", self.save_folder)
        self.settings.sync()

    def toggle_region_selection(self, enabled):
        self.source_view.set_selection_enabled(enabled)
        if enabled:
            self.review_label.setText("Drag across the original PDF to preserve an area. Intersecting lines, tables and figures are included whole. Preview to inspect the crop.")

    def _update_region_controls(self):
        count = len(self.page_regions.get(self.current_page, []))
        enabled = self.document is not None and self.process is None
        self.region_button.setEnabled(enabled)
        self.undo_region_button.setEnabled(enabled and count > 0)
        self.clear_regions_button.setEnabled(enabled and count > 0)
        self.regions_label.setText(f"{count} selected area{'s' if count != 1 else ''}")
        self.source_view.set_regions(self.resolved_regions.get(self.current_page, self.page_regions.get(self.current_page, [])))

    def add_region(self, region):
        if self.document is None or self.process is not None:
            return
        self.page_regions.setdefault(self.current_page, []).append(region)
        self.resolved_regions.pop(self.current_page, None)
        self.region_button.setChecked(False)
        self._update_region_controls()
        self.review_label.setText("Area added. Preview or export again to inspect the preserved region. Full-page image mode already preserves all areas.")

    def undo_region(self):
        self.resolved_regions.pop(self.current_page, None)
        regions = self.page_regions.get(self.current_page, [])
        if regions:
            regions.pop()
        self._update_region_controls()
        self.review_label.setText("Area removed. Preview or export again to apply it.")

    def clear_regions(self):
        self.page_regions.pop(self.current_page, None)
        self.resolved_regions.pop(self.current_page, None)
        self._update_region_controls()
        self.review_label.setText("Page areas cleared. Preview or export again to apply it.")

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open a PDF", self.open_folder, "PDF documents (*.pdf)")
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
        self.page_regions = {}
        self.pages.clear()
        self.resolved_regions = {}
        self.open_folder = str(self.source.parent)
        self.region_button.setChecked(False)
        self.preview_root = None
        self.page_list.clear()
        self.title_edit.setText(document.metadata.get("title", "") or self.source.stem)
        self.author_edit.setText(document.metadata.get("author", ""))
        self.output_edit.setText(str(Path(self.save_folder) / (self.source.stem + ".epub")) if self.save_folder else str(self.source.with_suffix(".epub")))
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
        self.region_button.setChecked(False)
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
        self._update_region_controls()

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
                message = item.toolTip(1) or "No automatic review flags. Compare content before sending to Kindle."
                summary = item.data(1, Qt.ItemDataRole.UserRole) or {}
                if self.job_kind == "preview" and summary.get("skipped_links"):
                    message += " This preview contains one page; links to other chosen pages are restored in a full export."
                self.review_label.setText(message)
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
                          page_modes=self.page_modes.copy(), preserve_links=self.preserve_links.isChecked(),
                          page_regions={page: [list(r) for r in regions] for page, regions in self.page_regions.items()})
        options.validate()
        select_pages(options.pages, len(self.document))
        return options

    def choose_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save EPUB", self.output_edit.text(), "EPUB books (*.epub)")
        if path:
            self.output_edit.setText(path if Path(path).suffix.lower() == ".epub" else path + ".epub")
            self.save_folder = str(Path(path).resolve().parent)
            self._save_settings()

    def preview_page(self):
        self._launch(True)

    def export(self):
        self._launch(False)

    def _launch(self, preview):
        if not self.source or self.process:
            return
        try:
            options = self.options(preview)
            self.region_button.setChecked(False)
            if not preview:
                self.save_folder = str(Path(self.output_edit.text()).resolve().parent)
            self._save_settings()
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
        self._update_region_controls()

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
                self.resolved_regions[result["page"]] = result.get("region_bounds", [])
                if result["page"] == self.current_page:
                    self.source_view.set_regions(result.get("region_bounds", []))
                item = self.page_list.topLevelItem(result["page"] - 1)
                detail = "Image" if result["mode"] == "preserve" else "Hybrid"
                if result["warnings"]:
                    detail += " / review"
                item.setText(1, detail)
                item.setData(1, Qt.ItemDataRole.UserRole, result)
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
                self.status.setText(f'<b>EPUB ready · {report["output_bytes"] / 1024**2:.2f} MiB</b><br/>'
                                    f'{report["elapsed_seconds"]:.1f} s · {report["review_pages"]} pages to review')
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
        self._save_settings()
        if self.job_dir:
            self.job_dir.cleanup()
        event.accept()


def main():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("LeafPress")
    app.setStyle("Fusion")
    window = Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
