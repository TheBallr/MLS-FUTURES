#!/usr/bin/env python3
"""Morning news scan: RSS feeds (ESPN soccer, mlssoccer.com, The Athletic MLS; whichever answer), each headline tagged by every
club it names (canonical names, the alias table in sim/teams.py and nicknames) and by category (scenario / manager / injury /
suspension / call-up / fixture / team news / congestion / transfer), deduped against outputs/news/seen.json.
Writes outputs/news/<date>.md and prints it: Results / Act / Watch / Scenarios / Injury list.
Usage: python3 scripts/news_scan.py"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, sys, unicodedata, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.common import get, today_et
from sim import data
from sim.teams import ROOT, load_teams, _ALIASES

FEEDS = {
    "espn": "https://www.espn.com/espn/rss/soccer/news",
    "mlssoccer": "https://www.mlssoccer.com/feeds/rss/news",
    "athletic": "https://theathletic.com/mls/?rss=1",
}
CATS = {
    "injury": r"\b(injur|hamstring|knee|ankle|acl|surgery|out for|sidelined|ruled out|fitness|return to training|strain|fracture)\w*",
    "suspension": r"\b(suspend|red card|ban|disciplinary|yellow card accumulation)\w*",
    "call-up": r"\b(call-?up|national team|international duty|roster for|squad for|usmnt|canada men)\w*",
    "manager": r"\b(head coach|manager|sacked|fired|dismiss|appoint|interim|resign)\w*",
    "transfer": r"\b(sign|transfer|loan|designated player|dp signing|contract|acquire|trade[sd]?|waive)\w*",
    "fixture": r"\b(postpon|reschedul|kickoff|weather|venue|moved to)\w*",
    "congestion": r"\b(leagues cup|champions cup|open cup|canadian championship|midweek|rotation|rested)\w*",
    "scenario": r"\b(sanction|points deduction|forfeit|protest|appeal|league office|investigation|salary budget|roster violation)\w*",
}
OUT = os.path.join(ROOT, "outputs", "news")


def parse_feed(xml_text: str) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for it in root.iter("item"):
        t = (it.findtext("title") or "").strip(); link = (it.findtext("link") or "").strip(); d = (it.findtext("pubDate") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")[:300]
        items.append({"title": t, "link": link, "pub": d, "desc": desc})
    for e in root.iter("{http://www.w3.org/2005/Atom}entry"):
        t = (e.findtext("{http://www.w3.org/2005/Atom}title") or "").strip(); l = e.find("{http://www.w3.org/2005/Atom}link"); link = l.get("href") if l is not None else ""
        items.append({"title": t, "link": link, "pub": e.findtext("{http://www.w3.org/2005/Atom}updated") or "", "desc": ""})
    return items


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " " + re.sub(r"[^a-z0-9]+", " ", t) + " "


# phrases that name one club in a headline: canonical names, the alias table (minus ambiguous short ones) and nicknames;
# common words ("fire", "union", "crew") and city-only "los angeles" / "la" are left out on purpose
_NICK = {"revs": "New England Revolution", "revolution": "New England Revolution", "earthquakes": "San Jose Earthquakes", "quakes": "San Jose Earthquakes",
         "sounders": "Seattle Sounders", "whitecaps": "Vancouver Whitecaps", "timbers": "Portland Timbers", "rapids": "Colorado Rapids",
         "dynamo": "Houston Dynamo", "loons": "Minnesota United", "red bulls": "New York Red Bulls", "nycfc": "New York City FC", "lafc": "LAFC",
         "rsl": "Real Salt Lake", "skc": "Sporting Kansas City", "rbny": "New York Red Bulls", "five stripes": "Atlanta United", "orlando city": "Orlando City"}
_SKIP = {"la", "los angeles", "los angeles football club"}
_PHRASES = sorted({**{a: c for a, c in _ALIASES.items() if a not in _SKIP and len(a) >= 4}, **{_plain(r["team"]).strip(): r["team"] for r in load_teams()}, **_NICK}.items(), key=lambda kv: -len(kv[0]))


def clubs_in(text: str) -> list[str]:
    low = _plain(text); out = set()
    for ph, club in _PHRASES:
        if f" {ph} " in low:
            out.add(club); low = low.replace(f" {ph} ", " | ")  # a longer phrase consumes its words ("new york city" before "new york")
    return sorted(out)


def tag(item: dict) -> dict:
    text = f"{item['title']} {item['desc']}"
    low = text.lower()
    clubs = clubs_in(text)
    cats = [c for c, pat in CATS.items() if re.search(pat, low)]
    return dict(item, clubs=clubs, cats=cats or ["team news"], key=hashlib.md5(item["title"].lower().encode()).hexdigest()[:10])


def main():
    argparse.ArgumentParser().parse_args()
    items = []
    reach = {}
    for name, url in FEEDS.items():
        txt = get(url, json=False, retries=1, timeout=20)
        reach[name] = bool(txt)
        if txt:
            items.extend(dict(x, feed=name) for x in parse_feed(txt))
    seen_path = os.path.join(OUT, "seen.json")
    try:
        seen_before = set(json.load(open(seen_path)))
    except Exception:
        seen_before = set()
    seen = set(); tagged = []
    for it in items:
        t = tag(it)
        if t["key"] in seen or t["key"] in seen_before or not t["clubs"]:
            continue
        seen.add(t["key"]); tagged.append(t)
    os.makedirs(OUT, exist_ok=True)
    json.dump(sorted(seen_before | seen), open(seen_path, "w"))
    today = today_et().isoformat()
    inj = data.load("injuries")
    res = data.load("results"); recent = res[res["date"] >= (today_et() - dt.timedelta(days=2)).isoformat()] if len(res) else res
    lines = [f"# News scan {today}", "", f"Feeds reachable: {', '.join(k for k, v in reach.items() if v) or 'none'}", "", "## Results (last 2 days)"]
    lines += [f"- {r.date} {r.home} {r.hg}-{r.ag} {r.away}" for r in recent.itertuples(index=False)] or ["- none on file"]
    lines += ["", "## Act (proposals, numbered)"]
    n = 0
    for t in tagged:
        if set(t["cats"]) & {"injury", "suspension", "scenario", "manager", "call-up"}:
            n += 1; lines.append(f"{n}. [{'/'.join(t['cats'])}] {', '.join(t['clubs'])}: {t['title']} ({t['feed']})")
    if n == 0:
        lines.append("- nothing that moves a rating")
    lines += ["", "## Watch"] + [f"- [{'/'.join(t['cats'])}] {', '.join(t['clubs'])}: {t['title']}" for t in tagged if not set(t["cats"]) & {"injury", "suspension", "scenario", "manager", "call-up"}][:12]
    lines += ["", "## Scenarios", "- " + ("; ".join(f"{r.team} {r.type} p={r.prob}" for r in data.load("scenarios").itertuples(index=False)) or "none on file")]
    lines += ["", "## Injury list", f"- {len(inj)} rows on file; " + ", ".join(f"{t}: {int((inj['team']==t).sum())}" for t in sorted(inj['team'].unique())[:10]) if len(inj) else "- empty"]
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, f"{today}.md"), "w").write("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
