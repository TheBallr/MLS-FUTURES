#!/usr/bin/env python3
"""Disciplinary points from ESPN's match summaries (no key needed), so the tiebreak step stays current every morning; the OpticOdds
version (scripts/disc_points.py) needs the key, which only the old task container had. Per played MLS game of the season ESPN gives
fouls committed and the card events by player (cached once per game in data/discipline/espn_games_<season>.csv). Scale as
disc_points.py: foul 1, yellow 3 (both yellows of a sent-off player counted), second yellow +1 (the incident totals 7), straight
red 7; technical-staff warnings are not in either feed. Writes data/discipline/disc_points_<season>.csv with source espn, unless
the existing file (OpticOdds) covers more matches.
Usage: python3 scripts/disc_points_espn.py [--season 2026]"""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim import data
from sim.teams import ROOT, canon

SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/summary?event={}"
DISC = os.path.join(ROOT, "data", "discipline")


def game_rows(eid: str) -> list[dict]:
    """Two rows (one per club) for one ESPN game, or [] when the summary has no box score yet."""
    d = json.load(urllib.request.urlopen(SUMMARY.format(eid), timeout=30))
    teams = {}
    for t in (d.get("boxscore") or {}).get("teams", []):
        st = {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
        if "foulsCommitted" not in st:
            return []
        teams[t["team"]["displayName"]] = {"fouls": float(st.get("foulsCommitted") or 0), "y": {}, "r": {}}
    for k in d.get("keyEvents", []):
        typ = (k.get("type") or {}).get("text", ""); tn = (k.get("team") or {}).get("displayName")
        if tn not in teams or "Card" not in typ:
            continue
        who = ((k.get("participants") or [{}])[0].get("athlete") or {}).get("displayName", "?")
        bucket = teams[tn]["r" if "Red" in typ else "y"]; bucket[who] = bucket.get(who, 0) + 1
    out = []
    for tn, v in teams.items():
        y = sum(v["y"].values()); sy = sr = 0
        for who, n in v["r"].items():
            if v["y"].get(who, 0) >= 1:  # a red after a yellow is a second yellow; count both yellows whether or not ESPN lists the second
                sy += n; y += max(0, 2 - v["y"][who])
            else:
                sr += n
        out.append({"espn_id": str(eid), "team": canon(tn, strict=False) or tn, "fouls": v["fouls"], "yellows": y, "second_yellows": sy, "straight_reds": sr})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--season", type=int, default=2026); a = ap.parse_args()
    sch = data.load("schedule"); res = data.load("results")
    played = set(zip(res["date"], res["home"], res["away"]))
    games = sch[(sch["competition"] == "MLS") & sch["date"].str.startswith(str(a.season)) & (sch["espn_id"].astype(str) != "")]
    games = games[[k in played for k in zip(games["date"], games["home"], games["away"])]]
    cache_p = os.path.join(DISC, f"espn_games_{a.season}.csv"); os.makedirs(DISC, exist_ok=True)
    cache = pd.read_csv(cache_p, dtype={"espn_id": str}) if os.path.exists(cache_p) else pd.DataFrame(columns=["espn_id", "team", "fouls", "yellows", "second_yellows", "straight_reds"])
    have = set(cache["espn_id"]); new = []; failed = 0
    for eid in games["espn_id"].astype(str):
        if eid in have:
            continue
        try:
            new += game_rows(eid); time.sleep(0.15)
        except Exception:
            failed += 1
    if new:
        cache = pd.concat([cache, pd.DataFrame(new)], ignore_index=True); cache.to_csv(cache_p, index=False)
    c = cache[cache["espn_id"].isin(set(games["espn_id"].astype(str)))].copy()
    c["points"] = c["fouls"] + 3 * c["yellows"] + c["second_yellows"] + 7 * c["straight_reds"]
    out = c.groupby("team").agg(points=("points", "sum"), matches=("points", "size"), fouls=("fouls", "sum"), yellows=("yellows", "sum"),
                                 second_yellows=("second_yellows", "sum"), straight_reds=("straight_reds", "sum")).reset_index().sort_values("points")
    out["points"] = out["points"].astype(int); out["source"] = "espn"
    p = os.path.join(DISC, f"disc_points_{a.season}.csv")
    if os.path.exists(p):
        old = pd.read_csv(p)
        if "source" not in old.columns and old["matches"].sum() > out["matches"].sum():
            print(f"disc_points_espn: kept the OpticOdds file ({int(old['matches'].sum())} club-matches v ESPN {int(out['matches'].sum())})"); return 0
    out.to_csv(p, index=False)
    print(f"disc_points_espn {a.season}: {len(new) // 2} new games, {failed} failed, clubs {len(out)}, matches {out['matches'].min()}-{out['matches'].max()}, "
          f"points {out['points'].min()}-{out['points'].max()} -> {p}")
    return 1 if failed and not len(out) else 0


if __name__ == "__main__":
    sys.exit(main())
