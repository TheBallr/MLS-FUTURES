#!/usr/bin/env python3
"""Results: ESPN scoreboard final scores merged into data/results.csv (regular season as competition MLS; playoff games as
"MLS Cup Playoffs" with the winner, which the season engine locks into the bracket). The schedule's status, date and kickoff
are refreshed by espn_id, so a rescheduled game moves instead of being simulated twice. Exits 1 when ESPN could not be reached
at all.
Usage: python3 scripts/fetch_results.py [--days 10]"""
from __future__ import annotations
import argparse, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import today_et
from scripts.fetch_schedule import fetch_range, FAILED_DAYS
from sim import data
from sim.data import merge_results


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=10); a = ap.parse_args()
    end = today_et(); start = end - dt.timedelta(days=a.days)
    rows = fetch_range(start, end + dt.timedelta(days=1))
    n_days = (end - start).days + 2
    if len(FAILED_DAYS) == n_days:
        print(f"fetch_results: ESPN unreachable on all {n_days} days; nothing changed"); return 1
    fin = [r for r in rows if r["status"] == "final" and str(r["hg"]) != "" and str(r["ag"]) != ""]
    # a playoff row carries the feed's winner (a level score went to penalties): the season engine locks it into the bracket
    new = pd.DataFrame([{"date": r["date"], "home": r["home"], "away": r["away"], "hg": r["hg"], "ag": r["ag"], "competition": r["competition"], "source": "espn",
                         "winner": r["winner"] if r["competition"] != "MLS" else ""} for r in fin], columns=data.cols("results"))
    res = data.load("results")
    before = len(res)
    res = merge_results(res, new)
    data.save("results", res)
    # refresh the schedule by espn_id: status, and date / kickoff when ESPN has moved a game
    sch = data.load("schedule")
    moved = []
    if len(sch) and len(rows):
        by = {str(r["espn_id"]): r for r in rows}
        for i, e in enumerate(sch["espn_id"].astype(str)):
            r = by.get(e)
            if r is None:
                continue
            sch.at[i, "status"] = r["status"]
            if r["kickoff_utc"] and (r["date"] != sch.at[i, "date"] or r["kickoff_utc"] != sch.at[i, "kickoff_utc"]):
                moved.append(f"{sch.at[i, 'home']} v {sch.at[i, 'away']} {sch.at[i, 'date']} -> {r['date']}")
                sch.at[i, "date"] = r["date"]; sch.at[i, "kickoff_utc"] = r["kickoff_utc"]
        data.save("schedule", sch.sort_values(["kickoff_utc", "home"], kind="stable"))
    print(f"fetch_results: {len(new)} finals in window, results.csv {before} -> {len(res)} rows, through {res['date'].max() if len(res) else 'n/a'}"
          + (f"; rescheduled: {'; '.join(moved)}" if moved else "") + (f"; {len(FAILED_DAYS)} days unreachable" if FAILED_DAYS else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
