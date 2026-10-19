#!/usr/bin/env python3
"""Team xG per game from American Soccer Analysis' public API. Writes data/ratings/xg_history.csv (date, home, away, home_xg,
away_xg, source, game_id), one row per ASA game_id, dated by the kickoff's ET date like every other file (ASA gives UTC, so a
late kickoff would otherwise land a day later and miss the next morning's run). --redate fixes rows already on file offline.
Usage: python3 scripts/fetch_xg.py [--season 2026] [--redate]"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import get, et_date
from sim import data
from sim.teams import canon, UnknownTeam

ASA = "https://app.americansocceranalysis.com/api/v1/mls"


def et_day(utc) -> str:
    try:
        return et_date(pd.Timestamp(str(utc)).tz_localize("UTC") if pd.Timestamp(str(utc)).tzinfo is None else pd.Timestamp(str(utc)))
    except (ValueError, TypeError):
        return str(utc or "")[:10]


def redate(xg: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Rows written before 2026-10-19 carry ASA's UTC date. Move a row back one day when the pairing was played the day before
    (ET) and not on the row's date, using every match on file (results.csv and data/history)."""
    res = data.load("results"); hist = data.load_history()
    played = set(zip(res["date"], res["home"], res["away"])) | set(zip(hist["date"], hist["home"], hist["away"]))
    prev = (pd.to_datetime(xg["date"]) - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    move = [(d, h, a) not in played and (p, h, a) in played for d, p, h, a in zip(xg["date"], prev, xg["home"], xg["away"])]
    out = xg.copy(); out.loc[move, "date"] = prev[move]
    return out, int(sum(move))


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
            home = canon(tname.get(g.get("home_team_id")), historical=True); away = canon(tname.get(g.get("away_team_id")), historical=True)
        except UnknownTeam as e:
            unknown.add(str(e)); continue
        key = r.get("game_id")
        row = rows.setdefault(key, {"date": et_day(g.get("date_time_utc")), "home": home, "away": away, "home_xg": "", "away_xg": "", "source": "asa", "game_id": key})
        team = canon(tname.get(r.get("team_id")), strict=False, historical=True)
        if team == home:
            row["home_xg"] = r.get("xgoals_for")
        elif team == away:
            row["away_xg"] = r.get("xgoals_for")
    if unknown:
        print(f"fetch_xg: unknown names: {sorted(unknown)}", file=sys.stderr)
    return pd.DataFrame(list(rows.values()), columns=data.cols("xg_history"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--season", type=int, default=2026); ap.add_argument("--redate", action="store_true"); a = ap.parse_args()
    if a.redate:
        out, n = redate(data.load("xg_history"))
        data.save("xg_history", out.sort_values(["date", "home", "away"], kind="stable"))
        print(f"fetch_xg: re-dated {n} rows from UTC to ET"); return 0
    df = fetch_season(a.season)
    if len(df) == 0:
        print("fetch_xg: nothing fetched (ASA unreachable or shape changed; see fetch_season)"); return 1
    old = data.load("xg_history")
    old = old[~old["game_id"].isin(df["game_id"])] if len(old) else old
    out = pd.concat([old, df], ignore_index=True).sort_values(["date", "home", "away"], kind="stable")  # a stable order keeps the daily diff to the rows that changed
    data.save("xg_history", out)
    print(f"fetch_xg: {len(df)} games for {a.season}, {len(out)} on file through {out['date'].max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
