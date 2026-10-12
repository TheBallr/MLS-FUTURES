#!/usr/bin/env python3
"""Historical results and closing odds from football-data.co.uk's USA file (extra leagues download).
Writes one file per season to data/history/USA_<season>.csv with decimal closes: Pinnacle (PH/PD/PA) when populated, else average (AvgH/AvgD/AvgA).
Usage: python3 scripts/fetch_history.py"""
from __future__ import annotations
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import get
from sim import data
from sim.teams import canon, UnknownTeam

URL = "https://www.football-data.co.uk/new/USA.csv"


def parse(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    out = []
    unknown = set()
    for r in df.to_dict("records"):
        try:
            home, away = canon(r.get("Home")), canon(r.get("Away"))
        except UnknownTeam as e:
            unknown.add(str(e)); continue
        try:
            date = pd.to_datetime(r.get("Date"), dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            continue
        ph, pdr, pa = r.get("PH", ""), r.get("PD", ""), r.get("PA", "")
        if ph and pdr and pa:
            h, d, a, book = ph, pdr, pa, "pinnacle_close"
        else:
            h, d, a, book = r.get("AvgH", ""), r.get("AvgD", ""), r.get("AvgA", ""), "avg_close"
        out.append({"season": r.get("Season", ""), "date": date, "time": r.get("Time", ""), "home": home, "away": away,
                    "hg": r.get("HG", ""), "ag": r.get("AG", ""), "h": h, "d": d, "a": a, "book": book,
                    "maxh": r.get("MaxH", ""), "maxd": r.get("MaxD", ""), "maxa": r.get("MaxA", "")})
    if unknown:
        print(f"fetch_history: unknown names (add to sim/teams.py): {sorted(unknown)}", file=sys.stderr)
    return pd.DataFrame(out)


def main():
    text = get(URL, json=False)
    if not text:
        print("fetch_history: USA.csv unreachable"); return 1
    df = parse(text)
    os.makedirs(data.HISTORY, exist_ok=True)
    n_pin = int((df["book"] == "pinnacle_close").sum())
    for season, g in df.groupby("season"):
        g.to_csv(os.path.join(data.HISTORY, f"USA_{str(season).replace('/', '_')}.csv"), index=False)
    seasons = ", ".join(f"{s}:{len(g)}" for s, g in df.groupby("season"))
    print(f"fetch_history: {len(df)} matches, {n_pin} with Pinnacle close; seasons {seasons}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
