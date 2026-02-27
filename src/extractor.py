"""PDF text extraction and page rendering."""

from pathlib import Path

from pdfminer.high_level import extract_text as _pdfminer_extract


def extract_text(pdf_path: Path) -> str:
    """Extract text from all pages of a PDF using pdfminer.six.

    Returns empty string on failure.
    """
    try:
        text = _pdfminer_extract(str(pdf_path))
        return text.strip() if text else ""
    except Exception:
        return ""


def render_page(pdf_path: Path, page: int = 0, dpi: int = 150):
    """Render a PDF page to QImage using pymupdf.

    Returns a QImage, or a placeholder on failure.
    """
    from PyQt6.QtGui import QImage

    try:
        import pymupdf

        doc = pymupdf.open(str(pdf_path))
        if page >= len(doc):
            page = 0
        pix = doc[page].get_pixmap(dpi=dpi)
        img = QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888
        )
        # Make a deep copy so pymupdf memory can be freed
        result = img.copy()
        doc.close()
        return result
    except Exception:
        # Return a small placeholder image
        img = QImage(400, 560, QImage.Format.Format_RGB888)
        img.fill(0xCCCCCC)
        return img
