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


def betas_from_knobs(kn: dict) -> dict | None:
    """The factor betas when `factors_enabled`, else None."""
    if not kn.get("factors_enabled", False):
        return None
    return {"abs": float(kn.get("factor_abs", 0.0) or 0.0), "rest": float(kn.get("factor_rest", 0.0) or 0.0), "short": float(kn.get("factor_short", 0.0) or 0.0), "elim": float(kn.get("factor_elim", 0.0) or 0.0)}


class LiveFactors:
    """Factor values for this season's fixtures as of a run date: absences from data/ratings/absence_values.csv (scripts/absence_values.py:
    listed players x prob_out x regular weight x value, for the dates they are out), rest from results (every competition) and the
    MLS schedule, eliminated status from the table at asof (scripts/dead_teams.py classification)."""

    def __init__(self, asof: str, schedule: pd.DataFrame, results: pd.DataFrame, teams: list, conf_map: dict, spots: int, absence_values: pd.DataFrame | None = None):
        from .teams import ROOT as _R
        p = os.path.join(_R, "data", "ratings", "absence_values.csv")
        av = absence_values if absence_values is not None else (pd.read_csv(p, dtype=str, keep_default_na=False) if os.path.exists(p) else pd.DataFrame())
        self.rows = []; self.long_term = []
        for r in (av.to_dict("records") if len(av) else []):
            try:
                cost = float(r.get("cost_per_game") or 0.0)
            except ValueError:
                cost = 0.0
            if cost == 0.0 or str(r.get("stale", "0")) == "1":
                continue
            self.rows.append((r["team"], str(r.get("out_from") or "0000"), str(r.get("expected_return") or "9999"), cost))
            # long-term flag for the bracket (Zac 2026-10-27, "1"): an undated row counts in the knockouts only when its note says the
            # absence is long (season-ending, ACL, cruciate) or it has already run 28 days or more; a dated row counts by its date
            note = str(r.get("note", "")).lower()
            long_note = any(k in note for k in ("sei", "season-ending", "season ending", "out for the season", "for 2026", "acl", "cruciate", "achilles"))
            try:
                days = (pd.Timestamp(asof) - pd.Timestamp(str(r.get("out_from") or asof))).days
            except (ValueError, TypeError):
                days = 0
            self.long_term.append(bool(long_note or days >= 28))
        self.asof = asof
        # competitive match dates per club: results (all competitions) plus unplayed MLS fixtures
        dates = {}
        for d, h, a in zip(results["date"], results["home"], results["away"]):
            dates.setdefault(h, set()).add(d); dates.setdefault(a, set()).add(d)
        played = set(zip(results["date"], results["home"], results["away"]))
        for d, h, a, c in zip(schedule["date"], schedule["home"], schedule["away"], schedule["competition"]):
            if c == "MLS" and (d, h, a) not in played:
                dates.setdefault(h, set()).add(d); dates.setdefault(a, set()).add(d)
        self.dates = {t: sorted(v) for t, v in dates.items()}
        # eliminated as of asof
        self.elim = {}
        try:
            from scripts.dead_teams import classify
            mls = results[results["competition"].isin(["MLS", ""])]
            before = mls[mls["date"] < asof]
            rem = schedule[(schedule["competition"] == "MLS")]
            rem = rem[[(d, h, a) not in played for d, h, a in zip(rem["date"], rem["home"], rem["away"])]]
            all_df = pd.concat([before[["date", "home", "away"]], rem[["date", "home", "away"]]], ignore_index=True)
            st = classify(before, all_df, asof, teams, conf_map, spots)
            self.elim = {t: int(s == "eliminated") for t, s in st.items()}
        except Exception:
            self.elim = {}

    def mv(self, team: str, date: str) -> float:
        return float(sum(c for t, d0, d1, c in self.rows if t == team and d0 <= date < d1))

    def playoff_mv(self, team: str, first_playoff_date: str) -> float:
        """Missing value carried into the bracket: live rows out on the first playoff date by a dated return, plus undated rows
        only when long-term (note or 28 days already; Zac 2026-10-27). A weekly "Out" with no date is usually a one or two week
        knock, and the list cannot close it between the Decision Day and Wild Card reports."""
        tot = 0.0
        for (t, d0, d1, c), lt in zip(self.rows, self.long_term):
            if t != team or not (d0 <= first_playoff_date < d1):
                continue
            if d1 == "9999" and not lt:
                continue
            tot += c
        return float(tot)

    def rest(self, team: str, date: str) -> float:
        ds = self.dates.get(team, [])
        prev = [d for d in ds if d < date]
        if not prev:
            return 7.0
        return float((pd.Timestamp(date) - pd.Timestamp(prev[-1])).days)

    def x(self, date: str, home: str, away: str) -> dict:
        rh, ra = self.rest(home, date), self.rest(away, date)
        return {"abs": self.mv(home, date) - self.mv(away, date), "rest": min(rh, 10.0) - min(ra, 10.0), "short": float(rh <= 3) - float(ra <= 3),
                "elim": float(self.elim.get(home, 0)) - float(self.elim.get(away, 0)), "mv_home": self.mv(home, date), "mv_away": self.mv(away, date)}


def live_factors(asof: str) -> "LiveFactors":
    from . import data
    from .teams import teams as _teams, conference_of
    from .knobs import load_config
    cfg = load_config()
    return LiveFactors(asof, data.load("schedule"), data.load("results"), _teams(), conference_of(), int(cfg.get("mls", {}).get("playoff_teams_per_conference", 9)))
