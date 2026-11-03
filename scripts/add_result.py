#!/usr/bin/env python3
"""Manual result for the rare miss. Usage: python3 scripts/add_result.py 2026-10-11 "Inter Miami" "Nashville SC" 2 1 [--winner "Nashville SC"] [--competition MLS]
A date after Decision Day is filed as "MLS Cup Playoffs" unless --competition says otherwise; a playoff result needs a winner (penalties
included), given with --winner or implied by the score (2026-11-03)."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim import data
from sim.teams import canon
from sim.data import merge_results
from sim.knobs import load_config

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("date"); ap.add_argument("home"); ap.add_argument("away"); ap.add_argument("hg", type=int); ap.add_argument("ag", type=int)
    ap.add_argument("--winner", default=""); ap.add_argument("--competition", default="")
    a = ap.parse_args()
    dday = load_config().get("mls", {}).get("decision_day", "")
    comp = a.competition or ("MLS Cup Playoffs" if dday and a.date > dday else "MLS")
    h, aw = canon(a.home), canon(a.away)
    w = canon(a.winner) if a.winner else (h if a.hg > a.ag else (aw if a.ag > a.hg else ""))
    if comp == "MLS Cup Playoffs" and w not in (h, aw):
        print("add_result: a playoff result needs --winner (penalties) when the score is level"); sys.exit(1)
    row = {"date": a.date, "home": h, "away": aw, "hg": a.hg, "ag": a.ag, "competition": comp, "source": "manual"}
    if comp == "MLS Cup Playoffs":
        row["winner"] = w
    res = merge_results(data.load("results"), pd.DataFrame([row]))
    data.save("results", res)
    print(f"add_result: {a.date} {h} {a.hg}-{a.ag} {aw} ({comp}{', winner ' + w if comp != 'MLS' else ''}) saved ({len(res)} rows)")
