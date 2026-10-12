#!/usr/bin/env python3
"""Pinnacle lines by the site's own guest API (public key from pinnacle.com's JavaScript; not an account credential).
Period 0 only: three-way moneyline, and the handicap and total whose two sides are priced closest to even (the main line).
American -> decimal. Appends every posted fixture to data/market/current_round_odds.csv with a UTC stamp.
--close writes fixtures kicking off within 25 minutes to closing_lines.csv as pinnacle_last. Live fixtures are dropped.
Usage: python3 scripts/fetch_pinnacle.py [--close] [--window-min 25] [--league-id 2663]"""
from __future__ import annotations
import argparse, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import get, now_utc, utc_iso, parse_utc, et_date
from sim import data
from sim.devig import american_to_decimal
from sim.teams import canon, UnknownTeam

BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
# The public guest key embedded in pinnacle.com's front end. If the API answers 401, read the current value from the site's JS bundle.
GUEST_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
HDR = {"X-API-Key": GUEST_KEY, "Accept": "application/json", "Referer": "https://www.pinnacle.com/", "Origin": "https://www.pinnacle.com"}
SOCCER = 29


def find_mls_league_id() -> int | None:
    j = get(f"{BASE}/sports/{SOCCER}/leagues", {"all": "false"}, headers=HDR)
    for lg in j or []:
        name = (lg.get("name") or "").lower()
        if "mls" in name or "major league soccer" in name:
            if "next" in name or "women" in name:
                continue
            return int(lg["id"])
    return None


def fetch_lines(league_id: int) -> list[dict]:
    matchups = get(f"{BASE}/leagues/{league_id}/matchups", headers=HDR) or []
    markets = get(f"{BASE}/leagues/{league_id}/markets/straight", headers=HDR) or []
    by_id = {}
    for m in matchups:
        if m.get("type") not in (None, "matchup") or m.get("parentId"):
            continue
        parts = {p.get("alignment"): p.get("name") for p in m.get("participants", [])}
        if "home" not in parts or "away" not in parts:
            continue
        by_id[m["id"]] = {"id": m["id"], "home_raw": parts["home"], "away_raw": parts["away"], "start": m.get("startTime"), "live": bool(m.get("isLive"))}
    rows = {}
    for mk in markets:
        mid = mk.get("matchupId")
        if mid not in by_id or mk.get("period") != 0 or mk.get("isAlternate"):
            pass
        if mid not in by_id or mk.get("period") != 0:
            continue
        r = rows.setdefault(mid, {"ml": None, "spreads": [], "totals": []})
        prices = {p.get("designation"): p for p in mk.get("prices", [])}
        t = mk.get("type")
        if t == "moneyline" and {"home", "draw", "away"} <= set(prices):
            r["ml"] = (prices["home"]["price"], prices["draw"]["price"], prices["away"]["price"])
        elif t == "spread" and {"home", "away"} <= set(prices):
            r["spreads"].append((prices["home"].get("points"), prices["home"]["price"], prices["away"]["price"]))
        elif t == "total" and {"over", "under"} <= set(prices):
            r["totals"].append((prices["over"].get("points"), prices["over"]["price"], prices["under"]["price"]))
    out = []
    stamp = utc_iso(now_utc())
    unknown = set()
    for mid, r in rows.items():
        m = by_id[mid]
        if m["live"]:
            continue
        try:
            home, away = canon(m["home_raw"]), canon(m["away_raw"])
        except UnknownTeam as e:
            unknown.add(str(e)); continue
        def main_line(cands):
            # the line whose two prices are closest to even (smallest |p1 - p2| in decimal)
            best = None
            for pts, p1, p2 in cands:
                try:
                    d1, d2 = american_to_decimal(p1), american_to_decimal(p2)
                except ValueError:
                    continue
                gap = abs(d1 - d2)
                if best is None or gap < best[0]:
                    best = (gap, pts, d1, d2)
            return best
        ko = parse_utc(m["start"])
        row = {"date": et_date(ko), "kickoff_utc": utc_iso(ko), "home": home, "away": away, "book": "pinnacle",
               "h": "", "d": "", "a": "", "ah_line": "", "ah_home": "", "ah_away": "", "total_line": "", "over": "", "under": "",
               "fetched_at": stamp, "fixture_id": str(mid)}
        if r["ml"]:
            try:
                row["h"], row["d"], row["a"] = [round(american_to_decimal(x), 4) for x in r["ml"]]
            except ValueError:
                pass
        sp = main_line(r["spreads"])
        if sp:
            row["ah_line"], row["ah_home"], row["ah_away"] = sp[1], round(sp[2], 4), round(sp[3], 4)
        tl = main_line(r["totals"])
        if tl:
            row["total_line"], row["over"], row["under"] = tl[1], round(tl[2], 4), round(tl[3], 4)
        if row["h"] or row["ah_line"]:
            out.append(row)
    if unknown:
        print(f"fetch_pinnacle: unknown names (add to sim/teams.py): {sorted(unknown)}", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--close", action="store_true"); ap.add_argument("--window-min", type=int, default=25); ap.add_argument("--league-id", type=int, default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    lid = a.league_id or find_mls_league_id()
    if not lid:
        print("fetch_pinnacle: MLS league id not found (guest API unreachable or key changed)"); return 1
    rows = fetch_lines(lid)
    if not rows:
        print(f"fetch_pinnacle: no posted MLS fixtures (league {lid})"); return 0
    cur = data.load("current_round_odds")
    cur = pd.concat([cur, pd.DataFrame(rows)], ignore_index=True)
    data.save("current_round_odds", cur)
    n_close = 0
    if a.close:
        now = now_utc()
        soon = [r for r in rows if 0 <= (parse_utc(r["kickoff_utc"]) - now).total_seconds() <= a.window_min * 60 + 60]
        if soon:
            cl = data.load("closing_lines")
            for r in soon:
                r = dict(r, book="pinnacle_last")
                # pinnacle_close (from the OpticOdds clv field) outranks pinnacle_last; never overwrite it
                m = (cl["date"] == r["date"]) & (cl["home"] == r["home"]) & (cl["away"] == r["away"])
                if m.any() and (cl.loc[m, "book"] == "pinnacle_close").any():
                    continue
                cl = cl[~m]
                cl = pd.concat([cl, pd.DataFrame([r])], ignore_index=True)
                n_close += 1
            data.save("closing_lines", cl.sort_values(["kickoff_utc", "home"]))
    if not a.quiet:
        for r in rows:
            print(f"  {r['date']} {r['home']} v {r['away']}: {r['h']}/{r['d']}/{r['a']} AH {r['ah_line']} ({r['ah_home']}/{r['ah_away']}) O/U {r['total_line']} ({r['over']}/{r['under']})")
    print(f"fetch_pinnacle: {len(rows)} posted MLS fixtures captured" + (f", {n_close} closes written" if a.close else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
