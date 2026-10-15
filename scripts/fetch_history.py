#!/usr/bin/env python3
"""Historical results and closing odds from football-data.co.uk's USA file (extra leagues download).
Writes one file per season to data/history/USA_<season>.csv with decimal closes: Pinnacle (PH/PD/PA) when populated, else average (AvgH/AvgD/AvgA).
Usage: python3 scripts/fetch_history.py"""
from __future__ import annotations
import datetime as dt, io, os, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
UK = ZoneInfo("Europe/London"); ET = ZoneInfo("America/New_York")
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
            home, away = canon(r.get("Home"), historical=True), canon(r.get("Away"), historical=True)
        except UnknownTeam as e:
            unknown.add(str(e)); continue
        try:
            d_uk = pd.to_datetime(r.get("Date"), dayfirst=True)
            t = (r.get("Time") or "00:00").strip()
            hh, mm = [int(x) for x in t.split(":")[:2]] if ":" in t else (12, 0)
            local = dt.datetime(d_uk.year, d_uk.month, d_uk.day, hh, mm, tzinfo=UK)
            date = local.astimezone(ET).strftime("%Y-%m-%d") if r.get("Time") else d_uk.strftime("%Y-%m-%d")
        except Exception:
            continue
        # column names as of 2026: PSCH/PSCD/PSCA = Pinnacle closing, AvgCH/AvgCD/AvgCA = average closing (older files: PH/PD/PA, AvgH)
        ph, pdr, pa = (r.get("PSCH") or r.get("PH", "")), (r.get("PSCD") or r.get("PD", "")), (r.get("PSCA") or r.get("PA", ""))
        if ph and pdr and pa:
            h, d, a, book = ph, pdr, pa, "pinnacle_close"
        else:
            h, d, a, book = (r.get("AvgCH") or r.get("AvgH", "")), (r.get("AvgCD") or r.get("AvgD", "")), (r.get("AvgCA") or r.get("AvgA", "")), "avg_close"
        if not (h and d and a):
            continue
        out.append({"season": r.get("Season", ""), "date": date, "time": r.get("Time", ""), "home": home, "away": away,
                    "hg": r.get("HG", ""), "ag": r.get("AG", ""), "h": h, "d": d, "a": a, "book": book,
                    "maxh": r.get("MaxCH") or r.get("MaxH", ""), "maxd": r.get("MaxCD") or r.get("MaxD", ""), "maxa": r.get("MaxCA") or r.get("MaxA", ""),
                    "b365h": r.get("B365CH", ""), "b365d": r.get("B365CD", ""), "b365a": r.get("B365CA", "")})
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
    per = df.groupby("season")["book"].apply(lambda b: f"{(b=='pinnacle_close').sum()}/{len(b)} pinnacle").to_dict()
    print(f"fetch_history: {len(df)} matches, {n_pin} with Pinnacle close; per season {per}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
