#!/usr/bin/env python3
"""Manual result for the rare miss. Usage: python3 scripts/add_result.py 2026-10-11 "Inter Miami" "Nashville SC" 2 1"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim import data
from sim.teams import canon
from scripts.fetch_results import merge_results

if __name__ == "__main__":
    d, h, a, hg, ag = sys.argv[1:6]
    row = pd.DataFrame([{"date": d, "home": canon(h), "away": canon(a), "hg": int(hg), "ag": int(ag), "competition": "MLS", "source": "manual"}])
    res = merge_results(data.load("results"), row)
    data.save("results", res)
    print(f"add_result: {d} {canon(h)} {hg}-{ag} {canon(a)} saved ({len(res)} rows)")
