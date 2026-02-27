"""File move operations, undo support, and logging."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_DIR = Path.home() / ".local" / "share" / "doc-classifier"
LOG_PATH = LOG_DIR / "moves.log"


class CollisionError(Exception):
    """Raised when a file with the target name already exists."""

    def __init__(self, existing_path: Path, suggested_name: str):
        self.existing_path = existing_path
        self.suggested_name = suggested_name
        super().__init__(f"File already exists: {existing_path}")


class MoveRecord:
    """Record of a single move operation for undo."""

    def __init__(self, src: Path, dst: Path):
        self.src = src
        self.dst = dst


_last_move: Optional[MoveRecord] = None


def _log(entry: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a") as f:
        f.write(f"{timestamp} {entry}\n")


def _suggest_unique_name(dst_folder: Path, filename: str) -> str:
    """Generate a unique filename with _1, _2, ... suffix."""
    stem = Path(filename).stem
    ext = Path(filename).suffix
    for i in range(1, 1000):
        candidate = f"{stem}_{i}{ext}"
        if not (dst_folder / candidate).exists():
            return candidate
    return f"{stem}_dup{ext}"


def move_file(src: Path, dst_folder: Path, filename: str) -> Path:
    """Move a file to the destination folder with the given filename.

    Raises CollisionError if the target file already exists.
    Returns the final destination path.
    """
    global _last_move

    # Ensure .pdf extension
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    # Create target directory if needed
    dst_folder.mkdir(parents=True, exist_ok=True)

    dst = dst_folder / filename

    if dst.exists():
        suggested = _suggest_unique_name(dst_folder, filename)
        raise CollisionError(dst, suggested)

    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    shutil.move(str(src), str(dst))
    _last_move = MoveRecord(src, dst)

    _log(f"MOVE {src} -> {dst}")
    return dst


def skip_file(src: Path) -> None:
    """Log that a file was skipped."""
    _log(f"SKIP {src}")


def undo_last() -> Optional[MoveRecord]:
    """Undo the last move operation. Returns the MoveRecord if successful."""
    global _last_move

    if _last_move is None:
        return None

    record = _last_move
    if not record.dst.exists():
        _last_move = None
        return None

    # Move back to original location
    shutil.move(str(record.dst), str(record.src))
    _log(f"UNDO {record.dst} -> {record.src}")

    _last_move = None
    return record
