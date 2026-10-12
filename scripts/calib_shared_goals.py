#!/usr/bin/env python3
"""Calibration 3: shared-goals mean (a) from Pinnacle's alternate handicap and total ladders (data/market/ladders.csv, captured by
fetch_pinnacle.py --ladders over several rounds): the c that best reproduces the ladder's fair prices given gd_fit and T_fit;
(b) from realised goal-difference and total variance around the closes over history. Report: outputs/calibration/shared_goals.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim.knobs import load_config, knobs
from sim.teams import ROOT
from sim.engine import score_grid, ah_home_fair, total_over_fair, margin_dist, total_dist
from sim.devig import power_devig
from scripts.replay import seasons_on_file

OUT = os.path.join(ROOT, "outputs", "calibration")
GRID = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
LADDERS = os.path.join(ROOT, "data", "market", "ladders.csv")


def realised_variance(seasons: dict, kn: dict) -> list[str]:
    rows = []
    allm = pd.concat(seasons.values()).dropna(subset=["gd_fit", "T_fit"])
    g = allm["gd_fit"].astype(float).to_numpy(); T = allm["T_fit"].astype(float).to_numpy()
    hg = allm["hg"].astype(float).to_numpy(); ag = allm["ag"].astype(float).to_numpy()
    m, t = hg - ag, hg + ag
    lines = [f"Realised over {len(allm)} lined matches: var(margin) {m.var():.3f}, var(total) {t.var():.3f}, E[margin - gd_fit] {np.mean(m-g):+.3f}, E[total - T_fit] {np.mean(t-T):+.3f}", "",
             "| c | model var(margin) | model var(total) | gap (abs sum) |", "|---|---|---|---|"]
    sub = allm.sample(min(400, len(allm)), random_state=0)
    best = None
    for c in GRID:
        vm, vt = [], []
        for r in sub.itertuples(index=False):
            P = score_grid(float(r.gd_fit), float(r.T_fit), kn["goal_floor"], c)
            md, td = margin_dist(P), total_dist(P)
            em = sum(k * p for k, p in md.items()); vm.append(sum((k - em) ** 2 * p for k, p in md.items()))
            et = sum(k * p for k, p in td.items()); vt.append(sum((k - et) ** 2 * p for k, p in td.items()))
        gap = abs(np.mean(vm) - m.var()) + abs(np.mean(vt) - t.var())
        lines.append(f"| {c:.2f} | {np.mean(vm):.3f} | {np.mean(vt):.3f} | {gap:.3f} |")
        if best is None or gap < best[1]:
            best = (c, gap)
    lines += ["", f"Realised-variance answer: c = {best[0]:.2f}"]
    return lines


def ladders(kn: dict) -> list[str]:
    if not os.path.exists(LADDERS):
        return ["No ladders.csv on file (run fetch_pinnacle.py --ladders over several rounds)."]
    L = pd.read_csv(LADDERS, dtype=str, keep_default_na=False)
    L = L[L["kind"].isin(["spread", "total"])]
    fixtures = L.groupby(["date", "home", "away"])
    lines = ["| c | ladder rmse (fair prob) | n prices |", "|---|---|---|"]
    best = None
    for c in GRID:
        errs = []
        for key, g in fixtures:
            try:
                gd, T = float(g["gd_fit"].iloc[0]), float(g["T_fit"].iloc[0])
            except (ValueError, IndexError):
                continue
            P = score_grid(gd, T, kn["goal_floor"], c)
            for r in g.itertuples(index=False):
                try:
                    p1, p2 = power_devig([float(r.price1), float(r.price2)])
                    line = float(r.line)
                except ValueError:
                    continue
                model = ah_home_fair(P, line) if r.kind == "spread" else total_over_fair(P, line)
                errs.append(model - p1)
        e = np.array(errs)
        if len(e):
            rm = float(np.sqrt((e ** 2).mean())); lines.append(f"| {c:.2f} | {rm:.4f} | {len(e)} |")
            if best is None or rm < best[1]:
                best = (c, rm)
    if best:
        lines += ["", f"Ladder answer: c = {best[0]:.2f}"]
    return lines


def main():
    cfg = load_config(); kn = knobs(cfg)
    seasons = seasons_on_file(cfg)
    lines = ["# Shared goals (bivariate Poisson common component)", "", "## From Pinnacle's alternate ladders", ""] + ladders(kn) + ["", "## From realised variance around the closes", ""]
    lines += realised_variance(seasons, kn) if seasons else ["no history on file"]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "shared_goals.md"), "w").write("\n".join(lines))
    print("\n".join(l for l in lines if l.endswith("answer: c = " + l.split("c = ")[-1]) or l.startswith("Realised over")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
