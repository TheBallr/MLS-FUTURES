#!/usr/bin/env python3
"""HISTORICAL (review 2026-10-19): the season replay of the 2026-10-12 programme, run on the retired least-squares ratings.
The knob it set is frozen and documented in config.json; the live procedure is in outputs/calibration/README.md.
Calibration 8: season replay against an equal-ratings benchmark at seven checkpoints per season: the sim must beat it at every
checkpoint on log-loss (Shield, conference, playoffs, Spoon) and expected points rmse. Report: outputs/calibration/replay.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sim.knobs import load_config, knobs
from sim.teams import ROOT, conference_of
from sim.markets import Archive
from scripts.replay import seasons_on_file, season_teams, checkpoints, simulate_from, actual_table, score_archive, conf_array, conf_map_for, playoff_spots

OUT = os.path.join(ROOT, "outputs", "calibration")


def main(n_seasons=5000):
    cfg = load_config(); kn = knobs(cfg); cm = conference_of()
    seasons = seasons_on_file(cfg)
    if not seasons:
        print("calib_replay: no seasons on file"); return 1
    lines = ["# Season replay vs equal-ratings benchmark", "", "| season | checkpoint | model ll (sh/conf/po/sp) | benchmark ll | model pts rmse | bench pts rmse | beats |", "|---|---|---|---|---|---|---|"]
    wins = tot = 0
    for s, df in sorted(seasons.items()):
        if len(df) < 200:
            continue
        T = season_teams(df); conf = conf_array(T, s); actual = actual_table(df, T, conf_map_for(s)); spots = playoff_spots(s)
        for cp in checkpoints(df):
            m = score_archive(Archive(simulate_from(df, cp, kn, T, conf, n_seasons=n_seasons, seed=8)), actual, T, spots)
            b = score_archive(Archive(simulate_from(df, cp, kn, T, conf, n_seasons=n_seasons, seed=8, ratings=np.zeros(len(T)))), actual, T, spots)
            mll = m["shield_ll"] + m["conf_ll"] + m["playoffs_ll"] + m["spoon_ll"]; bll = b["shield_ll"] + b["conf_ll"] + b["playoffs_ll"] + b["spoon_ll"]
            beat = mll <= bll + 1e-9 and m["points_rmse"] <= b["points_rmse"] + 1e-9; wins += beat; tot += 1
            lines.append(f"| {s} | {cp} | {mll:.4f} | {bll:.4f} | {m['points_rmse']:.2f} | {b['points_rmse']:.2f} | {'yes' if beat else 'NO'} |")
    lines += ["", f"Beats the benchmark at {wins}/{tot} checkpoints."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "replay.md"), "w").write("\n".join(lines))
    print(lines[-1])
    return 0 if wins == tot else 2


if __name__ == "__main__":
    sys.exit(main())
