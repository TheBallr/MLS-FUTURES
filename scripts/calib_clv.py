#!/usr/bin/env python3
"""HISTORICAL (review 2026-10-19): the CLV and posted-line shrink test of the 2026-10-12 programme, run on the retired least-squares ratings (shrink is 1.0 since 2026-10-15).
The knob it set is frozen and documented in config.json; the live procedure is in outputs/calibration/README.md.
Calibration 9 and the posted-line shrink, on Pinnacle opener/close pairs from the OpticOdds harvest (data/optic/lines_pinnacle.csv:
one 'open' (olv) and one 'close' (clv) row per fixture) plus the live CLV log.
(a) CLV test: where the closes-only ratings disagree with the opener by >= 0.15 goals, how often and how far does the close move
    the model's way. (b) Shrink grid: s in {0, .2, .35, .5, .7} for (1-s) model + s opener, scored on the close. Needs 150 pairs.
Note: the olv is Pinnacle's opening line, days before kickoff; the line the live model shrinks to is the 8:52 AM posted line, which
is fresher, so the right live s is at least the opener-based answer.
Report: outputs/calibration/clv.md"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT, teams
from sim.ratings import market_fit, gd_fit_row, load_club_home_edges, home_edge_for
from scripts.clv_log import summary
from scripts.replay import all_closes

OUT = os.path.join(ROOT, "outputs", "calibration")
S_GRID = [0.0, 0.2, 0.35, 0.5, 0.7, 1.0]
LINES = os.path.join(ROOT, "data", "optic", "lines_pinnacle.csv")


def pairs(kn) -> pd.DataFrame:
    if not os.path.exists(LINES):
        return pd.DataFrame()
    L = pd.read_csv(LINES, dtype=str, keep_default_na=False)
    rows = []
    for fid, g in L.groupby("fixture_id"):
        o = g[g["phase"] == "open"]; c = g[g["phase"] == "close"]
        if len(o) != 1 or len(c) != 1:
            continue
        o, c = o.iloc[0], c.iloc[0]
        go = gd_fit_row(o["h"], o["d"], o["a"], o["ah_line"] or None, o["ah_home"], o["ah_away"], o["total_line"] or None, o["over"], o["under"], kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"])
        gc = gd_fit_row(c["h"], c["d"], c["a"], c["ah_line"] or None, c["ah_home"], c["ah_away"], c["total_line"] or None, c["over"], c["under"], kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"])
        if np.isfinite(go["gd_fit"]) and np.isfinite(gc["gd_fit"]):
            rows.append({"date": c["date"], "season": c["season"], "home": c["home"], "away": c["away"], "g_open": go["gd_fit"], "g_close": gc["gd_fit"]})
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def main():
    cfg = load_config(); kn = knobs(cfg)
    lines = ["# CLV test and the posted-line shrink (Pinnacle opener -> close, OpticOdds olv/clv)", ""]
    live = summary(data.load("clv_log")); lines.append(f"Live CLV log: {live}")
    P = pairs(kn)
    lines.append(f"Opener/close pairs on file: {len(P)}" + (f" ({P.groupby('season').size().to_dict()})" if len(P) else ""))
    if len(P) < 150:
        lines.append("Fewer than 150 pairs: the shrink stays at the EPL value 0.35 and the CLV test waits.")
    else:
        T = teams(); idx = {t: i for i, t in enumerate(T)}
        deltas = load_club_home_edges(kn.get("club_home_edge_enabled", False))
        allc = all_closes()
        gm = np.full(len(P), np.nan)
        cache = {}
        for i, r in enumerate(P.itertuples(index=False)):
            if r.home not in idx or r.away not in idx:
                continue
            if r.date not in cache:
                mk = market_fit(allc, T, r.date, kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True, club_deltas=deltas)
                cache[r.date] = mk["ratings"] if mk["n"] >= 60 else None
            R = cache[r.date]
            if R is None:
                continue
            gm[i] = R[idx[r.home]] - R[idx[r.away]] + home_edge_for(r.home, kn["home_edge_goals"], deltas)
        ok = np.isfinite(gm); P = P[ok].copy(); gm = gm[ok]
        go, gc = P["g_open"].to_numpy(float), P["g_close"].to_numpy(float)
        lines += ["", f"Scored pairs: {len(P)}. Opener vs close rmse {np.sqrt(np.mean((go-gc)**2)):.4f}; model vs close rmse {np.sqrt(np.mean((gm-gc)**2)):.4f}; model vs opener rmse {np.sqrt(np.mean((gm-go)**2)):.4f}.", "",
                  "| s (weight on the opener) | rmse vs close | by season |", "|---|---|---|"]
        best = None
        for s in S_GRID:
            pred = (1 - s) * gm + s * go; e = pred - gc
            by = {sea: float(np.sqrt(np.mean(e[P['season'].to_numpy() == sea] ** 2))) for sea in sorted(P["season"].unique())}
            rm = float(np.sqrt(np.mean(e ** 2))); lines.append(f"| {s:.2f} | {rm:.4f} | " + ", ".join(f"{k} {v:.4f}" for k, v in by.items()) + " |")
            if best is None or rm < best[1]:
                best = (s, rm)
        # finer grid around the best
        fine = np.arange(0.0, 1.0001, 0.05); fr = [float(np.sqrt(np.mean(((1 - s) * gm + s * go - gc) ** 2))) for s in fine]
        s_star = float(fine[int(np.argmin(fr))])
        d = gm - go; mv = gc - go; att = np.abs(d) >= kn["clv_attack_threshold"]
        ours = np.sign(mv[att]) == np.sign(d[att]); signed = np.where(ours, np.abs(mv[att]), -np.abs(mv[att]))
        lines += ["", f"Shrink answer: s = {s_star:.2f} on true openers (fine grid); coarse best {best[0]:.2f}. Live posted lines are fresher than the opener, so the live s should sit between this and 1.0; keep the EPL 0.35 unless this says otherwise.",
                  "", f"CLV: {int(att.sum())} attacks (|model - opener| >= {kn['clv_attack_threshold']} goals) of {len(P)} pairs; the close moved the model's way {ours.mean():.1%} of the time; mean signed move {signed.mean():+.3f} goals; "
                  f"mean |close - opener| on attacks {np.abs(mv[att]).mean():.3f} vs {np.abs(mv[~att]).mean():.3f} on non-attacks.",
                  f"Where the model disagreed by >= 0.30: n {int((np.abs(d) >= 0.30).sum())}, moved our way {(np.sign(mv[np.abs(d) >= 0.30]) == np.sign(d[np.abs(d) >= 0.30])).mean():.1%}." if (np.abs(d) >= 0.30).sum() else ""]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "clv.md"), "w").write("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
