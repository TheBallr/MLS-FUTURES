#!/usr/bin/env python3
"""Full run: ratings -> fixtures with layers and posted-line shrink -> N seasons -> archive -> markets -> forecast check -> CLV log.
Outputs outputs/latest/{seasons.npz, markets.json, predictions.csv, games.csv, run_summary.json}, copied to outputs/runs/<stamp>/.
Usage: python3 scripts/run_sim.py [--asof YYYY-MM-DD] [--n 200000] [--quick]"""
from __future__ import annotations
import argparse, datetime as dt, json, os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import teams, conference_of, ROOT
from sim.season import SeasonInputs, Fixture, run_seasons, empty_played
from sim.markets import Archive, all_markets
from sim.engine import hda
from sim.layers import team_penalty, hand_adjustment, scenarios_for_engine
from sim.ratings import gd_fit_row, home_edge_for
from scripts.refresh_ratings import build_ratings, closes_with_targets
from scripts.common import today_et, now_utc, utc_iso

LATEST = os.path.join(ROOT, "outputs", "latest")
RUNS = os.path.join(ROOT, "outputs", "runs")


def played_stats(results: pd.DataFrame, T: list) -> dict:
    idx = {t: i for i, t in enumerate(T)}
    st = empty_played(len(T))
    for r in results.itertuples(index=False):
        if r.home not in idx or r.away not in idx:
            continue
        h, a = idx[r.home], idx[r.away]
        try:
            hg, ag = int(float(r.hg)), int(float(r.ag))
        except (TypeError, ValueError):
            continue
        m = hg - ag
        st["points"][h] += 3 if m > 0 else (1 if m == 0 else 0); st["points"][a] += 3 if m < 0 else (1 if m == 0 else 0)
        st["wins"][h] += m > 0; st["wins"][a] += m < 0
        st["gd"][h] += m; st["gd"][a] -= m; st["gf"][h] += hg; st["gf"][a] += ag
        st["home_gd"][h] += m; st["home_gf"][h] += hg; st["away_gd"][a] -= m; st["away_gf"][a] += ag
    return st


def played_h2h(results: pd.DataFrame, T: list) -> tuple[np.ndarray, np.ndarray]:
    """(T,T) points and goal difference of i against j in the real matches so far, for the head-to-head tiebreaker."""
    idx = {t: i for i, t in enumerate(T)}
    P = np.zeros((len(T), len(T)), dtype=np.int16); G = np.zeros((len(T), len(T)), dtype=np.int16)
    for r in results.itertuples(index=False):
        if r.home not in idx or r.away not in idx:
            continue
        try:
            hg, ag = int(float(r.hg)), int(float(r.ag))
        except (TypeError, ValueError):
            continue
        h, a = idx[r.home], idx[r.away]; m = hg - ag
        P[h, a] += 3 if m > 0 else (1 if m == 0 else 0); P[a, h] += 3 if m < 0 else (1 if m == 0 else 0)
        G[h, a] += m; G[a, h] -= m
    return P, G


def disc_points(T: list, season, enabled: bool) -> np.ndarray:
    """(T,) disciplinary points to date from data/discipline/disc_points_<season>.csv (zeros when off or missing)."""
    out = np.zeros(len(T))
    if not enabled:
        return out
    p = os.path.join(ROOT, "data", "discipline", f"disc_points_{season}.csv")
    if os.path.exists(p):
        d = pd.read_csv(p).set_index("team")["points"]
        out = np.array([float(d.get(t, 0.0)) for t in T])
    return out


def latest_posted(odds: pd.DataFrame, fresh_days: float = 3.0, asof=None) -> dict:
    """Latest Pinnacle posted line per (date, home, away), fetched within fresh_days of asof."""
    if len(odds) == 0:
        return {}
    o = odds[odds["book"].str.lower().isin(["pinnacle", "pinnacle_last", "pinnacle_close"])].copy()
    o = o.sort_values("fetched_at").drop_duplicates(["date", "home", "away"], keep="last")
    out = {}
    cutoff = (pd.Timestamp(asof or dt.date.today()) - pd.Timedelta(days=fresh_days))
    for r in o.to_dict("records"):
        try:
            f = pd.Timestamp(r["fetched_at"]).tz_localize(None)
        except Exception:
            continue
        if f >= cutoff:
            out[(r["date"], r["home"], r["away"])] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=today_et().isoformat())
    ap.add_argument("--n", type=int, default=None); ap.add_argument("--quick", action="store_true", help="20k seasons, no archive copy")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    cfg = load_config(); kn = knobs(cfg)
    if a.quick:
        kn["n_seasons"] = 20000
    if a.n:
        kn["n_seasons"] = a.n
    T = teams(); conf_map = conference_of(); conf = np.array([0 if conf_map[t] == "East" else 1 for t in T]); idx = {t: i for i, t in enumerate(T)}
    asof = a.asof
    closes = closes_with_targets(cfg)
    rat = build_ratings(asof, cfg, closes=closes, write=not a.no_write)
    R = rat["ratings"]
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
    tiers = kn["injury_tiers"]; s_knob = kn["posted_line_shrink"]
    fixtures, preds = [], []
    for r in unplayed:
        h, aw = r["home"], r["away"]
        if h not in idx or aw not in idx:
            continue
        ph = team_penalty(h, r["date"], inj, cal, season_closes, asof, kn["half_life_days"], tiers, True, True)
        pa = team_penalty(aw, r["date"], inj, cal, season_closes, asof, kn["half_life_days"], tiers, True, True)
        hand = hand_adjustment(h, r["date"], adj) - hand_adjustment(aw, r["date"], adj)
        layer_raw = (ph["injury"] - pa["injury"]) * (1 if kn["injury_layer_enabled"] else 0) + (ph["callup"] - pa["callup"]) * (1 if kn["callup_layer_enabled"] else 0)
        layer_full = (ph["injury"] + ph["callup"]) - (pa["injury"] + pa["callup"])  # what the layers would apply if both were on (measured every run)
        layer = layer_raw
        adj_total = home_edge_for(h, kn["home_edge_goals"], rat.get("club_deltas")) + hand + layer
        g_model = float(R[idx[h]] - R[idx[aw]] + adj_total)
        line = posted.get((r["date"], h, aw))
        s, g_pinn, Tt = 0.0, float("nan"), kn["avg_total_goals"]
        if line:
            gf = gd_fit_row(line.get("h"), line.get("d"), line.get("a"), line.get("ah_line") or None, line.get("ah_home"), line.get("ah_away"),
                            line.get("total_line") or None, line.get("over"), line.get("under"), kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
            if np.isfinite(gf["gd_fit"]):
                s, g_pinn, Tt = s_knob, float(gf["gd_fit"]), float(gf["T_fit"]) if np.isfinite(gf["T_fit"]) else Tt
        g_used = (1 - s) * g_model + s * g_pinn if s > 0 else g_model
        fixtures.append(Fixture(idx[h], idx[aw], r["date"], adj=adj_total, s=s, g_pinn=g_pinn if s > 0 else 0.0, T=Tt))
        mh, md, ma = hda(g_used, Tt, kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
        preds.append({"date": r["date"], "kickoff_utc": r["kickoff_utc"], "home": h, "away": aw, "g_model": round(g_model, 3), "g_pinn": round(g_pinn, 3) if s > 0 else "",
                      "g_used": round(g_used, 3), "T": round(Tt, 2), "p_home": round(mh, 4), "p_draw": round(md, 4), "p_away": round(ma, 4),
                      "layer_goals": round(layer, 3), "layer_full": round(layer_full, 3), "hand_goals": round(hand, 3), "shrink": s,
                      "pinn_h": round(gf["ph"], 4) if line and np.isfinite(gf["ph"]) else "", "pinn_d": round(gf["pd"], 4) if line and np.isfinite(gf["pd"]) else "", "pinn_a": round(gf["pa"], 4) if line and np.isfinite(gf["pa"]) else ""})
    scen = scenarios_for_engine(data.load("scenarios"), T)
    hp, hg_ = played_h2h(res, T)
    inp = SeasonInputs(T, conf, R, fixtures, played, scen, disc=disc_points(T, cfg["season"], kn.get("disc_points_enabled", False)),
                       h2h_pts=hp if kn.get("tiebreak_h2h", False) else None, h2h_gd=hg_ if kn.get("tiebreak_h2h", False) else None)
    out = run_seasons(inp, kn)
    arc = Archive(out)
    exempt = {s["team"] for s in scen}
    markets = all_markets(arc, kn["shade"], exempt)
    # forecast check: closes-only ratings vs today's posted lines (out of sample)
    fc = [(p["g_model"], float(p["g_pinn"]), p["layer_full"] - p["layer_goals"]) for p in preds if p["g_pinn"] != ""]
    forecast = {"n": len(fc)}
    if fc:
        d = np.array([m - p for m, p, _ in fc]); forecast.update(rmse=float(np.sqrt((d ** 2).mean())), bias=float(d.mean()))
        d2 = np.array([m + extra - p for m, p, extra in fc]); forecast.update(rmse_layers_on=float(np.sqrt((d2 ** 2).mean())), mean_abs_layer=float(np.mean([abs(x) for _, _, x in fc])))
        # running log of the layer measurement (section 8 of CLAUDE.md): one row per run
        lp = os.path.join(ROOT, "outputs", "calibration", "layers_log.csv")
        os.makedirs(os.path.dirname(lp), exist_ok=True)
        with open(lp, "a") as f:
            if os.path.getsize(lp) == 0:
                f.write("asof,n_lines,rmse_off,rmse_on,mean_abs_layer,injury_on,callup_on\n")
            f.write(f"{asof},{len(fc)},{forecast['rmse']:.4f},{forecast['rmse_layers_on']:.4f},{forecast['mean_abs_layer']:.4f},{int(kn['injury_layer_enabled'])},{int(kn['callup_layer_enabled'])}\n")
    stamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    summary = {"asof": asof, "run_utc": utc_iso(now_utc()), "stamp": stamp, "n_seasons": kn["n_seasons"], "seed": kn["seed"],
               "fixtures_remaining": len(fixtures), "results_on_file": int(len(res)), "results_through": str(res["date"].max()) if len(res) else None,
               "closes_in_fit": rat["market_fit"]["n"], "fit_resid_sd": rat["market_fit"]["resid_sd"], "weights": rat["weights"], "xg_games": rat["xg_n"],
               "forecast_check": forecast, "posted_lines": len(posted), "odds_fetched_at": max((v["fetched_at"] for v in posted.values()), default=None),
               "knobs": kn, "scenarios": scen, "seconds": round(time.time() - t0, 1)}
    if not a.no_write:
        os.makedirs(LATEST, exist_ok=True)
        np.savez_compressed(os.path.join(LATEST, "seasons.npz"), **{k: v for k, v in out.items()})
        with open(os.path.join(LATEST, "markets.json"), "w") as f:
            json.dump(markets, f, indent=1)
        pd.DataFrame(preds).to_csv(os.path.join(LATEST, "predictions.csv"), index=False)
        pd.DataFrame({"team": T, "rating": np.round(R, 4), "exp_points": [markets["points"][t]["mean"] for t in T]}).to_csv(os.path.join(LATEST, "ratings.csv"), index=False)
        with open(os.path.join(LATEST, "run_summary.json"), "w") as f:
            json.dump(summary, f, indent=1, default=str)
        try:
            from scripts.clv_log import update_clv
            update_clv(preds, stamp, asof)
        except Exception as e:
            print(f"run_sim: clv log skipped ({e})", file=sys.stderr)
        if not a.quick:
            dst = os.path.join(RUNS, stamp); os.makedirs(dst, exist_ok=True)
            for f in ("markets.json", "predictions.csv", "ratings.csv", "run_summary.json"):
                shutil.copy(os.path.join(LATEST, f), dst)
    top = sorted(markets["shield"].items(), key=lambda kv: -kv[1]["prob"])[:5]
    cup = sorted(markets["cup"].items(), key=lambda kv: -kv[1]["prob"])[:5]
    print(f"run_sim: {kn['n_seasons']} seasons, {len(fixtures)} fixtures left, {summary['closes_in_fit']} closes (resid sd {summary['fit_resid_sd'] if summary['fit_resid_sd']==summary['fit_resid_sd'] else float('nan'):.3f}), {summary['seconds']}s")
    print("  Shield: " + ", ".join(f"{t} {v['prob']*100:.1f}%" for t, v in top))
    print("  Cup:    " + ", ".join(f"{t} {v['prob']*100:.1f}%" for t, v in cup))
    if forecast.get("n"):
        print(f"  forecast check: {forecast['n']} posted lines, rmse {forecast['rmse']:.3f}, bias {forecast['bias']:+.3f} goals; with both layers on rmse {forecast['rmse_layers_on']:.3f} (mean |layer| {forecast['mean_abs_layer']:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
