#!/usr/bin/env python3
"""Official MLS Player Status Report (the league's availability report, one press release per matchday on mlssoccer.com: every
club's players listed Out or Questionable with the reason) plus Transfermarkt's injured-players table (expected return dates),
merged into data/ratings/injuries.csv (CLAUDE.md 14i). Sources are read through the site's content API
(dapi.mlssoccer.com, press releases tagged press-release, the newest slug containing "player-status-report") and the public
Transfermarkt page; raw payloads under data/optic/raw/psr/ and data/public/transfermarkt/raw/.

Merge rules: a listed player who is not in injuries.csv enters at squad tier with out_from = the report's match date (Questionable
-> prob_out 0.5, source psr); a player already on file gets the report's status and date in the note and prob_out 0.5 / 1.0 from
the report; a Transfermarkt "until" date fills a blank expected_return (never overwrites one Zac set). A suspension is one
match: its row closes the day after that match (the next report re-lists the player if the ban runs on). An open psr row of a
club the report covers whose player the report no longer lists is closed at the report's first match date; a player listed
again after his row closed gets a new row. Rows of other sources are left to their own fetchers (scripts/absence_values.py
marks any row stale once the player plays). Tiers and dates Zac set are never overwritten.
Usage: python3 scripts/fetch_psr.py [--asof 2026-10-19] [--no-transfermarkt]"""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.common import today_et
from sim import data
from sim.teams import ROOT, canon

DAPI = "https://dapi.mlssoccer.com/v2/content/en-us/stories"
TM = "https://www.transfermarkt.us/major-league-soccer/verletztespieler/wettbewerb/MLS1"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36", "Accept-Language": "en-US,en;q=0.9",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
RAW_PSR = os.path.join(ROOT, "data", "optic", "raw", "psr")
RAW_TM = os.path.join(ROOT, "data", "public", "transfermarkt", "raw")
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}


def _get(url, params=None, timeout=40):
    import requests
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]+", " ", s)).strip()


def candidate_slugs(asof: str) -> list[str]:
    """Slug forms MLS uses for the report ("mls-player-status-report-matchday-31-saturday-october-17-and-sunday-october-18",
    "...-matchday-15-saturday-may-23-and-sunday-may-24-2026", "...-matchday-30"): built from the next round's dates on the
    schedule (else the round just played) and the matchday number from the ASA games list (last played matchday, +1 for a
    round still to come)."""
    sch = data.load("schedule")
    mls = sch[sch["competition"] == "MLS"]
    lo = (pd.Timestamp(asof) - pd.Timedelta(days=5)).strftime("%Y-%m-%d"); hi = (pd.Timestamp(asof) + pd.Timedelta(days=6)).strftime("%Y-%m-%d")
    days = sorted({d for d in mls["date"] if lo <= d <= hi})
    # rounds: runs of schedule dates at most one day apart, newest first; each round gives its single dates and its first pair
    rounds = []; cur = []
    for d in days:
        if cur and (pd.Timestamp(d) - pd.Timestamp(cur[-1])).days > 1:
            rounds.append(cur); cur = []
        cur.append(d)
    if cur:
        rounds.append(cur)
    rounds = [(r, 1 if r[0] > asof else 0) for r in reversed(rounds)]
    md = 0
    gp = os.path.join(ROOT, "data", "public", "asa_gplus", "raw", f"games_{asof[:4]}.json")
    if os.path.exists(gp):
        for g in json.load(open(gp)):
            d = str((pd.Timestamp(g["date_time_utc"].replace(" UTC", "")) - pd.Timedelta(hours=4)).date())
            if g.get("status") == "FullTime" and d < asof and not g.get("knockout_game"):
                md = max(md, int(g.get("matchday") or 0))
    out = []
    for dates, ahead in rounds:
        ns = [md + ahead, md + ahead + 1, md + ahead - 1, md + ahead + 2] if md else []
        wd = lambda d: pd.Timestamp(d).strftime("%A").lower(); mo = lambda d: pd.Timestamp(d).strftime("%B").lower(); dy = lambda d: str(int(d[-2:]))
        for n in ns:
            base = f"mls-player-status-report-matchday-{n}"
            forms = [base]
            for d1 in dates:
                forms.append(f"{base}-{wd(d1)}-{mo(d1)}-{dy(d1)}")
            for d1, d2 in zip(dates, dates[1:]):
                forms.append(f"{base}-{wd(d1)}-{mo(d1)}-{dy(d1)}-and-{wd(d2)}-{mo(d2)}-{dy(d2)}")
                forms.append(f"{base}-{wd(d1)}-{mo(d1)}-{dy(d1)}-{wd(d2)}-{mo(d2)}-{dy(d2)}")
            for f in forms:
                out += [f, f + f"-{asof[:4]}"]
    seen = set(); return [x for x in out if not (x in seen or seen.add(x))]


def latest_report(asof: str) -> dict | None:
    """The newest Player Status Report story on or before asof: the slug candidates first (the API's list hides these stories),
    then a page through the press releases."""
    best = None
    for slug in candidate_slugs(asof):
        try:
            story = _get(f"{DAPI}/{slug}", timeout=20).json()
        except Exception:
            continue
        cd = story.get("contentDate", "")[:10]
        if story.get("slug") and cd <= asof and (pd.Timestamp(asof) - pd.Timestamp(cd)).days <= 10:  # a bare slug may belong to an old season
            if best is None or cd > best.get("contentDate", "")[:10]:
                best = story
    if best is not None:
        os.makedirs(RAW_PSR, exist_ok=True)
        with open(os.path.join(RAW_PSR, f"{best['contentDate'][:10]}_{best['slug'][:60]}.json"), "w") as f:
            json.dump(best, f)
        return best
    for skip in range(0, 400, 40):
        try:
            d = _get(DAPI, {"tags.slug": "press-release", "$skip": skip, "$limit": 40}).json()
        except Exception as e:
            print(f"fetch_psr: list failed at {skip} ({str(e)[:80]})", file=sys.stderr); break
        items = d.get("items", [])
        for it in items:
            if "player-status-report" in it.get("slug", "") and it.get("contentDate", "")[:10] <= asof and (pd.Timestamp(asof) - pd.Timestamp(it["contentDate"][:10])).days <= 10:
                if best is None or it["contentDate"] > best["contentDate"]:
                    best = it
        if len(items) < 40:
            break
    if best is None:
        return None
    story = _get(f"{DAPI}/{best['slug']}").json()
    os.makedirs(RAW_PSR, exist_ok=True)
    with open(os.path.join(RAW_PSR, f"{best['contentDate'][:10]}_{best['slug'][:60]}.json"), "w") as f:
        json.dump(story, f)
    return story


LINE = re.compile(r"^(.+?)\s+[-–—]\s+(.+?)\s*\((Out|Questionable|Doubtful|Probable|Suspended)\)\s*$", re.I)


def parse_report(story: dict) -> tuple[list[dict], str, set]:
    """(rows, report date, clubs covered): rows of team, player, reason, status, match_date from the markdown parts; a club with
    no one listed ("None") still counts as covered."""
    pub = str(story.get("contentDate", ""))[:10]
    year = int(pub[:4]) if pub else today_et().year
    rows = []; team = None; match_date = pub; covered = set()
    for part in story.get("parts", []):
        if part.get("type") != "markdown":
            continue
        for raw in part.get("content", "").splitlines():
            l = html.unescape(raw).strip().strip("*").strip()
            if not l:
                continue
            m = re.match(r"^#+\s*\w+,\s*([A-Za-z]+)\s+(\d{1,2})", l)
            if m and m.group(1).lower() in MONTHS:
                match_date = f"{year}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"; continue
            pm = LINE.match(l)
            if pm:
                if team:
                    rows.append({"team": team, "player": pm.group(1).strip(), "reason": pm.group(2).strip(), "status": pm.group(3).capitalize(), "match_date": match_date})
                continue
            t = canon(l, strict=False)
            if t:
                team = t; covered.add(t)
            elif l.lower() == "none":
                continue
    return rows, pub, covered


def transfermarkt() -> list[dict]:
    """(team, player, injury, until) from Transfermarkt's MLS injured-players page; until as YYYY-MM-DD or blank."""
    s = None
    for attempt in range(3):
        try:
            s = _get(TM).text; break
        except Exception as e:
            err = str(e)[:80]
            import time; time.sleep(3 * (attempt + 1))
    if s is None:
        print(f"fetch_psr: transfermarkt failed ({err})", file=sys.stderr); return []
    os.makedirs(RAW_TM, exist_ok=True)
    with open(os.path.join(RAW_TM, f"{today_et().isoformat()}.html"), "w", encoding="utf-8") as f:
        f.write(s)
    i = s.find('<table class="items">')
    if i < 0:
        return []
    tbl = s[i:s.find("</table>", s.find("</tbody>", i))]
    out = []
    for r in re.findall(r'<tr class="(?:odd|even)">(.*?)</tr>\s*(?=<tr class="(?:odd|even)">|</tbody>)', tbl, flags=re.S):
        names = re.findall(r'<td class="hauptlink">\s*<a title="([^"]+)"', r)
        clubs = re.findall(r'<td class="zentriert no-border-rechts">\s*<a title="([^"]+)"', r)
        inj = re.findall(r'<td class="links">(.*?)</td>', r, flags=re.S)
        cells = re.findall(r'<td class="zentriert">(.*?)</td>', r, flags=re.S)
        if not names or not clubs:
            continue
        until = ""
        for c in cells:
            c = re.sub(r"<[^>]+>", "", c).strip()
            try:
                until = dt.datetime.strptime(c, "%b %d, %Y").strftime("%Y-%m-%d"); break
            except ValueError:
                pass
        t = canon(clubs[0], strict=False)
        if t:
            out.append({"team": t, "player": html.unescape(names[0]), "injury": re.sub(r"<[^>]+>", "", inj[0]).strip() if inj else "", "until": until})
    return out


def _suspension(r: dict) -> bool:
    return r["status"] == "Suspended" or "suspen" in str(r["reason"]).lower()


def merge(existing: pd.DataFrame, rows: list[dict], tm: list[dict], report_date: str, asof: str, covered: set | None = None) -> tuple[pd.DataFrame, dict]:
    ex = existing.copy()
    for c in data.cols("injuries"):
        if c not in ex.columns:
            ex[c] = ""
    key = {(r["team"], _norm(r["player"])): i for i, r in ex.iterrows()}  # the last row per player wins (rows are appended in time order)
    stats = {"psr_rows": len(rows), "added": 0, "updated": 0, "tm_rows": len(tm), "tm_dates": 0, "closed": 0, "suspensions": 0}
    is_open = lambda i, d: str(ex.at[i, "expected_return"]).strip() == "" or str(ex.at[i, "expected_return"]) > d
    listed = set()
    for r in rows:
        k = (r["team"], _norm(r["player"]))
        p = 0.5 if r["status"] in ("Questionable", "Doubtful", "Probable") else 1.0
        note = f"{r['status'].lower()} {r['reason']} (MLS report {report_date})"
        i = key.get(k)
        if i is None:  # a surname match on an existing row (different spelling of the same player)
            same = [j for (t, n), j in key.items() if t == r["team"] and n.split()[-1:] == _norm(r["player"]).split()[-1:]]
            i = same[0] if len(same) == 1 else None
        if i is not None and not is_open(i, r["match_date"]):
            i = None  # listed again after his row closed: a new spell, a new row
        if i is not None:
            ex.at[i, "prob_out"] = str(p); ex.at[i, "note"] = note; ex.at[i, "updated"] = report_date
            if str(ex.at[i, "source"]) in ("sportsgambler", "optic", ""):
                ex.at[i, "source"] = "psr"
            stats["updated"] += 1
        else:
            ex = pd.concat([ex, pd.DataFrame([{"team": r["team"], "player": r["player"], "value_goals": "", "out_from": r["match_date"], "expected_return": "", "prob_out": str(p), "tier": "squad", "note": note, "source": "psr", "updated": report_date}])], ignore_index=True)
            i = len(ex) - 1; key[k] = i; stats["added"] += 1
        listed.add(i)
        if _suspension(r) and str(ex.at[i, "expected_return"]).strip() == "":  # one match: back for the next one
            ex.at[i, "expected_return"] = (pd.Timestamp(r["match_date"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"); stats["suspensions"] += 1
    # an open psr row of a club the report covers, for a player it no longer lists: available again from the report's round
    start = min((r["match_date"] for r in rows), default=report_date)
    for i in ex.index:
        if (covered and ex.at[i, "team"] in covered and i not in listed and str(ex.at[i, "source"]) == "psr" and str(ex.at[i, "out_from"]) < start
                and is_open(i, start) and (str(ex.at[i, "expected_return"]).strip() == "" or "(Transfermarkt)" in str(ex.at[i, "note"]))):
            ex.at[i, "expected_return"] = start; ex.at[i, "note"] = f"{ex.at[i, 'note']} | not on MLS report {report_date}"; ex.at[i, "updated"] = report_date
            stats["closed"] += 1
    for r in tm:
        if not r["until"]:
            continue
        k = (r["team"], _norm(r["player"]))
        i = key.get(k)
        if i is None:
            same = [j for (t, n), j in key.items() if t == r["team"] and n.split()[-1:] == _norm(r["player"]).split()[-1:]]
            i = same[0] if len(same) == 1 else None
        if i is not None and str(ex.at[i, "expected_return"]).strip() == "":
            ex.at[i, "expected_return"] = r["until"]; ex.at[i, "note"] = f"{ex.at[i, 'note']}; return {r['until']} (Transfermarkt)"; stats["tm_dates"] += 1
    return ex, stats


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--asof", default=today_et().isoformat()); ap.add_argument("--no-transfermarkt", action="store_true")
    a = ap.parse_args()
    story = latest_report(a.asof)
    if story is None:
        print("fetch_psr: no Player Status Report found"); return 2
    rows, pub, covered = parse_report(story)
    tm = [] if a.no_transfermarkt else transfermarkt()
    inj = data.load("injuries")
    merged, st = merge(inj, rows, tm, pub, a.asof, covered)
    data.save("injuries", merged)
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"fetch_psr: {story.get('title')} (published {pub}): {len(rows)} players {by}; injuries.csv +{st['added']} new, {st['updated']} updated, {st['suspensions']} suspensions dated to one match, {st['closed']} closed (off the report); Transfermarkt {st['tm_rows']} rows, {st['tm_dates']} return dates filled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
