#!/usr/bin/env python3
"""The scorecard: every source scored on predicting the next ten closes (rmse of gd_fit, goals) over every season on file;
the live sources on this season's closes. Run before changing any weight; record the numbers in CLAUDE.md.
Sources: market_recent at the config half-life, xg (where xg_history covers the season), blends at 75/25, 50/50, 25/75, and the
equal-ratings benchmark. Report: outputs/calibration/scorecard.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT
from sim.ratings import market_fit, xg_fit
from scripts.replay import seasons_on_file

OUT = os.path.join(ROOT, "outputs", "calibration")
BLENDS = {"market": 1.0, "blend75": 0.75, "blend50": 0.5, "blend25": 0.25, "xg": 0.0}
XG_HL_GRID = [21, 45, 90, 180]


def score_season(df: pd.DataFrame, xg: pd.DataFrame, kn: dict, min_matches=40, xg_hl=None) -> dict:
    Ts = sorted(set(df["home"]) | set(df["away"])); idx = {t: i for i, t in enumerate(Ts)}
    df = df.dropna(subset=["gd_fit"]).sort_values("date").reset_index(drop=True)
    errs = {k: [] for k in list(BLENDS) + ["benchmark"]}
    have_xg = len(xg) > 0
    xg_hl = xg_hl or kn["xg_half_life_days"]
    for d in sorted(df["date"].unique()):
        before = df[df["date"] < d]
        if len(before) < min_matches:
            continue
        nxt = df[df["date"] >= d].head(10)
        y = nxt["gd_fit"].astype(float).to_numpy()
        mk = market_fit(before, Ts, d, kn["half_life_days"], kn["market_ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True)
        Rm = mk["ratings"]
        Rx = xg_fit(xg, Ts, d, xg_hl, kn["ridge_lambda"], float(Rm.std()))["ratings"] if have_xg else None
        for name, wm in BLENDS.items():
            if Rx is None and wm < 1.0:
                continue
            R = Rm if Rx is None else (wm * Rm + (1 - wm) * Rx); R = R - R.mean()
            if kn.get("blend_rescale_to_market") and R.std() > 1e-9:
                R = R * (Rm.std() / R.std())
            pred = R[nxt["home"].map(idx)] - R[nxt["away"].map(idx)] + kn["home_edge_goals"]
            errs[name].extend((y - pred).tolist())
        errs["benchmark"].extend((y - kn["home_edge_goals"]).tolist())
    return {k: (float(np.sqrt(np.mean(np.square(v)))) if v else np.nan, len(v)) for k, v in errs.items()}


def main():
    cfg = load_config(); kn = knobs(cfg)
    seasons = seasons_on_file(cfg)
    if not seasons:
        print("scorecard: no seasons on file"); return 1
    xg_all = data.num(data.load("xg_history"), ["home_xg", "away_xg"])
    lines = ["# Rating scorecard: rmse (goals) predicting the next ten closes, walk-forward", "", "| season | n | " + " | ".join(list(BLENDS) + ["benchmark"]) + " |", "|---|---|" + "---|" * (len(BLENDS) + 1)]
    allres = {}
    for s, df in sorted(seasons.items()):
        xg = xg_all[pd.to_datetime(xg_all["date"]).dt.year.astype(str) == str(s)] if len(xg_all) else xg_all
        r = score_season(df, xg, kn); allres[s] = r
        lines.append(f"| {s} | {r['market'][1]} | " + " | ".join((f"{r[k][0]:.4f}" if r[k][1] else "-") for k in list(BLENDS) + ["benchmark"]) + " |")
    # xG half-life grid on the seasons that have xG: rmse of the pure xg source and of the 75/25 blend
    xg_seasons = sorted(set(pd.to_datetime(xg_all["date"]).dt.year.astype(str))) if len(xg_all) else []
    if xg_seasons:
        lines += ["", "## xG half-life grid (seasons with xG on file): rmse of xg alone / blend75 / blend50", "", "| season | " + " | ".join(f"hl {h}" for h in XG_HL_GRID) + " |", "|---|" + "---|" * len(XG_HL_GRID)]
        for s in xg_seasons:
            if s not in seasons:
                continue
            xg = xg_all[pd.to_datetime(xg_all["date"]).dt.year.astype(str) == s]
            cells = []
            for h in XG_HL_GRID:
                r = score_season(seasons[s], xg, kn, xg_hl=h); cells.append(f"{r['xg'][0]:.4f} / {r['blend75'][0]:.4f} / {r['blend50'][0]:.4f}")
            lines.append(f"| {s} | " + " | ".join(cells) + " |")
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "scorecard.md"), "w").write("\n".join(lines))
    json.dump({s: {k: v[0] for k, v in r.items()} for s, r in allres.items()}, open(os.path.join(OUT, "scorecard.json"), "w"), indent=1)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
