"""Named, pricable match-day factors netted out of every Pinnacle close so the Kalman state is full-health strength
(CLAUDE.md section 14), and added back per fixture: absences (scripts/absences.py missing value, goals), rest (days of rest
difference, capped 10), short week (3 days or fewer), eliminated status (scripts/dead_teams.py classification).

betas: {"abs": goals per goal of missing value, "rest": goals per day of rest difference, "short": goals per short-week flag
difference, "elim": goals per eliminated flag difference} (home minus away throughout). A close enters the filter as
y - sum(beta_k x_k); a prediction for a future fixture adds sum(beta_k x_k_expected), where expected absences come from
`abs_mode`: "actual" (the lineups, a ceiling in a backtest), "trail10" (the club's mean missing value over its last ten
games before asof, the honest persistence forecast), "last3", or "none"."""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
from .teams import ROOT

KEYS = ("abs", "rest", "short", "elim")
_F = None


def factor_vector(betas: dict | None, x: dict) -> float:
    if not betas:
        return 0.0
    return float(sum(float(betas.get(k, 0.0) or 0.0) * float(x.get(k, 0.0)) for k in KEYS))


class Factors:
    """Lookups built once: actual factor values per match, per-club absence history for forecasts, eliminated status."""

    def __init__(self):
        from scripts.absences import OUT_TEAM, match_frame
        from scripts.close_track import rest_table
        from scripts.absence_price import eliminated_table
        tm = pd.read_csv(OUT_TEAM, dtype={"season": str}) if os.path.exists(OUT_TEAM) else pd.DataFrame(columns=["season", "date", "team", "opp", "home", "mv", "early"])
        m = match_frame(tm) if len(tm) else pd.DataFrame(columns=["date", "home", "away", "mv_home", "mv_away"])
        self.mv = {(d, h, a): (float(x), float(y)) for d, h, a, x, y in zip(m["date"], m["home"], m["away"], m["mv_home"], m["mv_away"])}
        self.rest = rest_table()
        el = eliminated_table()
        self.elim = {(str(s), d, t): int(v) for s, d, t, v in zip(el["season"], el["date"], el["team"], el["eliminated"])}
        self.elim_dates = {}
        for s, d in zip(el["season"].astype(str), el["date"]):
            self.elim_dates.setdefault(s, set()).add(d)
        self.elim_dates = {s: sorted(v) for s, v in self.elim_dates.items()}
        self.team_hist = {}
        for t, g in tm.sort_values("date").groupby("team"):
            self.team_hist[t] = (np.array(g["date"], dtype="datetime64[D]"), np.concatenate([[0.0], np.cumsum(g["mv"].astype(float).to_numpy())]))

    def x_actual(self, date: str, home: str, away: str) -> dict:
        mvh, mva = self.mv.get((date, home, away), (0.0, 0.0))
        rh, ra = self.rest.get((date, home), 7.0), self.rest.get((date, away), 7.0)
        season = date[:4]
        return {"abs": mvh - mva, "rest": min(rh, 10.0) - min(ra, 10.0), "short": float(rh <= 3) - float(ra <= 3),
                "elim": float(self.elim.get((season, date, home), 0)) - float(self.elim.get((season, date, away), 0)), "mv_home": mvh, "mv_away": mva}

    def mv_forecast(self, team: str, asof: str, mode: str = "trail10") -> float:
        """Expected missing value of `team` for a fixture after `asof`, from its games strictly before asof."""
        if mode == "none" or team not in self.team_hist:
            return 0.0
        ds, cs = self.team_hist[team]
        hi = int(np.searchsorted(ds, np.datetime64(asof), side="left"))
        n = 10 if mode == "trail10" else (3 if mode == "last3" else 1)
        lo = max(0, hi - n)
        return float((cs[hi] - cs[lo]) / (hi - lo)) if hi > lo else 0.0

    def elim_asof(self, season: str, team: str, asof: str) -> int:
        ds = self.elim_dates.get(str(season))
        if not ds:
            return 0
        prev = [d for d in ds if d <= asof]
        return int(self.elim.get((str(season), prev[-1], team), 0)) if prev else 0

    def x_expected(self, date: str, home: str, away: str, asof: str, abs_mode: str = "trail10") -> dict:
        """Factor values for a fixture as forecast at `asof`: absences per abs_mode, rest and short week from the schedule
        (known), eliminated status as of asof."""
        x = self.x_actual(date, home, away)
        if abs_mode != "actual":
            x["abs"] = self.mv_forecast(home, asof, abs_mode) - self.mv_forecast(away, asof, abs_mode)
        season = date[:4]
        x["elim"] = float(self.elim_asof(season, home, asof)) - float(self.elim_asof(season, away, asof))
        return x


def factors() -> Factors:
    global _F
    if _F is None:
        _F = Factors()
    return _F
