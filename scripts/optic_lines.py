"""Reduce OpticOdds odds objects to one line row: three-way, main Asian handicap, main total. Shared by the harvest, the daily
fetch and the calibration scripts. Prices come back decimal. phase: None (current odds, price/points at top level),
'olv' (opening line value) or 'clv' (closing line value) for the historical endpoint."""
from __future__ import annotations
import re
from sim.devig import american_to_decimal

MONEYLINE = {"moneyline"}
HANDICAP = {"asian handicap"}
TOTAL = {"total goals", "asian total goals"}


def norm_sel(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def to_decimal(p) -> float | None:
    if p is None:
        return None
    try:
        p = float(p)
    except (TypeError, ValueError):
        return None
    if 1.0 < p < 100.0 and abs(p) < 100.0:
        return round(p, 4)
    try:
        return round(american_to_decimal(p), 4)
    except ValueError:
        return None


def _pp(o: dict, phase: str | None):
    """(price, points) for the phase."""
    if phase:
        v = o.get(phase) or {}
        return v.get("price"), v.get("points")
    return o.get("price"), o.get("points")


def lines_from_odds(odds: list[dict], home_name: str, away_name: str, phase: str | None = None) -> dict:
    """Returns {h, d, a, ah_line, ah_home, ah_away, total_line, over, under} (strings '' where missing).
    Main line = the line priced closest to even (books' is_main flags disagree with each other)."""
    hn, an = norm_sel(home_name), norm_sel(away_name)
    ml = {}
    ah: dict[float, dict] = {}
    tot: dict[float, dict] = {}
    for o in odds:
        mk = (o.get("market") or "").strip().lower()
        price, pts = _pp(o, phase)
        d = to_decimal(price)
        if d is None:
            continue
        sel = o.get("normalized_selection") or norm_sel(o.get("selection") or "")
        if mk in MONEYLINE:
            if sel == "draw":
                ml["d"] = d
            elif sel == hn or (o.get("team_id") and sel and sel in hn):
                ml["h"] = d
            elif sel == an or (sel and sel in an):
                ml["a"] = d
        elif mk in HANDICAP and pts is not None:
            pts = float(pts)
            if sel == hn:
                ah.setdefault(pts, {})["home"] = (d, bool(o.get("is_main")))
            elif sel == an:
                ah.setdefault(-pts, {})["away"] = (d, bool(o.get("is_main")))
        elif mk in TOTAL and pts is not None and mk == "total goals":
            pts = float(pts)
            side = (o.get("selection_line") or "").lower() or ("over" if "over" in (o.get("name") or "").lower() else "under" if "under" in (o.get("name") or "").lower() else "")
            if side in ("over", "under"):
                tot.setdefault(pts, {})[side] = (d, bool(o.get("is_main")))
    row = {"h": "", "d": "", "a": "", "ah_line": "", "ah_home": "", "ah_away": "", "total_line": "", "over": "", "under": ""}
    if {"h", "d", "a"} <= set(ml):
        row.update(h=ml["h"], d=ml["d"], a=ml["a"])

    def pick(table, k1, k2):
        full = {L: v for L, v in table.items() if k1 in v and k2 in v}
        if not full:
            return None
        L = min(full, key=lambda L: abs(full[L][k1][0] - full[L][k2][0]))
        return L, full[L][k1][0], full[L][k2][0]
    sp = pick(ah, "home", "away")
    if sp:
        row.update(ah_line=sp[0], ah_home=sp[1], ah_away=sp[2])
    tl = pick(tot, "over", "under")
    if tl:
        row.update(total_line=tl[0], over=tl[1], under=tl[2])
    return row


def ladder_rows(odds: list[dict], home_name: str, away_name: str, phase: str | None = None) -> list[dict]:
    """Every handicap and total line with both sides priced: [{kind, line, price1, price2}] (price1 = home / over)."""
    hn, an = norm_sel(home_name), norm_sel(away_name)
    ah, tot = {}, {}
    for o in odds:
        mk = (o.get("market") or "").strip().lower()
        price, pts = _pp(o, phase)
        d = to_decimal(price)
        if d is None or pts is None:
            continue
        sel = o.get("normalized_selection") or norm_sel(o.get("selection") or "")
        if mk in HANDICAP:
            if sel == hn:
                ah.setdefault(float(pts), {})["home"] = d
            elif sel == an:
                ah.setdefault(-float(pts), {})["away"] = d
        elif mk == "total goals":
            side = (o.get("selection_line") or "").lower()
            if side in ("over", "under"):
                tot.setdefault(float(pts), {})[side] = d
    out = [{"kind": "spread", "line": L, "price1": v["home"], "price2": v["away"]} for L, v in sorted(ah.items()) if "home" in v and "away" in v]
    out += [{"kind": "total", "line": L, "price1": v["over"], "price2": v["under"]} for L, v in sorted(tot.items()) if "over" in v and "under" in v]
    return out
