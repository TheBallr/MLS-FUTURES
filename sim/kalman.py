"""Kalman-filter ratings on Pinnacle closes (the "tracking" alternative to the half-life least-squares fit).

State: one strength per club (goals of expected margin on a neutral pitch), a random walk in time. Every close is one noisy
measurement of a difference of two strengths: gd_fit - home_edge = r_home - r_away + e, e ~ N(0, s^2). The filter carries the
full covariance across clubs, so a club with few recent closes keeps a wide posterior and moves further on its next line,
while a club with many closes moves little: the information weighting that a single half-life cannot give.

Knobs (all in goals; off_shrink is a factor): q_day (process sd per calendar day within a season), s (measurement sd of a close), s_open (an opener's
sd, when openers are fed as earlier measurements), p0 (prior sd for a club's first season), q_off (extra sd added across an
off-season: any league-wide gap of `gap_days` or more between measurement dates), prior_new (prior mean for a club in its
first season; the expansion prior), off_shrink (strengths revert toward the mean by this factor across an off-season,
1 = none). Within a season the random walk is per day, a gap capped at `gap_cap` days. A mid-season pause of 45 days or more
counts as an off-season too: the 2026 World Cup pause (May 24 to Jul 16, 53 days) did, and measured 2026-10-19 that tracks
the close better afterwards than treating it as an ordinary gap (0.278 v 0.291 goals rmse a week out, Jul 16 to Oct 14).

Scoring convention (same as the market fit): ratings centred at zero over the clubs of the season.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

DEFAULT = {"q_day": 0.012, "s": 0.22, "s_open": 0.30, "p0": 0.40, "q_off": 0.25, "prior_new": -0.25, "gap_days": 45, "gap_cap": 30, "off_shrink": 1.0}


class KalmanRatings:
    """Sequential filter over a frame of measurements sorted by date. Call `advance(date)` then `rating(teams)` to read the
    state as of a date (strictly after every measurement before it). The live build uses scripts/close_track.kalman_states."""

    def __init__(self, teams: list, knobs: dict | None = None):
        self.kn = dict(DEFAULT); self.kn.update(knobs or {})
        self.teams = list(teams); self.idx = {t: i for i, t in enumerate(self.teams)}
        n = len(self.teams)
        self.r = np.full(n, float(self.kn["prior_new"]))
        self.P = np.eye(n) * float(self.kn["p0"]) ** 2
        self.seen = np.zeros(n, bool)      # has the club had any measurement
        self.last_obs = np.full(n, np.datetime64("NaT"), dtype="datetime64[D]")  # date of each club's latest measurement
        self.t = None                      # current filter date
        self.n_obs = np.zeros(n, int)

    def _advance_to(self, date):
        """Add process noise for the days between the current filter date and `date` (league-wide: a capped gap, or an off-season jump)."""
        d = np.datetime64(pd.Timestamp(date).date())
        if self.t is None:
            self.t = d; return
        if d <= self.t:
            return
        days = float((d - self.t) / np.timedelta64(1, "D"))
        q = float(self.kn["q_day"]); cap = float(self.kn["gap_cap"]); gap = float(self.kn["gap_days"]); qoff = float(self.kn["q_off"])
        add = q * q * min(days, cap)
        diag = np.full(len(self.r), add)
        if days >= gap:  # a league-wide gap is an off-season for every club: strengths revert toward the mean by off_shrink, variance grows by q_off
            phi = float(self.kn.get("off_shrink", 1.0))
            if phi < 1.0:
                act = self.active()
                m = self.r[act].mean() if act.any() else 0.0
                self.r = m + phi * (self.r - m)
                self.P = (phi * phi) * self.P
            diag += qoff * qoff
        self.P[np.diag_indices_from(self.P)] += diag
        self.t = d

    def observe(self, home: str, away: str, y: float, sd: float | None = None):
        """One measurement y = r_home - r_away + e, e ~ N(0, sd^2). Returns the one-step-ahead prediction and its variance."""
        h, a = self.idx.get(home), self.idx.get(away)
        if h is None or a is None or not np.isfinite(y):
            return np.nan, np.nan
        s2 = float(sd if sd is not None else self.kn["s"]) ** 2
        Ph = self.P[h]; Pa = self.P[a]
        # H = e_h - e_a ; S = H P H' + s2 ; K = P H' / S
        PHt = Ph - Pa                      # P H' as a vector over clubs
        S = PHt[h] - PHt[a] + s2
        pred = self.r[h] - self.r[a]
        K = PHt / S
        self.r = self.r + K * (y - pred)
        self.P = self.P - np.outer(K, PHt)
        self.P = 0.5 * (self.P + self.P.T)
        self.seen[h] = True; self.seen[a] = True; self.n_obs[h] += 1; self.n_obs[a] += 1
        self.last_obs[h] = self.t; self.last_obs[a] = self.t
        return pred, S

    def run(self, obs: pd.DataFrame, until: str | None = None, record: bool = False) -> pd.DataFrame | None:
        """Feed a frame (date, home, away, y[, sd]) in date order, stopping before `until` (strictly). With record=True returns
        the one-step-ahead predictions (pred, var) per row for the likelihood / rmse of the filter's own tracking."""
        rows = []
        has_sd = "sd" in obs.columns
        for r in obs.itertuples(index=False):
            if until is not None and r.date >= until:
                break
            self._advance_to(r.date)
            sd = float(r.sd) if has_sd and r.sd is not None and r.sd == r.sd else None
            pred, S = self.observe(r.home, r.away, float(r.y), sd)
            if record:
                rows.append((r.date, r.home, r.away, float(r.y), pred, S))
        if until is not None:
            self._advance_to(until)
        return pd.DataFrame(rows, columns=["date", "home", "away", "y", "pred", "var"]) if record else None

    def active(self, days: int = 400) -> np.ndarray:
        """Clubs with a measurement in the last `days` (a defunct club's variance grows forever and must not enter the centring)."""
        if self.t is None:
            return self.seen.copy()
        age = (self.t - self.last_obs) / np.timedelta64(1, "D")
        return self.seen & (age <= days)

    def ratings(self, teams: list | None = None) -> np.ndarray:
        """Centred strengths for `teams` (default: every club that has a measurement)."""
        if teams is None:
            teams = [t for t, s in zip(self.teams, self.seen) if s]
        v = np.array([self.r[self.idx[t]] if t in self.idx else float(self.kn["prior_new"]) for t in teams], float)
        return v - v.mean()

    def sds(self, teams: list) -> np.ndarray:
        """Posterior sd of each club's centred strength (the common level is unidentified by difference measurements and is
        removed: var(r_i - mean_T r) over the clubs in `teams`)."""
        ids = [self.idx[t] for t in teams if t in self.idx]
        P = self.P[np.ix_(ids, ids)]
        n = len(ids)
        if n == 0:
            return np.full(len(teams), float(self.kn["p0"]))
        v = np.diag(P) - 2.0 * P.mean(axis=1) + P.mean()
        d = dict(zip([t for t in teams if t in self.idx], np.sqrt(np.clip(v, 0, None))))
        return np.array([d.get(t, float(self.kn["p0"])) for t in teams], float)


def _he(df: pd.DataFrame, he):
    """he: a number, a {season: value} dict, or the name of a per-row column."""
    if isinstance(he, str):
        return df[he].astype(float)
    if isinstance(he, dict):
        return df["season"].astype(str).map(he).astype(float)
    return float(he)


def measurements(closes: pd.DataFrame, he_by_season: dict | float, club_deltas: dict | None = None, openers: pd.DataFrame | None = None,
                 s_open: float | None = None) -> pd.DataFrame:
    """Closes (season, date, home, away, gd_fit) -> measurement frame y = gd_fit - home edge (league edge per season, plus the
    home club's delta). Openers, when given (same columns plus `date_open`), are earlier, noisier measurements of the same match."""
    df = closes.dropna(subset=["gd_fit"]).copy()
    he = _he(df, he_by_season)
    delta = df["home"].map(club_deltas or {}).fillna(0.0).astype(float) if club_deltas else 0.0
    df["y"] = df["gd_fit"].astype(float) - he - delta
    df["sd"] = np.nan
    out = df[["date", "home", "away", "y", "sd"]]
    if openers is not None and len(openers):
        o = openers.dropna(subset=["gd_fit"]).copy()
        heo = _he(o, he_by_season)
        do = o["home"].map(club_deltas or {}).fillna(0.0).astype(float) if club_deltas else 0.0
        o["y"] = o["gd_fit"].astype(float) - heo - do
        o["sd"] = float(s_open if s_open is not None else DEFAULT["s_open"])
        o["date"] = o["date_open"]
        out = pd.concat([out, o[["date", "home", "away", "y", "sd"]]], ignore_index=True)
    out = out.sort_values(["date"], kind="stable").reset_index(drop=True)
    out["sd"] = out["sd"].where(out["sd"].notna(), None)
    return out

