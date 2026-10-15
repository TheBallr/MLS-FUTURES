"""Config loading. Calibrated knobs are frozen for the season (see CLAUDE.md); nothing here mutates config.json."""
from __future__ import annotations
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config.json")


def load_config(path: str = CONFIG) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def knob(cfg: dict, name: str):
    """Knobs are stored as {"value": x, "note": "..."}; return the value."""
    v = cfg["knobs"][name]
    return v["value"] if isinstance(v, dict) else v


def knobs(cfg: dict) -> dict:
    return {k: (v["value"] if isinstance(v, dict) else v) for k, v in cfg["knobs"].items()}
