#!/usr/bin/env python3
"""The 8:52 ET task: fetch results and Pinnacle lines (and OpticOdds when the key is present), list capture slots, and if a
match-day has completed since the last run (every fixture of that calendar day has a result), apply pending site settings,
run the full model, build the Risk report and the site, and print what moved. --force runs the model regardless.
Fetch steps are soft (a failure is printed and the run goes on with the data on file); a failure in run_sim, site_data or
build_site stops the run, leaves the previous page untouched and exits 1, so nothing stale or half-built is published.
Usage: python3 scripts/weekly.py [--force] [--quick]"""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import data
from sim.teams import ROOT
from scripts.common import today_et

LATEST = os.path.join(ROOT, "outputs", "latest")
STATE = os.path.join(LATEST, "weekly_state.json")  # the newest complete match-day the last successful run covered


def sh(cmd):
    r = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    out = (r.stdout.strip().splitlines() or [""])[-1]
    print(f"  {os.path.basename(cmd[0])}: {out}" + ("" if r.returncode == 0 else f"  [exit {r.returncode}]"))
    if r.returncode != 0 and r.stderr.strip():
        print("   " + r.stderr.strip().splitlines()[-1])
    return r


def newest_complete_day() -> str | None:
    sch = data.load("schedule"); res = data.load("results")
    if len(sch) == 0:
        return None
    played = set(zip(res["date"], res["home"], res["away"]))
    mls = sch[sch["competition"] == "MLS"]
    done_days = [d for d in sorted(set(mls["date"])) if all((r["date"], r["home"], r["away"]) in played for r in mls[mls["date"] == d].to_dict("records"))]
    return done_days[-1] if done_days else None


def round_finished_since_last_run() -> tuple[bool, str]:
    """Compare the newest complete match-day with the one the last successful run covered (weekly_state.json). The run's
    results_through is not enough: an evening rerun on a half-played day would record that day and skip the next morning."""
    newest = newest_complete_day()
    if newest is None:
        return False, "no completed match-day"
    last = json.load(open(STATE)).get("complete_through") if os.path.exists(STATE) else None
    if last is None and os.path.exists(os.path.join(LATEST, "run_summary.json")):
        last = json.load(open(os.path.join(LATEST, "run_summary.json"))).get("results_through")
    return (last is None or newest > last), f"newest complete match-day {newest}, last run covered {last}"


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
    print(f"weekly {today_et()}:")
    sh(["scripts/fetch_results.py"])
    sh(["scripts/fetch_pinnacle.py", "--quiet"])
    sh(["scripts/fetch_optic.py"])
    sh(["scripts/close_schedule.py"])
    fin, why = round_finished_since_last_run()
    print(f"  round finished since last run: {fin} ({why})")
    if fin or a.force:
        before = json.load(open(os.path.join(LATEST, "markets.json"))) if os.path.exists(os.path.join(LATEST, "markets.json")) else None
        sh(["scripts/apply_site_settings.py"])
        sh(["scripts/fetch_xg.py"])
        sh(["scripts/fetch_public.py", "opta", "--latest"])  # the public sanity anchor (Zac, do 2)
        newest = newest_complete_day()
        if sh(["scripts/run_sim.py"] + (["--quick"] if a.quick else [])).returncode != 0:
            print("  FAILED: run_sim; the previous run and page are left as they were, nothing to publish"); return 1
        sh(["scripts/risk.py"] + (["--quick"] if a.quick else []))  # Risk tab (about 80 s); a failure only marks the tab stale
        for step in ("scripts/site_data.py", "scripts/build_site.py"):
            if sh([step]).returncode != 0:
                print(f"  FAILED: {os.path.basename(step)}; the page was not rebuilt, nothing to publish"); return 1
        if not a.quick:
            json.dump({"complete_through": newest, "run": json.load(open(os.path.join(LATEST, "run_summary.json"))).get("stamp")}, open(STATE, "w"))
        after = json.load(open(os.path.join(LATEST, "markets.json")))
        moved = what_moved(before, after)
        print("  moved: " + ("; ".join(moved) if moved else "nothing by 2 points or more"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
