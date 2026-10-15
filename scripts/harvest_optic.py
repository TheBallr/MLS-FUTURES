#!/usr/bin/env python3
"""One-off harvest of everything the OpticOdds key reaches for MLS into data/optic/ (build prompt section 4a). Verified against the
live v3 feed on 2026-10-12: fixtures page by `page` with `has_more`; the feed holds MLS seasons 2024-2026; the historical odds
endpoint returns every market's opening (olv) and closing (clv) price and points per odd. Raw JSON is stored gzipped.
Resumable: anything already on disk is never fetched twice. Key from OPTIC_API_KEY only.

Usage: OPTIC_API_KEY=... python3 scripts/harvest_optic.py [--seasons 2024-2026] [--books pinnacle,ps3838,betfair,bet365,draftkings,fanduel]
       [--stage all|catalogue|fixtures|results|futures|current|pinnacle|books|cups] [--max-fixtures N]
"""
from __future__ import annotations
import argparse, csv, datetime as dt, gzip, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.optic_client import Optic, dump, load_json
from sim.teams import ROOT

OUT = os.path.join(ROOT, "data", "optic")
RAW = os.path.join(OUT, "raw")
LEAGUE_HINTS = {
    "mls": ["major league soccer"],
    "leagues_cup": ["leagues cup"],
    "concacaf_champions_cup": ["concacaf - champions cup"],
    "us_open_cup": ["usa - open cup"],
    "canadian_championship": ["canadian championship", "canada - championship"],
}
DEFAULT_BOOKS = ["pinnacle", "ps3838", "betfair", "bet365", "draftkings", "fanduel"]
DONE = {"completed", "finished", "final", "ended"}
UPCOMING = {"unplayed", "scheduled", "not_started", "pending"}


def log(msg):
    print(msg, flush=True)


def dump_gz(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f)


def load_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def catalogues(c: Optic):
    cat = {}
    for name, path, params in [("sports", "/sports", None), ("leagues", "/leagues", {"sport": "soccer"}),
                               ("sportsbooks", "/sportsbooks", None), ("markets", "/markets", {"sport": "soccer", "league": "usa_-_major_league_soccer"})]:
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
    for lg in (leagues_json or {}).get("data", []):
        name = (lg.get("name") or "").lower()
        for key, hints in LEAGUE_HINTS.items():
            if key not in found and any(h in name for h in hints) and "women" not in name and "next" not in name:
                found[key] = lg
    return found


def fixtures_for(c: Optic, league_id: str, tag: str, seasons: list[int]) -> list:
    rows = []
    for season in seasons:
        p = os.path.join(RAW, "fixtures", f"{tag}_{season}.json.gz")
        if os.path.exists(p):
            pages = load_gz(p)
        else:
            pages = list(c.paged("/fixtures", {"league": league_id, "season_year": str(season)}))
            if not pages:
                pages = list(c.paged("/fixtures", {"league": league_id, "start_date_after": f"{season}-01-01", "start_date_before": f"{season}-12-31"}))
            if pages:
                dump_gz(pages, p)
        n = sum(len(pg.get("data", [])) for pg in pages)
        if n:
            log(f"harvest: {tag} {season}: {n} fixtures")
        for pg in pages:
            rows.extend(pg.get("data", []))
    return rows


def harvest_results(c: Optic, fixtures: list, tag: str):
    ids = [f["id"] for f in fixtures if (f.get("status") or "").lower() in DONE]
    n = 0
    for i in range(0, len(ids), 5):
        chunk = ids[i:i + 5]
        p = os.path.join(RAW, "results", tag, f"{chunk[0]}.json.gz")
        if os.path.exists(p):
            n += 1; continue
        j = c.get("/fixtures/results", [("fixture_id", x) for x in chunk])
        if j is not None:
            dump_gz(j, p); n += 1
        if c.dark:
            break
    log(f"harvest: {tag} results: {n} files for {len(ids)} completed fixtures")


def harvest_historical(c: Optic, fixtures: list, tag: str, books: list[str], label: str):
    todo = [(f["id"], b) for f in fixtures for b in books if not os.path.exists(os.path.join(RAW, "odds_historical", tag, b, f"{f['id']}.json.gz"))]
    log(f"harvest: {label}: {len(todo)} fixture-book files to fetch (~{len(todo)*1.5/60:.0f} min at 10 req / 15 s)")
    n = 0; t0 = time.time()
    for fid, b in todo:
        j = c.get("/fixtures/odds/historical", [("fixture_id", fid), ("sportsbook", b)], historical=True)
        if j is not None:
            dump_gz(j, os.path.join(RAW, "odds_historical", tag, b, f"{fid}.json.gz")); n += 1
        if c.dark:
            log("harvest: key went dark; stopping"); return n
        if n and n % 200 == 0:
            log(f"harvest: {label}: {n}/{len(todo)} ({(time.time()-t0)/60:.0f} min)")
    log(f"harvest: {label}: {n} fetched")
    return n


def harvest_current(c: Optic, fixtures: list, tag: str, books: list[str]):
    ids = [f["id"] for f in fixtures if (f.get("status") or "").lower() in UPCOMING]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    for i in range(0, len(ids), 5):
        chunk = ids[i:i + 5]
        for b0 in range(0, len(books), 5):
            bk = books[b0:b0 + 5]
            j = c.get("/fixtures/odds", [("fixture_id", x) for x in chunk] + [("sportsbook", b) for b in bk] + [("odds_format", "DECIMAL")])
            if j is not None:
                dump_gz(j, os.path.join(RAW, "odds_current", tag, f"{stamp}_{chunk[0]}_{b0}.json.gz")); n += 1
    log(f"harvest: {tag} current odds: {n} calls for {len(ids)} upcoming fixtures")


def harvest_futures(c: Optic, league_id: str, books: list[str]):
    j = c.get("/futures", {"league": league_id})
    if j is not None:
        dump(j, os.path.join(RAW, "futures", "futures_list.json"))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    for b0 in range(0, len(books), 5):
        bk = books[b0:b0 + 5]
        jj = c.get("/futures/odds", [("league", league_id), ("odds_format", "DECIMAL")] + [("sportsbook", b) for b in bk])
        if jj is not None:
            dump(jj, os.path.join(RAW, "futures", f"odds_{stamp}_{b0}.json")); n += 1
    log(f"harvest: futures: {'list ok' if j else 'no list'}, {n} odds calls")


def harvest_entities(c: Optic, league_id: str):
    for name, path in [("teams", "/teams"), ("players", "/players")]:
        p = os.path.join(RAW, "catalogues", f"{name}_mls.json.gz")
        if os.path.exists(p):
            continue
        pages = list(c.paged(path, {"league": league_id}))
        if pages:
            dump_gz(pages, p); log(f"harvest: {name}: {sum(len(x.get('data', [])) for x in pages)}")
    j = c.get("/injuries", {"league": league_id})
    if j is not None:
        dump(j, os.path.join(RAW, "injuries", dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d") + ".json")); log(f"harvest: injuries: {len(j.get('data', []))}")


def flatten_fixtures(fixtures: list, tag: str):
    rows = []
    for f in fixtures:
        sc = ((f.get("result") or {}).get("scores") or {}) if isinstance(f.get("result"), dict) else {}
        rows.append({"competition": tag, "fixture_id": f.get("id"), "start_date": f.get("start_date"), "status": f.get("status"),
                     "home": f.get("home_team_display"), "away": f.get("away_team_display"),
                     "home_id": (f.get("home_competitors") or [{}])[0].get("id"), "away_id": (f.get("away_competitors") or [{}])[0].get("id"),
                     "home_score": (sc.get("home") or {}).get("total") if sc else None, "away_score": (sc.get("away") or {}).get("total") if sc else None,
                     "season_year": f.get("season_year"), "season_week": f.get("season_week"), "season_type": f.get("season_type"), "venue": f.get("venue_name"), "neutral": f.get("venue_neutral")})
    return rows


def write_csv(rows, path):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2024-2026")
    ap.add_argument("--books", default=",".join(DEFAULT_BOOKS))
    ap.add_argument("--stage", default="all")
    ap.add_argument("--max-fixtures", type=int, default=None)
    a = ap.parse_args()
    y0, y1 = [int(x) for x in a.seasons.split("-")]; seasons = list(range(y0, y1 + 1))
    books = [b.strip() for b in a.books.split(",") if b.strip()]
    c = Optic()
    if not c.available:
        log("harvest: no OPTIC_API_KEY in the environment; nothing to do"); return 0
    t0 = time.time()
    cat = catalogues(c)
    found = find_leagues(cat.get("leagues"))
    log("harvest: leagues: " + ", ".join(f"{k}={v.get('id')}" for k, v in found.items()))
    if "mls" not in found:
        log("harvest: MLS not found in the league catalogue"); return 1
    mls = found["mls"]["id"]
    st = a.stage
    if st in ("all", "catalogue"):
        harvest_entities(c, mls)
    all_fx = {}
    for key, lg in found.items():
        fx = fixtures_for(c, lg["id"], key, seasons)
        if a.max_fixtures:
            fx = fx[: a.max_fixtures]
        all_fx[key] = fx
        write_csv(flatten_fixtures(fx, key), os.path.join(OUT, f"fixtures_{key}.csv"))
    if st in ("all", "results"):
        for key, fx in all_fx.items():
            harvest_results(c, fx, key)
    if st in ("all", "futures"):
        harvest_futures(c, mls, books)
    if st in ("all", "current"):
        harvest_current(c, all_fx["mls"], "mls", books)
    mls_done = sorted([f for f in all_fx["mls"] if (f.get("status") or "").lower() in DONE], key=lambda f: f.get("start_date") or "", reverse=True)
    if st in ("all", "pinnacle"):
        harvest_historical(c, mls_done, "mls", ["pinnacle"], "MLS Pinnacle history")
    if st in ("all", "books"):
        harvest_historical(c, mls_done, "mls", [b for b in books if b != "pinnacle"], "MLS other books")
    if st in ("all", "cups"):
        for key in ("leagues_cup", "concacaf_champions_cup", "us_open_cup", "canadian_championship"):
            if key in all_fx:
                done = [f for f in all_fx[key] if (f.get("status") or "").lower() in DONE]
                harvest_historical(c, done, key, ["pinnacle"], f"{key} Pinnacle history")
    manifest = {"finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "stage": st, "leagues": {k: v.get("id") for k, v in found.items()}, "books": books, "seasons": seasons,
                "fixtures": {k: len(v) for k, v in all_fx.items()}, "calls": c.calls, "key_dark": c.dark, "seconds": round(time.time() - t0)}
    dump(manifest, os.path.join(OUT, f"manifest_{st}.json"))
    log(f"harvest: stage {st} done, {c.calls} calls in {(time.time()-t0)/60:.1f} min, key_dark={c.dark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
