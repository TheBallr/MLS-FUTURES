#!/usr/bin/env python3
"""What-if: today's futures under alternative knobs or rating recipes, against the current configuration, same inputs, same
seed. Nothing is written to config.json or data/; this is the "how much it moves the futures probabilities" line of a proposal.
Fixtures are built exactly as scripts/run_sim.py builds them (layers, posted-line shrink, club home edge).

Usage: python3 scripts/what_if.py --n 100000 --asof 2026-10-15 \
         --alt "sd0.2_k0.01:rating_sd=0.2,drift_k_sim=0.01" --alt "ridge0:ridge_lambda=0" --alt "x90:xg_half_life_days=90"
Each --alt is name:key=value[,key=value]; keys are config knobs (rating_sd, drift_k_sim, drift_cap, ridge_lambda, half_life_days,
xg_half_life_days, shared_goals_mean ...) or the special keys xg_w (xG weight share, e.g. 0.25) and spread_mult."""
from __future__ import annotations
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import teams, conference_of, ROOT
from sim.season import SeasonInputs, Fixture, run_seasons
from sim.markets import Archive, all_markets
from sim.layers import team_penalty, hand_adjustment, scenarios_for_engine
from sim.ratings import gd_fit_row, home_edge_for
from scripts.refresh_ratings import build_ratings, closes_with_targets
from scripts.run_sim import played_stats, latest_posted, played_h2h, disc_points
from scripts.common import today_et

POOLS = ["cup", "shield", "east", "west", "playoffs", "conf_top4", "cup_finalist"]


def parse_alt(s: str) -> tuple[str, dict]:
    name, _, body = s.partition(":")
    kv = {}
    for part in body.split(","):
        if not part:
            continue
        k, _, v = part.partition("=")
        kv[k.strip()] = float(v)
    return name, kv


def ratings_with(cfg: dict, asof: str, closes, kv: dict) -> dict:
    """build_ratings with knob overrides (ridge, half-lives) and an optional xG weight share / spread multiplier."""
    c = json.loads(json.dumps(cfg))
    for k, v in kv.items():
        if k in c["knobs"]:
            c["knobs"][k]["value"] = v
    rat = build_ratings(asof, c, closes=closes, write=False)
    if "xg_w" in kv:
        src = rat["sources"]
        w = float(kv["xg_w"])
        R = (1 - w) * src["market_recent"] + w * src.get("xg", src["market_recent"]) if w > 0 else src["market_recent"]
        rat["ratings"] = R - R.mean()
    if "fdb_w" in kv:  # footballdatabase Elo-style points, latest monthly value before asof, rescaled to the market's spread (PDF blend step)
        fp = os.path.join(ROOT, "data", "public", "footballdatabase", "history.csv")
        f = pd.read_csv(fp); f = f[f["date"] < asof]; snap = f[f["date"] == f["date"].max()].set_index("team")["points"]
        v = np.array([snap.get(t, np.nan) for t in rat["teams"]], float); v = np.where(np.isnan(v), np.nanmean(v), v); v = v - v.mean()
        Rm = rat["sources"]["market_recent"]; v = v * (Rm.std() / v.std())
        w = float(kv["fdb_w"]); R = (1 - w) * rat["ratings"] + w * v; rat["ratings"] = R - R.mean()
    if "spread_mult" in kv:
        rat["ratings"] = rat["ratings"] * float(kv["spread_mult"])
    return rat


def build_fixtures(cfg, kn, asof, rat, T, idx, closes):
    sched = data.load("schedule"); res = data.load("results")
    res = res[res["competition"].isin(["MLS", ""])]
    sched = sched[sched["competition"] == "MLS"] if len(sched) else sched
    played_keys = set(zip(res["date"], res["home"], res["away"]))
    played = played_stats(res, T)
    unplayed = [r for r in sched.to_dict("records") if (r["date"], r["home"], r["away"]) not in played_keys]
    unplayed.sort(key=lambda r: (r["kickoff_utc"], r["home"]))
    inj, cal, adj = data.load("injuries"), data.load("callups"), data.load("adjustments")
    posted = latest_posted(data.load("current_round_odds"), asof=asof)
    season_closes = closes[closes["season"].astype(str) == str(cfg["season"])]
    tiers = kn["injury_tiers"]; s_knob = kn["posted_line_shrink"]; R = rat["ratings"]
    fixtures = []
    for r in unplayed:
        h, aw = r["home"], r["away"]
        if h not in idx or aw not in idx:
            continue
        ph = team_penalty(h, r["date"], inj, cal, season_closes, asof, kn["half_life_days"], tiers, True, True)
        pa = team_penalty(aw, r["date"], inj, cal, season_closes, asof, kn["half_life_days"], tiers, True, True)
        hand = hand_adjustment(h, r["date"], adj) - hand_adjustment(aw, r["date"], adj)
        layer = (ph["injury"] - pa["injury"]) * (1 if kn["injury_layer_enabled"] else 0) + (ph["callup"] - pa["callup"]) * (1 if kn["callup_layer_enabled"] else 0)
        adj_total = home_edge_for(h, kn["home_edge_goals"], rat.get("club_deltas")) + hand + layer
        line = posted.get((r["date"], h, aw))
        s, g_pinn, Tt = 0.0, 0.0, kn["avg_total_goals"]
        if line:
            gf = gd_fit_row(line.get("h"), line.get("d"), line.get("a"), line.get("ah_line") or None, line.get("ah_home"), line.get("ah_away"),
                            line.get("total_line") or None, line.get("over"), line.get("under"), kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"])
            if np.isfinite(gf["gd_fit"]):
                s, g_pinn, Tt = s_knob, float(gf["gd_fit"]), float(gf["T_fit"]) if np.isfinite(gf["T_fit"]) else Tt
        fixtures.append(Fixture(idx[h], idx[aw], r["date"], adj=adj_total, s=s, g_pinn=g_pinn, T=Tt))
    return fixtures, played, len(res)


def run_variant(cfg, asof, closes, kv: dict, n: int, T, conf, idx):
    kn = knobs(cfg)
    for k, v in kv.items():
        if k in kn:
            kn[k] = v
    rat = ratings_with(cfg, asof, closes, kv)
    fixtures, played, nres = build_fixtures(cfg, kn, asof, rat, T, idx, closes)
    scen = scenarios_for_engine(data.load("scenarios"), T)
    res = data.load("results"); res = res[res["competition"].isin(["MLS", ""])]; hp, hg_ = played_h2h(res, T)
    h2h_on = bool(kn.get("tiebreak_h2h", False))
    out = run_seasons(SeasonInputs(T, conf, rat["ratings"], fixtures, played, scen, disc=disc_points(T, cfg["season"], bool(kn.get("disc_points_enabled", False))),
                                   h2h_pts=hp if h2h_on else None, h2h_gd=hg_ if h2h_on else None), kn, n_seasons=n)
    mk = all_markets(Archive(out), kn["shade"], {s["team"] for s in scen})
    return mk, rat, len(fixtures), nres


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=today_et().isoformat()); ap.add_argument("--n", type=int, default=100000)
    ap.add_argument("--alt", action="append", default=[]); ap.add_argument("--top", type=int, default=8); ap.add_argument("--json")
    a = ap.parse_args()
    cfg = load_config(); T = teams(); cm = conference_of(); conf = np.array([0 if cm[t] == "East" else 1 for t in T]); idx = {t: i for i, t in enumerate(T)}
    closes = closes_with_targets(cfg)
    base, rat0, nfx, nres = run_variant(cfg, a.asof, closes, {}, a.n, T, conf, idx)
    print(f"what_if: asof {a.asof}, {nres} results on file, {nfx} fixtures left, {a.n} seasons; baseline = current config (blend sd {rat0['ratings'].std():.3f})")
    results = {"baseline": base}
    for s in a.alt:
        name, kv = parse_alt(s)
        mk, rat, _, _ = run_variant(cfg, a.asof, closes, kv, a.n, T, conf, idx)
        results[name] = mk
        print(f"\n== {name}: {kv} (blend sd {rat['ratings'].std():.3f}, ratio to baseline {rat['ratings'].std() / rat0['ratings'].std():.3f})")
        for pool in POOLS:
            b = base[pool]; m = mk[pool]
            teams_sorted = sorted(b, key=lambda t: -b[t]["prob"])
            moves = sorted(((t, b[t]["prob"], m[t]["prob"]) for t in b), key=lambda x: -abs(x[2] - x[1]))
            top = [(t, b[t]["prob"], m[t]["prob"]) for t in teams_sorted[: a.top]]
            print(f"  {pool}: " + ", ".join(f"{t} {p0*100:.1f}->{p1*100:.1f}" for t, p0, p1 in top))
            big = [x for x in moves[:4] if abs(x[2] - x[1]) >= 0.005 and x[0] not in teams_sorted[: a.top]]
            if big:
                print(f"    other moves: " + ", ".join(f"{t} {p0*100:.1f}->{p1*100:.1f}" for t, p0, p1 in big))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(results, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
