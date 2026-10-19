#!/usr/bin/env python3
"""Public rating sources (ratings session step one). Each subcommand fetches live and flattens to data/public/<source>/,
keeping the raw payloads under data/public/<source>/raw/. No sportsbook touches this file.

  opta     Opta Power Rankings (Stats Perform) daily snapshots: performfeeds JSON with a theanalyst.com Referer (anonymous
           wp-json proxy as fallback). rankDt=YYYY-MM-DD gives the ratings as of that morning (matches through the day before).
           -> data/public/opta/snapshots.csv (date, team, rating, rank, season, tmcl)
  gplus    American Soccer Analysis goals added by team and game, rebuilt from the player and goalkeeper by-game rows (the
           team by-game endpoint returns 500) -> data/public/asa_gplus/team_games.csv (date, home, away, home_gplus, away_gplus, game_id)
  fdb      footballdatabase.com club rating histories (Elo-style, monthly points) -> data/public/footballdatabase/history.csv

Usage: python3 scripts/fetch_public.py opta --dates 2023-06-01,2024-06-01 [--latest]
       python3 scripts/fetch_public.py gplus --seasons 2013-2026
       python3 scripts/fetch_public.py fdb
(ClubElo was removed 2026-10-19: CLAUDE.md 11b found it unusable for MLS and nothing read it.)"""
from __future__ import annotations
import argparse, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import session
from sim.teams import canon, UnknownTeam, ROOT, teams

PUB = os.path.join(ROOT, "data", "public")
S = session()
S.headers.update({"Accept": "application/json, text/html;q=0.9, */*;q=0.8"})


def _raw(source: str, name: str, text: str):
    d = os.path.join(PUB, source, "raw"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        f.write(text)


def _get(url, params=None, headers=None, retries=3, timeout=60):
    last = None
    for i in range(retries):
        try:
            r = S.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r
            last = r.status_code
            if r.status_code in (403, 404):
                return r
        except Exception as e:
            last = str(e)[:100]
        time.sleep(2 * (i + 1))
    print(f"fetch_public: {url.split('?')[0]} failed ({last})", file=sys.stderr)
    return None


def _canon(name: str) -> str | None:
    try:
        return canon(name, historical=True)
    except UnknownTeam:
        return None


# ---------------- Opta ----------------
OPTA_KEY = "1mjq6w6ezkxe611ykkj8rgz7f1"
OPTA_COMP = "287tckirbfj9nb8ar2k9r60vn"
OPTA_PF = f"https://api.performfeeds.com/soccerdata/seasonpowerrankings/{OPTA_KEY}"
OPTA_WP = "https://theanalyst.com/wp-json/sdapi/v1/soccerdata/seasonpowerrankings"
OPTA_CAL = f"https://api.performfeeds.com/soccerdata/tournamentcalendar/{OPTA_KEY}"
OPTA_HDR = {"Referer": "https://theanalyst.com/", "Origin": "https://theanalyst.com"}


def opta_calendar() -> dict:
    """season name -> tmcl id (cached in data/public/opta/tournament_calendar.json)."""
    p = os.path.join(PUB, "opta", "tournament_calendar.json")
    if os.path.exists(p):
        cal = json.load(open(p))
    else:
        r = _get(OPTA_CAL, {"comp": OPTA_COMP, "_fmt": "json", "_rt": "c"}, OPTA_HDR)
        if r is None or r.status_code != 200:
            raise SystemExit("opta: tournament calendar unavailable")
        cal = r.json(); os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(cal, open(p, "w"))
    out = {}
    for c in cal.get("competition", []):
        for t in c.get("tournamentCalendar", []):
            out[str(t["name"])] = {"tmcl": t["id"], "start": t.get("startDate", "")[:10], "end": t.get("endDate", "")[:10]}
    return out


def opta_snapshot(tmcl: str, date: str | None) -> list[dict] | None:
    params = {"tmcl": tmcl, "rank": "1TO100", "_fmt": "json", "_rt": "c"}
    if date:
        params["rankDt"] = date
    r = _get(OPTA_PF, params, OPTA_HDR)
    d = None
    if r is not None and r.status_code == 200:
        try:
            d = r.json()
        except Exception:
            d = None
    if not d or "division" not in d:
        r2 = _get(OPTA_WP, {"tmcl": tmcl, **({"rankDt": date} if date else {})})
        try:
            d = r2.json() if r2 is not None and r2.status_code == 200 else None
        except Exception:
            d = None
    if not d or "division" not in d:
        return None
    _raw("opta", f"{tmcl}_{date or 'latest'}.json", json.dumps(d))
    rows = []
    for div in d["division"]:
        for x in div.get("ranking", []):
            team = _canon(x.get("contestantClubName") or "") or _canon(x.get("contestantName") or "") or _canon(x.get("contestantShortName") or "")
            if team is None:
                print(f"opta: unknown team {x.get('contestantClubName')!r} / {x.get('contestantName')!r}", file=sys.stderr); continue
            rows.append({"date": (date or str(d.get("lastUpdated", ""))[:10]), "team": team, "rating": float(x["currentRating"]), "rank": int(x.get("rank", 0)),
                         "tmcl": tmcl, "last_updated": d.get("lastUpdated", "")})
    return rows


def cmd_opta(a):
    cal = opta_calendar()
    p = os.path.join(PUB, "opta", "snapshots.csv")
    old = pd.read_csv(p, dtype=str) if os.path.exists(p) else pd.DataFrame(columns=["date", "team", "rating", "rank", "season", "tmcl", "last_updated"])
    have = set(zip(old["season"], old["date"])) if len(old) else set()
    new = []
    dates = [x for x in (a.dates or "").split(",") if x]
    for d in dates:
        season = d[:4]
        if season not in cal:
            print(f"opta: no tournament calendar for {season}", file=sys.stderr); continue
        if (season, d) in have and not a.force:
            continue
        rows = opta_snapshot(cal[season]["tmcl"], d)
        if rows is None:
            print(f"opta: no data for {d}", file=sys.stderr); continue
        for r in rows:
            r["season"] = season
        new += rows; time.sleep(0.6)
    if a.latest:
        season = str(max(int(s) for s in cal if s.isdigit() and int(s) <= 2100 and cal[s]["start"]))
        rows = opta_snapshot(cal[season]["tmcl"], None)
        if rows:
            for r in rows:
                r["season"] = season
            new += rows
    if new:
        df = pd.concat([old, pd.DataFrame(new)], ignore_index=True)
        df = df.drop_duplicates(["season", "date", "team"], keep="last").sort_values(["date", "rank"])
        os.makedirs(os.path.dirname(p), exist_ok=True); df.to_csv(p, index=False)
    print(f"opta: {len(new)} rows added, {len(dates)} dates asked")
    return 0


# ---------------- ASA goals added ----------------
ASA = "https://app.americansocceranalysis.com/api/v1/mls"


def asa_pages(path: str, params: dict, limit=10000) -> list:
    out = []; off = 0
    while True:
        r = _get(f"{ASA}/{path}", {**params, "limit": limit, "offset": off})
        if r is None or r.status_code != 200:
            break
        try:
            chunk = r.json()
        except Exception:
            break
        if not isinstance(chunk, list):
            print(f"asa {path}: {str(chunk)[:120]}", file=sys.stderr); break
        out += chunk
        if len(chunk) < limit:
            break
        off += limit; time.sleep(0.5)
    return out


def cmd_gplus(a):
    lo, hi = [int(x) for x in a.seasons.split("-")] if "-" in a.seasons else (int(a.seasons), int(a.seasons))
    tr = _get(f"{ASA}/teams"); tname = {t["team_id"]: t["team_name"] for t in tr.json()} if tr is not None and tr.status_code == 200 else {}
    p = os.path.join(PUB, "asa_gplus", "team_games.csv")
    old = pd.read_csv(p, dtype=str) if os.path.exists(p) else pd.DataFrame(columns=["date", "home", "away", "home_gplus", "away_gplus", "home_gplus_gk", "away_gplus_gk", "game_id", "season"])
    frames = [old[~old["season"].astype(str).isin([str(y) for y in range(lo, hi + 1)])]] if len(old) else []
    for y in range(lo, hi + 1):
        games = asa_pages("games", {"season_name": y}, limit=1000)
        gid = {g["game_id"]: g for g in games}
        pl = asa_pages("players/goals-added", {"season_name": y, "split_by_games": "true"})
        gk = asa_pages("goalkeepers/goals-added", {"season_name": y, "split_by_games": "true"})
        _raw("asa_gplus", f"players_{y}.json", json.dumps(pl)); _raw("asa_gplus", f"goalkeepers_{y}.json", json.dumps(gk))
        tot = {}; totgk = {}
        for r in pl:
            v = sum(float(x.get("goals_added_raw") or 0) for x in r.get("data", []))
            tot[(r["game_id"], r["team_id"])] = tot.get((r["game_id"], r["team_id"]), 0.0) + v
        for r in gk:
            v = sum(float(x.get("goals_added_raw") or 0) for x in r.get("data", []))
            totgk[(r["game_id"], r["team_id"])] = totgk.get((r["game_id"], r["team_id"]), 0.0) + v
        rows = []; unknown = set()
        for g in games:
            h, aw = _canon(tname.get(g.get("home_team_id"), "")), _canon(tname.get(g.get("away_team_id"), ""))
            if h is None or aw is None:
                unknown.add(tname.get(g.get("home_team_id")) if h is None else tname.get(g.get("away_team_id"))); continue
            k_h, k_a = (g["game_id"], g["home_team_id"]), (g["game_id"], g["away_team_id"])
            if k_h not in tot and k_a not in tot:
                continue
            rows.append({"date": str(g.get("date_time_utc", ""))[:10], "home": h, "away": aw, "home_gplus": round(tot.get(k_h, 0.0) + totgk.get(k_h, 0.0), 4),
                         "away_gplus": round(tot.get(k_a, 0.0) + totgk.get(k_a, 0.0), 4), "home_gplus_gk": round(totgk.get(k_h, 0.0), 4), "away_gplus_gk": round(totgk.get(k_a, 0.0), 4),
                         "game_id": g["game_id"], "season": y})
        if unknown:
            print(f"gplus {y}: unknown names {sorted(x for x in unknown if x)}", file=sys.stderr)
        print(f"gplus {y}: {len(games)} games, {len(pl)} player rows, {len(gk)} gk rows, {len(rows)} team-games")
        frames.append(pd.DataFrame(rows)); time.sleep(1.0)
    df = pd.concat(frames, ignore_index=True).sort_values(["date", "home"])
    os.makedirs(os.path.dirname(p), exist_ok=True); df.to_csv(p, index=False)
    print(f"gplus: {len(df)} team-games on file")
    return 0


# ---------------- footballdatabase ----------------
FDB = "https://footballdatabase.com"
HTML_HDR = {"Accept": "text/html,application/xhtml+xml"}


def fdb_slugs() -> dict:
    """slug -> canonical team, from the US and Canada ranking pages (two pages each) plus known slugs."""
    out = {}
    for country in ("united-states", "canada"):
        for page in (1, 2):
            r = _get(f"{FDB}/ranking/{country}/{page}", headers=HTML_HDR)
            if r is None or r.status_code != 200:
                continue
            _raw("footballdatabase", f"ranking_{country}_{page}.html", r.text)
            for slug, title in re.findall(r'clubs-ranking/([a-z0-9-]+)"\s+title="([^"]+)"', r.text):
                t = _canon(re.sub(r"\s*\(.*?\)\s*$", "", title.strip()))
                if t:
                    out[slug] = t
            time.sleep(0.8)
    for slug, t in {"inter-miami": "Inter Miami", "los-angeles-fc": "LAFC", "st-louis-city": "St. Louis City", "austin-fc": "Austin FC", "charlotte-fc": "Charlotte FC",
                    "san-diego-fc": "San Diego FC", "cf-montreal": "CF Montréal", "toronto-fc": "Toronto FC", "vancouver-whitecaps": "Vancouver Whitecaps", "chivas-usa": "Chivas USA"}.items():
        out.setdefault(slug, t)
    return out


def cmd_fdb(a):
    slugs = fdb_slugs()
    rows = []; missing = []
    for slug, team in sorted(slugs.items()):
        r = _get(f"{FDB}/clubs-ranking/{slug}", headers=HTML_HDR)
        if r is None or r.status_code != 200:
            missing.append(slug); continue
        _raw("footballdatabase", f"club_{slug}.html", r.text)
        pts = re.findall(r"Date:\s*new Date\('(\d{4}-\d{2}-\d{2})'\),\s*Points:\s*(\d+),\s*Ranking:\s*(\d+)", r.text)
        for d, p_, rk in pts:
            rows.append({"date": d, "team": team, "points": int(p_), "ranking": int(rk), "slug": slug})
        time.sleep(0.8)
    df = pd.DataFrame(rows).drop_duplicates(["date", "team"]).sort_values(["date", "team"])
    p = os.path.join(PUB, "footballdatabase", "history.csv"); os.makedirs(os.path.dirname(p), exist_ok=True); df.to_csv(p, index=False)
    have = sorted(set(df["team"])); want = set(teams())
    print(f"fdb: {len(df)} monthly rows for {len(have)} clubs; missing current clubs: {sorted(want - set(have))}; failed slugs: {missing}")
    return 0


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("opta"); o.add_argument("--dates", default=""); o.add_argument("--latest", action="store_true"); o.add_argument("--force", action="store_true"); o.set_defaults(fn=cmd_opta)
    g = sub.add_parser("gplus"); g.add_argument("--seasons", default="2013-2026"); g.set_defaults(fn=cmd_gplus)
    f = sub.add_parser("fdb"); f.set_defaults(fn=cmd_fdb)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
