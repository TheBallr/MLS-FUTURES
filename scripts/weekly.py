#!/usr/bin/env python3
"""The morning refresh (one scheduled task at 8:30 ET since 2026-10-19, Zac: "a centralized routine ... everything refreshed"):
fetch every input, apply pending site edits, run the full model, the Risk report, the data checks, the morning report and the page,
and check the page. Every step runs every morning (until 2026-10-19 the model only ran after a finished match-day; --force is kept
for old prompts and changes nothing).
Order: results (ESPN, reschedules too) -> Pinnacle's posted lines -> book futures prices (The Odds API) -> close fallback -> the injury site -> close-capture
slots -> ASA minutes -> absence dataset -> MLS Player Status Report + Transfermarkt -> absence values -> disciplinary points (ESPN)
-> site edits -> xG -> Opta -> run_sim -> risk -> edges -> site_data -> freshness -> morning -> build_site -> check_site.
Fetch steps are soft (a failure is logged and the run goes on with the data on file); a failure in run_sim, site_data or build_site
stops the run, leaves the previous page untouched and exits 1. Each step's exit code and last line go to
outputs/latest/weekly_steps.json, which freshness.py reads for the Morning tab's data checks.
OpticOdds is not used since 2026-10-19 (Zac: the key is gone, do not rely on it): lines and closes come from Pinnacle's guest
API (the 10-minute captures, with close_fallback.py for a missed one), results from ESPN, injuries from the MLS report,
Transfermarkt and sportsgambler, discipline from ESPN.
The news scan (scripts/news_scan.py) is run by the routine itself before this script, because it reads and acts on the headlines.
Usage: python3 scripts/weekly.py [--quick]"""
import argparse, datetime as dt, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:  # a fresh task container may lack the packages: install requirements.txt once (check_site uses the Chromium in /opt/pw-browsers)
    import numpy, pandas, requests, playwright  # noqa: F401
except ImportError:
    _r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")],
                        capture_output=True, text=True)
    print("packages: installed requirements.txt" + ("" if _r.returncode == 0 else f" [exit {_r.returncode}]"))
from sim import data
from sim.teams import ROOT
from scripts.common import today_et

LATEST = os.path.join(ROOT, "outputs", "latest")
STATE = os.path.join(LATEST, "weekly_state.json")  # the newest complete match-day the last successful run covered
STEPS = os.path.join(LATEST, "weekly_steps.json")
_log = {}


def env() -> dict:
    e = dict(os.environ)
    return e


def sh(cmd, label=None):
    r = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True, env=env())
    out = (r.stdout.strip().splitlines() or [""])[-1]
    err = r.stderr.strip().splitlines()[-1] if r.returncode != 0 and r.stderr.strip() else ""
    print(f"  {os.path.basename(cmd[0])}: {out}" + ("" if r.returncode == 0 else f"  [exit {r.returncode}]"))
    if err:
        print("   " + err)
    _log[label or os.path.basename(cmd[0]).replace(".py", "")] = {"code": r.returncode, "line": (out or err)[:300]}
    json.dump({"date": today_et().isoformat(), "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "steps": _log}, open(STEPS, "w"), indent=1)
    return r


def newest_complete_day() -> str | None:
    sch = data.load("schedule"); res = data.load("results")
    if len(sch) == 0:
        return None
    played = set(zip(res["date"], res["home"], res["away"]))
    mls = sch[sch["competition"] == "MLS"]
    done_days = [d for d in sorted(set(mls["date"])) if all((r["date"], r["home"], r["away"]) in played for r in mls[mls["date"] == d].to_dict("records"))]
    return done_days[-1] if done_days else None


def what_moved(before: dict | None, after: dict) -> list[str]:
    if not before:
        return []
    out = []
    for pool in ("cup", "cup_finalist", "east", "west", "playoffs", "conf_semi", "conf_final"):
        for t, v in after.get(pool, {}).items():
            b = before.get(pool, {}).get(t, {}).get("prob")
            if b is not None and abs(v["prob"] - b) >= 0.02:
                out.append(f"{pool} {t}: {b*100:.1f}% -> {v['prob']*100:.1f}%")
    return sorted(out, key=lambda s: -abs(float(s.split('-> ')[1][:-1]) - float(s.split(': ')[1].split('%')[0])))[:12]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--force", action="store_true"); ap.add_argument("--quick", action="store_true"); a = ap.parse_args()
    year = str(today_et().year)
    print(f"weekly {today_et()}:")
    sh(["scripts/fetch_results.py"])
    sh(["scripts/fetch_pinnacle.py", "--quiet"])
    sh(["scripts/fetch_odds.py"])  # MLS futures prices for the Edges tab (The Odds API; skips without ODDS_API_KEY); comparison only
    sh(["scripts/close_fallback.py"])          # a played game whose 10-minute capture failed gets the last line before kickoff
    sh(["scripts/fetch_injuries.py"])            # sportsgambler (was only in the 7:40 task)
    sh(["scripts/close_schedule.py"])
    # full-health ratings (CLAUDE.md 14): ASA minutes for this season, the absence dataset, the MLS Player Status Report and
    # Transfermarkt return dates into injuries.csv, and today's absence values
    sh(["scripts/fetch_asa_players.py", "--seasons", str(int(year) - 1)])   # last season's raw files (fetched once per container): this season's values reach back 365 days
    sh(["scripts/fetch_asa_players.py", "--seasons", year, "--force"])
    sh(["scripts/absences.py", "build"])
    sh(["scripts/fetch_psr.py"])
    sh(["scripts/absence_values.py"])
    sh(["scripts/disc_points_espn.py", "--season", year])   # the tiebreak's disciplinary points, from ESPN (no key needed)
    before = json.load(open(os.path.join(LATEST, "markets.json"))) if os.path.exists(os.path.join(LATEST, "markets.json")) else None
    sh(["scripts/apply_site_settings.py"])
    sh(["scripts/fetch_xg.py"])
    sh(["scripts/fetch_public.py", "opta", "--latest"])  # the public sanity anchor (Zac, do 2)
    newest = newest_complete_day()
    if sh(["scripts/run_sim.py"] + (["--quick"] if a.quick else [])).returncode != 0:
        print("  FAILED: run_sim; the previous run and page are left as they were, nothing to publish"); return 1
    sh(["scripts/risk.py"] + (["--quick"] if a.quick else []))  # Risk tab and the rating history row (about 110 s); a failure marks the tab stale
    sh(["scripts/edges.py"])  # Edges tab: our fair v the books (needs markets.json and risk.json)
    if sh(["scripts/site_data.py"]).returncode != 0:
        print("  FAILED: site_data.py; the page was not rebuilt, nothing to publish"); return 1
    sh(["scripts/freshness.py"])   # data checks for the Morning tab
    sh(["scripts/morning.py"])     # the morning report (Morning tab); a failure leaves yesterday's report on the tab
    if sh(["scripts/build_site.py"]).returncode != 0:
        print("  FAILED: build_site.py; the page was not rebuilt, nothing to publish"); return 1
    sh(["scripts/check_site.py"])
    if not a.quick:
        json.dump({"complete_through": newest, "run": json.load(open(os.path.join(LATEST, "run_summary.json"))).get("stamp")}, open(STATE, "w"))
    after = json.load(open(os.path.join(LATEST, "markets.json")))
    moved = what_moved(before, after)
    print("  moved: " + ("; ".join(moved) if moved else "nothing by 2 points or more"))
    fp = os.path.join(LATEST, "freshness.json")
    if os.path.exists(fp):
        bad = [c for c in json.load(open(fp))["checks"] if c["status"] in ("bad", "warn")]
        print("  data checks: " + ("all current" if not bad else "; ".join(f"{c['label']} ({c['status']}): {c['text']}" for c in bad)))
    mp = os.path.join(LATEST, "morning.json")
    if os.path.exists(mp):
        print("  morning report:\n" + "\n".join("   - " + h for h in json.load(open(mp)).get("head", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
