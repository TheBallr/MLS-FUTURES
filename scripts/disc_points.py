#!/usr/bin/env python3
"""Disciplinary points per club for the season, from the OpticOdds team stats (data/optic/results_mls.csv), on the 2026 MLS
Competition Guidelines scale: foul 1, technical-staff warning 2, yellow card 3, second yellow 7 for the incident in total,
straight red 7 (a club receives at most 7 points for any individual incident). Assumptions (noted in CLAUDE.md): fouls =
free kicks conceded (fk_foul_lost); total_yellow_card counts both yellows of a sent-off player, so a second yellow adds 1 to
reach 7; straight reds = total_red_card - second_yellow. Writes data/discipline/disc_points_<season>.csv (team, points, matches).
Usage: python3 scripts/disc_points.py [--season 2026]"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim.teams import canon, ROOT


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--season", type=int, default=2026); a = ap.parse_args()
    d = pd.read_csv(os.path.join(ROOT, "data", "optic", "results_mls.csv"), low_memory=False)
    d = d[d["season_year"] == a.season]
    rows = []
    for side in ("home", "away"):
        g = lambda c: pd.to_numeric(d.get(f"{side}_{c}"), errors="coerce").fillna(0) if f"{side}_{c}" in d.columns else pd.Series(0.0, index=d.index)
        fouls = g("fk_foul_lost").where(g("fk_foul_lost") > 0, g("fouls")); staff = g("staff_yellow"); yel = g("total_yellow_card"); sy = g("second_yellow"); red = g("total_red_card")
        straight = (red - sy).clip(lower=0)
        pts = fouls + 2 * staff + 3 * yel + 1 * sy + 7 * straight
        for team, p, f, y, s, r in zip(d[side], pts, fouls, yel, sy, straight):
            t = canon(team, strict=False)
            if t:
                rows.append({"team": t, "points": float(p), "fouls": float(f), "yellows": float(y), "second_yellows": float(s), "straight_reds": float(r)})
    out = pd.DataFrame(rows).groupby("team").agg(points=("points", "sum"), matches=("points", "size"), fouls=("fouls", "sum"), yellows=("yellows", "sum"),
                                                  second_yellows=("second_yellows", "sum"), straight_reds=("straight_reds", "sum")).reset_index().sort_values("points")
    out["points"] = out["points"].astype(int)
    p = os.path.join(ROOT, "data", "discipline", f"disc_points_{a.season}.csv"); os.makedirs(os.path.dirname(p), exist_ok=True); out.to_csv(p, index=False)
    print(f"disc_points {a.season}: {len(out)} clubs, matches {out['matches'].min()}-{out['matches'].max()}, points {out['points'].min()}-{out['points'].max()} -> {p}")
    print(out[["team", "matches", "points", "fouls", "yellows", "second_yellows", "straight_reds"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
