#!/home/hari/venv/bin/python
"""Doc Classifier — entry point."""

import argparse
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PyQt6.QtCore import Qt

from . import config as cfg
from .gui.main_window import MainWindow
from .gui.setup_dialog import SetupDialog
from .indexer import build_index, load_index, save_index


def _collect_inbox(conf: cfg.Config) -> list[Path]:
    """Collect unfiled PDFs from scan_inbox."""
    inbox = Path(conf.scan_inbox)
    if not inbox.is_dir():
        return []
    files = []
    for ext in conf.extensions:
        files.extend(inbox.glob(f"*{ext}"))
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description="Local Document Classifier & Filer")
    parser.add_argument("--reindex", action="store_true", help="Force rebuild of index")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    # Load or create config
    conf = cfg.load()
    if conf is None:
        dialog = SetupDialog()
        if dialog.exec() != SetupDialog.DialogCode.Accepted:
            sys.exit(0)
        conf = dialog.get_config()
        cfg.save(conf)

    # Validate paths
    if not Path(conf.document_root).is_dir():
        QMessageBox.critical(
            None, "Error",
            f"Document root not found: {conf.document_root}\n\n"
            "Please check your config or delete it to re-run setup."
        )
        sys.exit(1)

    # Load or build index
    index = None
    if not args.reindex:
        index = load_index()

    if index is None:
        progress = QProgressDialog("Building index...", None, 0, 100)
        progress.setWindowTitle("Indexing")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        app.processEvents()

        def on_progress(current, total):
            if total > 0:
                progress.setMaximum(total)
                progress.setValue(current)
                progress.setLabelText(f"Indexing... {current}/{total} documents")
            app.processEvents()

        index = build_index(conf, progress_callback=on_progress)
        save_index(index)
        progress.close()

    # Collect inbox files
    inbox_files = _collect_inbox(conf)

    if not inbox_files:
        QMessageBox.information(
            None, "No documents",
            f"No unfiled documents found in: {conf.scan_inbox}"
        )
        sys.exit(0)

    # Launch main window
    window = MainWindow(conf, index, inbox_files)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
