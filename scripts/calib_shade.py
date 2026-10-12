#!/usr/bin/env python3
"""Calibration 6 and 7: the shade per published market and the longshot rule. Replay every season at seven checkpoints with the
frozen knobs, collect (predicted p, outcome) per pool, fit logit(p') = b logit(p) + c with b leave-one-season-out, apply only
where it wins held out. Longshot rule: realised frequency of events priced 5-10% and under 5%. Report: outputs/calibration/shade.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sim.knobs import load_config, knobs
from sim.teams import ROOT, conference_of
from sim.markets import Archive, shade_pool
from sim.playoffs import STAGE
from scripts.replay import seasons_on_file, season_teams, checkpoints, simulate_from, actual_table, conf_array, conf_map_for, playoff_spots, logloss

OUT = os.path.join(ROOT, "outputs", "calibration")
B_GRID = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5]
POOLS = {"shield": (lambda a: a.shield(), lambda act, t, T: act[t]["league_pos"] == 1, 1),
         "conf": (lambda a: a.conference_winner(), lambda act, t, T: act[t]["conf_seed"] == 1, 2),
         "playoffs": (lambda a: a.playoffs(), lambda act, t, T: act[t]["conf_seed"] <= 9, 18),  # scored on 2023+ only (nine-team playoffs)
         "conf_top4": (lambda a: a.conf_top(4), lambda act, t, T: act[t]["conf_seed"] <= 4, 8),
         "spoon": (lambda a: a.spoon(), lambda act, t, T: act[t]["league_pos"] == len(T), 1),
         "conf_bottom": (lambda a: a.bottom_of_conference(), lambda act, t, T: act[t]["conf_seed"] == 15, 2)}


def main(n_seasons=4000):
    cfg = load_config(); kn = knobs(cfg); cm = conference_of()
    seasons = seasons_on_file(cfg)
    if not seasons:
        print("calib_shade: no seasons on file"); return 1
    obs = {p: [] for p in POOLS}  # (season, p_raw, y, pool_size)
    for s, df in sorted(seasons.items()):
        if len(df) < 200:
            continue
        T = season_teams(df); conf = conf_array(T, s); actual = actual_table(df, T, conf_map_for(s)); spots = playoff_spots(s)
        for cp in checkpoints(df):
            arc = Archive(simulate_from(df, cp, kn, T, conf, n_seasons=n_seasons, seed=5))
            for name, (f, yf, size) in POOLS.items():
                if name in ("playoffs", "conf_top4", "conf_bottom") and spots != 9:
                    continue
                probs = f(arc)
                obs[name].append((s, np.array([probs[t] for t in T]), np.array([yf(actual, t, T) for t in T], float), size))
    lines = ["# Shade per pool (leave-one-season-out)", "", "| pool | b=1 ll | best b | best ll (held out) | apply |", "|---|---|---|---|---|"]
    chosen = {}
    for name, rows in obs.items():
        seasons_in = sorted(set(r[0] for r in rows))
        ll_by_b = {b: [] for b in B_GRID}
        for b in B_GRID:
            for r in rows:
                ll_by_b[b].append(logloss(shade_pool(r[1], b, r[3]), r[2]))
        # held-out choice: for each season pick b on the others, score on it
        held = []
        for s in seasons_in:
            train = [r for r in rows if r[0] != s]; test = [r for r in rows if r[0] == s]
            bb = min(B_GRID, key=lambda b: np.mean([logloss(shade_pool(r[1], b, r[3]), r[2]) for r in train]))
            held.append(np.mean([logloss(shade_pool(r[1], bb, r[3]), r[2]) for r in test]))
        base = float(np.mean(ll_by_b[1.0])); best_b = min(B_GRID, key=lambda b: np.mean(ll_by_b[b])); held_ll = float(np.mean(held))
        apply = held_ll < base - 1e-4 and best_b != 1.0
        if apply:
            chosen[name] = best_b
        lines.append(f"| {name} | {base:.4f} | {best_b} | {held_ll:.4f} | {'yes' if apply else 'no (raw)'} |")
    # longshot rule
    lines += ["", "## Longshot rule (all pools, raw prices)", "", "| bucket | n | mean price | realised | ratio |", "|---|---|---|---|---|"]
    allp = np.concatenate([r[1] for rows in obs.values() for r in rows]); ally = np.concatenate([r[2] for rows in obs.values() for r in rows])
    for lo, hi in ((0.0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.40), (0.40, 1.0)):
        m = (allp >= lo) & (allp < hi)
        if m.sum():
            lines.append(f"| {lo:.0%}-{hi:.0%} | {int(m.sum())} | {allp[m].mean():.3f} | {ally[m].mean():.3f} | {ally[m].mean()/max(allp[m].mean(),1e-9):.2f} |")
    lines += ["", f"Chosen shade: {chosen} (set config knob `shade` with this report as the note; scenario teams exempt)."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "shade.md"), "w").write("\n".join(lines))
    json.dump(chosen, open(os.path.join(OUT, "shade.json"), "w"))
    print(lines[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
