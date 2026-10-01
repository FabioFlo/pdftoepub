"""Source preview with normalized region selection; one pixmap at a time."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class PageCanvas(QWidget):
    regionSelected = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QPixmap()
        self.regions = []
        self.selecting = False
        self.origin = None
        self.current = None
        self.setMinimumSize(200, 200)

    def setPixmap(self, image):
        self.image = image
        self.origin = self.current = None
        self.setMinimumHeight(round(self.image_rect().height()) + 16)
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(max(200, self.image.width() + 16), max(200, self.image.height() + 16))

    def image_rect(self):
        width = min(self.image.width(), max(1, self.width() - 16))
        height = width * self.image.height() / max(1, self.image.width())
        return QRectF((self.width() - width) / 2, 8, width, height)

    def resizeEvent(self, _event):
        self.setMinimumHeight(round(self.image_rect().height()) + 16)

    def set_selection_enabled(self, enabled):
        self.selecting = enabled
        self.origin = self.current = None
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_regions(self, regions):
        self.regions = regions
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#e9eeeb"))
        bounds = self.image_rect()
        if not self.image.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(bounds, self.image, QRectF(self.image.rect()))
        painter.setPen(QPen(QColor("#216e62"), 2))
        for values in self.regions:
            rect = QRectF(bounds.x() + values[0] * bounds.width(), bounds.y() + values[1] * bounds.height(),
                          (values[2] - values[0]) * bounds.width(), (values[3] - values[1]) * bounds.height())
            painter.fillRect(rect, QColor(33, 110, 98, 35))
            painter.drawRect(rect)
        if self.origin is not None and self.current is not None:
            painter.drawRect(QRectF(self.origin, self.current).normalized().intersected(bounds))

    def mousePressEvent(self, event):
        if self.selecting and event.button() == Qt.MouseButton.LeftButton and self.image_rect().contains(event.position()):
            self.origin = self.current = event.position()
            self.update()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.current = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.origin is None or event.button() != Qt.MouseButton.LeftButton:
            return
        bounds = self.image_rect()
        rect = QRectF(self.origin, event.position()).normalized().intersected(bounds)
        self.origin = self.current = None
        if rect.width() >= 6 and rect.height() >= 6 and bounds.width() and bounds.height():
            self.regionSelected.emit([(rect.left() - bounds.left()) / bounds.width(),
                                      (rect.top() - bounds.top()) / bounds.height(),
                                      (rect.right() - bounds.left()) / bounds.width(),
                                      (rect.bottom() - bounds.top()) / bounds.height()])
        self.update()
