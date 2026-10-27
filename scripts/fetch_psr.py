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
Slugs: the matchday forms plus, from Decision Day on, the forms MLS used for the 2025 playoffs ("...-decision-day",
"...-wild-card-games-<weekday>-<month>-<day>", "...-round-one-best-of-3-series-game-1/2/3", "...-conference-semifinals",
"...-conference-finals", "...-mls-cup"); --slug reads one story by its slug when none of the forms fits (review 2026-10-27,
proposal 4).
Usage: python3 scripts/fetch_psr.py [--asof 2026-10-19] [--no-transfermarkt] [--slug mls-player-status-report-...]"""
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
    mls = sch   # every competition: the playoff rounds are on the schedule from Nov 8 (fetch_schedule.py in the routine)
    lo = (pd.Timestamp(asof) - pd.Timedelta(days=5)).strftime("%Y-%m-%d"); hi = (pd.Timestamp(asof) + pd.Timedelta(days=6)).strftime("%Y-%m-%d")
    days = sorted({d for d in mls["date"] if lo <= d <= hi})
    if not days:   # the schedule file may not carry a playoff round yet: take the round dates from config
        from sim.knobs import load_config as _lc
        _P = _lc().get("mls", {}); _PO = _P.get("playoffs", {})
        cand = [_P.get("decision_day"), _PO.get("wild_card"), (_PO.get("round_one") or [None])[0], (_PO.get("conf_semis") or [None])[0], (_PO.get("conf_finals") or [None])[0], _PO.get("mls_cup")]
        days = sorted({d for d in cand if d and lo <= d <= hi})
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
    # playoff rounds (review 2026-10-27, proposal 4): the round's name from config's playoff dates, in the forms MLS used in 2025
    from sim.knobs import load_config
    P = load_config().get("mls", {}); PO = P.get("playoffs", {})
    def playoff_forms(dates):
        d0 = dates[0]; f = []
        wd = lambda d: pd.Timestamp(d).strftime("%A").lower(); mo = lambda d: pd.Timestamp(d).strftime("%B").lower(); dy = lambda d: str(int(d[-2:]))
        dated = lambda base: [base] + [f"{base}-{wd(d)}-{mo(d)}-{dy(d)}" for d in dates[:2]] + ([f"{base}-{wd(dates[0])}-{mo(dates[0])}-{dy(dates[0])}-and-{wd(dates[1])}-{mo(dates[1])}-{dy(dates[1])}"] if len(dates) > 1 else [])
        if d0 == P.get("decision_day"):
            f += dated("mls-player-status-report-decision-day")
        elif PO.get("wild_card") and d0 <= PO["wild_card"] <= dates[-1] or d0 == PO.get("wild_card"):
            f += dated("mls-player-status-report-wild-card-games") + dated("mls-player-status-report-wild-card") + dated("mls-player-status-report-wild-card-round")
        elif PO.get("round_one") and PO["round_one"][0] <= d0 <= PO["round_one"][1]:
            for gnum in (1, 2, 3):
                f += dated(f"mls-player-status-report-round-one-best-of-3-series-game-{gnum}") + dated(f"mls-player-status-report-round-one-game-{gnum}")
        elif PO.get("conf_semis") and PO["conf_semis"][0] <= d0 <= PO["conf_semis"][1]:
            f += dated("mls-player-status-report-round-one-best-of-3-series-conference-semifinal") + dated("mls-player-status-report-conference-semifinals") + dated("mls-player-status-report-conference-semifinal")
        elif PO.get("conf_finals") and PO["conf_finals"][0] <= d0 <= PO["conf_finals"][1]:
            f += dated("mls-player-status-report-conference-finals") + dated("mls-player-status-report-conference-final")
        elif PO.get("mls_cup") and d0 == PO["mls_cup"]:
            f += dated("mls-player-status-report-mls-cup") + dated("mls-player-status-report-mls-cup-final") + dated("mls-player-status-report-mls-cup-presented-by-audi")
        return f
    for dates, ahead in rounds:
        for f in playoff_forms(dates):
            out += [f, f + f"-{asof[:4]}"]
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


def latest_report(asof: str, slug: str | None = None) -> dict | None:
    """The newest Player Status Report story on or before asof: the slug candidates first (the API's list hides these stories),
    then a page through the press releases. With `slug`, that story alone (pasted from the site when no form fits)."""
    best = None
    for slug in ([slug] if slug else candidate_slugs(asof)):
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
            elif raw.strip().startswith("**") and len(l.split()) <= 5 and not re.search(r"\d", l):
                # a bold line that is not a known club (a spelling sim/teams.py lacks): say so and file nothing under the previous club
                print(f"fetch_psr: unknown club heading {l!r} (add to sim/teams.py); its players are NOT filed", file=sys.stderr); team = None
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
        if (covered and ex.at[i, "team"] in covered and i not in listed and str(ex.at[i, "source"]) in ("psr", "optic") and str(ex.at[i, "out_from"]) < start
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
    ap.add_argument("--slug", default=None, help="read this story slug (from mlssoccer.com/news/<slug>) instead of probing the forms")
    a = ap.parse_args()
    story = latest_report(a.asof, a.slug)
    if story is None:
        # the report goes up the day before the round (late afternoon ET), so a morning run often finds the next one not out yet:
        # that is not a failure while the newest report on file is at most 8 days old (freshness.py checks that age on its own)
        on_file = sorted(f[:10] for f in os.listdir(RAW_PSR) if f[:4].isdigit()) if os.path.isdir(RAW_PSR) else []
        age = (pd.Timestamp(a.asof) - pd.Timestamp(on_file[-1])).days if on_file else 99
        if age <= 8:
            print(f"fetch_psr: next Player Status Report not published yet; newest on file {on_file[-1]} ({age} days old) stays in force"); return 0
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
