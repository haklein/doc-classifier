"""PDF preview widget."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel

from ..extractor import render_page


class PdfPreview(QLabel):
    """Widget that displays page 1 of a PDF scaled to fit."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 500)
        self.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self._pixmap = None

    def set_pdf(self, path: Path) -> None:
        """Render and display page 1 of the given PDF."""
        qimage = render_page(path, page=0)
        self._pixmap = QPixmap.fromImage(qimage)
        self._scale_and_show()

    def clear_preview(self) -> None:
        self._pixmap = None
        self.clear()
        self.setText("No document")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap:
            self._scale_and_show()

    def _scale_and_show(self):
        if self._pixmap:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
