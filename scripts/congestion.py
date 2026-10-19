#!/usr/bin/env python3
"""Rest and congestion against Pinnacle's close (the "how much does the close price a short week" study).

For every lined MLS match: days since each side's previous competitive match (MLS plus the four cups from the OpticOdds
harvest for 2025-2026; MLS only for 2012-2024, where the cups are not on file) and the number of matches each side played in
the previous 7 and 14 days. The residual is the close's expected margin minus the model's (a close_track per-close file,
one recipe at lag 0, both sides net of the home edge), regressed on the home-minus-away difference of each feature.
A coefficient is in goals of expected margin per unit of the feature difference; the close already carries whatever Pinnacle
prices for rest, so a non-zero coefficient is a feature the ratings should carry to track the close.

Usage: python3 scripts/congestion.py --track outputs/calibration/close_track/kf_var1.csv --recipe kf   (the plain Kalman filter, as
CLAUDE.md 13 quotes; wls1.csv / "live" is the retired least-squares fit)
"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.teams import ROOT, canon

OPTIC = os.path.join(ROOT, "data", "optic")


def all_matches() -> pd.DataFrame:
    """Every competitive match per MLS club: (date, team, competition). History files (MLS, 2012-2026) plus the OpticOdds
    fixtures (MLS and cups, 2025-2026, completed only)."""
    rows = []
    h = data.load_history()
    h = h.drop_duplicates(["season", "date", "home", "away"])
    for r in h.itertuples(index=False):
        d = str(pd.Timestamp(r.date).date())
        rows.append((d, r.home, "mls")); rows.append((d, r.away, "mls"))
    res = data.load("results")
    for r in res.itertuples(index=False):
        rows.append((r.date, r.home, "mls" if r.competition in ("MLS", "") else str(r.competition).lower())); rows.append((r.date, r.away, "mls" if r.competition in ("MLS", "") else str(r.competition).lower()))
    for comp in ("leagues_cup", "concacaf_champions_cup", "us_open_cup", "canadian_championship"):
        p = os.path.join(OPTIC, f"fixtures_{comp}.csv")
        if not os.path.exists(p):
            continue
        f = pd.read_csv(p, dtype=str, keep_default_na=False)
        f = f[f["status"] == "completed"]
        for r in f.itertuples(index=False):
            d = str((pd.Timestamp(r.start_date) - pd.Timedelta(hours=4)).date())  # ET date
            for t in (r.home, r.away):
                c = canon(t, strict=False)
                if c:
                    rows.append((d, c, comp))
    m = pd.DataFrame(rows, columns=["date", "team", "comp"]).drop_duplicates(["date", "team"])
    return m.sort_values(["team", "date"]).reset_index(drop=True)


def features(m: pd.DataFrame, mls_only: bool) -> pd.DataFrame:
    """Per (date, team): days since the previous match (capped at 14), matches in the previous 7 and 14 days."""
    mm = m[m["comp"] == "mls"] if mls_only else m
    out = []
    for t, g in mm.groupby("team"):
        d = pd.to_datetime(g["date"]).to_numpy()
        for i in range(len(d)):
            prev = d[:i]
            rest = float((d[i] - prev[-1]) / np.timedelta64(1, "D")) if len(prev) else 14.0
            n7 = int(((d[i] - prev) <= np.timedelta64(7, "D")).sum()) if len(prev) else 0
            n14 = int(((d[i] - prev) <= np.timedelta64(14, "D")).sum()) if len(prev) else 0
            out.append((str(pd.Timestamp(d[i]).date()), t, min(rest, 14.0), n7, n14))
    return pd.DataFrame(out, columns=["date", "team", "rest", "n7", "n14"])


def ols(y, X, names):
    X = np.column_stack([np.ones(len(y))] + [np.asarray(x, float) for x in X]); y = np.asarray(y, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    s2 = float(resid @ resid) / max(1, len(y) - X.shape[1])
    cov = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    return {n: (float(b), float(e)) for n, b, e in zip(["const"] + names, beta, se)}, float(np.sqrt(s2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--track", required=True); ap.add_argument("--recipe", default="kf"); ap.add_argument("--lag", type=int, default=0)
    a = ap.parse_args()
    tr = pd.read_csv(a.track, dtype={"season": str}); tr = tr[(tr["recipe"] == a.recipe) & (tr["lag"] == a.lag)].copy()
    tr["e"] = tr["y_close"] - tr["y_model"]
    m = all_matches()
    lines = []
    for label, mls_only, seasons in (("MLS + cups, 2025-2026", False, ["2025", "2026"]), ("MLS only, 2025-2026", True, ["2025", "2026"]), ("MLS only, 2012-2026", True, None)):
        f = features(m, mls_only)
        d = tr if seasons is None else tr[tr["season"].isin(seasons)]
        d = d.merge(f.rename(columns={"team": "home", "rest": "rest_h", "n7": "n7_h", "n14": "n14_h"}), on=["date", "home"], how="left")
        d = d.merge(f.rename(columns={"team": "away", "rest": "rest_a", "n7": "n7_a", "n14": "n14_a"}), on=["date", "away"], how="left").dropna(subset=["rest_h", "rest_a"])
        d["drest"] = d["rest_h"].clip(upper=10) - d["rest_a"].clip(upper=10); d["dn7"] = d["n7_h"] - d["n7_a"]; d["dn14"] = d["n14_h"] - d["n14_a"]
        d["short_h"] = (d["rest_h"] <= 3).astype(float); d["short_a"] = (d["rest_a"] <= 3).astype(float)
        d["long_h"] = (d["rest_h"] >= 7).astype(float); d["long_a"] = (d["rest_a"] >= 7).astype(float)
        lines.append(f"\n== {label}: {len(d)} lined matches, residual sd {d['e'].std():.3f} (close minus {a.recipe} at lag {a.lag})")
        b, s = ols(d["e"], [d["drest"]], ["rest_diff (days, capped 10)"]); lines.append("  " + ", ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b.items()))
        b, s = ols(d["e"], [d["dn7"]], ["matches_last7_diff"]); lines.append("  " + ", ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b.items()))
        b, s = ols(d["e"], [d["dn14"]], ["matches_last14_diff"]); lines.append("  " + ", ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b.items()))
        b, s = ols(d["e"], [d["short_h"] - d["short_a"], d["long_h"] - d["long_a"]], ["short_week(<=3d) h-a", "long_rest(>=7d) h-a"]); lines.append("  " + ", ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b.items()))
        # the raw close against the same features (does Pinnacle price rest at all, independent of our ratings?)
        b, s = ols(d["y_close"], [d["y_model"], d["drest"]], ["model", "rest_diff"]); lines.append("  close on model + rest: " + ", ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b.items()))
        tab = d.groupby(pd.cut(d["drest"], [-11, -3.5, -0.5, 0.5, 3.5, 11]), observed=True)["e"].agg(["mean", "count"])
        lines.append("  residual by rest difference (home minus away days):\n" + tab.to_string())
    txt = "\n".join(lines)
    print(txt)
    os.makedirs(os.path.join(ROOT, "outputs", "calibration"), exist_ok=True)
    with open(os.path.join(ROOT, "outputs", "calibration", "congestion.md"), "w") as fh:
        fh.write("# Rest and congestion against the close\n\n```\n" + txt + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
