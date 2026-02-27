"""Folder suggestion list widget."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

# Sentinel value for the "Browse..." entry
BROWSE_FOLDER = "__BROWSE__"


class FolderList(QListWidget):
    """List widget showing ranked folder suggestions with scores."""

    folder_selected = pyqtSignal(str)  # emits folder path when selection changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentItemChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_double_click)
        self._move_callback = None
        self._browse_callback = None

    def set_move_callback(self, callback):
        """Set callback for double-click (triggers move)."""
        self._move_callback = callback

    def set_browse_callback(self, callback):
        """Set callback for when "Browse..." is selected."""
        self._browse_callback = callback

    def set_suggestions(self, suggestions: list[tuple[str, float]]) -> None:
        """Populate list with (folder_name, score_percent) tuples.

        Always appends a "Browse..." entry at the end for picking a custom directory.
        """
        self.clear()
        for folder, score in suggestions:
            text = f"{score:5.1f}%  {folder}"
            item = QListWidgetItem(text)
            item.setData(256, folder)  # store folder path in UserRole
            self.addItem(item)

        # Append browse option
        browse_item = QListWidgetItem("       Browse for folder...")
        browse_item.setData(256, BROWSE_FOLDER)
        self.addItem(browse_item)

        if self.count() > 0:
            self.setCurrentRow(0)

    def selected_folder(self) -> str:
        """Return the currently selected folder path."""
        item = self.currentItem()
        if item:
            return item.data(256)
        return ""

    def select_by_index(self, index: int) -> None:
        """Select a folder by its 0-based index."""
        if 0 <= index < self.count():
            self.setCurrentRow(index)

    def set_custom_folder(self, folder: str) -> None:
        """Replace the Browse entry with a selected custom folder and select it."""
        # Remove the browse item (always last)
        last = self.count() - 1
        if last >= 0 and self.item(last).data(256) == BROWSE_FOLDER:
            self.takeItem(last)

        # Add the custom folder entry + a fresh browse item
        custom_item = QListWidgetItem(f"    ►  {folder}")
        custom_item.setData(256, folder)
        self.addItem(custom_item)

        browse_item = QListWidgetItem("       Browse for folder...")
        browse_item.setData(256, BROWSE_FOLDER)
        self.addItem(browse_item)

        # Select the custom entry
        self.setCurrentItem(custom_item)

    def _on_selection_changed(self, current, _previous):
        if current:
            value = current.data(256)
            if value == BROWSE_FOLDER:
                if self._browse_callback:
                    self._browse_callback()
            else:
                self.folder_selected.emit(value)

    def _on_double_click(self, item):
        if item.data(256) == BROWSE_FOLDER:
            if self._browse_callback:
                self._browse_callback()
        elif self._move_callback:
            self._move_callback()
