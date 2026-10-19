#!/usr/bin/env python3
"""Daily OpticOdds pull while the key lives (optional at every step; without the key it prints one line and exits 0):
 1. the coming three weeks' lines from every book into current_round_odds.csv (book id in `book`; Pinnacle rows join the guest-API ones);
 2. completed fixtures' scores into results.csv (source optic) where ESPN has not already filled them (after Decision Day as
    "MLS Cup Playoffs", with no winner: a level playoff score is locked once ESPN's row brings the shoot-out winner);
 3. Pinnacle's closes (book pinnacle_close) from the historical odds endpoint's clv field for fixtures finished in the last 3 days;
 4. the injury feed merged into injuries.csv (section 9 rules; tiers untouched).
Usage: OPTIC_API_KEY=... python3 scripts/fetch_optic.py [--days 21] [--books pinnacle,ps3838,betfair,bet365,draftkings,fanduel]"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.optic_client import Optic, dump
from scripts.common import now_utc, utc_iso, parse_utc, et_date, today_et
from scripts.harvest_optic import catalogues, find_leagues, RAW, dump_gz
from sim.data import merge_results
from scripts.fetch_injuries import merge as merge_injuries
from sim import data
from sim.knobs import load_config
from sim.teams import canon, UnknownTeam

from scripts.optic_lines import lines_from_odds


def odds_row(fx: dict, book: str, odds: list, home: str, away: str, stamp: str, phase: str | None = None) -> dict | None:
    r = lines_from_odds(odds, fx.get("home_team_display", ""), fx.get("away_team_display", ""), phase)
    if not (r["h"] or r["ah_line"] != ""):
        return None
    ko = parse_utc(fx["start_date"])
    return {"date": et_date(ko), "kickoff_utc": utc_iso(ko), "home": home, "away": away, "book": book, **r, "fetched_at": stamp, "fixture_id": fx["id"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--books", default="pinnacle,ps3838,betfair,bet365,draftkings,fanduel")
    ap.add_argument("--no-closes", action="store_true")
    a = ap.parse_args()
    c = Optic()
    if not c.available:
        print("fetch_optic: no OPTIC_API_KEY; skipped (guest API, ESPN and the injury site carry the routine)"); return 0
    books = [b.strip() for b in a.books.split(",") if b.strip()]
    cat = catalogues(c)
    found = find_leagues(cat.get("leagues"))
    if "mls" not in found:
        print("fetch_optic: key dark or MLS league not found; skipped"); return 0
    lid = found["mls"]["id"]
    now = now_utc(); stamp = utc_iso(now)
    fixtures = []
    for pg in c.paged("/fixtures", {"league": lid, "start_date_after": (now - dt.timedelta(days=3)).strftime("%Y-%m-%d"),
                                    "start_date_before": (now + dt.timedelta(days=a.days)).strftime("%Y-%m-%d")}):
        fixtures.extend(pg.get("data", []))
    dump(fixtures, os.path.join(RAW, "daily", f"fixtures_{stamp}.json"))
    names = {}
    unknown = set()
    for f in fixtures:
        try:
            names[f["id"]] = (canon(f.get("home_team_display")), canon(f.get("away_team_display")))
        except UnknownTeam as e:
            unknown.add(str(e))
    upcoming = [f for f in fixtures if f["id"] in names and not f.get("is_live") and (f.get("status") or "").lower() in ("unplayed", "scheduled", "not_started", "pending")]
    rows = []
    for i in range(0, len(upcoming), 5):
        chunk = upcoming[i:i + 5]
        for b0 in range(0, len(books), 5):
            bk = books[b0:b0 + 5]
            j = c.get("/fixtures/odds", [("fixture_id", f["id"]) for f in chunk] + [("sportsbook", b) for b in bk] + [("odds_format", "DECIMAL")])
            for fx in (j or {}).get("data", []):
                by_book = {}
                for o in fx.get("odds", []):
                    by_book.setdefault((o.get("sportsbook") or "").lower(), []).append(o)
                home, away = names.get(fx["id"], (None, None))
                if not home:
                    continue
                for book, odds in by_book.items():
                    r = odds_row(fx, book, odds, home, away, stamp)
                    if r:
                        rows.append(r)
    if rows:
        cur = data.load("current_round_odds")
        data.save("current_round_odds", pd.concat([cur, pd.DataFrame(rows)], ignore_index=True))
    # completed fixtures: scores
    done = [f for f in fixtures if f["id"] in names and (f.get("status") or "").lower() in ("completed", "finished", "final", "ended")]
    res_rows = []
    dd = load_config()["mls"]["decision_day"]  # a game after Decision Day is a playoff game, never a regular-season result
    for f in done:
        sc = ((f.get("result") or {}).get("scores") or {})
        hs, as_ = (sc.get("home") or {}).get("total"), (sc.get("away") or {}).get("total")
        if hs is None or as_ is None:
            continue
        home, away = names[f["id"]]
        d = et_date(parse_utc(f["start_date"]))
        res_rows.append({"date": d, "home": home, "away": away, "hg": int(hs), "ag": int(as_), "competition": "MLS" if d <= dd else "MLS Cup Playoffs", "source": "optic"})
    n_res = 0
    if res_rows:
        res = data.load("results")
        new = pd.DataFrame(res_rows)
        have = set(zip(res["date"], res["home"], res["away"]))
        new = new[[k not in have for k in zip(new["date"], new["home"], new["away"])]]
        n_res = len(new)
        if n_res:
            data.save("results", merge_results(res, new))
    # Pinnacle closes from the historical endpoint (clv field)
    n_close = 0
    if not a.no_closes:
        cl = data.load("closing_lines")
        for f in done:
            home, away = names[f["id"]]
            date = et_date(parse_utc(f["start_date"]))
            m = (cl["date"] == date) & (cl["home"] == home) & (cl["away"] == away)
            if m.any() and (cl.loc[m, "book"] == "pinnacle_close").any():
                continue
            j = c.get("/fixtures/odds/historical", [("fixture_id", f["id"]), ("sportsbook", "pinnacle")], historical=True)
            if not j or not j.get("data"):
                continue
            dump_gz(j, os.path.join(RAW, "odds_historical", "mls", "pinnacle", f"{f['id']}.json.gz"))
            fxh = j["data"][0]
            row = odds_row(fxh, "pinnacle_close", fxh.get("odds", []), home, away, stamp, phase="clv")
            if row:
                cl = cl[~m]
                cl = pd.concat([cl, pd.DataFrame([row])], ignore_index=True); n_close += 1
        if n_close:
            data.save("closing_lines", cl.sort_values(["kickoff_utc", "home"]))
    # injuries
    n_inj = ""
    j = c.get("/injuries", {"league": lid})
    if j is not None:
        dump(j, os.path.join(RAW, "injuries", today_et().strftime("%Y%m%d") + ".json"))
        site = []
        for r in j.get("data", []):
            t = canon((r.get("team") or {}).get("name"), strict=False)
            if t:
                st = str(r.get("status") or "").lower()
                site.append({"team": t, "player": (r.get("player") or {}).get("name", ""), "expected_return": "", "note": f"{r.get('status','')} {r.get('type','')}".strip(),
                             "status": "doubt" if st in ("gtd", "questionable", "doubtful", "day-to-day", "day to day") else "injury"})
        ex = data.load("injuries")
        ex, added, upd, closed = merge_injuries(ex, site, len(ex) == 0, today_et(), source="optic")
        data.save("injuries", ex)
        n_inj = f", injuries: {len(site)} listed, {added} new, {closed} closed"
    if unknown:
        print(f"fetch_optic: unknown names: {sorted(unknown)}", file=sys.stderr)
    print(f"fetch_optic: {len(rows)} book lines for {len(upcoming)} fixtures, {n_res} new results, {n_close} Pinnacle closes{n_inj}; {c.calls} calls{' (key went dark)' if c.dark else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
