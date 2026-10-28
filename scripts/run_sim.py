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
from sim.season import SeasonInputs, Fixture, run_seasons, empty_played, dock_exempt_from_prepass
from sim.playoffs import real_playoff_results
from sim.markets import Archive, all_markets
from sim.engine import hda
from sim.layers import team_penalty, hand_adjustment, scenarios_for_engine
from sim.ratings import gd_fit_row, home_edge_for
from scripts.refresh_ratings import live_home_edge, ratings_without_lines, build_ratings, closes_with_targets, team_totals, fixture_total, with_posted_lines
from scripts.common import today_et, now_utc, utc_iso

LATEST = os.path.join(ROOT, "outputs", "latest")
RUNS = os.path.join(ROOT, "outputs", "runs")


def playoff_inputs(kn: dict, rat: dict, T: list, LF=None, cfg: dict | None = None) -> dict:
    """The two playoff-only inputs (review 2026-10-27, proposal 7): each club's home delta for the games it hosts, and the goals its
    live absences that run past Decision Day take off its rating in the bracket (absence value on the Wild Card date x factor_abs)."""
    deltas = rat.get("club_deltas") or {}
    che = np.array([float(deltas.get(t, 0.0)) for t in T]) if deltas else None
    pf = None
    if LF is not None and kn.get("factors_enabled", False):
        from sim.knobs import load_config
        po = (cfg or load_config()).get("mls", {}).get("playoffs", {})
        d0 = po.get("wild_card") or ""
        beta = float(kn.get("factor_abs", 0.0) or 0.0)
        pf = np.array([beta * LF.playoff_mv(t, d0) for t in T]) if d0 else None
    return {"club_home_deltas": che, "playoff_adj": pf}


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


def bracket_slots(out: dict, T: list, conf) -> dict:
    """Per conference: P(seed k) for k 1..9 and 'out' per club, and the share of seasons each club fills each bracket slot
    (Round One winners by pairing 1/WC, 2/7, 3/6, 4/5; semi winners by branch {1,WC,4,5} and {2,7,3,6}; conference final winner),
    plus the MLS Cup winner share. Keys: seeds {team: [p1..p9, p_out]}, r1 [4 x {team: p}], semi [2 x {team: p}],
    final {team: p}, wc {team: p} (the Wild Card winner, 2026-10-24); cup {team: p}. Values under 0.001 are dropped."""
    from sim.playoffs import STAGE
    seed = out["conf_seed"]; stage = out["stage"]; N = seed.shape[0]
    res = {}
    for cname, cval in (("East", 0), ("West", 1)):
        idx = [i for i, t in enumerate(T) if int(conf[i]) == cval]
        seeds = {}
        for i in idx:
            ps = [float((seed[:, i] == k).mean()) for k in range(1, 10)]
            seeds[T[i]] = [round(x, 4) for x in ps] + [round(1 - sum(ps), 4)]
        def slot(min_stage, seed_set):
            d = {}
            for i in idx:
                p = float(((stage[:, i] >= min_stage) & np.isin(seed[:, i], list(seed_set))).mean())
                if p >= 0.001:
                    d[T[i]] = round(p, 4)
            return dict(sorted(d.items(), key=lambda kv: -kv[1]))
        res[cname] = {"seeds": seeds,
                      "wc": slot(STAGE["round_one"], {8, 9}),
                      "r1": [slot(STAGE["conf_semi"], {1, 8, 9}), slot(STAGE["conf_semi"], {2, 7}), slot(STAGE["conf_semi"], {3, 6}), slot(STAGE["conf_semi"], {4, 5})],
                      "semi": [slot(STAGE["conf_final"], {1, 8, 9, 4, 5}), slot(STAGE["conf_final"], {2, 7, 3, 6})],
                      "final": slot(STAGE["cup_final"], set(range(1, 10)))}
    res["cup"] = dict(sorted({T[i]: round(float((stage[:, i] >= STAGE["cup_winner"]).mean()), 4) for i in range(len(T)) if (stage[:, i] >= STAGE["cup_winner"]).mean() >= 0.001}.items(), key=lambda kv: -kv[1]))
    return res


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
    kn["home_edge_goals"] = live_home_edge(rat, kn)   # one home edge (review 11): the monthly fit the state was netted with, fixtures and playoffs alike
    print(f"home edge {kn['home_edge_goals']:.3f} (monthly fit the ratings were netted with; config {knobs(cfg)['home_edge_goals']:.2f})")
    # the ratings WITHOUT this round's lines score the forecast check and the CLV log: with posted_in_fit on, the live ratings carry
    # the very lines they are checked against (CLAUDE.md 4 item 4; the run line read rmse ~0.06 when the honest figure is ~0.24)
    R_nl = ratings_without_lines(asof, cfg, closes=closes)["ratings"] if kn.get("posted_in_fit") else R
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
    if kn.get("posted_in_fit"):  # the layer's absorption counts the current round's posted lines too (they are in the ratings since 2026-10-15)
        pl = with_posted_lines(closes, asof, kn); season_closes = pd.concat([season_closes, pl[pl["season"].astype(str) == "posted"]], ignore_index=True)
    tiers = kn["injury_tiers"]; s_knob = kn["posted_line_shrink"]
    tt = team_totals(closes, T, asof, kn)
    from sim.factors import betas_from_knobs, factor_vector, live_factors
    betas = betas_from_knobs(kn); LF = live_factors(asof) if betas else None   # full-health ratings: each fixture's own factors added back (CLAUDE.md 14)
    if tt:
        print(f"team totals: league base {tt['base']:.2f}, offsets " + ", ".join(f"{t} {u:+.2f}" for t, u in sorted(tt["offsets"].items(), key=lambda x: -x[1])[:3]) + " ... " + ", ".join(f"{t} {u:+.2f}" for t, u in sorted(tt["offsets"].items(), key=lambda x: x[1])[:3]))
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
        fac = factor_vector(betas, LF.x(r["date"], h, aw)) if betas else 0.0
        adj_total = home_edge_for(h, kn["home_edge_goals"], rat.get("club_deltas")) + hand + layer + fac
        g_model = float(R[idx[h]] - R[idx[aw]] + adj_total)
        g_model_nl = float(R_nl[idx[h]] - R_nl[idx[aw]] + adj_total)
        line = posted.get((r["date"], h, aw))
        s, g_pinn, Tt = 0.0, float("nan"), fixture_total(tt, h, aw, kn["avg_total_goals"])
        if line:
            gf = gd_fit_row(line.get("h"), line.get("d"), line.get("a"), line.get("ah_line") or None, line.get("ah_home"), line.get("ah_away"),
                            line.get("total_line") or None, line.get("over"), line.get("under"), kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
            if np.isfinite(gf["gd_fit"]):
                s, g_pinn, Tt = s_knob, float(gf["gd_fit"]), float(gf["T_fit"]) if np.isfinite(gf["T_fit"]) else Tt
        g_used = (1 - s) * g_model + s * g_pinn if s > 0 else g_model
        fixtures.append(Fixture(idx[h], idx[aw], r["date"], adj=adj_total, s=s, g_pinn=g_pinn if s > 0 else 0.0, T=Tt))
        mh, md, ma = hda(g_used, Tt, kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
        preds.append({"date": r["date"], "kickoff_utc": r["kickoff_utc"], "home": h, "away": aw, "g_model": round(g_model, 3), "g_model_nl": round(g_model_nl, 3), "g_pinn": round(g_pinn, 3) if s > 0 else "",
                      "g_used": round(g_used, 3), "T": round(Tt, 2), "p_home": round(mh, 4), "p_draw": round(md, 4), "p_away": round(ma, 4),
                      "layer_goals": round(layer, 3), "layer_full": round(layer_full, 3), "hand_goals": round(hand, 3), "factor_goals": round(fac, 3), "shrink": s,
                      "pinn_h": round(gf["ph"], 4) if line and np.isfinite(gf["ph"]) else "", "pinn_d": round(gf["pd"], 4) if line and np.isfinite(gf["pd"]) else "", "pinn_a": round(gf["pa"], 4) if line and np.isfinite(gf["pa"]) else ""})
    scen = scenarios_for_engine(data.load("scenarios"), T)
    hp, hg_ = played_h2h(res, T)
    pin = playoff_inputs(kn, rat, T, LF, cfg)
    if pin["playoff_adj"] is not None and np.any(pin["playoff_adj"] != 0):
        print("playoff absences (goals off the rating in the bracket): " + ", ".join(f"{T[i]} {pin['playoff_adj'][i]:+.3f}" for i in np.argsort(pin["playoff_adj"]) if abs(pin["playoff_adj"][i]) >= 0.005))
    inp = SeasonInputs(T, conf, R, fixtures, played, scen, disc=disc_points(T, cfg["season"], kn.get("disc_points_enabled", False)),
                       h2h_pts=hp if kn.get("tiebreak_h2h", False) else None, h2h_gd=hg_ if kn.get("tiebreak_h2h", False) else None,
                       totals=tt, playoff_results=real_playoff_results(data.load("results"), T, cfg["season"]), **pin)
    dock_info = {}
    if float(kn.get("dead_dock_goals", 0.0) or 0.0) > 0:
        inp.dock_exempt = dock_exempt_from_prepass(inp, kn)
        dock_info["exempt"] = [T[i] for i in np.where(inp.dock_exempt)[0]]
    out = run_seasons(inp, kn)
    if out.get("docked_share") is not None and float(np.max(out["docked_share"])) > 0:
        dock_info["docked_share"] = {T[i]: round(float(out["docked_share"][i]), 3) for i in np.argsort(-out["docked_share"]) if out["docked_share"][i] >= 0.005}
        print("  dock: exempt " + ", ".join(dock_info.get("exempt", [])) + "; docked share " + ", ".join(f"{t} {v*100:.0f}%" for t, v in dock_info["docked_share"].items()))
    arc = Archive(out)
    exempt = {s["team"] for s in scen}
    markets = all_markets(arc, kn["shade"], exempt)
    markets["bracket"] = bracket_slots(out, T, conf)   # seed and bracket-slot distributions for the page's Bracket tab (2026-10-23)
    # forecast check: the ratings without this round's lines vs today's posted lines (out of sample)
    fc = [(p["g_model_nl"], float(p["g_pinn"]), p["layer_full"] - p["layer_goals"]) for p in preds if p["g_pinn"] != ""]
    forecast = {"n": len(fc)}
    if fc:
        d = np.array([m - p for m, p, _ in fc]); forecast.update(rmse=float(np.sqrt((d ** 2).mean())), bias=float(d.mean()))
        d2 = np.array([m + extra - p for m, p, extra in fc]); forecast.update(rmse_layers_on=float(np.sqrt((d2 ** 2).mean())), mean_abs_layer=float(np.mean([abs(x) for _, _, x in fc])))
        # running log of the layer measurement (section 8 of CLAUDE.md): one row per run
        lp = os.path.join(ROOT, "outputs", "calibration", "layers_log.csv")
        os.makedirs(os.path.dirname(lp), exist_ok=True)
        with open(lp if not (a.no_write or a.quick) else os.devnull, "a") as f:   # quick and no-write runs leave the log alone
            if f.name == lp and os.path.getsize(lp) == 0:
                f.write("asof,n_lines,rmse_off,rmse_on,mean_abs_layer,injury_on,callup_on\n")
            f.write(f"{asof},{len(fc)},{forecast['rmse']:.4f},{forecast['rmse_layers_on']:.4f},{forecast['mean_abs_layer']:.4f},{int(kn['injury_layer_enabled'])},{int(kn['callup_layer_enabled'])}\n")
    stamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    summary = {"asof": asof, "run_utc": utc_iso(now_utc()), "stamp": stamp, "n_seasons": kn["n_seasons"], "seed": kn["seed"],
               "fixtures_remaining": len(fixtures), "results_on_file": int(len(res)), "results_through": str(res["date"].max()) if len(res) else None,
               "closes_in_fit": rat["market_fit"]["n"], "fit_resid_sd": (None if rat["market_fit"].get("resid_sd") is None or rat["market_fit"]["resid_sd"] != rat["market_fit"]["resid_sd"] else rat["market_fit"]["resid_sd"]), "weights": rat["weights"], "xg_games": rat["xg_n"],
               "forecast_check": forecast, "posted_lines": len(posted), "odds_fetched_at": max((v["fetched_at"] for v in posted.values()), default=None),
               "knobs": kn, "scenarios": scen, "dock": dock_info, "seconds": round(time.time() - t0, 1)}
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
            if not a.quick:   # a quick run is a preview: it must not record the opener view
                update_clv(preds, stamp, asof)
        except Exception as e:
            print(f"run_sim: clv log skipped ({e})", file=sys.stderr)
        if not a.quick:
            dst = os.path.join(RUNS, stamp); os.makedirs(dst, exist_ok=True)
            for f in ("markets.json", "predictions.csv", "ratings.csv", "run_summary.json"):
                shutil.copy(os.path.join(LATEST, f), dst)
    top = sorted(markets["shield"].items(), key=lambda kv: -kv[1]["prob"])[:5]
    cup = sorted(markets["cup"].items(), key=lambda kv: -kv[1]["prob"])[:5]
    rsd = summary["fit_resid_sd"]; rsd_txt = "" if rsd is None else f" (resid sd {rsd:.3f})"
    print(f"run_sim: {kn['n_seasons']} seasons, {len(fixtures)} fixtures left, {summary['closes_in_fit']} closes{rsd_txt}, {summary['seconds']}s")
    print("  Shield: " + ", ".join(f"{t} {v['prob']*100:.1f}%" for t, v in top))
    print("  Cup:    " + ", ".join(f"{t} {v['prob']*100:.1f}%" for t, v in cup))
    if forecast.get("n"):
        print(f"  forecast check (ratings without this round's lines): {forecast['n']} posted lines, rmse {forecast['rmse']:.3f}, bias {forecast['bias']:+.3f} goals; with both layers on rmse {forecast['rmse_layers_on']:.3f} (mean |layer| {forecast['mean_abs_layer']:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
