#!/usr/bin/env python3
"""MLS futures prices from The Odds API (the-odds-api.com, v4; official documented feed, key in ODDS_API_KEY).
Comparison only (CLAUDE.md section 16): these prices never enter the ratings or the sim. edges.py reads them.

Finds the MLS outright markets on the feed (sport keys starting soccer_usa_mls with has_outrights), fetches every
bookmaker's prices and writes:
  data/market/futures_odds.csv          the latest snapshot (this source's rows replaced, other sources kept)
  data/market/futures_odds_history.csv  every snapshot appended (for CLV against later prices)
Markets: cup (MLS Cup winner), conf_east / conf_west (conference champion = reaches the MLS Cup final).
Without a key it prints one line and exits 0, leaving the files as they are.
Usage: python3 scripts/fetch_odds.py [--regions us,us2] [--list]"""
from __future__ import annotations
import argparse, csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.teams import ROOT, canon
from scripts.common import session, now_utc, utc_iso, et_date
from scripts.odds_math import decimal_to_american

BASE = "https://api.the-odds-api.com/v4"
OUT = os.path.join(ROOT, "data", "market", "futures_odds.csv")
HIST = os.path.join(ROOT, "data", "market", "futures_odds_history.csv")
COLS = ["date", "market", "team", "line", "price_american", "price_decimal", "book", "fetched_at", "source"]
SOURCE = "the_odds_api"


def market_of(title: str) -> str:
    t = title.lower()
    if "east" in t:
        return "conf_east"
    if "west" in t:
        return "conf_west"
    return "cup"


def call(s, path, **params):
    r = s.get(BASE + path, params=params, timeout=40)
    left = r.headers.get("x-requests-remaining")
    if r.status_code != 200:
        print(f"fetch_odds: {path} -> {r.status_code} {r.text[:160]}", file=sys.stderr)
        return None, left
    return r.json(), left


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", default="us,us2")
    ap.add_argument("--list", action="store_true", help="print the MLS sport keys on the feed and stop")
    a = ap.parse_args()
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        print("fetch_odds: skipped (ODDS_API_KEY not set)")
        return 0
    s = session()
    sports, left = call(s, "/sports/", apiKey=key, all="true")
    if sports is None:
        return 1
    mls = [x for x in sports if str(x.get("key", "")).startswith("soccer_usa_mls") and x.get("has_outrights")]
    if a.list:
        for x in sports:
            if "mls" in str(x.get("key", "")) or "MLS" in str(x.get("title", "")):
                print(x.get("key"), "|", x.get("title"), "|", x.get("description"), "| outrights", x.get("has_outrights"), "| active", x.get("active"))
        return 0
    if not mls:
        print("fetch_odds: the feed lists no MLS outright market today (nothing written)")
        return 0
    stamp = utc_iso(now_utc())
    day = et_date(now_utc())
    rows, unknown = [], set()
    for sp in mls:
        data, left = call(s, f"/sports/{sp['key']}/odds/", apiKey=key, regions=a.regions, markets="outrights", oddsFormat="decimal")
        for ev in data or []:
            mk = market_of(" ".join(str(ev.get(k) or "") for k in ("sport_title", "home_team")) + " " + str(sp.get("title", "")) + " " + str(sp.get("description", "")))
            for bk in ev.get("bookmakers", []):
                for m in bk.get("markets", []):
                    if m.get("key") != "outrights":
                        continue
                    for o in m.get("outcomes", []):
                        team = canon(o.get("name", ""), strict=False)
                        if not team:
                            unknown.add(o.get("name"))
                            continue
                        d = float(o["price"])
                        if d <= 1:
                            continue
                        rows.append({"date": day, "market": mk, "team": team, "line": "", "price_american": decimal_to_american(d),
                                     "price_decimal": round(d, 4), "book": bk.get("key"), "fetched_at": bk.get("last_update") or stamp,
                                     "source": SOURCE})
    keep = []
    if os.path.exists(OUT):
        with open(OUT) as f:
            keep = [r for r in csv.DictReader(f) if r.get("source") != SOURCE]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(keep + rows)
    new = not os.path.exists(HIST)
    with open(HIST, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS + ["snapshot"])
        if new:
            w.writeheader()
        w.writerows({**r, "snapshot": stamp} for r in rows)
    books = sorted({r["book"] for r in rows})
    by = {m: sum(r["market"] == m for r in rows) for m in ("cup", "conf_east", "conf_west")}
    print(f"fetch_odds: {len(rows)} prices from {len(books)} books ({', '.join(books)}); cup {by['cup']}, east {by['conf_east']}, "
          f"west {by['conf_west']}; quota left {left}" + (f"; unmatched names: {', '.join(sorted(map(str, unknown)))}" if unknown else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
