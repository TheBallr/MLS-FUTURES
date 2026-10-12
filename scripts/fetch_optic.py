#!/usr/bin/env python3
"""Daily OpticOdds pull while the key lives (optional at every step; without the key it prints one line and exits 0):
 1. the coming three weeks' lines from every book into current_round_odds.csv (book id in `book`; Pinnacle rows join the guest-API ones);
 2. completed fixtures' scores into results.csv (source optic) where ESPN has not already filled them;
 3. Pinnacle's closes (book pinnacle_close) from the historical odds endpoint's clv field for fixtures finished in the last 3 days;
 4. the injury feed merged into injuries.csv (section 9 rules; tiers untouched).
Usage: OPTIC_API_KEY=... python3 scripts/fetch_optic.py [--days 21] [--books pinnacle,ps3838,betfair,bet365,draftkings,fanduel]"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.optic_client import Optic, dump
from scripts.common import now_utc, utc_iso, parse_utc, et_date, today_et
from scripts.harvest_optic import catalogues, find_leagues, RAW
from scripts.fetch_results import merge_results
from scripts.fetch_injuries import merge as merge_injuries
from sim import data
from sim.teams import canon, UnknownTeam

MONEYLINE = {"moneyline", "match result", "1x2", "full time result", "3-way moneyline", "3way"}
HANDICAP = {"asian handicap", "spread", "handicap", "goal spread"}
TOTAL = {"total goals", "total", "totals", "over/under"}


def _norm_market(m: str) -> str:
    return (m or "").strip().lower()


def main_line_from_odds(odds: list[dict]) -> dict:
    """From a fixture's odds (one book), pick period-0 three-way, main AH and main total (closest to even)."""
    row = {"h": "", "d": "", "a": "", "ah_line": "", "ah_home": "", "ah_away": "", "total_line": "", "over": "", "under": ""}
    ml = {}
    ah, tot = {}, {}
    for o in odds:
        mk = _norm_market(o.get("market"))
        sel = (o.get("normalized_selection") or o.get("selection") or "").lower()
        price = o.get("price")
        pts = o.get("points")
        if price is None:
            continue
        if mk in MONEYLINE:
            ml[sel] = price
        elif mk in HANDICAP and pts is not None:
            ah.setdefault(pts, {})[sel] = price
        elif mk in TOTAL and pts is not None:
            tot.setdefault(pts, {})[sel] = price
    return ml, ah, tot


def odds_to_row(fx: dict, book: str, ml, ah, tot, home, away, stamp) -> dict | None:
    from sim.devig import american_to_decimal
    def dec(p):
        p = float(p)
        return round(p, 4) if p >= 1.01 and p < 100 and abs(p) < 100 else round(american_to_decimal(p), 4)
    row = {"date": et_date(parse_utc(fx["start_date"])), "kickoff_utc": utc_iso(parse_utc(fx["start_date"])), "home": home, "away": away, "book": book,
           "h": "", "d": "", "a": "", "ah_line": "", "ah_home": "", "ah_away": "", "total_line": "", "over": "", "under": "", "fetched_at": stamp, "fixture_id": fx["id"]}
    hk = [k for k in ml if home.lower() in k or k in ("home", "1")]; ak = [k for k in ml if away.lower() in k or k in ("away", "2")]; dk = [k for k in ml if "draw" in k or k == "x"]
    if hk and ak and dk:
        row["h"], row["d"], row["a"] = dec(ml[hk[0]]), dec(ml[dk[0]]), dec(ml[ak[0]])
    def pick(d, side_a, side_b):
        best = None
        for pts, sides in d.items():
            ka = [k for k in sides if side_a(k)]; kb = [k for k in sides if side_b(k)]
            if not ka or not kb:
                continue
            da, db = dec(sides[ka[0]]), dec(sides[kb[0]])
            gap = abs(da - db)
            if best is None or gap < best[0]:
                best = (gap, pts, da, db, ka[0])
        return best
    sp = pick(ah, lambda k: home.lower() in k or k.startswith("home"), lambda k: away.lower() in k or k.startswith("away"))
    if sp:
        pts = float(sp[1])
        # OpticOdds points on a handicap row are the line for that selection; the home line is the home selection's points
        row["ah_line"], row["ah_home"], row["ah_away"] = pts, sp[2], sp[3]
    tl = pick(tot, lambda k: k.startswith("over"), lambda k: k.startswith("under"))
    if tl:
        row["total_line"], row["over"], row["under"] = float(tl[1]), tl[2], tl[3]
    return row if (row["h"] or row["ah_line"]) else None


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
                    ml, ah, tot = main_line_from_odds(odds)
                    r = odds_to_row(fx, book, ml, ah, tot, home, away, stamp)
                    if r:
                        rows.append(r)
    if rows:
        cur = data.load("current_round_odds")
        data.save("current_round_odds", pd.concat([cur, pd.DataFrame(rows)], ignore_index=True))
    # completed fixtures: scores
    done = [f for f in fixtures if f["id"] in names and (f.get("status") or "").lower() in ("completed", "finished", "final", "ended")]
    res_rows = []
    for f in done:
        sc = ((f.get("result") or {}).get("scores") or {})
        hs, as_ = (sc.get("home") or {}).get("total"), (sc.get("away") or {}).get("total")
        if hs is None or as_ is None:
            continue
        home, away = names[f["id"]]
        res_rows.append({"date": et_date(parse_utc(f["start_date"])), "home": home, "away": away, "hg": int(hs), "ag": int(as_), "competition": "MLS", "source": "optic"})
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
            if j is None:
                j = c.get("/fixtures/odds/history", [("fixture_id", f["id"]), ("sportsbook", "pinnacle")], historical=True)
            if not j:
                continue
            dump(j, os.path.join(RAW, "odds_historical", "mls", "pinnacle", f"{f['id']}.json"))
            row = closing_row_from_history(j, f, home, away, stamp)
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
                site.append({"team": t, "player": (r.get("player") or {}).get("name", ""), "expected_return": "", "note": f"{r.get('status','')} {r.get('type','')}".strip()})
        ex = data.load("injuries")
        ex, added, upd = merge_injuries(ex, site, len(ex) == 0, today_et())
        data.save("injuries", ex)
        n_inj = f", injuries: {len(site)} listed, {added} new"
    if unknown:
        print(f"fetch_optic: unknown names: {sorted(unknown)}", file=sys.stderr)
    print(f"fetch_optic: {len(rows)} book lines for {len(upcoming)} fixtures, {n_res} new results, {n_close} Pinnacle closes{n_inj}; {c.calls} calls{' (key went dark)' if c.dark else ''}")
    return 0


def closing_row_from_history(j, fx, home, away, stamp) -> dict | None:
    """Reduce the historical odds payload to one closing row. The feed's shape is verified on first real run; this handles
    (a) a list of odds entries each with a price history / clv object, (b) a flat list of price events with timestamps."""
    entries = j.get("data", j) if isinstance(j, dict) else j
    ml, ah, tot = {}, {}, {}
    def last_price(e):
        clv = e.get("clv") if isinstance(e, dict) else None
        if isinstance(clv, dict):
            for k in ("closing_price", "close", "price"):
                if clv.get(k) is not None:
                    return clv[k]
        hist = e.get("history") or e.get("price_history") or e.get("odds") or []
        if isinstance(hist, list) and hist:
            last = sorted(hist, key=lambda x: x.get("timestamp", 0))[-1]
            return last.get("price")
        return e.get("price")
    for e in entries if isinstance(entries, list) else []:
        if not isinstance(e, dict):
            continue
        mk = _norm_market(e.get("market")); sel = (e.get("normalized_selection") or e.get("selection") or "").lower(); pts = e.get("points")
        p = last_price(e)
        if p is None:
            continue
        if mk in MONEYLINE:
            ml[sel] = p
        elif mk in HANDICAP and pts is not None:
            ah.setdefault(pts, {})[sel] = p
        elif mk in TOTAL and pts is not None:
            tot.setdefault(pts, {})[sel] = p
    row = odds_to_row(fx, "pinnacle_close", ml, ah, tot, home, away, stamp)
    return row


if __name__ == "__main__":
    sys.exit(main())
