"""CSV schemas and tolerant loaders. Every file has a fixed header; a missing file loads as an empty frame."""
from __future__ import annotations
import os
import pandas as pd
from .teams import ROOT

DATA = os.path.join(ROOT, "data")
MARKET = os.path.join(DATA, "market")
RATINGS = os.path.join(DATA, "ratings")
HISTORY = os.path.join(DATA, "history")

ODDS_COLS = ["date", "kickoff_utc", "home", "away", "book", "h", "d", "a", "ah_line", "ah_home", "ah_away", "total_line", "over", "under", "fetched_at", "fixture_id"]
SCHEMA = {
    "schedule": (os.path.join(DATA, "schedule.csv"), ["date", "kickoff_utc", "round", "home", "away", "competition", "status", "espn_id"]),
    "results": (os.path.join(DATA, "results.csv"), ["date", "home", "away", "hg", "ag", "competition", "source"]),
    "current_round_odds": (os.path.join(MARKET, "current_round_odds.csv"), ODDS_COLS),
    "closing_lines": (os.path.join(MARKET, "closing_lines.csv"), ODDS_COLS),
    "futures_odds": (os.path.join(MARKET, "futures_odds.csv"), ["date", "market", "team", "line", "price_american", "price_decimal", "book", "fetched_at", "source"]),
    "sources": (os.path.join(RATINGS, "sources.csv"), ["team"]),
    "source_config": (os.path.join(RATINGS, "source_config.csv"), ["source", "enabled", "weight", "note"]),
    "blend": (os.path.join(RATINGS, "blend.csv"), ["team", "rating", "n_closes", "generated"]),
    "injuries": (os.path.join(RATINGS, "injuries.csv"), ["team", "player", "value_goals", "out_from", "expected_return", "prob_out", "tier", "note", "source", "updated"]),
    "callups": (os.path.join(RATINGS, "callups.csv"), ["team", "player", "window_start", "window_end", "prob_out", "tier", "note", "updated"]),
    "scenarios": (os.path.join(RATINGS, "scenarios.csv"), ["team", "type", "prob", "mean", "sd", "min", "from", "to", "note"]),
    "adjustments": (os.path.join(RATINGS, "adjustments.csv"), ["team", "goals", "from", "to", "reason", "date_set"]),
    "hand_log": (os.path.join(RATINGS, "hand_log.csv"), ["week", "team", "goals", "saved_at", "source", "note"]),
    "xg_history": (os.path.join(RATINGS, "xg_history.csv"), ["date", "home", "away", "home_xg", "away_xg", "source", "game_id"]),
    "clv_log": (os.path.join(DATA, "market", "clv_log.csv"), ["date", "home", "away", "opener_run", "g_model_opener", "g_pinn_opener", "g_pinn_close", "disagree", "attack", "moved_our_way", "move_goals", "updated"]),
}


def path(name: str) -> str:
    return SCHEMA[name][0]


def cols(name: str) -> list[str]:
    return SCHEMA[name][1]


def load(name: str) -> pd.DataFrame:
    p, c = SCHEMA[name]
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return pd.DataFrame(columns=c)
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    for col in c:
        if col not in df.columns:
            df[col] = ""
    return df


def save(name: str, df: pd.DataFrame):
    p, c = SCHEMA[name]
    os.makedirs(os.path.dirname(p), exist_ok=True)
    extra = [x for x in df.columns if x not in c]
    df[c + extra].to_csv(p, index=False)


def num(df: pd.DataFrame, columns) -> pd.DataFrame:
    df = df.copy()
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_history() -> pd.DataFrame:
    """All seasons under data/history/*.csv: date, home, away, hg, ag, h, d, a (decimal closes), book, season."""
    frames = []
    if os.path.isdir(HISTORY):
        for f in sorted(os.listdir(HISTORY)):
            if f.endswith(".csv"):
                df = pd.read_csv(os.path.join(HISTORY, f), dtype=str, keep_default_na=False)
                frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["season", "date", "home", "away", "hg", "ag", "h", "d", "a", "book"])
    return pd.concat(frames, ignore_index=True)


def merge_results(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Merge result rows on (date, home, away): a manual row wins over a feed row; otherwise the latest row wins."""
    key = ["date", "home", "away"]
    out = pd.concat([existing, new], ignore_index=True)
    if len(out) == 0:
        return out
    out["_pri"] = out["source"].map(lambda s: 2 if s == "manual" else 1)
    out = out.sort_values(["_pri"], kind="stable").drop_duplicates(key, keep="last").drop(columns="_pri")
    return out.sort_values(["date", "home"]).reset_index(drop=True)
