#!/usr/bin/env python3
"""One-off harvest of everything the OpticOdds key can reach for MLS into data/optic/ (section 4a of the build prompt).
Resumable: raw JSON already on disk is never fetched twice. Key from OPTIC_API_KEY only.

Usage: OPTIC_API_KEY=... python3 scripts/harvest_optic.py [--seasons 2019-2026] [--books pinnacle,ps3838,betfair,bet365,draftkings,fanduel]
       [--skip-history] [--max-fixtures N]
"""
from __future__ import annotations
import argparse, csv, datetime as dt, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.optic_client import Optic, dump, load_json
from sim.teams import ROOT

OUT = os.path.join(ROOT, "data", "optic")
RAW = os.path.join(OUT, "raw")
LEAGUE_HINTS = {
    "mls": ["mls", "major league soccer"],
    "leagues_cup": ["leagues cup"],
    "concacaf_champions_cup": ["concacaf champions", "champions cup"],
    "us_open_cup": ["open cup", "us open cup", "u.s. open cup"],
    "canadian_championship": ["canadian championship"],
}
DEFAULT_BOOKS = ["pinnacle", "ps3838", "betfair", "bet365", "draftkings", "fanduel"]


def log(msg):
    print(msg, flush=True)


def catalogues(c: Optic):
    """sports, leagues (soccer), sportsbooks, markets for soccer."""
    cat = {}
    for name, path, params in [("sports", "/sports", None), ("leagues", "/leagues", {"sport": "soccer"}),
                               ("sportsbooks", "/sportsbooks", None), ("markets", "/markets", {"sport": "soccer"})]:
        p = os.path.join(RAW, "catalogues", f"{name}.json")
        if os.path.exists(p):
            cat[name] = load_json(p)
        else:
            j = c.get(path, params)
            if j is not None:
                dump(j, p); cat[name] = j
    return cat


def find_leagues(leagues_json) -> dict:
    found = {}
    data = (leagues_json or {}).get("data", [])
    for lg in data:
        name = (lg.get("name") or "").lower()
        region = (lg.get("region") or "").lower()
        for key, hints in LEAGUE_HINTS.items():
            if any(h in name for h in hints):
                if key == "mls" and ("next" in name or "women" in name or "nwsl" in name):
                    continue
                if key in found:
                    continue
                found[key] = lg
    return found


def harvest_fixtures(c: Optic, league_id: str, tag: str, seasons: list[int], max_fixtures: int | None):
    """Every fixture (with scores in the fixture object when the feed carries them) per season, paged."""
    all_rows = []
    for season in seasons:
        p = os.path.join(RAW, "fixtures", f"{tag}_{season}.json")
        if os.path.exists(p):
            pages = load_json(p)
        else:
            pages = list(c.paged("/fixtures", {"league": league_id, "season_year": str(season)}))
            if not pages:
                # some leagues are not keyed by season_year; fall back to a date range
                pages = list(c.paged("/fixtures", {"league": league_id, "start_date_after": f"{season}-01-01", "start_date_before": f"{season}-12-31"}))
            if pages:
                dump(pages, p)
        n = sum(len(pg.get("data", [])) for pg in pages)
        log(f"harvest: {tag} {season}: {n} fixtures")
        for pg in pages:
            all_rows.extend(pg.get("data", []))
        if max_fixtures and len(all_rows) >= max_fixtures:
            break
    return all_rows


def harvest_results(c: Optic, fixtures: list, tag: str):
    """Scores and Opta-style team stats per completed fixture, 5 fixture ids per call."""
    done = [f for f in fixtures if (f.get("status") or "").lower() in ("completed", "finished", "final", "ended")]
    ids = [f["id"] for f in done]
    out = []
    for i in range(0, len(ids), 5):
        chunk = ids[i:i + 5]
        p = os.path.join(RAW, "results", tag, f"{chunk[0]}.json")
        if os.path.exists(p):
            j = load_json(p)
        else:
            j = c.get("/fixtures/results", [("fixture_id", x) for x in chunk])
            if j is not None:
                dump(j, p)
        if j:
            out.extend(j.get("data", []))
    log(f"harvest: {tag} results: {len(out)} of {len(ids)} completed fixtures")
    return out


def harvest_historical_odds(c: Optic, fixtures: list, tag: str, books: list[str], markets=("Moneyline", "Asian Handicap", "Total Goals")):
    """Opening and closing lines (historical odds endpoint, carries a clv field) per fixture and book. 10 req / 15 s."""
    n_ok = 0
    for f in fixtures:
        fid = f["id"]
        for book in books:
            p = os.path.join(RAW, "odds_historical", tag, book, f"{fid}.json")
            if os.path.exists(p):
                n_ok += 1
                continue
            j = c.get("/fixtures/odds/historical", [("fixture_id", fid), ("sportsbook", book)], historical=True)
            if j is None:
                j = c.get("/fixtures/odds/history", [("fixture_id", fid), ("sportsbook", book)], historical=True)
            if j is not None:
                dump(j, p); n_ok += 1
            if c.dark:
                return n_ok
    log(f"harvest: {tag} historical odds files: {n_ok}")
    return n_ok


def harvest_current_odds(c: Optic, fixtures: list, tag: str, books: list[str]):
    """Current lines for upcoming fixtures, 5 fixture ids and up to 5 books per call."""
    up = [f for f in fixtures if (f.get("status") or "").lower() in ("unplayed", "scheduled", "not_started", "pending")]
    ids = [f["id"] for f in up]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    for i in range(0, len(ids), 5):
        chunk = ids[i:i + 5]
        for b0 in range(0, len(books), 5):
            bk = books[b0:b0 + 5]
            j = c.get("/fixtures/odds", [("fixture_id", x) for x in chunk] + [("sportsbook", b) for b in bk] + [("odds_format", "DECIMAL")])
            if j is not None:
                dump(j, os.path.join(RAW, "odds_current", tag, f"{stamp}_{chunk[0]}_{b0}.json")); n += 1
    log(f"harvest: {tag} current odds calls: {n} for {len(ids)} upcoming fixtures")


def harvest_futures(c: Optic, league_id: str, books: list[str]):
    p = os.path.join(RAW, "futures", "futures_list.json")
    j = c.get("/futures", {"league": league_id})
    if j is not None:
        dump(j, p)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    for b0 in range(0, len(books), 5):
        bk = books[b0:b0 + 5]
        jj = c.get("/futures/odds", [("league", league_id), ("odds_format", "DECIMAL")] + [("sportsbook", b) for b in bk])
        if jj is not None:
            dump(jj, os.path.join(RAW, "futures", f"odds_{stamp}_{b0}.json")); n += 1
    log(f"harvest: futures: list {'ok' if j else 'none'}, odds calls {n}")


def harvest_entities(c: Optic, league_id: str):
    for name, path in [("teams", "/teams"), ("players", "/players")]:
        p = os.path.join(RAW, "catalogues", f"{name}_mls.json")
        if os.path.exists(p):
            continue
        pages = list(c.paged(path, {"league": league_id}))
        if pages:
            dump(pages, p)
            log(f"harvest: {name}: {sum(len(x.get('data', [])) for x in pages)}")
    p = os.path.join(RAW, "injuries", dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d") + ".json")
    j = c.get("/injuries", {"league": league_id})
    if j is not None:
        dump(j, p); log(f"harvest: injuries: {len(j.get('data', []))}")


def flatten_fixtures(fixtures: list, tag: str):
    rows = []
    for f in fixtures:
        res = f.get("result") or {}
        sc = (res.get("scores") or {}) if isinstance(res, dict) else {}
        rows.append({
            "competition": tag, "fixture_id": f.get("id"), "start_date": f.get("start_date"), "status": f.get("status"),
            "home": f.get("home_team_display"), "away": f.get("away_team_display"),
            "home_id": (f.get("home_competitors") or [{}])[0].get("id"), "away_id": (f.get("away_competitors") or [{}])[0].get("id"),
            "home_score": ((sc.get("home") or {}).get("total") if sc else None), "away_score": ((sc.get("away") or {}).get("total") if sc else None),
            "season_year": f.get("season_year"), "season_week": f.get("season_week"), "venue": f.get("venue_name"), "neutral": f.get("venue_neutral"),
        })
    return rows


def write_csv(rows, path, fields=None):
    if not rows:
        return
    fields = fields or list(rows[0].keys())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2018-2026")
    ap.add_argument("--books", default=",".join(DEFAULT_BOOKS))
    ap.add_argument("--skip-history", action="store_true")
    ap.add_argument("--max-fixtures", type=int, default=None)
    a = ap.parse_args()
    y0, y1 = [int(x) for x in a.seasons.split("-")]
    seasons = list(range(y0, y1 + 1))
    books = [b.strip() for b in a.books.split(",") if b.strip()]

    c = Optic()
    if not c.available:
        log("harvest: no OPTIC_API_KEY in the environment; nothing to do")
        return 0
    os.makedirs(RAW, exist_ok=True)
    t0 = time.time()
    cat = catalogues(c)
    if "leagues" not in cat:
        log("harvest: could not read /leagues (key dark or host unreachable); stopping")
        return 1
    found = find_leagues(cat["leagues"])
    log("harvest: leagues found: " + ", ".join(f"{k}={v.get('id')}" for k, v in found.items()))
    if "mls" not in found:
        log("harvest: MLS league id not found in catalogue; see data/optic/raw/catalogues/leagues.json")
        return 1
    manifest = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "leagues": {k: v.get("id") for k, v in found.items()}, "books": books, "seasons": seasons}
    harvest_entities(c, found["mls"]["id"])
    all_fx = {}
    for key, lg in found.items():
        fx = harvest_fixtures(c, lg["id"], key, seasons, a.max_fixtures)
        all_fx[key] = fx
        write_csv(flatten_fixtures(fx, key), os.path.join(OUT, f"fixtures_{key}.csv"))
        harvest_results(c, fx, key)
        if c.dark:
            break
    if not c.dark:
        harvest_futures(c, found["mls"]["id"], books)
        harvest_current_odds(c, all_fx.get("mls", []), "mls", books)
    if not a.skip_history and not c.dark:
        mls_done = [f for f in all_fx.get("mls", []) if (f.get("status") or "").lower() in ("completed", "finished", "final", "ended")]
        mls_done.sort(key=lambda f: f.get("start_date") or "", reverse=True)
        log(f"harvest: historical odds for {len(mls_done)} completed MLS fixtures x {len(books)} books at 10 req/15s (~{len(mls_done)*len(books)*1.5/60:.0f} min)")
        harvest_historical_odds(c, mls_done, "mls", ["pinnacle"])      # Pinnacle first: the calibration set
        harvest_historical_odds(c, mls_done, "mls", [b for b in books if b != "pinnacle"])
        for key in ("leagues_cup", "concacaf_champions_cup", "us_open_cup"):
            if key in all_fx:
                done = [f for f in all_fx[key] if (f.get("status") or "").lower() in ("completed", "finished", "final", "ended")]
                harvest_historical_odds(c, done, key, ["pinnacle"])
    manifest.update(finished_utc=dt.datetime.now(dt.timezone.utc).isoformat(), calls=c.calls, key_dark=c.dark, seconds=round(time.time() - t0))
    dump(manifest, os.path.join(OUT, "manifest.json"))
    log(f"harvest: done, {c.calls} calls in {time.time()-t0:.0f}s, key_dark={c.dark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
