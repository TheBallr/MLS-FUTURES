"""Config loading. Calibrated knobs are frozen for the season (see CLAUDE.md); nothing here mutates config.json."""
from __future__ import annotations
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config.json")


def load_config(path: str = CONFIG) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def knobs(cfg: dict) -> dict:
    return {k: (v["value"] if isinstance(v, dict) else v) for k, v in cfg["knobs"].items()}
