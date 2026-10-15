#!/usr/bin/env python3
"""Calibration 2 (and the scorecard's core): half-life grid 7/14/21/28 days for the market fit, scored on predicting the next
ten closes (gd_fit) walk-forward over every season on file. Report: outputs/calibration/half_life.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim.knobs import load_config, knobs
from sim.teams import ROOT
from sim.ratings import market_fit
from scripts.replay import seasons_on_file

OUT = os.path.join(ROOT, "outputs", "calibration")
GRID = [7, 14, 21, 28, 45]


def next_ten_score(df: pd.DataFrame, half_life: float, kn: dict, min_matches=40, step_dates=1, ridge=None) -> dict:
    """Walk forward by date: fit on closes strictly before d, score the next ten matches (by date order) on rmse of gd_fit."""
    Ts = sorted(set(df["home"]) | set(df["away"])); idx = {t: i for i, t in enumerate(Ts)}
    df = df.dropna(subset=["gd_fit"]).sort_values("date").reset_index(drop=True)
    dates = sorted(df["date"].unique())
    errs = []
    for d in dates[::step_dates]:
        before = df[df["date"] < d]
        if len(before) < min_matches:
            continue
        nxt = df[df["date"] >= d].head(10)
        mk = market_fit(before, Ts, d, half_life, kn["ridge_lambda"] if ridge is None else ridge, fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True)
        R = mk["ratings"]
        pred = R[nxt["home"].map(idx)] - R[nxt["away"].map(idx)] + kn["home_edge_goals"]
        errs.extend((nxt["gd_fit"].astype(float).to_numpy() - pred).tolist())
    e = np.array(errs)
    return {"n": int(len(e)), "rmse": float(np.sqrt((e ** 2).mean())) if len(e) else np.nan, "mae": float(np.abs(e).mean()) if len(e) else np.nan}


def main():
    cfg = load_config(); kn = knobs(cfg)
    seasons = seasons_on_file(cfg)
    if not seasons:
        print("calib_half_life: no seasons on file"); return 1
    lines = ["# Half-life grid: rmse (goals) predicting the next ten closes, walk-forward", "", "| season | " + " | ".join(f"hl {h}" for h in GRID) + " |", "|---|" + "---|" * len(GRID)]
    tot = {h: [] for h in GRID}
    for s, df in sorted(seasons.items()):
        row = []
        for h in GRID:
            sc = next_ten_score(df, h, kn); row.append(sc); tot[h].append(sc)
        lines.append(f"| {s} ({row[0]['n']}) | " + " | ".join(f"{r['rmse']:.4f}" for r in row) + " |")
    pooled = {h: float(np.sqrt(np.average([r["rmse"] ** 2 for r in tot[h]], weights=[r["n"] for r in tot[h]]))) for h in GRID}
    best = min(pooled, key=pooled.get)
    lines += ["", "Pooled: " + ", ".join(f"hl {h}: {v:.4f}" for h, v in pooled.items()), f"Best: {best} days (current config {kn['half_life_days']})."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "half_life.md"), "w").write("\n".join(lines))
    json.dump(pooled, open(os.path.join(OUT, "half_life.json"), "w"))
    print("\n".join(lines[-2:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
