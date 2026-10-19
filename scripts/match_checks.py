#!/usr/bin/env python3
"""Match-level checks from the method PDF, on every lined match on file (closes with results): home/draw/away rates realised vs
the engine at the close's own margin and total vs the devigged close; the draw rate (the Dixon-Coles question); the sd of
(actual margin - closing margin); favourite win rate by closing-probability bucket; realised home edge by season.
Report: outputs/calibration/match_checks.md"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim.knobs import load_config, knobs
from sim.teams import ROOT
from sim.engine import hda
from scripts.backtest_season import load_inputs

OUT = os.path.join(ROOT, "outputs", "calibration")


def main():
    kn = knobs(load_config()); inp = load_inputs()
    df = pd.concat([d.assign(season=s) for s, d in inp["seasons"].items()], ignore_index=True)
    df = df.dropna(subset=["gd_fit"]).copy()
    for c in ("hg", "ag", "gd_fit", "T_fit", "ph", "pd", "pa"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["T_use"] = df["T_fit"].where(df["T_fit"].notna(), kn["avg_total_goals"])
    m = np.array([hda(g, t, kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0)) for g, t in zip(df["gd_fit"], df["T_use"])])
    df["mh"], df["md"], df["ma"] = m[:, 0], m[:, 1], m[:, 2]
    df["margin"] = df["hg"] - df["ag"]; df["res"] = np.sign(df["margin"])
    has3 = df["ph"].notna()
    L = ["# Match-level checks (every lined match with a result on file)", "", f"n matches {len(df)}, with a three-way close {int(has3.sum())}", ""]
    L += ["## Home / draw / away", "", "| | realised | engine at the close (g, T) | devigged three-way close |", "|---|---|---|---|"]
    for name, cond in (("home", df["res"] > 0), ("draw", df["res"] == 0), ("away", df["res"] < 0)):
        col = {"home": "mh", "draw": "md", "away": "ma"}[name]; pc = {"home": "ph", "draw": "pd", "away": "pa"}[name]
        L.append(f"| {name} | {cond.mean():.4f} | {df[col].mean():.4f} | {df.loc[has3, pc].mean():.4f} |")
    L += ["", f"Draw rate by season (realised / engine): " + ", ".join(f"{s} {(g['res'] == 0).mean():.3f}/{g['md'].mean():.3f}" for s, g in df.groupby('season')), ""]
    # scoreline cells the Dixon-Coles correction touches
    L += ["## Low scorelines (realised share / engine share)", ""]
    from sim.engine import score_grid
    P = np.zeros((11, 11))
    for g, t in zip(df["gd_fit"], df["T_use"]):
        P += score_grid(g, t, kn["goal_floor"], kn["shared_goals_mean"], rho=float(kn.get("dc_rho", 0.0) or 0.0))
    P /= len(df)
    for x, y in ((0, 0), (1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (2, 2)):
        L.append(f"- {x}-{y}: {((df['hg'] == x) & (df['ag'] == y)).mean():.4f} / {P[x, y]:.4f}")
    e = df["margin"] - df["gd_fit"]
    L += ["", "## Margin noise", "", f"sd(actual margin - closing margin) = {e.std():.3f} goals (mean {e.mean():+.3f})", ""]
    # engine variance of the margin at the close
    var = []
    for g, t in zip(df["gd_fit"], df["T_use"]):
        mu_h = max(t / 2 + g / 2, kn["goal_floor"]); mu_a = max(t / 2 - g / 2, kn["goal_floor"]); c = min(kn["shared_goals_mean"], min(mu_h, mu_a) - kn["goal_floor"]); c = max(c, 0)
        var.append(mu_h + mu_a - 2 * c)
    L.append(f"engine sd of the margin at the same lines (bivariate Poisson, shared {kn['shared_goals_mean']}) = {np.sqrt(np.mean(var)):.3f} goals")
    L += ["", "## Favourite win rate by closing probability (three-way, devigged)", "", "| bucket | n | mean p(fav) | realised fav win | realised draw | engine p(fav) | engine draw |", "|---|---|---|---|---|---|---|"]
    d3 = df[has3].copy()
    d3["fav_home"] = d3["ph"] >= d3["pa"]
    d3["pfav"] = np.where(d3["fav_home"], d3["ph"], d3["pa"]); d3["efav"] = np.where(d3["fav_home"], d3["mh"], d3["ma"])
    d3["fav_won"] = np.where(d3["fav_home"], d3["res"] > 0, d3["res"] < 0)
    for lo, hi in ((0.3, 0.4), (0.4, 0.45), (0.45, 0.5), (0.5, 0.55), (0.55, 0.6), (0.6, 0.7), (0.7, 1.0)):
        b = d3[(d3["pfav"] >= lo) & (d3["pfav"] < hi)]
        if len(b):
            L.append(f"| {lo:.2f}-{hi:.2f} | {len(b)} | {b['pfav'].mean():.3f} | {b['fav_won'].mean():.3f} | {(b['res'] == 0).mean():.3f} | {b['efav'].mean():.3f} | {b['md'].mean():.3f} |")
    L += ["", "## Home edge by season (mean closing margin / realised margin / realised total)", "", "| season | n | close margin | realised margin | realised total |", "|---|---|---|---|---|"]
    for s, g in df.groupby("season"):
        L.append(f"| {s} | {len(g)} | {g['gd_fit'].mean():+.3f} | {g['margin'].mean():+.3f} | {(g['hg'] + g['ag']).mean():.2f} |")
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "match_checks.md"), "w").write("\n".join(L))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
