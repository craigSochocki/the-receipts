"""Shared config loader for The Receipts pipeline scripts.

Every script loads config.yaml (repo root) through load_config() and
resolves paths relative to the repo root, so the repo runs from any
checkout location and from any working directory.

Usage in a script (work/*.py):
    from config import load_config
    CFG = load_config()
    ROOT = CFG["_root"]            # pathlib.Path to the repo root
    WORK = str(ROOT / CFG["paths"]["work"])

`import config` works from any cwd because Python puts the script's own
directory (work/) first on sys.path when a script is run by path.
"""
from pathlib import Path

import yaml


def repo_root():
    """Repo root = parent of the work/ directory holding this file."""
    return Path(__file__).resolve().parents[1]


def load_config():
    """Load config.yaml from the repo root. Returns the parsed dict plus
    `_root` (pathlib.Path). Raises if config.yaml is missing."""
    root = repo_root()
    cfg_path = root / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    cfg["_root"] = root
    return cfg
