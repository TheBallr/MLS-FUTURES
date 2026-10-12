#!/usr/bin/env python3
"""Pre-push guard: fail if the live OpticOdds key (or any UUID-shaped key) is in the tree or the staged diff. Run before every push."""
import os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
key = os.environ.get("OPTIC_API_KEY", "").strip()
pat = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
bad = []
files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout.decode().split("\0")
files += subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT, capture_output=True).stdout.decode().split("\0")
for f in sorted(set(x for x in files if x)):
    p = os.path.join(ROOT, f)
    if not os.path.isfile(p) or os.path.getsize(p) > 50_000_000:
        continue
    try:
        text = open(p, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    if key and key in text:
        bad.append((f, "live key"))
    elif pat.search(text) and f.endswith((".py", ".md", ".json", ".html", ".csv", ".txt", ".js")):
        if "data/optic/raw" not in f:
            bad.append((f, "uuid-shaped token: " + pat.search(text).group(0)[:13] + "..."))
if bad:
    for f, why in bad:
        print(f"check_secrets: {f}: {why}")
    sys.exit(1)
print("check_secrets: clean")
