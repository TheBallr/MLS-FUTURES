#!/usr/bin/env python3
"""Calibration 5: drift from the market. For each team, closing-line rating at successive dates (closes-only fit) is a random walk;
measure (a) the market's own drift per team-match (sd of weekly rating changes) and (b) its re-rating per goal of surprise
(regress the rating change over a week on the team's summed surprise = actual margin - gd_fit in that week).
Then grid drift_k_sim x drift_cap on the points backtest (calib_rating_sd machinery). Report: outputs/calibration/drift.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim.knobs import load_config, knobs
from sim.teams import ROOT
from sim.ratings import market_fit
from scripts.replay import seasons_on_file, season_teams
from scripts.calib_rating_sd import run as grid_run

OUT = os.path.join(ROOT, "outputs", "calibration")


def market_drift(seasons: dict, kn: dict) -> list[str]:
    lines = ["| season | weekly rating sd (market drift) | re-rating per goal of surprise (slope) | n team-weeks |", "|---|---|---|---|"]
    allx, ally = [], []
    for s, df in sorted(seasons.items()):
        T = season_teams(df); idx = {t: i for i, t in enumerate(T)}
        df = df.dropna(subset=["gd_fit"]).sort_values("date")
        dates = pd.to_datetime(sorted(df["date"].unique()))
        if len(dates) < 10:
            continue
        weeks = pd.date_range(dates[0] + pd.Timedelta(days=42), dates[-1], freq="7D")
        prev = None; xs, ys = [], []
        for w in weeks:
            mk = market_fit(df, T, w.strftime("%Y-%m-%d"), kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True)
            R = mk["ratings"]
            if prev is not None:
                wk = df[(pd.to_datetime(df["date"]) >= prev[0]) & (pd.to_datetime(df["date"]) < w)]
                surprise = np.zeros(len(T))
                for r in wk.itertuples(index=False):
                    sp = (float(r.hg) - float(r.ag)) - float(r.gd_fit)
                    surprise[idx[r.home]] += sp; surprise[idx[r.away]] -= sp
                xs.extend(surprise.tolist()); ys.extend((R - prev[1]).tolist())
            prev = (w, R)
        xs, ys = np.array(xs), np.array(ys)
        if len(xs) > 10:
            slope = float(np.polyfit(xs, ys, 1)[0]); lines.append(f"| {s} | {ys.std():.3f} | {slope:+.4f} | {len(xs)} |")
            allx.extend(xs); ally.extend(ys)
    if allx:
        slope = float(np.polyfit(np.array(allx), np.array(ally), 1)[0])
        lines += ["", f"Pooled: weekly sd {np.std(ally):.3f}, re-rating per goal of surprise {slope:+.4f} (the EPL kept k 0.01, cap 0.10)."]
    return lines


def main():
    cfg = load_config(); kn = knobs(cfg)
    seasons = seasons_on_file(cfg)
    if not seasons:
        print("calib_drift: no seasons on file"); return 1
    lines = ["# Drift: the market's random walk and the sim's k", ""] + market_drift(seasons, kn)
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "drift.md"), "w").write("\n".join(lines))
    print(lines[-1])
    grid_run(grid=[0.0, 0.005, 0.01, 0.02, 0.04], n_seasons=3000, key="drift_k_sim", report="drift_k_grid.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
