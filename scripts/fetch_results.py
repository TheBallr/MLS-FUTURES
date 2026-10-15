#!/usr/bin/env python3
"""Results: ESPN scoreboard (same-day final scores) merged into data/results.csv; the schedule's status is refreshed too.
Usage: python3 scripts/fetch_results.py [--days 10]"""
from __future__ import annotations
import argparse, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import today_et
from scripts.fetch_schedule import fetch_range
from sim import data
from sim.data import merge_results


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=10); a = ap.parse_args()
    end = today_et(); start = end - dt.timedelta(days=a.days)
    rows = fetch_range(start, end + dt.timedelta(days=1))
    fin = [r for r in rows if r["status"] == "final" and r["competition"] == "MLS"]
    new = pd.DataFrame([{"date": r["date"], "home": r["home"], "away": r["away"], "hg": r["hg"], "ag": r["ag"], "competition": "MLS", "source": "espn"} for r in fin], columns=data.cols("results"))
    res = data.load("results")
    before = len(res)
    res = merge_results(res, new)
    data.save("results", res)
    # refresh schedule statuses
    sch = data.load("schedule")
    if len(sch) and len(rows):
        st = {r["espn_id"]: r["status"] for r in rows}
        sch["status"] = [st.get(e, s) for e, s in zip(sch["espn_id"], sch["status"])]
        data.save("schedule", sch)
    print(f"fetch_results: {len(new)} finals in window, results.csv {before} -> {len(res)} rows, through {res['date'].max() if len(res) else 'n/a'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
