"""dashboard/config.py — dashboard-wide runtime config, read from config.json.

Single source for the sample/full data-mode toggle used by both data.py
(Pages 1-2) and model_data.py (Model section) — previously each hardcoded
its own USE_SAMPLE literal, so switching modes meant editing two files.
Edit config.json to switch modes; no code edit needed. Falls back to the
"sample" default if config.json is missing or omits the key.
"""
from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
_DEFAULT = {"data_mode": "sample"}


def _load() -> dict:
    if not _CONFIG_PATH.exists():
        return dict(_DEFAULT)
    return {**_DEFAULT, **json.loads(_CONFIG_PATH.read_text())}


_config = _load()

DATA_MODE: str = _config["data_mode"]
if DATA_MODE not in ("sample", "full"):
    raise ValueError(f"config.json: data_mode must be 'sample' or 'full', got {DATA_MODE!r}")

USE_SAMPLE: bool = DATA_MODE == "sample"
