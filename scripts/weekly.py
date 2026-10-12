#!/usr/bin/env python3
"""The 8:52 ET routine: fetch Pinnacle lines (and OpticOdds when the key lives), list capture slots, and if a round has finished
since the last run (every fixture of a calendar match-day has a result), apply pending site settings, run the full model, build the
site, and print what moved. --force runs the model regardless.
Usage: python3 scripts/weekly.py [--force] [--quick]"""
import argparse, datetime as dt, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import data
from sim.teams import ROOT
from scripts.common import today_et

LATEST = os.path.join(ROOT, "outputs", "latest")


def sh(cmd):
    r = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    out = (r.stdout.strip().splitlines() or [""])[-1]
    print(f"  {os.path.basename(cmd[0])}: {out}")
    if r.returncode not in (0, 2) and r.stderr.strip():
        print("   " + r.stderr.strip().splitlines()[-1])
    return r


def round_finished_since_last_run() -> tuple[bool, str]:
    sch = data.load("schedule"); res = data.load("results")
    if len(sch) == 0:
        return False, "no schedule"
    last = None
    p = os.path.join(LATEST, "run_summary.json")
    if os.path.exists(p):
        last = json.load(open(p)).get("results_through")
    played = set(zip(res["date"], res["home"], res["away"]))
    days = sorted(set(sch[sch["competition"] == "MLS"]["date"]))
    done_days = [d for d in days if all((r["date"], r["home"], r["away"]) in played for r in sch[sch["date"] == d].to_dict("records"))]
    if not done_days:
        return False, "no completed match-day"
    newest = done_days[-1]
    return (last is None or newest > last), f"newest complete match-day {newest}, last run through {last}"


def what_moved(before: dict | None, after: dict) -> list[str]:
    if not before:
        return []
    out = []
    for pool in ("shield", "cup", "east", "west", "playoffs"):
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
        sh(["scripts/run_sim.py"] + (["--quick"] if a.quick else []))
        sh(["scripts/site_data.py"]); sh(["scripts/build_site.py"])
        after = json.load(open(os.path.join(LATEST, "markets.json")))
        moved = what_moved(before, after)
        print("  moved: " + ("; ".join(moved) if moved else "nothing by 2 points or more"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
