#!/usr/bin/env python3
"""List the distinct kickoff times (UTC and ET) in the next N days from data/schedule.csv, each minus ten minutes: the capture
Routine times. The daily Routine creates one Routine per slot that does not exist yet.
Usage: python3 scripts/close_schedule.py [--days 8] [--json]"""
import argparse, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.common import parse_utc, now_utc, ET
from sim import data


def slots(days: int) -> list[dict]:
    sch = data.load("schedule")
    now = now_utc(); end = now + dt.timedelta(days=days)
    out = {}
    for r in sch.itertuples(index=False):
        if r.status == "final" or not r.kickoff_utc:
            continue
        ko = parse_utc(r.kickoff_utc)
        if now < ko <= end:
            cap = ko - dt.timedelta(minutes=10)
            key = cap.strftime("%Y-%m-%dT%H:%M")
            out.setdefault(key, {"capture_utc": cap.strftime("%Y-%m-%dT%H:%M:00Z"), "capture_et": cap.astimezone(ET).strftime("%a %b %d %I:%M %p"), "fixtures": []})["fixtures"].append(f"{r.home} v {r.away}")
    return [out[k] for k in sorted(out)]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=8); ap.add_argument("--json", action="store_true"); a = ap.parse_args()
    s = slots(a.days)
    if a.json:
        print(json.dumps(s, indent=1))
    else:
        for x in s:
            print(f"{x['capture_utc']}  {x['capture_et']} ET  {len(x['fixtures'])} fixtures: {'; '.join(x['fixtures'])}")
        print(f"close_schedule: {len(s)} capture slots in the next {a.days} days")
