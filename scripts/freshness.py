#!/usr/bin/env python3
"""Morning data checks (Zac 2026-10-19: "updated and non stale injuries/prices/ratings for the day ... reviewed for red flags"): is
every input the model reads current, and did today's run use it? Writes outputs/latest/freshness.json ({made_utc, checks: [{key,
label, status ok|warn|bad|info, text}]}); morning.py puts it at the top of the Morning tab. Runs in weekly.py after site_data.py,
reading weekly.py's own step log (outputs/latest/weekly_steps.json) for the fetches.
Usage: python3 scripts/freshness.py"""
from __future__ import annotations
import datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT, code_of
from scripts.common import today_et, parse_utc, ET

LATEST = os.path.join(ROOT, "outputs", "latest")
CAPTURE_FROM = "2026-10-14"   # the ten-minute close capture began here (CLAUDE.md 4)


def main():
    cfg = load_config(); kn = knobs(cfg); codes = code_of()
    today = today_et().isoformat(); now = dt.datetime.now(dt.timezone.utc)
    sch = data.load("schedule"); res = data.load("results")
    mls = sch[sch["competition"] == "MLS"]
    played = set(zip(res["date"], res["home"], res["away"]))
    g = lambda r: f"{codes.get(r['home'], r['home'])} v {codes.get(r['away'], r['away'])} {r['date'][5:]}"
    checks = []
    add = lambda key, label, status, text: checks.append({"key": key, "label": label, "status": status, "text": text})

    # fetch steps of this morning's weekly.py
    sp = os.path.join(LATEST, "weekly_steps.json")
    steps = json.load(open(sp)) if os.path.exists(sp) else {}
    failed = [k for k, v in steps.get("steps", {}).items() if v.get("code", 0) != 0]
    if not steps:
        add("steps", "Morning fetches", "warn", "no step log (weekly.py did not run this morning)")
    elif steps.get("date") != today:
        add("steps", "Morning fetches", "bad", f"last full refresh was {steps.get('date')}, not today")
    else:
        add("steps", "Morning fetches", "bad" if failed else "ok", ("failed: " + ", ".join(failed)) if failed else f"all {len(steps['steps'])} steps ran today")

    # results: every MLS game before today has a score
    past = mls[mls["date"] < today]
    missing = [g(r) for r in past.to_dict("records") if (r["date"], r["home"], r["away"]) not in played]
    add("results", "Results", "bad" if missing else "ok", ("missing: " + ", ".join(missing[:6])) if missing else f"every game through {past['date'].max() if len(past) else '-'} has a score")

    # closes: every played game since the capture began has Pinnacle's close
    from scripts.refresh_ratings import closes_with_targets
    cl = closes_with_targets(cfg); cl = cl[cl["season"].astype(str) == str(cfg["season"])]
    pin = set((r["date"], r["home"], r["away"]) for r in cl.to_dict("records") if str(r.get("book", "")).startswith("pinnacle"))
    rec = [r for r in past[past["date"] >= CAPTURE_FROM].to_dict("records") if (r["date"], r["home"], r["away"]) in played]
    noclose = [g(r) for r in rec if (r["date"], r["home"], r["away"]) not in pin]
    lastposted = [g(r) for r in rec if any(x["date"] == r["date"] and x["home"] == r["home"] and x["away"] == r["away"] and x.get("book") == "pinnacle_lastposted" for x in cl.to_dict("records"))] if len(rec) else []
    add("closes", "Pinnacle closes", "warn" if noclose or lastposted else "ok",
        ("no close on file: " + ", ".join(noclose[:6]) + ("; " if lastposted else "") if noclose else "")
        + (f"capture missed, last line before kickoff used: {', '.join(lastposted[:6])}" if lastposted else "")
        if noclose or lastposted else f"all {len(rec)} games since {CAPTURE_FROM[5:]} have Pinnacle's close")

    # Pinnacle's kickoff v the schedule's (fetch_pinnacle.py writes the mismatches it saw; review 2026-10-27, proposals 1 and 5)
    kp = os.path.join(LATEST, "pinnacle_kickoffs.json")
    if os.path.exists(kp):
        km = json.load(open(kp))
        if km.get("mismatch"):
            add("kickoffs", "Pinnacle kickoffs", "warn", "Pinnacle's start time differs from the schedule's: " + ", ".join(km["mismatch"][:4]) + " (captures key on the schedule)")
    # a playoff result on file with no winner (a level score ESPN has not settled yet): the bracket cannot lock it
    po = res[(res["competition"] == "MLS Cup Playoffs")] if "competition" in res.columns else res.iloc[0:0]
    if len(po):
        nw = [f"{codes.get(r['home'], r['home'])} v {codes.get(r['away'], r['away'])} {r['date'][5:]}" for r in po.to_dict("records") if str(r.get("winner", "")).strip() == "" and str(r.get("hg", "")) == str(r.get("ag", ""))]
        add("playoff_winners", "Playoff results", "bad" if nw else "ok", ("level score with no winner on file (not locked into the bracket): " + ", ".join(nw)) if nw else f"{len(po)} playoff results on file, every one with a winner")

    # posted lines: the next three days' games carry a Pinnacle line fetched in the last 24 hours
    odds = data.load("current_round_odds"); odds = odds[odds["book"].str.lower() == "pinnacle"] if len(odds) else odds
    last_fetch = pd.to_datetime(odds["fetched_at"], utc=True).max() if len(odds) else None
    soon = mls[(mls["date"] >= today) & (mls["date"] <= (today_et() + dt.timedelta(days=3)).isoformat())]
    fresh = set()
    if len(odds):
        o = odds[pd.to_datetime(odds["fetched_at"], utc=True) >= pd.Timestamp(now) - pd.Timedelta(hours=24)]
        fresh = set(zip(o["date"], o["home"], o["away"]))
    unlined = [g(r) for r in soon.to_dict("records") if (r["date"], r["home"], r["away"]) not in fresh]
    age = (pd.Timestamp(now) - last_fetch).total_seconds() / 3600 if last_fetch is not None else None
    st = "bad" if age is None or age > 24 else ("warn" if unlined else "ok")
    add("lines", "Pinnacle lines", st, (f"last fetch {age:.0f} h ago" if age is not None else "never fetched") + (f"; not lined yet: {', '.join(unlined[:6])}" if unlined else f"; all {len(soon)} games in the next 3 days lined"))

    # xG and lineups for every played game of the season
    xg = data.load("xg_history"); xg = xg[xg["date"].str.startswith(str(cfg["season"]))]
    xk = set(zip(xg["date"], xg["home"], xg["away"])) | set(zip((pd.to_datetime(xg["date"]) + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d"), xg["home"], xg["away"]))
    season_played = [r for r in mls[mls["date"] < today].to_dict("records") if (r["date"], r["home"], r["away"]) in played]
    noxg = [g(r) for r in season_played if (r["date"], r["home"], r["away"]) not in xk]
    add("xg", "xG", "warn" if noxg else "ok", ("no xG yet: " + ", ".join(noxg[:6])) if noxg else f"xG on file for all {len(season_played)} played games")
    ap = os.path.join(ROOT, "data", "public", "asa_gplus", "absence_players.csv")
    if os.path.exists(ap):
        lastmin = str(pd.read_csv(ap, usecols=["date"])["date"].max()); lastres = max(r["date"] for r in season_played) if season_played else ""
        add("minutes", "Lineups (ASA minutes)", "ok" if lastmin >= lastres else "warn", f"minutes through {lastmin}; last result {lastres}")

    # the absence dataset reaches back a season (this season's player values use 365 days): a failed last-season ASA fetch would cut it
    abp = os.path.join(ROOT, "data", "public", "asa_gplus", "absences.csv")
    if os.path.exists(abp):
        seas = set(pd.read_csv(abp, usecols=["season"])["season"].astype(str)) if "season" in pd.read_csv(abp, nrows=0).columns else set()
        prev = str(int(cfg["season"]) - 1)
        if seas:
            add("absence_seasons", "Absence dataset", "ok" if prev in seas else "bad",
                f"{min(seas)}-{max(seas)} on file" + ("" if prev in seas else f"; {prev} missing (last season's ASA fetch failed?): player values lose their 365-day reach"))
    # the official injury report: its own date, so an old report is visible even when the rows were re-stamped
    injp = os.path.join(ROOT, "data", "ratings", "injuries.csv")
    if os.path.exists(injp):
        inj = pd.read_csv(injp, dtype=str, keep_default_na=False)
        psr = inj[inj.get("source", pd.Series(dtype=str)) == "psr"] if "source" in inj.columns else inj.iloc[0:0]
        if len(psr):
            rep = psr["note"].str.extract(r"MLS report (\d{4}-\d{2}-\d{2})")[0].dropna()   # the report's own date, from the row's note
            last = str(rep.max()) if len(rep) else str(psr["updated"].max()); days = (today_et() - dt.date.fromisoformat(last[:10])).days if last[:4].isdigit() else 99
            # the report for a round goes up the day before it: on a match day, or the day before once the evening has passed, the
            # newest report must be dated within 3 days of that round (review 2026-10-27, proposal 4)
            next_round = next((d for d in sorted(set(sch["date"])) if d >= today and not all((d, r["home"], r["away"]) in played for r in sch[sch["date"] == d].to_dict("records"))), None)
            stale_round = next_round is not None and (dt.date.fromisoformat(next_round) - today_et()).days <= 0 and (dt.date.fromisoformat(next_round) - dt.date.fromisoformat(last[:10])).days > 3 if last[:4].isdigit() else False
            add("psr", "MLS injury report", "bad" if days > 8 else ("warn" if stale_round else "ok"),
                f"newest report used dated {last[:10]} ({days} days old)" + (f"; no report yet for the {next_round[5:]} round" if stale_round else ""))

    # injuries: today's list in goals, and how many listed rows carry nothing (stale)
    avp = os.path.join(ROOT, "data", "ratings", "absence_values.csv")
    if os.path.exists(avp):
        av = pd.read_csv(avp, dtype=str, keep_default_na=False)
        asof = av["asof"].max() if "asof" in av.columns and len(av) else ""
        stale = int((av.get("stale", pd.Series(dtype=str)) == "1").sum())
        live = av[(av.get("stale", "0") != "1") & (pd.to_numeric(av["cost_per_game"], errors="coerce").fillna(0).abs() >= 0.01)]
        top = live.assign(c=pd.to_numeric(live["cost_per_game"])).groupby("team")["c"].sum().sort_values(ascending=False).head(3)
        add("injuries", "Injury list", "ok" if asof == today else "bad",
            f"valued {asof}; {len(av)} listed, {len(live)} cost 0.01+ goals a game" + (f" (most: {', '.join(f'{codes.get(t, t)} {c:.2f}' for t, c in top.items())})" if len(top) else "") + (f"; {stale} listed but have played since (carry nothing)" if stale else ""))

    # discipline (tiebreak step), Opta anchor
    dp = os.path.join(ROOT, "data", "discipline", f"disc_points_{cfg['season']}.csv")
    if os.path.exists(dp):
        d = pd.read_csv(dp); behind = int(len(season_played) * 2 / 30 - d["matches"].mean())
        add("discipline", "Disciplinary points", "ok" if behind <= 1 else "warn", f"through {int(d['matches'].min())}-{int(d['matches'].max())} matches per club ({d.get('source', pd.Series(['optic'])).iloc[0]})")
    op = os.path.join(ROOT, "data", "public", "opta", "snapshots.csv")
    if os.path.exists(op):
        od = str(pd.read_csv(op, usecols=["date"])["date"].max()); days = (today_et() - dt.date.fromisoformat(od)).days
        add("opta", "Opta anchor", "ok" if days <= 7 else "warn", f"snapshot {od} ({days} days old)")

    # today's run: built today, on today's data, history and page inputs in step
    summ = json.load(open(os.path.join(LATEST, "run_summary.json")))
    run_day = parse_utc(summ["run_utc"]).astimezone(ET).date().isoformat()
    lastres = max((r["date"] for r in season_played), default="")
    ok_run = run_day == today and (summ.get("results_through") or "") >= lastres
    add("run", "Model run", "ok" if ok_run else "bad", f"run {summ.get('stamp')} ({summ.get('n_seasons'):,} seasons), results through {summ.get('results_through')}")
    rk = json.load(open(os.path.join(LATEST, "risk.json"))) if os.path.exists(os.path.join(LATEST, "risk.json")) else {}
    add("risk", "Risk report", "ok" if rk.get("stamp") == summ.get("stamp") else "bad", "built for this run" if rk.get("stamp") == summ.get("stamp") else f"built for {rk.get('stamp')}, not this run")
    hp = os.path.join(ROOT, "data", "ratings", "ratings_history.csv")
    if os.path.exists(hp):
        h = pd.read_csv(hp, dtype=str)
        col = "stamp"
        add("history", "Rating history", "ok" if summ.get("stamp") in set(h[col]) else "bad", "today's ratings are in the history" if summ.get("stamp") in set(h[col]) else "today's run is missing from ratings_history.csv")

    # Zac's inputs: unapplied site edits, hand adjustments in force
    pp = os.path.join(LATEST, "pending_settings.json")
    if os.path.exists(pp):
        p = json.load(open(pp)); s = p.get("settings") or {}
        unapplied = (s and not s.get("applied")) or (s.get("adjustments") and not s.get("adjustments_applied"))
        add("site_edits", "Site edits", "bad" if unapplied else "ok", "saved edits not applied" if unapplied else "every saved edit applied")
    from sim.layers import week_of, hand_week_values
    hv = hand_week_values(data.load("hand_log"), week_of(today))[0]
    hv = {t: v for t, v in hv.items() if t and abs(v) > 1e-9}
    add("hand", "Hand adjustments", "info", (", ".join(f"{codes.get(t, t)} {v:+.2f}" for t, v in sorted(hv.items(), key=lambda x: -abs(x[1])))
                                              + " in force (re-size or drop as the closes come in)") if hv else "none")
    out = {"made_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "date": today, "checks": checks}
    json.dump(out, open(os.path.join(LATEST, "freshness.json"), "w"), indent=1)
    worst = "bad" if any(c["status"] == "bad" for c in checks) else ("warn" if any(c["status"] == "warn" for c in checks) else "ok")
    print(f"freshness: {worst}; " + "; ".join(f"{c['label']} {c['status']}" for c in checks if c["status"] in ("bad", "warn")) if worst != "ok" else "freshness: all inputs current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
