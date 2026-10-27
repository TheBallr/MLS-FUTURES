#!/usr/bin/env python3
"""Safety net for a missed close capture (Zac 2026-10-19, "do 1"): every played MLS game of the season with no Pinnacle close on
file (no `pinnacle_close`, no 10-minute `pinnacle_last`) gets the last Pinnacle line we fetched before its kickoff, from
data/market/current_round_odds.csv, written to closing_lines.csv as book `pinnacle_lastposted` (it ranks below a real capture and
above football-data's market-average close in refresh_ratings.closes_with_targets); a line fetched within 15 minutes of the
scheduled kickoff is as good as a capture and is written as `pinnacle_last` (review 2026-10-27, proposal 1). Every competition in
the schedule (playoff games too). The row keeps that line's fetched_at, so its age before kickoff is on file; the run line prints
each game filled and how many hours before kickoff its line was taken.
Runs in weekly.py every morning before the model. Usage: python3 scripts/close_fallback.py"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim import data
from scripts.common import parse_utc, now_utc

REAL = {"pinnacle_close", "pinnacle_last"}


def main():
    sch = data.load("schedule"); res = data.load("results"); cl = data.load("closing_lines"); odds = data.load("current_round_odds")
    if len(odds) == 0:
        print("close_fallback: no posted lines on file"); return 0
    played = set(zip(res["date"], res["home"], res["away"]))
    have = set(zip(cl.loc[cl["book"].isin(REAL), "date"], cl.loc[cl["book"].isin(REAL), "home"], cl.loc[cl["book"].isin(REAL), "away"]))
    pin = odds[odds["book"].str.lower() == "pinnacle"]
    first_line = str(pin["fetched_at"].min()) if len(pin) else ""
    now = now_utc(); filled = []
    for r in sch[sch["kickoff_utc"].astype(str) != ""].to_dict("records"):
        k = (r["date"], r["home"], r["away"])
        ko = parse_utc(r["kickoff_utc"])
        if k in have or k not in played or ko > now or r["kickoff_utc"] < first_line:
            continue
        cand = pin[(pin["date"] == r["date"]) & (pin["home"] == r["home"]) & (pin["away"] == r["away"]) & (pin["fetched_at"] < r["kickoff_utc"])]
        if not len(cand):
            continue
        row = cand.sort_values("fetched_at").iloc[-1].to_dict()
        age_min = (ko - parse_utc(row["fetched_at"])).total_seconds() / 60
        book = "pinnacle_last" if age_min <= 15 else "pinnacle_lastposted"
        row.update({"book": book, "kickoff_utc": r["kickoff_utc"]})
        m = (cl["date"] == r["date"]) & (cl["home"] == r["home"]) & (cl["away"] == r["away"]) & (cl["book"].isin(["pinnacle_lastposted", "pinnacle_last"]))
        cl = pd.concat([cl[~m], pd.DataFrame([row])], ignore_index=True)
        filled.append(f"{r['home']} v {r['away']} {r['date']} (line {age_min / 60:.0f} h before kickoff" + (", counted as a capture)" if book == "pinnacle_last" else ")"))
    if filled:
        data.save("closing_lines", cl.sort_values(["kickoff_utc", "home"]))
    print("close_fallback: " + (f"{len(filled)} missed capture(s) filled with the last line before kickoff: " + "; ".join(filled) if filled else "every played game since the lines began has a captured close"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
