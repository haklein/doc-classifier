"""Index builder: scan document_root, build TF-IDF model, persist to cache."""

import hashlib
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import Config
from .extractor import extract_text

CACHE_DIR = Path.home() / ".cache" / "doc-classifier"
INDEX_PATH = CACHE_DIR / "index.pkl"

# Combined German + English stopwords
STOPWORDS = {
    # English
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "this", "that",
    "these", "those", "it", "its", "not", "no", "nor", "so", "if", "then",
    "than", "too", "very", "just", "about", "above", "after", "again",
    "all", "also", "am", "any", "as", "because", "before", "between",
    "both", "each", "few", "he", "her", "here", "him", "his", "how", "i",
    "into", "me", "more", "most", "my", "myself", "now", "only", "other",
    "our", "out", "over", "own", "same", "she", "some", "such", "their",
    "them", "there", "they", "through", "under", "up", "us", "we", "what",
    "when", "where", "which", "while", "who", "whom", "why", "you", "your",
    # German
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einem",
    "einen", "einer", "und", "oder", "aber", "nicht", "ist", "sind",
    "war", "waren", "wird", "werden", "wurde", "wurden", "hat", "haben",
    "hatte", "hatten", "sein", "sein", "seine", "seinem", "seinen",
    "seiner", "ihr", "ihre", "ihrem", "ihren", "ihrer", "wir", "sie",
    "es", "ich", "du", "er", "mir", "mich", "dir", "dich", "uns",
    "euch", "sich", "von", "zu", "mit", "auf", "für", "an", "bei",
    "nach", "über", "unter", "vor", "zwischen", "durch", "gegen",
    "ohne", "um", "aus", "bis", "seit", "während", "wegen", "trotz",
    "auch", "noch", "schon", "nur", "sehr", "mehr", "da", "hier",
    "dort", "wo", "wie", "was", "wer", "wenn", "als", "ob", "dass",
    "weil", "denn", "so", "dann", "also", "doch", "ja", "nein",
    "kein", "keine", "keinem", "keinen", "keiner", "alle", "alles",
    "allem", "allen", "aller", "diese", "dieser", "diesem", "diesen",
    "dieses", "jede", "jeder", "jedem", "jeden", "jedes",
}


@dataclass
class Index:
    vectorizer: TfidfVectorizer
    centroids: np.ndarray  # shape: (n_folders, n_features)
    folder_names: list[str]
    folder_doc_counts: dict[str, int]
    folder_filenames: dict[str, list[str]]
    file_hashes: dict[str, str]


def _file_hash(path: Path) -> str:
    h = hashlib.md5()
    h.update(str(path).encode())
    h.update(str(path.stat().st_mtime_ns).encode())
    return h.hexdigest()


def _scan_pdfs(config: Config) -> list[Path]:
    """Find all PDFs in document_root."""
    root = Path(config.document_root)
    exclude = set(config.exclude_folders)
    pdfs = []
    for ext in config.extensions:
        for p in root.rglob(f"*{ext}"):
            if any(part in exclude for part in p.parts):
                continue
            pdfs.append(p)
    return sorted(pdfs)


def build_index(
    config: Config,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Index:
    """Build a fresh TF-IDF index from document_root."""
    root = Path(config.document_root)
    pdfs = _scan_pdfs(config)
    total = len(pdfs)

    folder_texts: dict[str, list[str]] = defaultdict(list)
    folder_filenames: dict[str, list[str]] = defaultdict(list)
    file_hashes: dict[str, str] = {}

    for i, pdf_path in enumerate(pdfs):
        if progress_callback:
            progress_callback(i, total)

        text = extract_text(pdf_path)
        if not text:
            continue

        rel = pdf_path.relative_to(root)
        folder = str(rel.parent)
        folder_texts[folder].append(text)
        folder_filenames[folder].append(rel.name)
        file_hashes[str(rel)] = _file_hash(pdf_path)

    if progress_callback:
        progress_callback(total, total)

    # Build TF-IDF
    folder_names = sorted(folder_texts.keys())
    all_texts = []
    folder_indices = []  # which folder each text belongs to

    for fi, folder in enumerate(folder_names):
        for text in folder_texts[folder]:
            all_texts.append(text)
            folder_indices.append(fi)

    if not all_texts:
        # Empty index
        vectorizer = TfidfVectorizer(stop_words=list(STOPWORDS))
        vectorizer.fit(["dummy"])
        centroids = np.zeros((0, len(vectorizer.get_feature_names_out())))
        return Index(
            vectorizer=vectorizer,
            centroids=centroids,
            folder_names=[],
            folder_doc_counts={},
            folder_filenames=dict(folder_filenames),
            file_hashes=file_hashes,
        )

    vectorizer = TfidfVectorizer(
        stop_words=list(STOPWORDS),
        max_features=50000,
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(all_texts)

    # Compute per-folder centroids
    n_folders = len(folder_names)
    n_features = tfidf_matrix.shape[1]
    centroids = np.zeros((n_folders, n_features))

    for doc_idx, folder_idx in enumerate(folder_indices):
        centroids[folder_idx] += tfidf_matrix[doc_idx].toarray().flatten()

    folder_doc_counts = {}
    for fi, folder in enumerate(folder_names):
        count = len(folder_texts[folder])
        folder_doc_counts[folder] = count
        if count > 0:
            centroids[fi] /= count

    return Index(
        vectorizer=vectorizer,
        centroids=centroids,
        folder_names=folder_names,
        folder_doc_counts=folder_doc_counts,
        folder_filenames=dict(folder_filenames),
        file_hashes=file_hashes,
    )


def save_index(index: Index) -> None:
    """Persist index to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index, f)


def load_index() -> Optional[Index]:
    """Load cached index. Returns None if not found."""
    if not INDEX_PATH.exists():
        return None
    try:
        with open(INDEX_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None
