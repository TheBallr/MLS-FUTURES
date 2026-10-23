#!/usr/bin/env python3
"""Player headshots from ESPN's CDN (the same source as the crests), for the absences lists on the page (Zac 2026-10-23, "related
images"). Reads each club's ESPN id from data/logos.csv, pulls its roster from the ESPN site API, downloads every headshot once,
resizes it to 36 px (palette PNG, about 1.5 KB) under data/headshots/<espn_id>.png and writes data/headshots/roster.csv
(team, player, espn_id, position). site_data.py matches listed players to this roster by name and embeds the small image.
Usage: python3 scripts/fetch_headshots.py [--force]"""
from __future__ import annotations
import argparse, io, json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim.teams import ROOT

DIR = os.path.join(ROOT, "data", "headshots")
ROSTER = os.path.join(DIR, "roster.csv")
API = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/teams/{id}/roster"
HEAD = "https://a.espncdn.com/i/headshots/soccer/players/full/{id}.png"
UA = {"User-Agent": "Mozilla/5.0"}
SIZE = 36


def get(url: str, timeout: int = 25) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def shrink(raw: bytes) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    # ESPN headshots are landscape with the face centred: crop to a square around the centre-top, then shrink
    w, h = im.size; s = min(w, h)
    im = im.crop(((w - s) // 2, 0, (w - s) // 2 + s, s)).resize((SIZE, SIZE), Image.LANCZOS)
    im = im.quantize(colors=48, method=Image.Quantize.FASTOCTREE)
    out = io.BytesIO(); im.save(out, "PNG", optimize=True); return out.getvalue()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--force", action="store_true"); a = ap.parse_args()
    os.makedirs(DIR, exist_ok=True)
    logos = pd.read_csv(os.path.join(ROOT, "data", "logos.csv"), dtype=str)
    rows, jobs = [], []
    for r in logos.to_dict("records"):
        m = re.search(r"/(\d+)\.png", r["logo"] or "")
        if not m:
            continue
        try:
            d = json.loads(get(API.format(id=m.group(1))))
        except Exception as e:
            print(f"  roster failed for {r['team']}: {e}"); continue
        for p in d.get("athletes", []):
            pid = str(p.get("id") or "")
            if not pid:
                continue
            rows.append({"team": r["team"], "player": p.get("fullName") or p.get("displayName") or "", "espn_id": pid,
                         "position": (p.get("position") or {}).get("abbreviation", "")})
            dest = os.path.join(DIR, f"{pid}.png")
            if a.force or not os.path.exists(dest):
                jobs.append((pid, dest))
    pd.DataFrame(rows).to_csv(ROSTER, index=False)

    def fetch(job):
        pid, dest = job
        try:
            img = shrink(get(HEAD.format(id=pid)))
        except Exception:
            return 0      # no photo on the CDN for this player (404), or a transient error: nothing written, retried next run
        open(dest, "wb").write(img); return 1
    with ThreadPoolExecutor(4) as ex:
        got = sum(ex.map(fetch, jobs))
    print(f"headshots: {len(rows)} roster rows for {logos['team'].nunique()} clubs; {got} of {len(jobs)} new images fetched -> {os.path.relpath(DIR, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
