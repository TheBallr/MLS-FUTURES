#!/usr/bin/env python3
"""Team xG per game from American Soccer Analysis' public API (the Statz equivalent). VERIFY endpoint shape on first run.
Writes data/ratings/xg_history.csv (date, home, away, home_xg, away_xg) and appends today's xg ratings to xg_ratings_history.csv.
Usage: python3 scripts/fetch_xg.py [--season 2026]"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import get
from sim import data
from sim.teams import canon, UnknownTeam

ASA = "https://app.americansocceranalysis.com/api/v1/mls"


def fetch_season(season: int) -> pd.DataFrame:
    teams = get(f"{ASA}/teams") or []
    tname = {t.get("team_id"): t.get("team_name") for t in teams}
    games = get(f"{ASA}/games", {"season_name": season}) or []
    gid = {g.get("game_id"): g for g in games}
    xg = get(f"{ASA}/teams/xgoals", {"season_name": season, "split_by_games": "true"}) or []
    rows = {}
    unknown = set()
    for r in xg:
        g = gid.get(r.get("game_id"))
        if not g:
            continue
        try:
            home = canon(tname.get(g.get("home_team_id"))); away = canon(tname.get(g.get("away_team_id")))
        except UnknownTeam as e:
            unknown.add(str(e)); continue
        key = r.get("game_id")
        row = rows.setdefault(key, {"date": str(g.get("date_time_utc", ""))[:10], "home": home, "away": away, "home_xg": "", "away_xg": "", "source": "asa", "game_id": key})
        team = canon(tname.get(r.get("team_id")), strict=False)
        if team == home:
            row["home_xg"] = r.get("xgoals_for")
        elif team == away:
            row["away_xg"] = r.get("xgoals_for")
    if unknown:
        print(f"fetch_xg: unknown names: {sorted(unknown)}", file=sys.stderr)
    return pd.DataFrame(list(rows.values()), columns=data.cols("xg_history"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--season", type=int, default=2026); a = ap.parse_args()
    df = fetch_season(a.season)
    if len(df) == 0:
        print("fetch_xg: nothing fetched (ASA unreachable or shape changed; see fetch_season)"); return 1
    old = data.load("xg_history")
    old = old[~old["game_id"].isin(df["game_id"])] if len(old) else old
    out = pd.concat([old, df], ignore_index=True).sort_values("date")
    data.save("xg_history", out)
    print(f"fetch_xg: {len(df)} games for {a.season}, {len(out)} on file through {out['date'].max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
