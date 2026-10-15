#!/usr/bin/env python3
"""Synthetic data for smoke tests only (NEVER written into data/ of the real repo): builds a scratch copy of the repo with a fake
schedule, results, closes, three history seasons and xG consistent with the engine, then the real scripts run against it.
Usage: python3 tests/synth.py /path/to/scratch_repo [--asof 2026-10-12]"""
from __future__ import annotations
import argparse, datetime as dt, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim.teams import ROOT, teams, conference_of
from sim.engine import score_grid, hda_from_grid, ah_home_fair, total_over_fair, sample_goals


def fake_prices(g, T, rng, hold=0.04):
    P = score_grid(g, T, 0.15, 0.15)
    h, d, a = hda_from_grid(P)
    k = 1 + hold
    jitter = lambda p: max(0.02, p * (1 + rng.normal(0, 0.02)))
    line = round(-g * 4) / 4.0
    pah = ah_home_fair(P, line)
    tl = round(T * 4) / 4.0
    po = total_over_fair(P, tl)
    return {"h": round(1 / (jitter(h) * k), 3), "d": round(1 / (jitter(d) * k), 3), "a": round(1 / (jitter(a) * k), 3),
            "ah_line": line, "ah_home": round(1 / (pah * (1 + hold / 2)), 3), "ah_away": round(1 / ((1 - pah) * (1 + hold / 2)), 3),
            "total_line": tl, "over": round(1 / (po * (1 + hold / 2)), 3), "under": round(1 / ((1 - po) * (1 + hold / 2)), 3)}


def season_fixtures(T, year, rng, start=(2, 21), end=(11, 7)):
    """34 per club: 24 intra-conference-ish, 10 cross. Dates spread weekly with midweeks, skipping the World Cup pause in 2026."""
    conf = conference_of(); east = [t for t in T if conf[t] == "East"]; west = [t for t in T if conf[t] == "West"]
    pairs = []
    for group in (east, west):
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                pairs.append((a, b)); pairs.append((b, a))  # 28 intra each -> too many; thin below
    rng.shuffle(pairs)
    count = {t: 0 for t in T}; chosen = []
    for a, b in pairs:
        if count[a] < 24 and count[b] < 24:
            chosen.append((a, b)); count[a] += 1; count[b] += 1
    cross = [(a, b) for a in east for b in west] + [(b, a) for a in east for b in west]
    rng.shuffle(cross)
    for a, b in cross:
        if count[a] < 34 and count[b] < 34:
            chosen.append((a, b)); count[a] += 1; count[b] += 1
    rng.shuffle(chosen)
    d0 = dt.date(year, *start); d1 = dt.date(year, *end)
    days = []
    d = d0
    while d <= d1:
        if year == 2026 and dt.date(2026, 5, 25) <= d <= dt.date(2026, 7, 15):
            d += dt.timedelta(days=1); continue
        if d.weekday() in (5, 2):  # Saturdays and Wednesdays
            days.append(d)
        d += dt.timedelta(days=1)
    rows = []
    per_day = int(np.ceil(len(chosen) / len(days)))
    busy = {}
    i = 0
    for day in days:
        n = 0
        for a, b in list(chosen[i:]):
            if n >= per_day:
                break
            if busy.get((day, a)) or busy.get((day, b)):
                continue
            busy[(day, a)] = busy[(day, b)] = True
            ko = dt.datetime(day.year, day.month, day.day, 23, 30, tzinfo=dt.timezone.utc) if day.weekday() == 5 else dt.datetime(day.year, day.month, day.day, 23, 30, tzinfo=dt.timezone.utc)
            rows.append({"date": day.isoformat(), "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "round": "", "home": a, "away": b, "competition": "MLS", "status": "scheduled", "espn_id": f"syn{year}{len(rows)}"})
            chosen.remove((a, b)); n += 1
        # leftovers roll to the next day
    for a, b in chosen:
        day = days[-1]; rows.append({"date": day.isoformat(), "kickoff_utc": f"{day.isoformat()}T23:30:00Z", "round": "", "home": a, "away": b, "competition": "MLS", "status": "scheduled", "espn_id": f"syn{year}x{len(rows)}"})
    return pd.DataFrame(rows).sort_values(["kickoff_utc", "home"]).reset_index(drop=True)


def build(dst: str, asof: str, seed=42):
    rng = np.random.default_rng(seed)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "outputs", "__pycache__", "node_modules"))
    os.makedirs(os.path.join(dst, "outputs", "latest"), exist_ok=True)
    T = teams(); HE, TOT = 0.35, 3.0
    hist = []
    for year in (2023, 2024, 2025, 2026):
        R = rng.normal(0, 0.35, 30); R -= R.mean(); R = dict(zip(T, R))
        sch = season_fixtures(T, year, rng)
        res, closes, xg = [], [], []
        for r in sch.itertuples(index=False):
            if year == 2026 and r.date >= asof:
                break
            # the market knows ratings up to noise; ratings drift slowly across the season
            g = R[r.home] - R[r.away] + HE + rng.normal(0, 0.08)
            pr = fake_prices(g, TOT + rng.normal(0, 0.15), rng)
            hg, ag = sample_goals(rng, np.array([g]), np.array([TOT]), 0.15, 0.15)
            res.append({"date": r.date, "home": r.home, "away": r.away, "hg": int(hg[0]), "ag": int(ag[0]), "competition": "MLS", "source": "synthetic"})
            closes.append({"date": r.date, "kickoff_utc": r.kickoff_utc, "home": r.home, "away": r.away, "book": "pinnacle_close", **pr, "fetched_at": r.kickoff_utc, "fixture_id": r.espn_id})
            xg.append({"date": r.date, "home": r.home, "away": r.away, "home_xg": round(max(0.1, TOT / 2 + g / 2 + rng.normal(0, 0.5)), 2), "away_xg": round(max(0.1, TOT / 2 - g / 2 + rng.normal(0, 0.5)), 2), "source": "synthetic", "game_id": r.espn_id})
            for t in (r.home, r.away):
                R[t] += rng.normal(0, 0.01)
        if year < 2026:
            h = pd.DataFrame(closes).merge(pd.DataFrame(res)[["date", "home", "away", "hg", "ag"]], on=["date", "home", "away"])
            h["season"] = str(year)
            h[["season", "date", "home", "away", "hg", "ag", "h", "d", "a", "book", "ah_line", "ah_home", "ah_away", "total_line", "over", "under"]].to_csv(os.path.join(dst, "data", "history", f"USA_{year}.csv"), index=False)
            hist.append(pd.DataFrame(xg))
        else:
            sch.loc[sch["date"] < asof, "status"] = "final"
            sch.to_csv(os.path.join(dst, "data", "schedule.csv"), index=False)
            pd.DataFrame(res).to_csv(os.path.join(dst, "data", "results.csv"), index=False)
            pd.DataFrame(closes).to_csv(os.path.join(dst, "data", "market", "closing_lines.csv"), index=False)
            hist.append(pd.DataFrame(xg))
            # posted lines for the next week
            posted = []
            for r in sch[(sch["date"] >= asof)].head(16).itertuples(index=False):
                g = R[r.home] - R[r.away] + HE + rng.normal(0, 0.12)
                pr = fake_prices(g, TOT, rng)
                posted.append({"date": r.date, "kickoff_utc": r.kickoff_utc, "home": r.home, "away": r.away, "book": "pinnacle", **pr, "fetched_at": f"{asof}T12:00:00Z", "fixture_id": r.espn_id})
            pd.DataFrame(posted).to_csv(os.path.join(dst, "data", "market", "current_round_odds.csv"), index=False)
            pd.DataFrame([{"team": "Inter Miami", "player": "Star Player", "value_goals": "", "out_from": (dt.date.fromisoformat(asof) - dt.timedelta(days=5)).isoformat(), "expected_return": (dt.date.fromisoformat(asof) + dt.timedelta(days=20)).isoformat(), "prob_out": 1.0, "tier": "star", "note": "synthetic", "source": "synthetic", "updated": asof}]).to_csv(os.path.join(dst, "data", "ratings", "injuries.csv"), index=False)
            pd.DataFrame([{"team": "Nashville SC", "type": "points", "prob": 0.3, "mean": 6, "sd": 2, "min": 3, "from": "", "to": "", "note": "synthetic scenario"}]).to_csv(os.path.join(dst, "data", "ratings", "scenarios.csv"), index=False)
    pd.concat(hist).to_csv(os.path.join(dst, "data", "ratings", "xg_history.csv"), index=False)
    print(f"synth: scratch repo at {dst}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("dst"); ap.add_argument("--asof", default="2026-10-12"); a = ap.parse_args()
    build(a.dst, a.asof)
