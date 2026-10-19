#!/usr/bin/env python3
"""Injury list maintenance from sportsgambler.com's MLS page (dated with expected returns); `merge` is shared with
fetch_optic.py's OpticOdds injury feed. Merge rules (build prompt section 9): a new name enters at squad tier with the source's
return date (a doubt at prob_out 0.5); a name already on file gets the source's newer return date; a row of this source that
the source no longer lists is closed (expected_return = today); names match without accents, case or middle names. Rows Zac
has set (a tier other than squad, or a value) are never touched.
Usage: python3 scripts/fetch_injuries.py [--first-import]"""
from __future__ import annotations
import argparse, datetime as dt, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import get, today_et
from sim import data
from sim.teams import canon

URL = "https://www.sportsgambler.com/injuries/football/usa-mls/"


def parse_page(html: str) -> list[dict]:
    """sportsgambler markup (Oct 2026): <div class="injury-block"><h3 class="injuries-title"><a>Team</a></h3> ... <div class="inj-row"><div class="inj-container">
    <span class="inj-type CLASS"></span><span class="inj-player">Name</span>...<span class="inj-info">Reason</span><span class="inj-return h-sm">date or -</span>"""
    rows = []
    for block in re.findall(r'<div class="injury-block">(.*?)(?=<div class="injury-block">|$)', html, flags=re.S):
        h = re.search(r'<h3 class="injuries-title"[^>]*>(.*?)</h3>', block, flags=re.S)
        if not h:
            continue
        team = canon(re.sub(r"<[^>]+>", "", h.group(1)).strip(), strict=False)
        if not team:
            continue
        for row in re.findall(r'<div class="inj-container">(.*?)</div>', block, flags=re.S):
            def span(cls):
                m = re.search(rf'<span class="{cls}[^"]*"[^>]*>(.*?)</span>', row, flags=re.S)
                return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else ""
            tm = re.search(r'<span class="inj-type ([^"]*)"', row)
            kind = (tm.group(1) if tm else "").strip()
            player = span("inj-player")
            if not player:
                continue
            info = span("inj-info"); ret_txt = span("inj-return")
            ret = ""
            if ret_txt and ret_txt != "-":
                for fmt in ("%d %b %Y", "%d/%m/%Y", "%Y-%m-%d", "%b %d, %Y", "%d %B %Y"):
                    try:
                        ret = dt.datetime.strptime(ret_txt, fmt).strftime("%Y-%m-%d"); break
                    except ValueError:
                        pass
                if not ret:
                    try:
                        ret = pd.to_datetime(ret_txt).strftime("%Y-%m-%d")
                    except Exception:
                        ret = ""
            status = "doubt" if "question" in kind else ("suspension" if ("card" in kind or "suspen" in kind) else "injury")
            rows.append({"team": team, "player": player, "expected_return": ret, "note": f"{status}: {info}" + (f" (site return {ret_txt})" if ret_txt and ret_txt != "-" else ""), "status": status, "position": span("inj-position")})
    return rows


def name_key(name: str) -> tuple[str, str]:
    """(first, last) token without accents or case: 'André Filipe Russo Franco' and 'Andre Franco' match."""
    t = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z ]", " ", t).split()
    return (t[0], t[-1]) if t else ("", "")


def zacs(row) -> bool:
    return str(row.get("tier", "squad") or "squad") != "squad" or str(row.get("value_goals", "") or "") not in ("", "0", "0.0")


def true_source(row) -> str:
    """The feed a row really came from. Before 2026-10-19 fetch_optic.py wrote its rows as "sportsgambler"; sportsgambler's
    notes start "injury:", "doubt:" or "suspension:", OpticOdds' are "<status> <type>" (e.g. "gtd Ankle")."""
    src = str(row.get("source", "") or "")
    if src == "sportsgambler" and not re.match(r"^(injury|doubt|suspension):", str(row.get("note", "") or "")):
        return "optic"
    return src


def merge(existing: pd.DataFrame, site: list[dict], first_import: bool, today: dt.date, source: str = "sportsgambler") -> tuple[pd.DataFrame, int, int, int]:
    """Merge one source's current list. A listed player with an open row (no return date, or one after today) keeps it: the
    return date and doubt/out status follow the source unless Zac set the row; a listed player with no open row gets a new row;
    an open row of this source that the source no longer lists is closed today. Returns (rows, added, updated, closed)."""
    ex = existing.copy().reset_index(drop=True)
    if len(ex):
        ex["source"] = [true_source(r) for r in ex.to_dict("records")]
    td = today.isoformat()
    is_open = lambda i: not ex.at[i, "expected_return"] or str(ex.at[i, "expected_return"]) > td
    idx = {}
    for i, (t, p) in enumerate(zip(ex["team"], ex["player"])):
        idx.setdefault((t, name_key(p)), []).append(i)
    added = updated = closed = 0
    seen = set()
    n0 = len(ex)
    for r in site:
        prob = 0.5 if r.get("status") == "doubt" else 1.0
        hits = [i for i in idx.get((r["team"], name_key(r["player"])), []) if is_open(i)]
        if hits:
            seen.update(hits)
            for i in hits:
                if zacs(ex.loc[i]):
                    continue
                ch = False
                if r["expected_return"] and ex.at[i, "expected_return"] != r["expected_return"]:
                    ex.at[i, "expected_return"] = r["expected_return"]; ch = True
                try:
                    cur = float(ex.at[i, "prob_out"])
                except (TypeError, ValueError):
                    cur = None
                if cur != prob:
                    ex.at[i, "prob_out"] = f"{prob:.1f}"; ch = True  # the file loads as text
                if ch:
                    ex.at[i, "updated"] = td; updated += 1
            continue
        out_from = (today - dt.timedelta(days=28)).isoformat() if first_import else td
        ex = pd.concat([ex, pd.DataFrame([{"team": r["team"], "player": r["player"], "value_goals": "", "out_from": out_from,
                                           "expected_return": r["expected_return"], "prob_out": f"{prob:.1f}", "tier": "squad", "note": r["note"],
                                           "source": source, "updated": td}])], ignore_index=True)
        idx.setdefault((r["team"], name_key(r["player"])), []).append(len(ex) - 1); seen.add(len(ex) - 1)
        added += 1
    if site:  # the source answered: its open rows it no longer lists are closed today
        for i in range(n0):
            if i not in seen and ex.at[i, "source"] == source and is_open(i) and not zacs(ex.loc[i]):
                ex.at[i, "expected_return"] = td; ex.at[i, "note"] = f"{ex.at[i, 'note']} | not listed {td}".strip(" |"); ex.at[i, "updated"] = td; closed += 1
    return ex, added, updated, closed


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--first-import", action="store_true"); a = ap.parse_args()
    html = get(URL, json=False)
    if not html:
        print("fetch_injuries: injury site unreachable"); return 1
    site = parse_page(html)
    ex = data.load("injuries")
    first = a.first_import or len(ex) == 0
    ex, added, updated, closed = merge(ex, site, first, today_et())
    data.save("injuries", ex)
    print(f"fetch_injuries: site lists {len(site)}; {added} new at squad tier{' (first import, dated 28d back)' if first else ''}, {updated} return dates updated, {closed} closed (no longer listed); {len(ex)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
