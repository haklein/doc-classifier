"""Configuration loading and saving."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path.home() / ".config" / "doc-classifier"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class Config:
    document_root: str = ""
    scan_inbox: str = ""
    min_similarity: float = 0.10
    top_n: int = 30
    extensions: list[str] = field(default_factory=lambda: [".pdf"])
    exclude_folders: list[str] = field(
        default_factory=lambda: [".git", "__pycache__"]
    )


def load() -> Optional[Config]:
    """Load config from YAML file. Returns None if file doesn't exist."""
    if not CONFIG_PATH.exists():
        return None
    with open(CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f)
    if not data:
        return None
    return Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__})


def save(config: Config) -> None:
    """Save config to YAML file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    from dataclasses import asdict
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(asdict(config), f, default_flow_style=False)
