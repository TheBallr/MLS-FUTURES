#!/usr/bin/env python3
"""Public rating sources as backtest recipes. Registers loaders (season, checkpoint, teams) -> rating vector into
scripts/backtest_season._PUBLIC and runs the ratings stage over the public recipes (alone and blended with the market).

Sources (data/public/, written by scripts/fetch_public.py):
  opta    Opta Power Rankings: the latest snapshot dated on or before the checkpoint in the same season (snapshot at date d holds
          matches through d-1). Scale 0-100; the blend step rescales it to the market's spread (PDF).
  fdb     footballdatabase.com Elo-style points: the latest monthly value dated before the checkpoint. Rescaled.
  gplus   ASA goals added: WLS on the team-game g+ difference (home g+ minus away g+), half-life `gplus_hl`, ridge, like the xG fit.
Usage: python3 scripts/public_sources.py --name public1 [--workers 4]"""
from __future__ import annotations
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim.teams import ROOT
from sim.ratings import wls_fit, half_life_weights
import scripts.backtest_season as bt

PUB = os.path.join(ROOT, "data", "public")
_CACHE = {}


def _opta() -> pd.DataFrame:
    if "opta" not in _CACHE:
        p = os.path.join(PUB, "opta", "snapshots.csv")
        d = pd.read_csv(p, dtype={"season": str}) if os.path.exists(p) else pd.DataFrame(columns=["date", "team", "rating", "season"])
        _CACHE["opta"] = d
    return _CACHE["opta"]


def _fdb() -> pd.DataFrame:
    if "fdb" not in _CACHE:
        p = os.path.join(PUB, "footballdatabase", "history.csv")
        _CACHE["fdb"] = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(columns=["date", "team", "points"])
    return _CACHE["fdb"]


def _gplus() -> pd.DataFrame:
    if "gplus" not in _CACHE:
        p = os.path.join(PUB, "asa_gplus", "team_games.csv")
        d = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(columns=["date", "home", "away", "home_gplus", "away_gplus"])
        _CACHE["gplus"] = d
    return _CACHE["gplus"]


def opta_at(season: str, cp: str, T: list, max_age_days: int = 21):
    d = _opta(); d = d[(d["season"] == str(season)) & (d["date"] <= cp)]
    if len(d) == 0:
        return None
    last = d["date"].max()
    if (pd.Timestamp(cp) - pd.Timestamp(last)).days > max_age_days:
        return None
    snap = d[d["date"] == last].set_index("team")["rating"]
    v = np.array([snap.get(t, np.nan) for t in T], float)
    if np.isnan(v).sum() > 2:
        return None
    v = np.where(np.isnan(v), np.nanmean(v), v)
    return v - v.mean()


def fdb_at(season: str, cp: str, T: list, max_age_days: int = 45):
    d = _fdb(); d = d[d["date"] < cp]
    if len(d) == 0:
        return None
    last = d["date"].max()
    if (pd.Timestamp(cp) - pd.Timestamp(last)).days > max_age_days:
        return None
    snap = d[d["date"] == last].set_index("team")["points"]
    v = np.array([snap.get(t, np.nan) for t in T], float)
    if np.isnan(v).sum() > 2:
        return None
    v = np.where(np.isnan(v), np.nanmean(v), v)
    return v - v.mean()


def gplus_fit(cp: str, T: list, half_life: float, ridge: float):
    d = _gplus(); idx = {t: i for i, t in enumerate(T)}
    d = d[d["home"].isin(idx) & d["away"].isin(idx) & (d["date"] < cp)]
    if len(d) < 60:
        return None
    w = half_life_weights(d["date"], cp, half_life)
    y = d["home_gplus"].astype(float).to_numpy() - d["away_gplus"].astype(float).to_numpy()
    R, HE, _ = wls_fit(d["home"].map(idx).to_numpy(), d["away"].map(idx).to_numpy(), y, w, len(T), ridge, True)
    return R


def register():
    bt._PUBLIC["opta"] = lambda s, cp, T: opta_at(s, cp, T)
    bt._PUBLIC["fdb"] = lambda s, cp, T: fdb_at(s, cp, T)
    for hl in (45, 90, 180):
        bt._PUBLIC[f"gplus{hl}"] = (lambda h: (lambda s, cp, T: gplus_fit(cp, T, h, 0.5)))(hl)


register()

RECIPES = {
    "market_live": {"half_life": 28, "ridge": 0.5},
    "live": {"half_life": 28, "ridge": 0.5, "xg_w": 0.25, "xg_hl": 45},
    "opta_alone": {"half_life": 28, "ridge": 0.5, "public": {"opta": 1.0}},
    "fdb_alone": {"half_life": 28, "ridge": 0.5, "public": {"fdb": 1.0}},
    "gplus90_alone": {"half_life": 28, "ridge": 0.5, "public": {"gplus90": 1.0}},
    "gplus180_alone": {"half_life": 28, "ridge": 0.5, "public": {"gplus180": 1.0}},
    "xg_alone_hl90": {"half_life": 28, "ridge": 0.5, "xg_w": 1.0, "xg_hl": 90},
}
for w in (0.15, 0.25, 0.35, 0.5):
    RECIPES[f"m_opta{w}"] = {"half_life": 28, "ridge": 0.5, "public": {"opta": w}}
    RECIPES[f"m_fdb{w}"] = {"half_life": 28, "ridge": 0.5, "public": {"fdb": w}}
    for hl in (45, 90, 180):
        RECIPES[f"m_gplus{hl}_{w}"] = {"half_life": 28, "ridge": 0.5, "public": {f"gplus{hl}": w}}
    RECIPES[f"live_opta{w}"] = {"half_life": 28, "ridge": 0.5, "xg_w": 0.25, "xg_hl": 45, "public": {"opta": w}}
    RECIPES[f"live_gplus90_{w}"] = {"half_life": 28, "ridge": 0.5, "xg_w": 0.25, "xg_hl": 45, "public": {"gplus90": w}}
    RECIPES[f"x90_opta{w}"] = {"half_life": 28, "ridge": 0.5, "xg_w": 0.25, "xg_hl": 90, "public": {"opta": w}}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", default="public1"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", help="comma list of recipe names")
    a = ap.parse_args()
    recipes = {k: v for k, v in RECIPES.items() if not a.only or k in a.only.split(",")}
    df = bt.run("ratings", a.name, recipes, workers=a.workers)
    print(bt.summarize(df, "market_live", "match_ll"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
