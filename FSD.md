# Functional Specification Document: Local Document Classifier & Filer

**Version:** 1.0
**Date:** 2026-02-27
**Status:** Draft

---

## 1. Overview

### 1.1 Problem Statement

Years of ScanSnap-scanned, OCR'd PDF documents have accumulated in a flat folder with timestamp-based filenames. Previously managed by a Mac-based auto-classifier, the documents now need to be sorted into an existing folder hierarchy and renamed meaningfully — without relying on any external/cloud-based AI services due to confidentiality.

### 1.2 Solution Summary

A local-only Python application with a GUI that:

1. Learns the existing folder structure and naming conventions from already-filed documents.
2. Presents each unfiled PDF one at a time with a preview.
3. Suggests the most likely target folder and a meaningful filename.
4. Lets the user confirm, adjust, or skip, then moves the file.

### 1.3 Privacy Constraint

All processing is strictly local. No network calls, no external APIs, no cloud models. OCR text extraction and classification happen entirely on-device using only local libraries.

---

## 2. Architecture

### 2.1 Technology Stack

| Component         | Choice                        | Rationale                                    |
|--------------------|-------------------------------|----------------------------------------------|
| Language           | Python 3.10+                  | Rich ecosystem for PDF/NLP/GUI               |
| GUI framework      | PyQt6                         | Mature, well-supported on Linux, PDF preview |
| PDF text extraction| pdfminer.six                  | Pure Python, no external deps                |
| PDF rendering      | pymupdf (fitz)                | Fast page-to-image for preview               |
| Text similarity    | scikit-learn (TF-IDF + cosine)| Local, no model download, proven approach    |
| Filename proposal  | Rule-based keyword extraction | No ML model needed                           |

### 2.2 Component Diagram

```
┌─────────────────────────────────────────────────────┐
│                    GUI (PyQt6)                       │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ PDF      │  │ Folder       │  │ Filename      │  │
│  │ Preview  │  │ Suggestions  │  │ Editor        │  │
│  │ (page 1) │  │ (ranked list)│  │ + Move/Skip   │  │
│  └──────────┘  └──────────────┘  └───────────────┘  │
└────────────┬───────────────────────────┬─────────────┘
             │                           │
     ┌───────▼───────┐          ┌───────▼────────┐
     │  Classifier   │          │  File Mover    │
     │  (TF-IDF +    │          │  (rename +     │
     │   cosine sim) │          │   shutil.move) │
     └───────┬───────┘          └────────────────┘
             │
     ┌───────▼───────┐
     │  Index Builder │
     │  (scan filed   │
     │   docs, build  │
     │   TF-IDF model)│
     └───────┬───────┘
             │
     ┌───────▼───────┐
     │  Text Extractor│
     │  (pdfminer.six)│
     └────────────────┘
```

---

## 3. Functional Requirements

### 3.1 Index Building (Learning Phase)

**FR-1:** On first run (or when explicitly triggered), the application scans a user-configured **document root** directory recursively.

**FR-2:** For each PDF found in the document root:
- Extract text from all pages via pdfminer.six.
- Record the file's relative path (folder + filename) as its category label.
- Store extracted text associated with its folder path.

**FR-3:** Build a TF-IDF vectorizer from all extracted texts, grouped by folder. Each folder becomes a "class" represented by the centroid (mean vector) of all documents it contains.

**FR-4:** Persist the index to a local cache file (`~/.cache/doc-classifier/index.pkl`) so subsequent runs don't require a full rescan. Store a file-hash manifest to detect changes.

**FR-5:** The index includes:
- TF-IDF vectorizer (fitted vocabulary)
- Per-folder centroid vectors
- Per-folder filename patterns (see 3.3)
- Per-folder document count
- File hash manifest for incremental updates

### 3.2 Folder Classification

**FR-6:** For a given unfiled PDF, extract its text and transform it using the fitted TF-IDF vectorizer.

**FR-7:** Compute cosine similarity between the document's TF-IDF vector and every folder centroid.

**FR-8:** Return the top 10 folders ranked by descending similarity score, each with a confidence percentage (similarity normalized to 0–100%).

**FR-9:** If the highest similarity is below a configurable threshold (default: 10%), prepend a special entry `[NEW FOLDER]` to the suggestion list, signaling the document may not fit any existing category.

### 3.3 Filename Proposal

**FR-10:** Analyze existing filenames within each folder to detect naming patterns:
- Common prefixes (e.g., `Rechnung_`, `Gehaltsabrechnung_`)
- Date formats used (e.g., `YYYY-MM-DD`, `YYYY_MM`)
- Separators (underscore, hyphen, space)
- Keyword positions

**FR-11:** For the top-ranked folder, propose a filename by:
1. Extracting key terms from the document text (dates, amounts, company/sender names, reference numbers) using regex patterns for:
   - Dates: multiple formats (`DD.MM.YYYY`, `YYYY-MM-DD`, `MM/DD/YYYY`, etc.)
   - Monetary amounts: `€`, `EUR`, `USD`, currency patterns
   - Common identifiers: invoice numbers, policy numbers, account numbers
2. Applying the detected naming pattern of the target folder.
3. Appending `.pdf` extension.

**FR-12:** When the user selects a different target folder from the list, the filename proposal updates to match that folder's naming pattern.

### 3.4 GUI

**FR-13:** Single-window application with the following layout:

```
┌─────────────────────────────────────────────────────────────┐
│  Doc Classifier                                    [x]      │
├─────────────────────────┬───────────────────────────────────┤
│                         │  Source: /scans/20231015_1423.pdf │
│                         ├───────────────────────────────────┤
│                         │  Target folder:                   │
│    PDF Preview          │  ┌───────────────────────────┐    │
│    (first page,         │  │ ● 87% Rechnungen/Strom    │    │
│     scaled to fit)      │  │   72% Rechnungen/Telefon  │    │
│                         │  │   65% Versicherungen      │    │
│                         │  │   ...                     │    │
│                         │  │   12% Verträge/Handy      │    │
│                         │  └───────────────────────────┘    │
│                         ├───────────────────────────────────┤
│                         │  Filename:                        │
│                         │  ┌───────────────────────────┐    │
│                         │  │ Rechnung_Strom_2023-10-15 │    │
│                         │  └───────────────────────────┘    │
│                         ├───────────────────────────────────┤
│                         │  Progress: 14 / 237               │
│                         │  ┌────────┐  ┌────────┐          │
│                         │  │  Move  │  │  Skip  │          │
│                         │  └────────┘  └────────┘          │
└─────────────────────────┴───────────────────────────────────┘
```

**FR-14:** PDF Preview panel:
- Renders page 1 of the current PDF as an image using pymupdf.
- Scales to fit the available panel area, maintaining aspect ratio.
- Scroll or zoom is nice-to-have, not required for v1.

**FR-15:** Folder suggestion list:
- Displays top 10 folders with similarity percentage.
- Radio-button or click-to-select interaction.
- Top entry is pre-selected.
- Selecting a different folder updates the filename proposal (FR-12).
- Double-clicking a folder entry triggers "Move" immediately.

**FR-16:** Filename field:
- Editable text input, pre-filled with the proposal.
- `.pdf` extension is appended automatically if omitted.
- Invalid filesystem characters are rejected in real-time.

**FR-17:** Action buttons:
- **Move**: Moves the PDF to `<document_root>/<selected_folder>/<filename>.pdf`. If a file with that name exists, append `_1`, `_2`, etc. Advances to the next unfiled document.
- **Skip**: Leaves the file in place, advances to the next.

**FR-18:** Progress indicator showing `current / total` unfiled documents.

**FR-19:** Keyboard shortcuts:
- `Enter` or `Ctrl+M`: Move
- `Ctrl+S` or `Escape`: Skip
- `1`–`9`, `0`: Select folder suggestion 1–10 (when filename field is not focused)
- `Ctrl+E`: Focus the filename field

### 3.5 Configuration

**FR-20:** Configuration via a YAML file at `~/.config/doc-classifier/config.yaml`:

```yaml
# Root directory containing the organized folder structure
document_root: /home/user/Documents/Ablage

# Directory containing unfiled scanned PDFs
scan_inbox: /home/user/Documents/ScanSnap

# Minimum similarity threshold (below this, suggest [NEW FOLDER])
min_similarity: 0.10

# Number of folder suggestions to show
top_n: 10

# File extensions to process
extensions:
  - .pdf

# Folders to exclude from indexing
exclude_folders:
  - .git
  - __pycache__
```

**FR-21:** On first launch, if no config file exists, show a setup dialog asking for `document_root` and `scan_inbox` paths (with directory picker dialogs).

### 3.6 File Operations

**FR-22:** Before any move, verify:
- Target directory exists (create if it doesn't — the user may have typed a new subfolder in the folder suggestion).
- **No filename collision** — documents are never silently overwritten. If a file with the same name exists, show a warning dialog offering the user to either pick a different name (pre-filled with an auto-incremented suggestion like `_1`, `_2`) or cancel the move.
- Source file is still present (hasn't been moved externally).

**FR-23:** Log all move operations to `~/.local/share/doc-classifier/moves.log` in the format:
```
2026-02-27T14:30:00 MOVE /scans/20231015_1423.pdf -> /Ablage/Rechnungen/Strom/Rechnung_Strom_2023-10-15.pdf
2026-02-27T14:30:15 SKIP /scans/20231015_1424.pdf
```

**FR-24:** Support an undo for the last move operation (`Ctrl+Z`): moves the file back to inbox and returns to it in the queue.

---

## 4. Non-Functional Requirements

**NFR-1:** Entire application runs offline. Zero network access.

**NFR-2:** Index building for 1,000 documents should complete in under 5 minutes on a modern machine. Show a progress bar during indexing.

**NFR-3:** Per-document classification (TF-IDF transform + cosine similarity for top-10) should take under 500ms.

**NFR-4:** PDF preview rendering should take under 1 second per page.

**NFR-5:** Memory usage should stay under 500MB for a 5,000-document index.

---

## 5. Data Flow

### 5.1 Indexing Flow

```
document_root/
├── Rechnungen/
│   ├── Strom/
│   │   ├── Rechnung_Strom_2023-01-15.pdf  ──► extract text ──► TF-IDF
│   │   └── Rechnung_Strom_2023-04-15.pdf  ──► extract text ──► TF-IDF
│   └── Telefon/
│       └── ...
├── Versicherungen/
│   └── ...
└── Gehalt/
    └── ...

Result: { folder_path → centroid_vector, filename_patterns }
```

### 5.2 Classification Flow

```
unfiled.pdf
    │
    ▼
extract text (pdfminer)
    │
    ▼
TF-IDF transform (fitted vectorizer)
    │
    ▼
cosine_similarity(doc_vector, all_centroids)
    │
    ▼
top 10 folders + scores
    │
    ▼
filename proposal (patterns from top folder + extracted dates/keywords)
    │
    ▼
GUI presents to user
    │
    ├── [Move] → shutil.move() + log
    └── [Skip] → log + next
```

---

## 6. Project Structure

```
doc-classifier/
├── FSD.md                  # This document
├── requirements.txt        # Python dependencies
├── src/
│   ├── __init__.py
│   ├── main.py             # Entry point, arg parsing
│   ├── config.py           # Config loading/saving, first-run setup
│   ├── indexer.py          # Scan document_root, build TF-IDF index
│   ├── extractor.py        # PDF text extraction (pdfminer.six)
│   ├── classifier.py       # TF-IDF similarity ranking
│   ├── namer.py            # Filename pattern detection & proposal
│   ├── mover.py            # File move operations & logging
│   └── gui/
│       ├── __init__.py
│       ├── main_window.py  # Main application window
│       ├── preview.py      # PDF page renderer widget
│       ├── folder_list.py  # Ranked folder suggestion widget
│       └── setup_dialog.py # First-run configuration dialog
└── tests/
    ├── test_extractor.py
    ├── test_classifier.py
    └── test_namer.py
```

---

## 7. Dependencies

```
PyQt6>=6.5
pymupdf>=1.23
pdfminer.six>=20221105
scikit-learn>=1.3
pyyaml>=6.0
```

---

## 8. Resolved Design Decisions

1. **Language of documents**: Mixed German and English. TF-IDF uses combined stopword lists for both languages.
2. **Multi-page extraction**: All pages are extracted for classification accuracy. Only page 1 is rendered for GUI preview.
3. **Incremental indexing**: Lazy update — index is marked dirty when documents are moved and rebuilt on next application launch (or manual trigger via menu/button).
4. **Overwrite protection**: Documents are **never** overwritten. If a file with the target name already exists, the move is refused and the user is shown a warning dialog with options to pick a different name. The auto-increment suffix (`_1`, `_2`, ...) from FR-22 serves as a suggestion in that dialog, but the user must confirm.
