#!/usr/bin/env python3
"""Injury list maintenance from sportsgambler.com's MLS page (dated with expected returns). Merge rules (build prompt section 9):
new names enter at squad tier with the site's return date; a name the site already listed on first import is dated 28 days back;
tiers are Zac's. Never overwrites a row whose tier or value Zac has set.
Usage: python3 scripts/fetch_injuries.py [--first-import]"""
from __future__ import annotations
import argparse, datetime as dt, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import get, today_et
from sim import data
from sim.teams import canon

URL = "https://www.sportsgambler.com/injuries/football/usa-mls/"


def parse_page(html: str) -> list[dict]:
    """Tolerant parse: team headers followed by player rows with a return date. VERIFY against the live page on first run."""
    rows = []
    team = None
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    for block in re.split(r"(?=<h[23][^>]*>)", text):
        h = re.search(r"<h[23][^>]*>(.*?)</h[23]>", block, flags=re.S)
        if not h:
            continue
        name = re.sub(r"<[^>]+>", "", h.group(1)).strip()
        t = canon(name, strict=False)
        if t:
            team = t
        if not team:
            continue
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", block, flags=re.S):
            cells = [re.sub(r"<[^>]+>", " ", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(1), flags=re.S)]
            cells = [re.sub(r"\s+", " ", c) for c in cells if c]
            if len(cells) < 2 or cells[0].lower() in ("player", "name"):
                continue
            player = cells[0]
            ret = ""
            for c in cells[1:]:
                mm = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2} \d{1,2},? \d{4})", c)
                if mm:
                    try:
                        ret = pd.to_datetime(mm.group(1), dayfirst=False).strftime("%Y-%m-%d"); break
                    except Exception:
                        pass
            note = " | ".join(cells[1:])[:120]
            rows.append({"team": team, "player": player, "expected_return": ret, "note": note})
    return rows


def merge(existing: pd.DataFrame, site: list[dict], first_import: bool, today: dt.date) -> tuple[pd.DataFrame, int, int]:
    ex = existing.copy()
    key = set(zip(ex["team"], ex["player"]))
    added = updated = 0
    for r in site:
        k = (r["team"], r["player"])
        if k in key:
            m = (ex["team"] == r["team"]) & (ex["player"] == r["player"])
            if r["expected_return"] and (ex.loc[m, "expected_return"] != r["expected_return"]).any():
                ex.loc[m, "expected_return"] = r["expected_return"]; ex.loc[m, "updated"] = today.isoformat(); updated += 1
            continue
        out_from = (today - dt.timedelta(days=28)).isoformat() if first_import else today.isoformat()
        ex = pd.concat([ex, pd.DataFrame([{"team": r["team"], "player": r["player"], "value_goals": "", "out_from": out_from,
                                           "expected_return": r["expected_return"], "prob_out": 1.0, "tier": "squad", "note": r["note"],
                                           "source": "sportsgambler", "updated": today.isoformat()}])], ignore_index=True)
        added += 1
    return ex, added, updated


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--first-import", action="store_true"); a = ap.parse_args()
    html = get(URL, json=False)
    if not html:
        print("fetch_injuries: injury site unreachable"); return 1
    site = parse_page(html)
    ex = data.load("injuries")
    first = a.first_import or len(ex) == 0
    ex, added, updated = merge(ex, site, first, today_et())
    data.save("injuries", ex)
    print(f"fetch_injuries: site lists {len(site)}; {added} new at squad tier{' (first import, dated 28d back)' if first else ''}, {updated} return dates updated; {len(ex)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
