#!/usr/bin/env python3
"""One close-capture task (ten minutes before each distinct kickoff; Zac 2026-10-19 "do 2"): take Pinnacle's line for every fixture
kicking off within 25 minutes as its close (fetch_pinnacle.py --close, retries built in), then rebuild the page data and the page
(site_data.py, build_site.py; no model rerun, so the futures stay the morning run's) so the top-corner "Last close" is current.
Exit 1 when a due fixture's close is missing (the morning's close_fallback.py fills it from the last line before kickoff).
The task then publishes outputs/latest/site.html and commits. Usage: python3 scripts/close_capture.py"""
import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd):
    r = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    out = (r.stdout.strip().splitlines() or [""])
    print("\n".join(out[-15:]) if cmd[0].endswith("fetch_pinnacle.py") else out[-1])
    if r.returncode != 0 and r.stderr.strip():
        print("  " + r.stderr.strip().splitlines()[-1])
    return r.returncode


if __name__ == "__main__":
    code = run(["scripts/fetch_pinnacle.py", "--close"])
    page = run(["scripts/site_data.py"]) or run(["scripts/build_site.py"])
    print("close_capture: page rebuilt" if page == 0 else "close_capture: page NOT rebuilt (publish nothing)")
    sys.exit(code or page)
