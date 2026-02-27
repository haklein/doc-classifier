# Doc Classifier

A local-only document classifier and filer for scanned PDFs. Uses TF-IDF similarity to suggest target folders based on your existing folder structure, and proposes meaningful filenames from document content.

**All processing is strictly local — no network calls, no cloud APIs.**

## Features

- **PDF preview** — renders page 1 of each document
- **Folder suggestions** — ranks up to 30 folders by TF-IDF cosine similarity against existing documents
- **Filename proposals** — three modes: folder pattern matching, content-based best guess, or keep original
- **Smart extraction** — dates (including German/English month names), company/sender names, reference numbers, amounts
- **Browse & create folders** — pick any directory or create new ones from the GUI
- **Move & undo** — move files with collision protection, undo last move with Ctrl+Z
- **Random order** — optionally process inbox files in random order
- **Move logging** — all operations logged to `~/.local/share/doc-classifier/moves.log`

## Requirements

- Python 3.10+
- PyQt6
- pymupdf (fitz)
- pdfminer.six
- scikit-learn
- pyyaml

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python -m src.main
```

On first launch, a setup dialog asks for:
- **Document root** — your organized folder hierarchy (used to learn classification)
- **Scan inbox** — folder containing unfiled PDFs

To force a full re-index of your document root:

```bash
python -m src.main --reindex
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Move file to selected folder |
| Ctrl+M | Move file to selected folder |
| Escape | Skip current file |
| Ctrl+S | Skip current file |
| Ctrl+Z | Undo last move |
| Ctrl+E | Focus filename field |
| 1–9, 0 | Select folder suggestion 1–10 |

## Configuration

Stored at `~/.config/doc-classifier/config.yaml`:

```yaml
document_root: /path/to/organized/documents
scan_inbox: /path/to/unfiled/scans
min_similarity: 0.1
top_n: 30
extensions:
  - .pdf
exclude_folders:
  - .git
  - __pycache__
```

## How It Works

1. **Indexing** — scans all PDFs in `document_root`, extracts text via pdfminer.six, builds a TF-IDF model with combined German+English stopwords, computes per-folder centroid vectors
2. **Classification** — for each unfiled PDF, transforms its text with the fitted vectorizer and ranks folders by cosine similarity
3. **Naming** — analyzes existing filenames in the target folder to detect patterns (prefix, separator, date format), extracts dates/sender/references from document text
4. **Filing** — moves the file, logs the operation, advances to next document

The index is cached at `~/.cache/doc-classifier/index.pkl` for fast subsequent launches.

## Project Structure

```
src/
├── main.py             # Entry point
├── config.py           # YAML configuration
├── extractor.py        # PDF text extraction & page rendering
├── indexer.py          # TF-IDF index builder
├── classifier.py       # Cosine similarity ranking
├── namer.py            # Filename pattern detection & proposal
├── mover.py            # File operations & logging
└── gui/
    ├── main_window.py  # Main application window
    ├── preview.py      # PDF preview widget
    ├── folder_list.py  # Ranked folder suggestion list
    └── setup_dialog.py # First-run setup dialog
```

## License

MIT
