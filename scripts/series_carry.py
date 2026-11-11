#!/usr/bin/env python3
"""Does a playoff series' first Pinnacle close carry into the later games' closes? (review 2026-11-11)
For every pair that met twice or more in one season's playoffs (two-leg ties 2012-2018, best-of-three Round One 2023-2025; rows from
scripts/playoff_strength.py -> outputs/calibration/playoff_strength.csv): r1 = game 1 close minus the regular-season ratings' price,
rk = the same for each later game, both from the game 1 host's side. Slope of rk on r1 = the share of the game 1 gap that is still in
the later lines (0 = the later games are priced off the ratings, 1 = off the game 1 line). m1 = game 1's result minus its close."""
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.teams import ROOT
d = pd.read_csv(os.path.join(ROOT, "outputs", "calibration", "playoff_strength.csv")); d = d[d.kind == "playoff"].copy()
d["res"] = d.close - d.pred_full; d["pair"] = [ "|".join(sorted(x)) for x in zip(d.home, d.away)]
rows = []
for (s, p), g in d.groupby(["season", "pair"]):
    g = g.sort_values("date")
    if len(g) < 2: continue
    g1 = g.iloc[0]
    for k in range(1, len(g)):
        gk = g.iloc[k]
        rows.append(dict(season=s, pair=p, k=k, r1=g1.res, rk=gk.res if gk.home == g1.home else -gk.res, m1=(g1.hg - g1.ag) - g1.close))
x = pd.DataFrame(rows); x.to_csv(os.path.join(ROOT, "outputs", "calibration", "series_carry_rows.csv"), index=False)
out = ["# Series carry: game 1 close v the later games' closes (scripts/series_carry.py)", "",
       "| sample | n | slope of later gap on game 1 gap (se) | game 1 result surprise (se) | rmse carry 0 | 0.5 | 0.75 | 1.0 |", "|---|---|---|---|---|---|---|---|"]
for lab, sub in (("all", x), ("best-of-three 2023-2025", x[x.season >= 2023]), ("two-leg 2012-2018", x[x.season < 2023])):
    A = np.c_[np.ones(len(sub)), sub.r1.values, sub.m1.values]; b = np.linalg.lstsq(A, sub.rk.values, rcond=None)[0]
    e = sub.rk.values - A @ b; se = np.sqrt(np.diag(np.linalg.inv(A.T @ A) * e.var(ddof=3)))
    rm = [np.sqrt(((sub.rk - w * sub.r1) ** 2).mean()) for w in (0, 0.5, 0.75, 1.0)]
    out.append(f"| {lab} | {len(sub)} | {b[1]:.2f} ({se[1]:.2f}) | {b[2]:+.3f} ({se[2]:.3f}) | " + " | ".join(f"{v:.3f}" for v in rm) + " |")
open(os.path.join(ROOT, "outputs", "calibration", "series_carry.md"), "w").write("\n".join(out) + "\n"); print("\n".join(out))
