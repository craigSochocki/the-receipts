"""Shared config loader for The Receipts pipeline scripts.

Every script loads config.yaml (repo root) through load_config() and
resolves paths relative to the repo root, so the repo runs from any
checkout location and from any working directory.

Usage in a script (src/**/*.py):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
    from src.common.config import load_config
    CFG = load_config()
    ROOT = CFG["_root"]            # pathlib.Path to the repo root
    IM = str(ROOT / CFG["paths"]["intermediate"])

`load_config()` finds the root from this file's own location
(src/common/ -> parents[2]), never from the working directory.
"""
from pathlib import Path

import yaml


def repo_root():
    """Repo root = two levels above src/common/ (the directory holding
    config.yaml)."""
    return Path(__file__).resolve().parents[2]


def load_config():
    """Load config.yaml from the repo root. Returns the parsed dict plus
    `_root` (pathlib.Path). Raises if config.yaml is missing."""
    root = repo_root()
    cfg_path = root / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    cfg["_root"] = root
    return cfg
