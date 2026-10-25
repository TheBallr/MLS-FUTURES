#!/usr/bin/env python3
"""One matte colour per club from its crest (Zac 2026-10-23: club colour on every row and chart line). The crest's most common
saturated hue, lightened or darkened to sit on the page's charcoal, written to data/club_colours.csv (team, code, hex, source).
A row with source "hand" is never overwritten (edit the csv to override a club). Usage: python3 scripts/club_colours.py"""
from __future__ import annotations
import colorsys, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim.teams import ROOT, code_of

OUT = os.path.join(ROOT, "data", "club_colours.csv")


def dominant(path: str) -> str:
    from PIL import Image
    im = Image.open(path).convert("RGBA").resize((48, 48))
    buckets = {}
    for r, g, b, a in im.getdata():
        if a < 200:
            continue
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if s < 0.25 or l < 0.12 or l > 0.92:     # skip white, black and grey outlines
            continue
        k = (round(h * 24) % 24)
        w = s * (1 - abs(l - 0.5))              # weight saturated mid-tones
        acc = buckets.setdefault(k, [0.0, 0.0, 0.0, 0.0]); acc[0] += w; acc[1] += w * h; acc[2] += w * l; acc[3] += w * s
    if not buckets:
        return "#8a9099"
    k, (w, hs, ls, ss) = max(buckets.items(), key=lambda kv: kv[1][0])
    h, l, s = hs / w, ls / w, ss / w
    l = min(0.66, max(0.48, l)); s = min(0.62, max(0.35, s))   # matte: mid lightness, capped saturation, reads on charcoal
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def main():
    codes = code_of()
    old = pd.read_csv(OUT, dtype=str).set_index("team") if os.path.exists(OUT) else pd.DataFrame()
    rows = []
    for t, c in codes.items():
        p = os.path.join(ROOT, "data", "logos", f"{c}.png")
        if len(old) and t in old.index and str(old.loc[t, "source"]) == "hand":
            rows.append({"team": t, "code": c, "hex": old.loc[t, "hex"], "source": "hand"}); continue
        rows.append({"team": t, "code": c, "hex": dominant(p) if os.path.exists(p) else "#8a9099", "source": "crest"})
    pd.DataFrame(rows).sort_values("team").to_csv(OUT, index=False)
    print(f"club_colours: {len(rows)} clubs -> {os.path.relpath(OUT, ROOT)}")
    for r in rows:
        print(f"  {r['code']:4} {r['hex']} {r['source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
