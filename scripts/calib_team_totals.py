#!/usr/bin/env python3
"""Per-team total tendencies (build prompt section 6): walk-forward on every Pinnacle total on file (2025-2026 OpticOdds closes
and this season's closes), the total the sim would use for an unlined fixture against the close's own total: the constant
avg_total_goals, the trailing league mean, and totals_fit at a grid of half-lives and ridges. Rmse in goals of total.
Usage: python3 scripts/calib_team_totals.py"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim.teams import ROOT
from sim.knobs import load_config, knobs
from sim.ratings import totals_fit
from scripts.refresh_ratings import closes_with_targets


def main():
    cfg = load_config(); kn = knobs(cfg)
    c = closes_with_targets(cfg)
    c["T"] = pd.to_numeric(c["T_fit"], errors="coerce"); c["tl"] = pd.to_numeric(c["total_line"], errors="coerce")
    c = c[c["tl"].notna() & c["T"].notna()].sort_values("date").reset_index(drop=True)
    teams = sorted(set(c["home"]) | set(c["away"]))
    dates = sorted(c["date"].unique())
    grid = [(hl, rg) for hl in (30, 60, 90, 180, 365) for rg in (0.25, 0.5, 1.0, 2.0)]
    errs = {"const": [], "trail200": []}; errs.update({f"hl{hl}_r{rg}": [] for hl, rg in grid}); lag7 = {f"hl{hl}_r{rg}": [] for hl, rg in grid}
    for i, d in enumerate(dates):
        if i < 30:
            continue
        bef = c[c["date"] < d]; cur = c[c["date"] == d]
        d7 = (pd.Timestamp(d) - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        fits = {k: totals_fit(c, teams, d, hl, rg) for k, (hl, rg) in zip([f"hl{hl}_r{rg}" for hl, rg in grid], grid)}
        fits7 = {k: totals_fit(c, teams, d7, hl, rg) for k, (hl, rg) in zip([f"hl{hl}_r{rg}" for hl, rg in grid], grid)}
        idx = {t: j for j, t in enumerate(teams)}
        for r in cur.itertuples(index=False):
            errs["const"].append(r.T - kn["avg_total_goals"]); errs["trail200"].append(r.T - bef["T"].tail(200).mean())
            for k, f in fits.items():
                errs[k].append(r.T - (f["base"] + f["offsets"][idx[r.home]] + f["offsets"][idx[r.away]]) if np.isfinite(f["base"]) else np.nan)
            for k, f in fits7.items():
                lag7[k].append(r.T - (f["base"] + f["offsets"][idx[r.home]] + f["offsets"][idx[r.away]]) if np.isfinite(f["base"]) else np.nan)
    lines = [f"{len(c)} closes with a Pinnacle total ({c['date'].min()} to {c['date'].max()}), {sum(len(v) for v in [errs['const']])} scored walk-forward", "", "| model | rmse lag 0 | bias | rmse lag 7 |", "|---|---|---|---|"]
    for k, v in errs.items():
        v = np.array(v, float); m = np.isfinite(v)
        v7 = np.array(lag7.get(k, v), float); m7 = np.isfinite(v7)
        lines.append(f"| {k} | {np.sqrt((v[m] ** 2).mean()):.3f} | {v[m].mean():+.3f} | {np.sqrt((v7[m7] ** 2).mean()):.3f} |")
    best = min((k for k in errs if k.startswith("hl")), key=lambda k: np.nanmean(np.array(errs[k], float) ** 2))
    f = totals_fit(c, teams, (pd.Timestamp(c["date"].max()) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), float(best.split("_")[0][2:]), float(best.split("_r")[1]))
    o = np.argsort(-f["offsets"])
    lines += ["", f"best {best}: league base {f['base']:.2f} today; offsets (goals a club adds to every match it plays): " + ", ".join(f"{teams[i]} {f['offsets'][i]:+.2f}" for i in o)]
    txt = "\n".join(lines); print(txt)
    with open(os.path.join(ROOT, "outputs", "calibration", "team_totals.md"), "w") as fh:
        fh.write("# Per-team total tendencies against Pinnacle's totals\n\n" + txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
