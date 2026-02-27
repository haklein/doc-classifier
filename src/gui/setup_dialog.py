"""First-run setup dialog for configuring document_root and scan_inbox."""

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..config import Config


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Doc Classifier - Setup")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Welcome! Please configure your directories."))
        layout.addSpacing(10)

        # Document root
        layout.addWidget(QLabel("Document root (organized folder structure):"))
        root_row = QHBoxLayout()
        self.root_edit = QLineEdit()
        root_row.addWidget(self.root_edit)
        root_btn = QPushButton("Browse...")
        root_btn.clicked.connect(self._browse_root)
        root_row.addWidget(root_btn)
        layout.addLayout(root_row)

        layout.addSpacing(10)

        # Scan inbox
        layout.addWidget(QLabel("Scan inbox (unfiled PDFs):"))
        inbox_row = QHBoxLayout()
        self.inbox_edit = QLineEdit()
        inbox_row.addWidget(self.inbox_edit)
        inbox_btn = QPushButton("Browse...")
        inbox_btn.clicked.connect(self._browse_inbox)
        inbox_row.addWidget(inbox_btn)
        layout.addLayout(inbox_row)

        layout.addSpacing(20)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_root(self):
        path = QFileDialog.getExistingDirectory(self, "Select Document Root")
        if path:
            self.root_edit.setText(path)

    def _browse_inbox(self):
        path = QFileDialog.getExistingDirectory(self, "Select Scan Inbox")
        if path:
            self.inbox_edit.setText(path)

    def _validate_and_accept(self):
        if self.root_edit.text().strip() and self.inbox_edit.text().strip():
            self.accept()

    def get_config(self) -> Config:
        return Config(
            document_root=self.root_edit.text().strip(),
            scan_inbox=self.inbox_edit.text().strip(),
        )
