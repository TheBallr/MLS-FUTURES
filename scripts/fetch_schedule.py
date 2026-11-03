#!/usr/bin/env python3
"""Season schedule from ESPN's public scoreboard feed (usa.1 = MLS). Writes data/schedule.csv with kickoff in UTC and status.
Cross-checks the league count against 30 x 34 / 2 = 510. Competition tag MLS; cup ties never enter (other feeds carry them).
Usage: python3 scripts/fetch_schedule.py [--start 2026-02-15] [--end 2026-12-20]"""
from __future__ import annotations
import argparse, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import parse_utc, et_date, utc_iso, session
from sim import data
from sim.teams import canon, UnknownTeam
from sim.knobs import load_config

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"
LOGOS = {}
FAILED_DAYS = []  # days whose request failed in the last fetch_range call (callers decide whether that is fatal)
RETRIES = 3       # requests per day before it counts as failed (2026-11-03)
LOGOS_CSV = os.path.join(os.path.dirname(data.DATA), "data", "logos.csv")


def fetch_range(start: dt.date, end: dt.date) -> list[dict]:
    """One request per day (ESPN's soccer scoreboard rejects date ranges with 400)."""
    rows, unknown = [], set()
    FAILED_DAYS.clear()
    s = session()
    d = start
    while d <= end:
        j = None
        for attempt in range(RETRIES):
            try:
                r = s.get(ESPN, params={"dates": f"{d:%Y%m%d}"}, timeout=30)
                j = r.json() if r.status_code == 200 else None
            except Exception:
                j = None
            if j is not None:
                break
            import time; time.sleep(2 * (attempt + 1))
        if j is None:
            FAILED_DAYS.append(d.isoformat()); j = {}
        for ev in (j or {}).get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            teams = {c.get("homeAway"): c for c in comp.get("competitors", [])}
            try:
                home = canon(teams["home"]["team"]["displayName"]); away = canon(teams["away"]["team"]["displayName"])
            except (KeyError, UnknownTeam) as e:
                unknown.add(str(e)); continue
            ko = parse_utc(ev.get("date"))
            st = ((ev.get("status") or {}).get("type") or {})
            sname = str(st.get("name") or "").upper()
            status = "final" if st.get("completed") else ("live" if st.get("state") == "in" else ("canceled" if "CANCEL" in sname else ("postponed" if "POSTPONE" in sname else "scheduled")))   # an unneeded Round One game 3 is STATUS_CANCELED on the feed (2026-11-03)
            week = (ev.get("week") or {}).get("number") or ""
            slug = ((ev.get("season") or {}).get("slug") or "regular-season").lower()
            comp_name = "MLS" if "regular" in slug else "MLS Cup Playoffs"
            for side in ("home", "away"):
                tm = teams[side]["team"]
                if tm.get("logo"):
                    LOGOS[canon(tm["displayName"])] = tm["logo"]
            rows.append({"date": et_date(ko), "kickoff_utc": utc_iso(ko), "round": week, "home": home, "away": away,
                         "competition": comp_name, "status": status, "espn_id": ev.get("id"),
                         "hg": teams["home"].get("score", ""), "ag": teams["away"].get("score", ""),
                         "winner": home if teams["home"].get("winner") else (away if teams["away"].get("winner") else "")})
        d = d + dt.timedelta(days=1)
    if unknown:
        print(f"fetch_schedule: unknown team names (add to sim/teams.py): {sorted(unknown)}", file=sys.stderr)
    return rows


def main():
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=(dt.date.fromisoformat(cfg["mls"]["season_start"]) - dt.timedelta(days=7)).isoformat())
    ap.add_argument("--end", default=cfg["mls"]["playoffs"]["mls_cup"])
    ap.add_argument("--playoffs", action="store_true", help="the playoff window only (the day after Decision Day to MLS Cup + 3 days): replaces the playoff rows, keeps the league rows as they are")
    a = ap.parse_args()
    old = data.load("schedule")
    if a.playoffs:   # the daily post-Decision-Day fetch (playoff readiness 2026-11-03, proposal 3): about 45 requests, with retries, and the league rows untouched
        start = dt.date.fromisoformat(cfg["mls"]["decision_day"]) + dt.timedelta(days=1); end = dt.date.fromisoformat(cfg["mls"]["playoffs"]["mls_cup"]) + dt.timedelta(days=3)
        rows = fetch_range(start, end)
        if FAILED_DAYS:
            print(f"fetch_schedule --playoffs: NOT saved: {len(FAILED_DAYS)} day(s) failed ({', '.join(FAILED_DAYS[:5])})"); return 1
        new = pd.DataFrame(rows, columns=list(old.columns) + [c for c in (pd.DataFrame(rows).columns if rows else []) if c not in old.columns]) if rows else pd.DataFrame(columns=old.columns)
        new = new[new["competition"] != "MLS"] if len(new) else new
        keep = old[~((old["competition"] != "MLS") & (old["date"] >= start.isoformat()))] if len(old) else old
        df = pd.concat([keep, new[data.cols("schedule")] if len(new) else new], ignore_index=True).drop_duplicates("espn_id", keep="last").sort_values(["kickoff_utc", "home"])
        data.save("schedule", df[data.cols("schedule")])
        po = df[df["competition"] != "MLS"]
        print(f"fetch_schedule --playoffs: {len(new)} playoff fixtures on the feed ({int((new['status'] == 'final').sum()) if len(new) else 0} final, {int(new['status'].isin(['canceled', 'postponed']).sum()) if len(new) else 0} cancelled/postponed); {len(po)} playoff rows on file; league rows untouched")
        return 0
    rows = fetch_range(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
    if not rows:
        print("fetch_schedule: nothing fetched (host unreachable?)"); return 1
    df = pd.DataFrame(rows).drop_duplicates("espn_id").sort_values(["kickoff_utc", "home"])
    n_old = int((old["competition"] == "MLS").sum()) if len(old) else 0
    if FAILED_DAYS or int((df["competition"] == "MLS").sum()) < n_old:  # a partial fetch would delete fixtures from the sim
        print(f"fetch_schedule: NOT saved: {len(FAILED_DAYS)} days failed, {int((df['competition'] == 'MLS').sum())} MLS fixtures v {n_old} on file"); return 1
    data.save("schedule", df[data.cols("schedule")])
    if LOGOS:
        pd.DataFrame(sorted(LOGOS.items()), columns=["team", "logo"]).to_csv(LOGOS_CSV, index=False)
    # every final score on the schedule feed goes into results.csv (ESPN source)
    fin = df[(df["status"] == "final") & (df["competition"] == "MLS") & (df["hg"] != "") & (df["ag"] != "")]
    res = data.merge_results(data.load("results"), pd.DataFrame({"date": fin["date"], "home": fin["home"], "away": fin["away"], "hg": fin["hg"], "ag": fin["ag"], "competition": "MLS", "source": "espn"}))
    data.save("results", res)
    league = df[df["competition"] == "MLS"]
    n = len(league); per = league["home"].value_counts().add(league["away"].value_counts(), fill_value=0)
    print(f"fetch_schedule: {n} MLS fixtures ({'ok' if n == cfg['mls']['league_matches'] else 'EXPECTED ' + str(cfg['mls']['league_matches'])}), "
          f"{int((league['status']=='final').sum())} final; per club min {int(per.min())} max {int(per.max())}; was {len(old)} rows; results.csv {len(res)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
