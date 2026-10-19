#!/usr/bin/env python3
"""Nothing-to-play-for clubs (method PDF: "a team with nothing to play for and a locked seed plays a lot worse"), REGULAR SEASON
ONLY: the 2026-10-12 dead_teams.py run kept the playoff games in its last ten rounds, so its locked / top-seed-locked rows are mostly
playoff matches (its eliminated row is unaffected). Status from the regular-season table before each date (dead_teams.classify);
residual v the close and v the closes-only ratings before the date (as dead_teams.py); benching = missing value of absent regulars
(the ASA absence dataset) minus the club's season mean. Needs the full absence dataset (2013-2025). Report:
outputs/calibration/locked_seed.md (CLAUDE.md 15)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim.teams import ROOT
from sim.knobs import load_config, knobs
from sim.ratings import market_fit
from scripts.backtest_season import load_inputs
from scripts.replay import season_teams, conf_map_for, playoff_spots
from scripts.dead_teams import classify

OUT = os.path.join(ROOT, "outputs", "calibration")


def main():
    kn = knobs(load_config()); inp = load_inputs()
    A = pd.read_csv(os.path.join(ROOT, "data", "public", "asa_gplus", "absences.csv"), dtype={"season": str})
    A["dt"] = pd.to_datetime(A["date"])
    smean = A.groupby(["season", "team"])["mv"].mean()
    rows = []
    for season, df in sorted(inp["seasons"].items()):
        if not ("2013" <= str(season) <= "2025"):
            continue
        a = A[(A.season == str(season)) & (A.home == 1)]
        keys = {(h, w): list(g["dt"]) for (h, w), g in a.groupby(["team", "opp"])}
        df = df.copy(); df["dt"] = pd.to_datetime(df["date"])
        reg = [any(abs((d - x).days) <= 1 for x in keys.get((h, w), [])) for h, w, d in zip(df.home, df.away, df.dt)]  # ASA's games list is regular season only
        df = df[reg].dropna(subset=["gd_fit"]).sort_values("date").reset_index(drop=True)
        for c in ("hg", "ag", "gd_fit"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        T = season_teams(df); cm = conf_map_for(season); spots = playoff_spots(season)
        dates = sorted(df["date"].unique()); per_club = df.groupby("date").size().cumsum() * 2 / len(T)
        late = [d for d in dates if per_club[d] >= per_club.iloc[-1] - 10]
        for d in late:
            status = classify(df[df["date"] < d], df, d, T, cm, spots)
            mk = market_fit(inp["closes"], T, d, kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=0.5, before=True)
            R = dict(zip(T, mk["ratings"]))
            for r in df[df["date"] == d].itertuples(index=False):
                m = float(r.hg) - float(r.ag); g_close = float(r.gd_fit); g_rat = R[r.home] - R[r.away] + 0.5
                for team, opp, sgn in ((r.home, r.away, 1), (r.away, r.home, -1)):
                    aa = A[(A.season == str(season)) & (A.team == team) & ((A.dt - r.dt).abs() <= pd.Timedelta(days=1))]
                    mv = float(aa["mv"].iloc[0]) if len(aa) else np.nan
                    rows.append({"season": season, "date": d, "team": team, "opp": opp, "status": status[team], "opp_status": status[opp],
                                 "res_close": sgn * (m - g_close), "res_rating": sgn * (m - g_rat), "close_minus_rating": sgn * (g_close - g_rat),
                                 "mv": mv, "d_mv": mv - smean.get((str(season), team), np.nan),
                                 "games_left": int(((df["date"] >= d) & ((df["home"] == team) | (df["away"] == team))).sum())})
    x = pd.DataFrame(rows); x.to_csv(os.path.join(OUT, "locked_seed_rows.csv"), index=False)
    se = lambda s: s.std() / np.sqrt(max(1, s.count()))
    L = ["# Nothing-to-play-for clubs, regular season 2013-2025 (scripts/locked_seed.py)", "",
         "residual = actual margin minus expected (team's view, goals); bench = missing value of absent regulars minus the club's season mean", "",
         "| status | n | v close (se) | v ratings (se) | close minus ratings | bench (se) |", "|---|---|---|---|---|---|"]
    for s, g in x.groupby("status"):
        L.append(f"| {s} | {len(g)} | {g.res_close.mean():+.3f} ({se(g.res_close):.3f}) | {g.res_rating.mean():+.3f} ({se(g.res_rating):.3f}) | {g.close_minus_rating.mean():+.3f} | {g.d_mv.mean():+.3f} ({se(g.d_mv):.3f}) |")
    nt = x[x.status.isin(["locked", "seed1_locked"])]
    L += ["", f"Nothing to play for (locked + top seed locked): n {len(nt)}, v close {nt.res_close.mean():+.3f} ({se(nt.res_close):.3f}), v ratings {nt.res_rating.mean():+.3f} ({se(nt.res_rating):.3f}), bench {nt.d_mv.mean():+.3f} ({se(nt.d_mv):.3f})",
          "By games left: " + "; ".join(f"{k}: n {len(g)} v ratings {g.res_rating.mean():+.2f} bench {g.d_mv.mean():+.3f}" for k, g in nt.groupby(np.minimum(nt.games_left, 4))),
          "By season: " + "; ".join(f"{k} {len(g)} {g.res_rating.mean():+.2f}" for k, g in nt.groupby("season"))]
    op = x[(x.status == "open") & x.opp_status.isin(["locked", "seed1_locked"])]
    L.append(f"Open clubs v a nothing-to-play-for opponent: n {len(op)}, v close {op.res_close.mean():+.3f} ({se(op.res_close):.3f}), v ratings {op.res_rating.mean():+.3f} ({se(op.res_rating):.3f})")
    open(os.path.join(OUT, "locked_seed.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
