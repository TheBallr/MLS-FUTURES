#!/usr/bin/env python3
"""HISTORICAL (review 2026-10-19): the dead-team measurement of the 2026-10-12 programme, run on the retired least-squares ratings with a fixed 0.5 home edge; the dock was re-checked at the filter ratings in backtest kf_final_sim.
The knob it set is frozen and documented in config.json; the live procedure is in outputs/calibration/README.md.
Dead-team measurement (method PDF: eliminated / clinched / nothing-to-play-for teams play worse; measure first).
For every lined match in the last ten rounds of each history season, classify each side from the table before that date:
  eliminated: cannot reach the current points of the last playoff place (max points < points of the N-th club in the conference)
  locked:     has clinched the playoffs and can neither move up nor down a seed (min > max of the club below, max < min of the club above)
  clinched:   has clinched the playoffs (min points > max of the (N+1)-th club) but the seed is open
  seed1_locked: top seed clinched (min > max of the second club)
Residual = actual margin - expected margin from the team's view, against (a) the Pinnacle close (gd_fit) and (b) the closes-only
market ratings fitted before the date (what the sim uses for future rounds). If (a) is about zero and (b) is negative, the close
prices the dead team and the sim does not. Report: outputs/calibration/dead_teams.md"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim.knobs import load_config, knobs
from sim.teams import ROOT
from sim.ratings import market_fit
from scripts.backtest_season import load_inputs, season_context
from scripts.replay import season_teams, conf_map_for, playoff_spots
from scripts.run_sim import played_stats

OUT = os.path.join(ROOT, "outputs", "calibration")


def classify(before: pd.DataFrame, all_df: pd.DataFrame, date: str, T: list, cm: dict, spots: int) -> dict:
    """team -> status at `date` from results before it and the remaining fixtures on file."""
    st = played_stats(before, T)
    left = all_df[all_df["date"] >= date]
    rem = {t: int(((left["home"] == t) | (left["away"] == t)).sum()) for t in T}
    pts = {t: int(st["points"][i]) for i, t in enumerate(T)}
    mx = {t: pts[t] + 3 * rem[t] for t in T}
    out = {}
    for conf in ("East", "West"):
        ts = [t for t in T if cm.get(t, "East") == conf]
        if len(ts) <= spots:
            for t in ts:
                out[t] = "open"
            continue
        order = sorted(ts, key=lambda t: (-pts[t], -st["wins"][T.index(t)], -st["gd"][T.index(t)]))
        line_pts = pts[order[spots - 1]]            # current points of the last playoff place
        next_max = max(mx[t] for t in order[spots:])  # best the first club outside can reach
        for t in ts:
            others_above_max = sorted((mx[u] for u in ts if u != t), reverse=True)
            s = "open"
            if mx[t] < line_pts:
                s = "eliminated"
            elif pts[t] > next_max:
                s = "clinched"
                # locked seed: nobody below can catch, nobody above can be caught
                above = [u for u in ts if pts[u] > pts[t]]; below = [u for u in ts if pts[u] < pts[t]]
                cant_move_up = all(mx[t] < pts[u] for u in above)
                cant_move_down = all(pts[t] > mx[u] for u in below) and not any(pts[u] == pts[t] for u in ts if u != t)
                if cant_move_up and cant_move_down:
                    s = "locked"
                if not above and all(pts[t] > mx[u] for u in ts if u != t):
                    s = "seed1_locked"
            out[t] = s
    return out


def main():
    kn = knobs(load_config()); inp = load_inputs()
    rows = []
    for season, df in sorted(inp["seasons"].items()):
        if int(season) >= 2026 or len(df) < 200:
            continue
        T = season_teams(df); cm = conf_map_for(season); spots = playoff_spots(season)
        df = df.dropna(subset=["gd_fit"]).sort_values("date").reset_index(drop=True)
        for c in ("hg", "ag", "gd_fit"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        dates = sorted(df["date"].unique())
        n_teams = len(T); per_club = df.groupby("date").size().cumsum() * 2 / n_teams
        late = [d for d in dates if per_club[d] >= per_club.iloc[-1] - 10]   # last ten matches per club, roughly
        for d in late:
            before = df[df["date"] < d]
            status = classify(before, df, d, T, cm, spots)
            mk = market_fit(inp["closes"], T, d, kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=0.5, before=True)
            R = dict(zip(T, mk["ratings"]))
            ctx_he = 0.5
            for r in df[df["date"] == d].itertuples(index=False):
                m = float(r.hg) - float(r.ag); g_close = float(r.gd_fit); g_rat = R[r.home] - R[r.away] + ctx_he
                for side, team, sgn in (("home", r.home, 1), ("away", r.away, -1)):
                    opp = r.away if side == "home" else r.home
                    rows.append({"season": season, "date": d, "team": team, "status": status[team], "opp_status": status[opp],
                                 "res_close": sgn * (m - g_close), "res_rating": sgn * (m - g_rat), "close_minus_rating": sgn * (g_close - g_rat),
                                 "games_left": int(((df["date"] >= d) & ((df["home"] == team) | (df["away"] == team))).sum())})
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(OUT, "dead_teams_rows.csv"), index=False)
    L = ["# Dead-team measurement (last ten rounds of 2012-2025, lined matches)", "",
         "residual = actual margin - expected margin from the team's view (goals); se = sd / sqrt(n)", "",
         "| status | team-matches | vs close: mean (se) | vs ratings: mean (se) | close minus ratings |", "|---|---|---|---|---|"]
    for s_ in ("open", "clinched", "locked", "seed1_locked", "eliminated"):
        g = d[d["status"] == s_]
        if len(g):
            L.append(f"| {s_} | {len(g)} | {g.res_close.mean():+.3f} ({g.res_close.std() / np.sqrt(len(g)):.3f}) | {g.res_rating.mean():+.3f} ({g.res_rating.std() / np.sqrt(len(g)):.3f}) | {g.close_minus_rating.mean():+.3f} |")
    L += ["", "Opponent dead, team open (the other side of the same matches):", "", "| opp status | n | vs close | vs ratings |", "|---|---|---|---|"]
    for s_ in ("eliminated", "locked", "clinched"):
        g = d[(d["opp_status"] == s_) & (d["status"] == "open")]
        if len(g):
            L.append(f"| {s_} | {len(g)} | {g.res_close.mean():+.3f} ({g.res_close.std() / np.sqrt(len(g)):.3f}) | {g.res_rating.mean():+.3f} ({g.res_rating.std() / np.sqrt(len(g)):.3f}) |")
    L += ["", "Eliminated teams by games left:", "", "| games left | n | vs close | vs ratings |", "|---|---|---|---|"]
    for gl in (1, 2, 3, 4, 5):
        g = d[(d["status"] == "eliminated") & (d["games_left"] == gl)]
        if len(g):
            L.append(f"| {gl} | {len(g)} | {g.res_close.mean():+.3f} | {g.res_rating.mean():+.3f} |")
    L += ["", "By season, eliminated (n, vs close, vs ratings): " + "; ".join(f"{s} ({len(g)}, {g.res_close.mean():+.2f}, {g.res_rating.mean():+.2f})" for s, g in d[d.status == 'eliminated'].groupby('season'))]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "dead_teams.md"), "w").write("\n".join(L)); print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
