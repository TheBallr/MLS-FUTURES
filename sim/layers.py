"""Layers on top of the ratings: injuries, call-ups, hand adjustments, scenarios. Team ratings never change here;
each layer returns a per-fixture adjustment in goals (positive favours the home side)."""
from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd
from .ratings import half_life_weights


def _d(x):
    try:
        return pd.Timestamp(x).date() if str(x) != "" else None
    except Exception:
        return None


def absorption_share(team: str, d0, d1, closes: pd.DataFrame, asof, half_life: float) -> float:
    """Share of the team's half-life weight that comes from closes dated inside [d0, d1)."""
    if closes is None or len(closes) == 0:
        return 0.0
    c = closes[(closes["home"] == team) | (closes["away"] == team)]
    if len(c) == 0:
        return 0.0
    dates = pd.to_datetime(c["date"])
    w = half_life_weights(dates, asof, half_life)
    inside = (dates.dt.date >= d0) & (dates.dt.date < d1) if d1 is not None else (dates.dt.date >= d0)
    tot = w.sum()
    return float(w[inside.to_numpy()].sum() / tot) if tot > 0 else 0.0


def absence_penalty(value: float, prob_out: float, absent: bool, s: float) -> float:
    """penalty = value x ((1 - prob_out if absent else 1) - (1 - prob_out x s)); negative = cost, positive = return bonus."""
    now = (1.0 - prob_out) if absent else 1.0
    absorbed = 1.0 - prob_out * s
    return value * (now - absorbed)


def _rows_penalty(rows: pd.DataFrame, team: str, fixture_date, closes, asof, half_life, tiers: dict, start_col, end_col, default_value=None) -> tuple[float, list]:
    """Sum of penalties for one team on one fixture date. Returns (total, detail rows)."""
    total = 0.0
    details = []
    fd = _d(fixture_date)
    for r in rows.itertuples(index=False):
        d0, d1 = _d(getattr(r, start_col)), _d(getattr(r, end_col))
        if d0 is None:
            continue
        try:
            value = float(r.value_goals) if str(getattr(r, "value_goals", "")) != "" else None
        except (TypeError, ValueError):
            value = None
        if value is None:
            tier = str(getattr(r, "tier", "squad") or "squad").lower()
            value = float(tiers.get(tier.replace("doubt", "").strip() or "squad", tiers["squad"]))
            if "doubt" in tier:
                value *= 0.5
        try:
            p = float(r.prob_out) if str(r.prob_out) != "" else 1.0
        except (TypeError, ValueError):
            p = 1.0
        absent = (fd >= d0) and (d1 is None or fd < d1)
        s = absorption_share(team, d0, min(d1, _d(asof)) if d1 else _d(asof), closes, asof, half_life)
        pen = absence_penalty(value, p, absent, s)
        if abs(pen) > 1e-9:
            total += pen
            details.append({"player": getattr(r, "player", ""), "value": value, "prob_out": p, "absent": absent, "absorbed": round(s, 3), "penalty": round(pen, 4)})
    return total, details


def team_penalty(team: str, fixture_date, injuries: pd.DataFrame, callups: pd.DataFrame, closes, asof, half_life, tiers: dict,
                 injuries_on: bool, callups_on: bool) -> dict:
    """Net penalty for a team on a date, in goals (negative = weaker)."""
    out = {"injury": 0.0, "callup": 0.0, "detail": []}
    if injuries_on and injuries is not None and len(injuries):
        rows = injuries[injuries["team"] == team]
        pen, det = _rows_penalty(rows, team, fixture_date, closes, asof, half_life, tiers, "out_from", "expected_return")
        out["injury"] = pen; out["detail"] += [dict(d, kind="injury") for d in det]
    if callups_on and callups is not None and len(callups):
        rows = callups[callups["team"] == team]
        pen, det = _rows_penalty(rows, team, fixture_date, closes, asof, half_life, tiers, "window_start", "window_end")
        out["callup"] = pen; out["detail"] += [dict(d, kind="callup") for d in det]
    return out


def _adj_dates(r):
    """(from, to) of an adjustments row; `from` is a Python keyword so itertuples renames it, hence positional access (team, goals, from, to, ...)."""
    return _d(r[2]) if len(r) > 2 else None, _d(r[3]) if len(r) > 3 else None


def hand_adjustment(team: str, fixture_date, adjustments: pd.DataFrame) -> float:
    """Dated (from/to) hand adjustments in goals for one fixture, on Zac's word only. Rows with no `to` are rating-level
    (see rating_adjustments) and are not counted here, so nothing is applied twice."""
    if adjustments is None or len(adjustments) == 0:
        return 0.0
    fd = _d(fixture_date)
    tot = 0.0
    for r in adjustments[adjustments["team"] == team].itertuples(index=False):
        d0, d1 = _adj_dates(r)
        if d1 is None:
            continue
        if (d0 is None or fd >= d0) and fd <= d1:
            try:
                tot += float(r.goals)
            except (TypeError, ValueError):
                pass
    return tot


def rating_adjustments(adjustments: pd.DataFrame, asof) -> dict:
    """team -> goals for open-ended rows (no `to`) whose `from` is on or before asof: added to the club's rating itself, so the
    regular season, the playoffs and the Ratings tab all see it. The blend file stays the regenerated blend."""
    out = {}
    if adjustments is None or len(adjustments) == 0:
        return out
    a = _d(asof)
    for r in adjustments.itertuples(index=False):
        d0, d1 = _adj_dates(r)
        if d1 is not None or (d0 is not None and a is not None and a < d0):
            continue
        try:
            out[r.team] = out.get(r.team, 0.0) + float(r.goals)
        except (TypeError, ValueError):
            pass
    return out


def scenarios_for_engine(scen: pd.DataFrame, teams: list) -> list[dict]:
    idx = {t: i for i, t in enumerate(teams)}
    rows = []
    for r in scen.itertuples(index=False):
        if r.team not in idx:
            continue
        rows.append({"team": r.team, "team_idx": idx[r.team], "type": str(r.type).strip().lower(), "prob": float(r.prob or 0),
                     "mean": float(r.mean or 0), "sd": float(r.sd or 0), "min": float(r.min or 0),
                     "from": str(getattr(r, "_7", "") if False else r[6]), "to": str(r[7]), "note": str(r.note)})
    return rows
