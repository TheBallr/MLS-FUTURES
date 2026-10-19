#!/usr/bin/env python3
"""HISTORICAL (review 2026-10-19): the home edge and total calibration of the 2026-10-12 programme, run on the retired least-squares ratings.
The knob it set is frozen and documented in config.json; the live procedure is in outputs/calibration/README.md.
Calibration 1: league-wide home edge and average total from Pinnacle's closes, per season and pooled; per-club home residuals
(a per-club edge only if the residuals demand it, with several seasons of closes). Report: outputs/calibration/home_total.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim.knobs import load_config, knobs
from sim.teams import ROOT, teams
from sim.ratings import market_fit
from scripts.replay import seasons_on_file

OUT = os.path.join(ROOT, "outputs", "calibration")


def main():
    cfg = load_config(); kn = knobs(cfg)
    seasons = seasons_on_file(cfg)
    if not seasons:
        print("calib_home_total: no seasons with closes on file"); return 1
    lines = ["# Home edge and average total from Pinnacle closes", ""]
    lines.append("| season | matches | mean gd_fit (home edge) | mean T_fit | realised margin | realised total | fitted HE (full-season WLS) |")
    lines.append("|---|---|---|---|---|---|---|")
    pooled = []
    resid_by_club = {}
    for s, df in sorted(seasons.items()):
        d = df.dropna(subset=["gd_fit"]); d = d[d["gd_fit"].astype(float).abs() < 5]
        g = d["gd_fit"].astype(float); T = d["T_fit"].astype(float); hg = d["hg"].astype(float); ag = d["ag"].astype(float)
        Ts = sorted(set(d["home"]) | set(d["away"]))
        mk = market_fit(d.assign(date=d["date"]), Ts, "2100-01-01", 10000, kn["ridge_lambda"], fit_home_edge=True)
        lines.append(f"| {s} | {len(d)} | {g.mean():+.3f} | {T.mean():.3f} | {(hg-ag).mean():+.3f} | {(hg+ag).mean():.3f} | {mk['home_edge']:+.3f} |")
        pooled.append(d)
        # per-club home residual: gd_fit - (R_h - R_a + HE)
        idx = {t: i for i, t in enumerate(Ts)}
        R = mk["ratings"]
        res = g.to_numpy() - (R[d["home"].map(idx)] - R[d["away"].map(idx)] + mk["home_edge"])
        for t, r in zip(d["home"], res):
            resid_by_club.setdefault(t, []).append(float(r))
    allp = pd.concat(pooled)
    g = allp["gd_fit"].astype(float); T = allp["T_fit"].astype(float)
    lines += ["", f"Pooled: {len(allp)} matches, home edge {g.mean():+.3f} (se {g.std()/np.sqrt(len(g)):.3f}), average total {T.mean():.3f} (se {T.std()/np.sqrt(len(T)):.3f}).", ""]
    lines += ["## Per-club home residual (goals; a per-club edge is justified only if |mean| > 2 se over several seasons)", "", "| club | n | mean | se |", "|---|---|---|---|"]
    for t, v in sorted(resid_by_club.items(), key=lambda kv: -abs(np.mean(kv[1]))):
        v = np.array(v); lines.append(f"| {t} | {len(v)} | {v.mean():+.3f} | {v.std()/np.sqrt(len(v)):.3f} |")
    lines += ["", f"Recommendation: home_edge_goals = {g.mean():.2f}, avg_total_goals = {T.mean():.2f} (last two seasons: "
              f"{pd.concat(pooled[-2:])['gd_fit'].astype(float).mean():+.3f} / {pd.concat(pooled[-2:])['T_fit'].astype(float).mean():.3f}). Set in config.json with this report as the note, then freeze."]
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "home_total.md"), "w").write("\n".join(lines))
    json.dump({"home_edge": float(g.mean()), "avg_total": float(T.mean()), "n": int(len(allp))}, open(os.path.join(OUT, "home_total.json"), "w"))
    print("\n".join(lines[-3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
