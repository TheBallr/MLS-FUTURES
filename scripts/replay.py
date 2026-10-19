"""Season replay machinery shared by the calibration scripts: load a history season (results + closes with gd_fit),
walk-forward fit at a checkpoint, simulate the remainder, score points and position markets against what happened."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import teams, conference_of, canon
from sim.ratings import market_fit, fit_targets, apply_expansion_prior
from sim.season import SeasonInputs, Fixture, run_seasons, empty_played
from sim.standings import rank_single
from sim.markets import Archive
from scripts.refresh_ratings import closes_with_targets
from scripts.run_sim import played_stats


def seasons_on_file(cfg) -> dict[str, pd.DataFrame]:
    """season -> frame of matches (date, home, away, hg, ag, gd_fit, T_fit, ph, pd, pa, book), closes only."""
    cl = closes_with_targets(cfg)
    hist = data.load_history()
    out = {}
    if len(hist):
        hist = hist.copy(); hist["date"] = pd.to_datetime(hist["date"]).dt.strftime("%Y-%m-%d")
        # one result per match: football-data and OpticOdds history files overlap (2025), and a duplicate here doubles the season
        res = hist[["season", "date", "home", "away", "hg", "ag"]].drop_duplicates(["season", "date", "home", "away"])
        m = cl.merge(res, on=["season", "date", "home", "away"], how="inner")
        for s, g in m.groupby("season"):
            out[str(s)] = g.sort_values("date").reset_index(drop=True)
    # current season: closes joined to results.csv
    cur = str(cfg["season"])
    res = data.load("results")
    if len(res):
        g = cl[cl["season"].astype(str) == cur].merge(res[["date", "home", "away", "hg", "ag"]], on=["date", "home", "away"], how="inner")
        if len(g):
            out[cur] = g.sort_values("date").reset_index(drop=True)
    return out


def season_teams(df: pd.DataFrame) -> list:
    return sorted(set(df["home"]) | set(df["away"]))


def checkpoints(df: pd.DataFrame, n=7, first_round=5) -> list[str]:
    """Seven dates spread from matchweek `first_round` to late season (by cumulative matches per club)."""
    dates = sorted(df["date"].unique())
    per_club = len(df) * 2 / max(1, len(season_teams(df)))
    counts = df.groupby("date").size().cumsum() * 2 / max(1, len(season_teams(df)))
    starts = [d for d, c in counts.items() if c >= first_round]
    if not starts:
        return []
    idx = np.linspace(0, len(starts) - 1, n).round().astype(int)
    return [starts[i] for i in sorted(set(idx))]


_ALL_CLOSES = None


def all_closes() -> pd.DataFrame:
    """Every close on file (all seasons): the live recipe fits on all of them with half-life weights, so an early-season
    checkpoint sees last season's closes decayed by the offseason."""
    global _ALL_CLOSES
    if _ALL_CLOSES is None:
        _ALL_CLOSES = closes_with_targets(load_config())
    return _ALL_CLOSES


def simulate_from(df: pd.DataFrame, asof: str, kn: dict, T: list, conf: np.ndarray, n_seasons=5000, seed=1, ratings=None, use_closes_as_lines=False, fixture_adj: dict | None = None) -> dict:
    """Fit ratings on every close before asof (all seasons, unless ratings are given), lock results before asof, simulate the rest.
    fixture_adj: {(date, home, away): goals} added to each fixture's adjustment (the match-day factors of CLAUDE.md 14)."""
    idx = {t: i for i, t in enumerate(T)}
    before = df[df["date"] < asof]; after = df[df["date"] >= asof]
    if ratings is None:
        mk = market_fit(all_closes(), T, asof, kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True)
        ratings = mk["ratings"]
    played = played_stats(before, T)
    fx = []
    win_end = (pd.Timestamp(asof) + pd.Timedelta(days=float(use_closes_as_lines))).strftime("%Y-%m-%d") if use_closes_as_lines and use_closes_as_lines is not True else None
    for r in after.itertuples(index=False):
        extra = float(fixture_adj.get((r.date, r.home, r.away), 0.0)) if fixture_adj else 0.0
        if use_closes_as_lines and np.isfinite(float(r.gd_fit)) and (win_end is None or r.date <= win_end):
            # a number means: only the current round (matches within that many days of asof) is priced off its line, as the live run does
            fx.append(Fixture(idx[r.home], idx[r.away], r.date, adj=kn["home_edge_goals"] + extra, s=kn["posted_line_shrink"], g_pinn=float(r.gd_fit), T=float(r.T_fit) if np.isfinite(float(r.T_fit)) else kn["avg_total_goals"]))
        else:
            fx.append(Fixture(idx[r.home], idx[r.away], r.date, adj=kn["home_edge_goals"] + extra, T=kn["avg_total_goals"]))
    inp = SeasonInputs(T, conf, ratings, fx, played)
    if float(kn.get("dead_dock_goals", 0.0) or 0.0) > 0:
        from sim.season import dock_exempt_from_prepass
        inp.dock_exempt = dock_exempt_from_prepass(inp, kn, seed=seed, n=min(n_seasons, 4000))
    out = run_seasons(inp, kn, n_seasons=n_seasons, seed=seed)
    out["ratings"] = ratings
    return out


def actual_table(df: pd.DataFrame, T: list, conf_map: dict) -> dict:
    st = played_stats(df, T)
    rows = [{"team": t, "points": int(st["points"][i]), "wins": int(st["wins"][i]), "gd": int(st["gd"][i]), "gf": int(st["gf"][i]),
             "away_gd": int(st["away_gd"][i]), "away_gf": int(st["away_gf"][i]), "home_gd": int(st["home_gd"][i]), "home_gf": int(st["home_gf"][i])} for i, t in enumerate(T)]
    return {r["team"]: r for r in rank_single(rows, conf_map)}


def logloss(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6); y = np.asarray(y, float)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def score_archive(arc: Archive, actual: dict, T: list, spots: int = 9) -> dict:
    """Points: rmse of expected points and mean log-pmf of actual points; positions: log-loss of shield / conf winner / playoffs / spoon."""
    pts = arc.points.astype(int)
    act = np.array([actual[t]["points"] for t in T]); exp = pts.mean(axis=0)
    pmf = np.array([(pts[:, i] == act[i]).mean() for i in range(len(T))])
    pmf = np.clip(pmf, 1e-4, None)
    out = {"points_rmse": float(np.sqrt(((exp - act) ** 2).mean())), "points_logpmf": float(np.log(pmf).mean())}
    y_sh = np.array([actual[t]["league_pos"] == 1 for t in T]); y_cf = np.array([actual[t]["conf_seed"] == 1 for t in T])
    y_po = np.array([actual[t]["conf_seed"] <= spots for t in T]); y_sp = np.array([actual[t]["league_pos"] == len(T) for t in T])
    sh, cf, po, sp = arc.shield(), arc.conference_winner(), arc.conf_top(spots), arc.spoon()
    out.update(shield_ll=logloss([sh[t] for t in T], y_sh), conf_ll=logloss([cf[t] for t in T], y_cf), playoffs_ll=logloss([po[t] for t in T], y_po), spoon_ll=logloss([sp[t] for t in T], y_sp))
    return out


# Historical conference membership where it differs from today's (season -> {team: conf}); defunct clubs listed once.
CONF_OVERRIDES = {"Chivas USA": "West"}
CONF_BY_SEASON = {"2012": {"Houston Dynamo": "East", "Sporting Kansas City": "East"}, "2013": {"Houston Dynamo": "East", "Sporting Kansas City": "East"},
                  "2014": {"Houston Dynamo": "East", "Sporting Kansas City": "East"}, "2020": {"Nashville SC": "West"}}
# Playoff places per conference by season (the "make playoffs" market in the replay).
PLAYOFF_SPOTS = {"2012": 5, "2013": 5, "2014": 5, "2015": 6, "2016": 6, "2017": 6, "2018": 6, "2019": 7, "2020": 8, "2021": 7, "2022": 7}


def conf_map_for(season: str | None = None) -> dict:
    cm = dict(conference_of()); cm.update(CONF_OVERRIDES); cm.update(CONF_BY_SEASON.get(str(season), {}))
    return cm


def conf_array(T: list, season: str | None = None) -> np.ndarray:
    cm = conf_map_for(season)
    return np.array([0 if cm.get(t, "East") == "East" else 1 for t in T])


def playoff_spots(season) -> int:
    return PLAYOFF_SPOTS.get(str(season), 9)
