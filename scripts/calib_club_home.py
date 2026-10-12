#!/usr/bin/env python3
"""Per-club home edge (altitude, turf, travel): delta per club in goals on top of the league home edge, from the residuals of
full-season fits over every season on file, shrunk toward zero with k pseudo-games (delta = n/(n+k) x mean residual).
Measured held out: for each test season, deltas from the other seasons; walk-forward next-ten-closes rmse with and without.
Writes data/ratings/home_edges.csv (all seasons, chosen k) and outputs/calibration/club_home.md.
Usage: python3 scripts/calib_club_home.py [--test-seasons 2022-2026]"""
from __future__ import annotations
import argparse, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT, teams
from sim.ratings import market_fit, wls_fit, half_life_weights
from scripts.replay import seasons_on_file

OUT = os.path.join(ROOT, "outputs", "calibration")
K_GRID = [50, 100, 200, 400]


def residuals_by_club(seasons: dict, skip: str | None, kn: dict) -> dict:
    """Home residuals (gd_fit - (R_h - R_a + HE_season)) per club, pooled over seasons except `skip`."""
    res = {}
    for s, df in seasons.items():
        if s == skip:
            continue
        d = df.dropna(subset=["gd_fit"]); d = d[d["gd_fit"].astype(float).abs() < 5]
        Ts = sorted(set(d["home"]) | set(d["away"])); idx = {t: i for i, t in enumerate(Ts)}
        mk = market_fit(d, Ts, "2100-01-01", 10000, kn["ridge_lambda"], fit_home_edge=True)
        R = mk["ratings"]
        r = d["gd_fit"].astype(float).to_numpy() - (R[d["home"].map(idx)] - R[d["away"].map(idx)] + mk["home_edge"])
        for t, x in zip(d["home"], r):
            res.setdefault(t, []).append(float(x))
    return res


def deltas_from(res: dict, k: float, clubs: list) -> dict:
    out = {}
    for t in clubs:
        v = np.array(res.get(t, []))
        out[t] = float(len(v) / (len(v) + k) * v.mean()) if len(v) else 0.0
    mu = np.mean([out[t] for t in clubs])
    return {t: out[t] - mu for t in clubs}


def next_ten_rmse(df: pd.DataFrame, kn: dict, deltas: dict | None, min_matches=40) -> tuple[float, int]:
    """Walk-forward on one season with per-match home edge = HE + delta[home] (fit target and prediction)."""
    from scripts.replay import all_closes
    Ts = sorted(set(df["home"]) | set(df["away"])); idx = {t: i for i, t in enumerate(Ts)}
    allc = all_closes(); allc = allc[allc["home"].isin(idx) & allc["away"].isin(idx)].dropna(subset=["gd_fit"]).copy()
    allc["date"] = pd.to_datetime(allc["date"])
    df = df.dropna(subset=["gd_fit"]).sort_values("date").reset_index(drop=True)
    he_all = kn["home_edge_goals"] + (allc["home"].map(deltas).fillna(0.0).to_numpy() if deltas else 0.0)
    errs = []
    for d in sorted(df["date"].unique()):
        before_season = df[df["date"] < d]
        if len(before_season) < min_matches:
            continue
        nxt = df[df["date"] >= d].head(10)
        m = allc["date"] < pd.Timestamp(d)
        sub = allc[m]
        w = half_life_weights(sub["date"], d, kn["half_life_days"])
        R, _, _ = wls_fit(sub["home"].map(idx).to_numpy(), sub["away"].map(idx).to_numpy(), sub["gd_fit"].to_numpy(), w, len(Ts), kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=he_all[m.to_numpy()] if deltas else kn["home_edge_goals"])
        he_n = kn["home_edge_goals"] + (nxt["home"].map(deltas).fillna(0.0).to_numpy() if deltas else 0.0)
        pred = R[nxt["home"].map(idx)] - R[nxt["away"].map(idx)] + he_n
        errs.extend((nxt["gd_fit"].astype(float).to_numpy() - pred).tolist())
    e = np.array(errs)
    return float(np.sqrt((e ** 2).mean())) if len(e) else np.nan, int(len(e))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--test-seasons", default="2022-2026"); a = ap.parse_args()
    y0, y1 = [int(x) for x in a.test_seasons.split("-")]
    cfg = load_config(); kn = knobs(cfg)
    seasons = seasons_on_file(cfg)
    clubs = teams()
    lines = ["# Per-club home edge: held-out test (deltas from the other seasons, walk-forward next-ten rmse)", "", "| season | n | no club edge | " + " | ".join(f"k={k}" for k in K_GRID) + " |", "|---|---|---|" + "---|" * len(K_GRID)]
    tot = {None: []}; tot.update({k: [] for k in K_GRID})
    for s in [str(y) for y in range(y0, y1 + 1)]:
        if s not in seasons:
            continue
        df = seasons[s]
        base, n = next_ten_rmse(df, kn, None)
        res = residuals_by_club(seasons, s, kn)
        row = [base]
        for k in K_GRID:
            r, _ = next_ten_rmse(df, kn, deltas_from(res, k, sorted(set(df["home"]) | set(df["away"])))); row.append(r); tot[k].append((r, n))
        tot[None].append((base, n))
        lines.append(f"| {s} | {n} | {base:.4f} | " + " | ".join(f"{r:.4f}" for r in row[1:]) + " |")
    pooled = {k: float(np.sqrt(np.average([r ** 2 for r, n in v], weights=[n for r, n in v]))) for k, v in tot.items() if v}
    best = min(pooled, key=pooled.get)
    lines += ["", "Pooled: " + ", ".join(f"{'none' if k is None else 'k='+str(k)}: {v:.4f}" for k, v in pooled.items()), f"Best: {'no club edge' if best is None else 'k=' + str(best)}"]
    # final deltas from all seasons at the chosen k (or k=100 for the table when none wins)
    res_all = residuals_by_club(seasons, None, kn)
    kk = best if best is not None else 100
    d = deltas_from(res_all, kk, clubs)
    rows = [{"team": t, "delta_goals": round(d[t], 3), "n_home_closes": len(res_all.get(t, [])), "raw_mean": round(float(np.mean(res_all.get(t, [0.0]))), 3),
             "se": round(float(np.std(res_all.get(t, [0.0])) / np.sqrt(max(1, len(res_all.get(t, []))))), 3), "k": kk, "note": ""} for t in clubs]
    pd.DataFrame(rows).sort_values("delta_goals", ascending=False).to_csv(os.path.join(ROOT, "data", "ratings", "home_edges.csv"), index=False)
    lines += ["", f"## Deltas from all seasons, k={kk} (data/ratings/home_edges.csv)", "", "| club | n home closes | raw mean | se | delta |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -r["delta_goals"]):
        lines.append(f"| {r['team']} | {r['n_home_closes']} | {r['raw_mean']:+.3f} | {r['se']:.3f} | {r['delta_goals']:+.3f} |")
    lines += ["", f"Decision rule: switch `club_home_edge_enabled` on only if a k beats 'none' pooled and in most test seasons. Result here: {'ENABLE k=' + str(best) if best is not None else 'KEEP OFF'}."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "club_home.md"), "w").write("\n".join(lines))
    json.dump({"pooled": {str(k): v for k, v in pooled.items()}, "best": best}, open(os.path.join(OUT, "club_home.json"), "w"))
    print("\n".join(lines[:len(lines) - len(rows) - 6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
