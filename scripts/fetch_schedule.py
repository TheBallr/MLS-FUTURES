#!/usr/bin/env python3
"""Season schedule from ESPN's public scoreboard feed (usa.1 = MLS). Writes data/schedule.csv with kickoff in UTC and status.
Cross-checks the league count against 30 x 34 / 2 = 510. Competition tag MLS; cup ties never enter (other feeds carry them).
Usage: python3 scripts/fetch_schedule.py [--start 2026-02-15] [--end 2026-12-20]"""
from __future__ import annotations
import argparse, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import get, parse_utc, et_date, utc_iso
from sim import data
from sim.teams import canon, UnknownTeam
from sim.knobs import load_config

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"


def fetch_range(start: dt.date, end: dt.date) -> list[dict]:
    rows, unknown = [], set()
    d = start
    while d <= end:
        # ESPN accepts a date range: dates=YYYYMMDD-YYYYMMDD (ESPN groups by its own day); step in 7-day chunks
        d2 = min(d + dt.timedelta(days=6), end)
        j = get(ESPN, {"dates": f"{d:%Y%m%d}-{d2:%Y%m%d}", "limit": 400})
        for ev in (j or {}).get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            teams = {c.get("homeAway"): c for c in comp.get("competitors", [])}
            try:
                home = canon(teams["home"]["team"]["displayName"]); away = canon(teams["away"]["team"]["displayName"])
            except (KeyError, UnknownTeam) as e:
                unknown.add(str(e)); continue
            ko = parse_utc(ev.get("date"))
            st = ((ev.get("status") or {}).get("type") or {})
            status = "final" if st.get("completed") else ("live" if st.get("state") == "in" else "scheduled")
            week = (ev.get("week") or {}).get("number") or ""
            season_type = (ev.get("season") or {}).get("type")
            comp_name = "MLS" if (season_type in (None, 2) or st) else "MLS"
            rows.append({"date": et_date(ko), "kickoff_utc": utc_iso(ko), "round": week, "home": home, "away": away,
                         "competition": "MLS Cup Playoffs" if season_type == 3 else "MLS", "status": status, "espn_id": ev.get("id"),
                         "hg": teams["home"].get("score", ""), "ag": teams["away"].get("score", "")})
        d = d2 + dt.timedelta(days=1)
    if unknown:
        print(f"fetch_schedule: unknown team names (add to sim/teams.py): {sorted(unknown)}", file=sys.stderr)
    return rows


def main():
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=(dt.date.fromisoformat(cfg["mls"]["season_start"]) - dt.timedelta(days=7)).isoformat())
    ap.add_argument("--end", default=cfg["mls"]["playoffs"]["mls_cup"])
    a = ap.parse_args()
    rows = fetch_range(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
    if not rows:
        print("fetch_schedule: nothing fetched (host unreachable?)"); return 1
    df = pd.DataFrame(rows).drop_duplicates("espn_id").sort_values(["kickoff_utc", "home"])
    old = data.load("schedule")
    data.save("schedule", df[data.cols("schedule")])
    league = df[df["competition"] == "MLS"]
    n = len(league); per = league["home"].value_counts().add(league["away"].value_counts(), fill_value=0)
    print(f"fetch_schedule: {n} MLS fixtures ({'ok' if n == cfg['mls']['league_matches'] else 'EXPECTED ' + str(cfg['mls']['league_matches'])}), "
          f"{int((league['status']=='final').sum())} final; per club min {int(per.min())} max {int(per.max())}; was {len(old)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
