#!/usr/bin/env python3
"""Calibration 4: rating_sd from the points backtest. Replay each season from matchweek 5 with the live recipe at seven checkpoints,
grid rating_sd, score the team points distributions (log-pmf of actual points, rmse of expected points) and the position markets
(Shield, conference winner, playoffs, Spoon log-loss). Keep the points answer; carry any disagreement as the shade.
Report: outputs/calibration/rating_sd.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sim.knobs import load_config, knobs
from sim.teams import ROOT, conference_of
from sim.markets import Archive
from scripts.replay import seasons_on_file, season_teams, checkpoints, simulate_from, actual_table, score_archive, conf_array

OUT = os.path.join(ROOT, "outputs", "calibration")
GRID = [0.0, 0.10, 0.20, 0.25, 0.30, 0.35, 0.45]


def run(grid=GRID, n_seasons=4000, key="rating_sd", report="rating_sd.md"):
    cfg = load_config(); kn0 = knobs(cfg)
    seasons = seasons_on_file(cfg)
    if not seasons:
        print(f"calib_{key}: no seasons on file"); return 1
    cm = conference_of()
    acc = {v: [] for v in grid}
    lines = [f"# {key} grid (points backtest, 7 checkpoints per season)", ""]
    for s, df in sorted(seasons.items()):
        T = season_teams(df); conf = conf_array(T)
        if len(df) < 200:
            continue
        actual = actual_table(df, T, cm)
        for cp in checkpoints(df):
            for v in grid:
                kn = dict(kn0); kn[key] = v
                out = simulate_from(df, cp, kn, T, conf, n_seasons=n_seasons, seed=3)
                sc = score_archive(Archive(out), actual, T); sc["season"] = s; sc["cp"] = cp
                acc[v].append(sc)
        lines.append(f"season {s}: {len(checkpoints(df))} checkpoints")
    lines += ["", f"| {key} | points log-pmf (higher better) | points rmse | shield ll | conf ll | playoffs ll | spoon ll |", "|---|---|---|---|---|---|---|"]
    summ = {}
    for v in grid:
        a = acc[v]
        if not a:
            continue
        summ[v] = {k: float(np.mean([x[k] for x in a])) for k in ("points_logpmf", "points_rmse", "shield_ll", "conf_ll", "playoffs_ll", "spoon_ll")}
        m = summ[v]; lines.append(f"| {v:.2f} | {m['points_logpmf']:.4f} | {m['points_rmse']:.3f} | {m['shield_ll']:.4f} | {m['conf_ll']:.4f} | {m['playoffs_ll']:.4f} | {m['spoon_ll']:.4f} |")
    if summ:
        best_pts = max(summ, key=lambda v: summ[v]["points_logpmf"]); best_pos = min(summ, key=lambda v: summ[v]["shield_ll"] + summ[v]["conf_ll"] + summ[v]["playoffs_ll"] + summ[v]["spoon_ll"])
        lines += ["", f"Points answer: {key} = {best_pts}. Position answer: {best_pos}. Keep the points answer; if they differ, the shade carries the difference."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, report), "w").write("\n".join(lines))
    json.dump({str(k): v for k, v in summ.items()}, open(os.path.join(OUT, report.replace(".md", ".json")), "w"), indent=1)
    print("\n".join(lines[-1:]))
    return 0


if __name__ == "__main__":
    sys.exit(run())
