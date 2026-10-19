#!/usr/bin/env python3
"""Raw ASA player-level inputs for the absence dataset (CLAUDE.md section 14): per season the games list, the player and
goalkeeper goals-added rows by game (minutes played per player per game), plus the players and teams directories.
Everything lands under data/public/asa_gplus/raw/ (gitignored; the flattened absences file is the record).
Usage: python3 scripts/fetch_asa_players.py [--seasons 2013-2026] [--force]"""
from __future__ import annotations
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.fetch_public import asa_pages, _get, _raw, ASA, PUB

RAW = os.path.join(PUB, "asa_gplus", "raw")


def have(name: str) -> bool:
    p = os.path.join(RAW, name)
    return os.path.exists(p) and os.path.getsize(p) > 100


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seasons", default="2013-2026"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    lo, hi = [int(x) for x in a.seasons.split("-")] if "-" in a.seasons else (int(a.seasons), int(a.seasons))
    if a.force or not have("teams.json"):
        r = _get(f"{ASA}/teams"); _raw("asa_gplus", "teams.json", r.text if r is not None else "[]")
    if a.force or not have("players.json"):
        pl = asa_pages("players", {}, limit=1000); _raw("asa_gplus", "players.json", json.dumps(pl)); print(f"players directory: {len(pl)}")
    for y in range(lo, hi + 1):
        if a.force or not have(f"games_{y}.json"):
            g = asa_pages("games", {"season_name": y}, limit=1000); _raw("asa_gplus", f"games_{y}.json", json.dumps(g)); print(f"games {y}: {len(g)}")
        if a.force or not have(f"players_{y}.json"):
            pl = asa_pages("players/goals-added", {"season_name": y, "split_by_games": "true"}); _raw("asa_gplus", f"players_{y}.json", json.dumps(pl)); print(f"players {y}: {len(pl)} rows")
            time.sleep(1.0)
        if a.force or not have(f"goalkeepers_{y}.json"):
            gk = asa_pages("goalkeepers/goals-added", {"season_name": y, "split_by_games": "true"}); _raw("asa_gplus", f"goalkeepers_{y}.json", json.dumps(gk)); print(f"goalkeepers {y}: {len(gk)} rows")
            time.sleep(1.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
