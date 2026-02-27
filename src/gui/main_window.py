"""Main application window."""

import random
import re
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..classifier import classify
from ..config import Config
from ..indexer import Index
from ..mover import CollisionError, move_file, skip_file, undo_last
from ..namer import detect_patterns, guess_name, propose_name
from ..extractor import extract_text
from .folder_list import BROWSE_FOLDER, FolderList
from .preview import PdfPreview

# Characters not allowed in filenames
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class MainWindow(QMainWindow):
    def __init__(self, config: Config, index: Index, inbox_files: list[Path]):
        super().__init__()
        self.config = config
        self.index = index
        self.inbox_files = list(inbox_files)
        self.current_idx = 0

        self.setWindowTitle("Doc Classifier")
        self.setMinimumSize(900, 600)
        self.resize(1100, 750)

        self._build_ui()
        self._setup_shortcuts()

        if self.inbox_files:
            self._show_document(0)
        else:
            self._show_empty()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Left: PDF preview
        self.preview = PdfPreview()
        main_layout.addWidget(self.preview, stretch=1)

        # Right: controls
        right = QVBoxLayout()
        main_layout.addLayout(right, stretch=1)

        # Source label
        self.source_label = QLabel("Source: —")
        self.source_label.setWordWrap(True)
        right.addWidget(self.source_label)

        # Folder suggestions
        right.addWidget(QLabel("Target folder:"))
        self.folder_list = FolderList()
        self.folder_list.folder_selected.connect(self._on_folder_selected)
        self.folder_list.set_move_callback(self._do_move)
        self.folder_list.set_browse_callback(self._browse_folder)
        right.addWidget(self.folder_list, stretch=1)

        # Original filename + new filename field
        self.original_name_label = QLabel("Original: —")
        self.original_name_label.setStyleSheet("color: #666;")
        right.addWidget(self.original_name_label)
        right.addWidget(QLabel("Filename:"))
        self.filename_edit = QLineEdit()
        self.filename_edit.textChanged.connect(self._sanitize_filename)
        right.addWidget(self.filename_edit)

        # Filename preset buttons
        name_btn_row = QHBoxLayout()
        self.keep_name_btn = QPushButton("Keep original")
        self.keep_name_btn.setToolTip("Use the current source filename")
        self.keep_name_btn.clicked.connect(self._use_original_name)
        name_btn_row.addWidget(self.keep_name_btn)

        self.guess_name_btn = QPushButton("Best guess")
        self.guess_name_btn.setToolTip("Generate a filename from the document content")
        self.guess_name_btn.clicked.connect(self._use_guessed_name)
        name_btn_row.addWidget(self.guess_name_btn)

        self.pattern_name_btn = QPushButton("Folder pattern")
        self.pattern_name_btn.setToolTip("Match the naming pattern of the target folder")
        self.pattern_name_btn.clicked.connect(self._update_filename_proposal)
        name_btn_row.addWidget(self.pattern_name_btn)

        right.addLayout(name_btn_row)

        # Progress + random toggle
        progress_row = QHBoxLayout()
        self.progress_label = QLabel("Progress: 0 / 0")
        progress_row.addWidget(self.progress_label)
        self.random_cb = QCheckBox("Random order")
        self.random_cb.setToolTip("Pick the next document randomly instead of sequentially")
        progress_row.addWidget(self.random_cb)
        right.addLayout(progress_row)

        # Buttons
        btn_row = QHBoxLayout()
        self.move_btn = QPushButton("Move")
        self.move_btn.clicked.connect(self._do_move)
        btn_row.addWidget(self.move_btn)

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.clicked.connect(self._do_skip)
        btn_row.addWidget(self.skip_btn)

        self.undo_btn = QPushButton("Undo (Ctrl+Z)")
        self.undo_btn.clicked.connect(self._do_undo)
        btn_row.addWidget(self.undo_btn)

        right.addLayout(btn_row)

    def _setup_shortcuts(self):
        # Move: Enter, Ctrl+M
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._shortcut_move)
        QShortcut(QKeySequence("Ctrl+M"), self, self._do_move)

        # Skip: Escape, Ctrl+S
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._do_skip)
        QShortcut(QKeySequence("Ctrl+S"), self, self._do_skip)

        # Undo: Ctrl+Z
        QShortcut(QKeySequence("Ctrl+Z"), self, self._do_undo)

        # Focus filename: Ctrl+E
        QShortcut(QKeySequence("Ctrl+E"), self, self.filename_edit.setFocus)

        # Number keys 1-9, 0 for folder selection
        for i in range(10):
            key = str(i) if i > 0 else "0"
            idx = i - 1 if i > 0 else 9  # 1->0, 2->1, ..., 9->8, 0->9
            QShortcut(
                QKeySequence(key),
                self,
                lambda checked=False, x=idx: self._select_folder_by_key(x),
            )

    def _shortcut_move(self):
        """Handle Enter key — only move if filename field isn't focused."""
        if not self.filename_edit.hasFocus():
            self._do_move()

    def _select_folder_by_key(self, index: int):
        """Select folder by number key, only when filename field isn't focused."""
        if not self.filename_edit.hasFocus():
            self.folder_list.select_by_index(index)

    def _show_document(self, idx: int):
        if idx >= len(self.inbox_files):
            self._show_empty()
            return

        self.current_idx = idx
        pdf_path = self.inbox_files[idx]

        # Update source label
        self.source_label.setText(f"Source: {pdf_path}")

        # Render preview
        self.preview.set_pdf(pdf_path)

        # Classify
        text = extract_text(pdf_path)
        suggestions = classify(
            text, self.index,
            top_n=self.config.top_n,
            min_similarity=self.config.min_similarity,
        )
        self.folder_list.set_suggestions(suggestions)

        # Store extracted text and original filename for proposals
        self._current_text = text
        self._original_stem = pdf_path.stem
        self.original_name_label.setText(f"Original: {pdf_path.name}")

        # Update filename proposal for top folder
        self._update_filename_proposal()

        # Update progress
        total = len(self.inbox_files)
        self.progress_label.setText(f"Progress: {idx + 1} / {total}")

    def _show_empty(self):
        self.preview.clear_preview()
        self.source_label.setText("Source: — (no more documents)")
        self.original_name_label.setText("Original: —")
        self.folder_list.clear()
        self.filename_edit.clear()
        self.progress_label.setText(f"Done! {len(self.inbox_files)} documents processed.")
        self.move_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)

    def _on_folder_selected(self, folder: str):
        self._update_filename_proposal()

    def _update_filename_proposal(self):
        folder = self.folder_list.selected_folder()
        if not folder or folder == "[NEW FOLDER]":
            self.filename_edit.setText("")
            return

        # Get filename patterns for this folder
        filenames = self.index.folder_filenames.get(folder, [])
        pattern = detect_patterns(filenames)

        # Propose name
        text = getattr(self, "_current_text", "")
        name = propose_name(text, pattern)
        self.filename_edit.setText(name)

    def _use_original_name(self):
        """Set filename to the original source filename (without extension)."""
        stem = getattr(self, "_original_stem", "")
        if stem:
            self.filename_edit.setText(stem)

    def _use_guessed_name(self):
        """Set filename to a best-guess derived from document content."""
        text = getattr(self, "_current_text", "")
        name = guess_name(text)
        self.filename_edit.setText(name)

    def _sanitize_filename(self, text: str):
        """Remove invalid filesystem characters in real-time."""
        clean = INVALID_CHARS.sub("", text)
        if clean != text:
            self.filename_edit.setText(clean)

    def _browse_folder(self):
        """Open a directory picker rooted at document_root."""
        root = Path(self.config.document_root)
        dialog = QFileDialog(self, "Select Target Folder", str(root))
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        # Allow creating new directories in the native dialog
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, False)

        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            chosen = Path(dialog.selectedFiles()[0])
            # Make it relative to document_root if it's inside it
            try:
                rel = str(chosen.relative_to(root))
            except ValueError:
                # Chosen path is outside document_root — use absolute
                rel = str(chosen)
            self.folder_list.set_custom_folder(rel)

    def _do_move(self):
        if self.current_idx >= len(self.inbox_files):
            return

        folder = self.folder_list.selected_folder()
        if not folder or folder == BROWSE_FOLDER:
            return

        if folder == "[NEW FOLDER]":
            folder, ok = QInputDialog.getText(
                self, "New Folder", "Enter new folder path (relative to document root):"
            )
            if not ok or not folder:
                return

        filename = self.filename_edit.text().strip()
        if not filename:
            QMessageBox.warning(self, "No filename", "Please enter a filename.")
            return

        src = self.inbox_files[self.current_idx]
        dst_folder = Path(self.config.document_root) / folder

        try:
            move_file(src, dst_folder, filename)
            self._advance()
        except CollisionError as e:
            reply = QMessageBox.warning(
                self,
                "File exists",
                f"A file named '{Path(filename).name}' already exists in this folder.\n\n"
                f"Suggested alternative: {e.suggested_name}\n\n"
                "Use the suggested name?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.filename_edit.setText(Path(e.suggested_name).stem)
                # Retry with suggested name
                try:
                    move_file(src, dst_folder, e.suggested_name)
                    self._advance()
                except Exception as e2:
                    QMessageBox.critical(self, "Error", str(e2))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _do_skip(self):
        if self.current_idx >= len(self.inbox_files):
            return
        skip_file(self.inbox_files[self.current_idx])
        self._advance()

    def _do_undo(self):
        record = undo_last()
        if record is None:
            QMessageBox.information(self, "Undo", "Nothing to undo.")
            return
        # Re-insert the file back into the queue at current position
        self.inbox_files.insert(self.current_idx, record.src)
        self._show_document(self.current_idx)

    def _advance(self):
        """Move to next document (remove current from list)."""
        if self.current_idx < len(self.inbox_files):
            self.inbox_files.pop(self.current_idx)
        if not self.inbox_files:
            self._show_document(0)
            return
        if self.random_cb.isChecked():
            self.current_idx = random.randrange(len(self.inbox_files))
        elif self.current_idx >= len(self.inbox_files):
            self.current_idx = len(self.inbox_files) - 1
        self._show_document(self.current_idx)
