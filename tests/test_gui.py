from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QPoint, QSettings, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from leafpress.gui import STYLE, Window
    HAS_QT = True
except ImportError:
    HAS_QT = False

PROJECT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "Install the gui extra for desktop smoke checks")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.preferences_dir = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.preferences_dir.name) / "settings.ini"), QSettings.Format.IniFormat)
        self.window = Window(self.settings)
        self.window.show()
        self.app.processEvents()
        self.window.load_pdf(str(PROJECT / "examples/conversion-lab.pdf"))

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.preferences_dir.cleanup()

    def wait_for_worker(self):
        deadline = time.monotonic() + 15
        while self.window.process is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertIsNone(self.window.process, "Worker did not finish")
        self.assertFalse(self.window.job_error, self.window.job_error)

    def test_preview_table_and_page_override_in_real_worker(self):
        self.window.page_list.setCurrentItem(self.window.page_list.topLevelItem(1))
        self.window.preview_page()
        self.wait_for_worker()
        self.assertIn("Notebook", self.window.book_view.toPlainText())
        self.assertEqual(self.window.job_complete["summary"]["totals"]["html_tables"], 1)
        self.window.override.setCurrentIndex(2)
        self.window.preview_page()
        self.wait_for_worker()
        self.assertEqual(self.window.job_complete["summary"]["pages"][0]["mode"], "preserve")

    def test_export_and_reopen_pages(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "gui.epub"
            self.window.output_edit.setText(str(output))
            self.window.export()
            self.wait_for_worker()
            self.assertTrue(output.is_file())
            self.window.page_list.setCurrentItem(self.window.page_list.topLevelItem(4))
            self.assertIn("LEFT_1", self.window.book_view.toPlainText())
            self.assertIn("Two-column", self.window.review_label.text())
            self.assertTrue(self.window.folder_button.isEnabled())

    def test_cancel_worker_and_clean_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "cancelled.epub"
            self.window.output_edit.setText(str(output))
            self.window.export()
            self.window.cancel()
            self.wait_for_worker()
            self.assertFalse(output.exists())
            self.assertFalse(list(Path(temp).glob(".leafpress-*")))
            self.assertIn("Cancelled", self.window.status.text())

    def test_drag_region_preserves_table_in_real_worker(self):
        self.window.page_list.setCurrentItem(self.window.page_list.topLevelItem(1))
        self.app.processEvents()
        view = self.window.source_view
        bounds = view.image_rect()
        # Touch part of the ruled table; the engine must include the whole grid.
        first = QPoint(round(bounds.x() + bounds.width() * .15), round(bounds.y() + bounds.height() * .29))
        last = QPoint(round(bounds.x() + bounds.width() * .7), round(bounds.y() + bounds.height() * .45))
        self.window.region_button.setChecked(True)
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=first)
        QTest.mouseMove(view, last)
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=last)
        self.assertEqual(len(self.window.page_regions[2]), 1)
        self.assertFalse(self.window.region_button.isChecked())
        self.window.preview_page()
        self.wait_for_worker()
        self.assertEqual(self.window.job_complete["summary"]["totals"]["manual_regions"], 1)
        self.assertEqual(self.window.job_complete["summary"]["totals"]["html_tables"], 0)
        self.window.undo_region()
        self.assertFalse(self.window.page_regions[2])

    def test_saved_preferences_and_profiles_exclude_document_edits(self):
        from unittest.mock import patch
        self.window.profile.setCurrentIndex(self.window.profile.findData("compact"))
        self.window.preserve_links.setChecked(False)
        self.window.page_regions = {1: [[.1, .1, .4, .4]]}
        with patch("leafpress.gui.QInputDialog.getText", return_value=("My Kindle", True)):
            self.window.save_profile()
        self.window.close()
        restored = Window(self.settings)
        try:
            self.assertEqual(restored.quality.currentData(), "compact")
            self.assertFalse(restored.preserve_links.isChecked())
            self.assertEqual(restored.profile.currentData(), "saved:My Kindle")
            self.assertEqual(restored.page_regions, {})
            self.assertEqual(restored.page_modes, {})
            restored.profile.setCurrentIndex(restored.profile.findData("technical"))
            self.assertEqual(restored.tables.currentData(), "image")
            self.assertFalse(restored.preserve_links.isChecked())
        finally:
            restored.close()


if __name__ == "__main__":
    unittest.main()
