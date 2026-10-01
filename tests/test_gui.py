from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QTimer
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
        self.window = Window()
        self.window.show()
        self.app.processEvents()
        self.window.load_pdf(str(PROJECT / "examples/conversion-lab.pdf"))

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

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


if __name__ == "__main__":
    unittest.main()
