#!/usr/bin/env python3
"""Rebuild data/ratings/sources.csv (every source side by side) and blend.csv (generated, never edited) for a date.
Sources: market_recent (WLS on Pinnacle closes, half-life weights), xg (ASA match xG, rescaled to the market's spread).
Usage: python3 scripts/refresh_ratings.py [--asof 2026-10-12]"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import teams, load_teams, ROOT
from sim.ratings import fit_targets, market_fit, xg_fit, blend, apply_expansion_prior

CACHE = os.path.join(ROOT, "outputs", "cache", "gd_fit.csv")
LINE_COLS = ["h", "d", "a", "ah_line", "ah_home", "ah_away", "total_line", "over", "under"]


def _key(r) -> str:
    return hashlib.md5("|".join(str(r.get(c, "")) for c in ["date", "home", "away", "book"] + LINE_COLS).encode()).hexdigest()


def closes_with_targets(cfg: dict, include_history=True) -> pd.DataFrame:
    """One close per match (pinnacle_close > pinnacle_last > avg_close), this season plus history, with gd_fit (cached)."""
    kn = knobs(cfg)
    cl = data.load("closing_lines")
    frames = [cl.assign(season=str(cfg["season"]))]
    if include_history:
        h = data.load_history()
        if len(h):
            h = h.rename(columns={})
            for c in LINE_COLS:
                if c not in h.columns:
                    h[c] = ""
            frames.append(h[["season", "date", "home", "away", "book"] + LINE_COLS])
    df = pd.concat(frames, ignore_index=True)
    if len(df) == 0:
        return pd.DataFrame(columns=["season", "date", "home", "away", "book"] + LINE_COLS + ["gd_fit", "gd_3way", "gd_ah", "T_fit", "ph", "pd", "pa"])
    pri = {"pinnacle_close": 0, "pinnacle_last": 1, "avg_close": 2}
    df["_p"] = df["book"].map(pri).fillna(3)
    df = df.sort_values("_p").drop_duplicates(["date", "home", "away"]).drop(columns="_p")
    df["_k"] = [_key(r) for r in df.to_dict("records")]
    cache = pd.read_csv(CACHE, dtype={"_k": str}) if os.path.exists(CACHE) else pd.DataFrame(columns=["_k", "gd_fit", "gd_3way", "gd_ah", "T_fit", "ph", "pd", "pa"])
    have = df["_k"].isin(cache["_k"])
    todo = df[~have]
    if len(todo):
        fitted = fit_targets(todo[LINE_COLS], kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"])
        fitted["_k"] = todo["_k"].to_numpy()
        cache = pd.concat([cache, fitted[["_k", "gd_fit", "gd_3way", "gd_ah", "T_fit", "ph", "pd", "pa"]]], ignore_index=True)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        cache.to_csv(CACHE, index=False)
    out = df.merge(cache.drop_duplicates("_k"), on="_k", how="left").drop(columns="_k")
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def build_ratings(asof: str, cfg: dict, closes: pd.DataFrame | None = None, xg_hist: pd.DataFrame | None = None, write=True, before=False) -> dict:
    kn = knobs(cfg)
    T = teams()
    closes = closes_with_targets(cfg) if closes is None else closes
    mk = market_fit(closes, T, asof, kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=before)
    R_m = mk["ratings"]
    n_closes = mk["n_closes"]
    exp_mask = np.array([int(r["expansion_year"]) >= int(cfg["season"]) - 1 for r in load_teams()])
    R_m = apply_expansion_prior(R_m, n_closes, kn["expansion_prior_rating"], kn["expansion_closes_threshold"], exp_mask)
    sources = {"market_recent": R_m}
    xg_hist = data.load("xg_history") if xg_hist is None else xg_hist
    xg = xg_fit(data.num(xg_hist, ["home_xg", "away_xg"]), T, asof, kn["xg_half_life_days"], kn["ridge_lambda"], float(R_m.std()) if mk["n"] else None) if len(xg_hist) else {"ratings": np.zeros(len(T)), "n": 0}
    if xg["n"] > 0:
        sources["xg"] = xg["ratings"]
    sc = data.load("source_config")
    if len(sc) == 0:
        sc = pd.DataFrame([{"source": "market_recent", "enabled": "y", "weight": 1.0, "note": "backbone"}, {"source": "xg", "enabled": "y", "weight": 1.0, "note": "ASA xG; weight after scorecard"}])
    R, used = blend(sources, sc)
    out = {"asof": asof, "ratings": R, "sources": sources, "weights": used, "n_closes": n_closes, "market_fit": mk, "xg_n": xg["n"], "teams": T}
    if write:
        src = pd.DataFrame({"team": T, **{k: np.round(v, 4) for k, v in sources.items()}, "n_closes": n_closes})
        data.save("sources", src)
        data.save("blend", pd.DataFrame({"team": T, "rating": np.round(R, 4), "n_closes": n_closes, "generated": asof}))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--asof", default=dt.date.today().isoformat()); a = ap.parse_args()
    cfg = load_config()
    out = build_ratings(a.asof, cfg)
    mk = out["market_fit"]
    print(f"refresh_ratings: {mk['n']} closes in fit, residual sd {mk['resid_sd']:.3f} goals, xg games {out['xg_n']}, weights {out['weights']}")
    order = np.argsort(-out["ratings"])
    print("  " + ", ".join(f"{out['teams'][i]} {out['ratings'][i]:+.2f}" for i in order[:5]) + " ... " + ", ".join(f"{out['teams'][i]} {out['ratings'][i]:+.2f}" for i in order[-3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
