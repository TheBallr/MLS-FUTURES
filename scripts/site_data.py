#!/usr/bin/env python3
"""One JSON of everything the page needs -> outputs/latest/site_data.json.
Ratings (two conference tables with Shield/Conf/Playoffs/Cup), Games (weeks Tue-Mon ET: last/this/next and more, walk-forward
model lines for played games), Conferences (expected points, pools raw and shaded), Injuries (per club with player rows and
call-ups), Scenarios (rows, a 20k-season sample of the football-only run), Settings (run knobs, sources, engine inputs for the
worker), header stamps in ET."""
from __future__ import annotations
import base64, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT, teams, conference_of, code_of, load_teams
from sim.engine import hda
from sim.devig import power_devig
from sim.ratings import market_fit, gd_fit_row, home_edge_for
from sim.layers import team_penalty
from sim.season import SeasonInputs, run_seasons
from sim.markets import Archive, all_markets
from scripts.refresh_ratings import closes_with_targets, build_ratings
from scripts.run_sim import played_stats, latest_posted
from scripts.common import ET, parse_utc, et_str, now_utc

LATEST = os.path.join(ROOT, "outputs", "latest")
LOGOS = os.path.join(ROOT, "data", "logos.csv")


def b64(arr, dtype):
    return base64.b64encode(np.ascontiguousarray(arr.astype(dtype)).tobytes()).decode()


def week_start(d: dt.date) -> dt.date:
    """Weeks run Tuesday to Monday (ET)."""
    return d - dt.timedelta(days=(d.weekday() - 1) % 7)


def main():
    cfg = load_config(); kn = knobs(cfg)
    summ = json.load(open(os.path.join(LATEST, "run_summary.json")))
    markets = json.load(open(os.path.join(LATEST, "markets.json")))
    arcd = dict(np.load(os.path.join(LATEST, "seasons.npz"), allow_pickle=False))
    preds = pd.read_csv(os.path.join(LATEST, "predictions.csv"), dtype=str, keep_default_na=False)
    T = teams(); cm = conference_of(); codes = code_of(); idx = {t: i for i, t in enumerate(T)}
    asof = summ["asof"]
    rat = build_ratings(asof, cfg, write=False)
    R = rat["ratings"]
    logos = {}
    if os.path.exists(LOGOS):
        logos = {r["team"]: r["logo"] for r in pd.read_csv(LOGOS, dtype=str).to_dict("records")}
    teams_out = [{"team": t, "code": codes[t], "conf": cm[t], "rating": round(float(R[i]), 3), "logo": logos.get(t, ""),
                  "sources": {k: round(float(v[i]), 3) for k, v in rat["sources"].items()}, "n_closes": int(rat["n_closes"][i]),
                  "note": next((r["note"] for r in load_teams() if r["team"] == t), ""), "home_delta": round(float((rat.get("club_deltas") or {}).get(t, 0.0)), 3)} for i, t in enumerate(T)]
    # ----- games: schedule with results, Pinnacle fair (power devig), model HDA, gap -----
    sch = data.load("schedule"); res = data.load("results"); closes = closes_with_targets(cfg)
    season_closes = closes[closes["season"].astype(str) == str(cfg["season"])]
    resmap = {(r["date"], r["home"], r["away"]): r for r in res.to_dict("records")}
    predmap = {(r["date"], r["home"], r["away"]): r for r in preds.to_dict("records")}
    closemap = {(r["date"], r["home"], r["away"]): r for r in season_closes.to_dict("records")}
    today = dt.date.fromisoformat(asof)
    lo, hi = week_start(today) - dt.timedelta(days=28), week_start(today) + dt.timedelta(days=35)
    fits = {}
    games = []
    for r in sch.sort_values("kickoff_utc").to_dict("records"):
        if r["competition"] != "MLS" or not r["date"]:
            continue
        d = dt.date.fromisoformat(r["date"])
        if d < lo or d >= hi:
            continue
        key = (r["date"], r["home"], r["away"])
        ko = parse_utc(r["kickoff_utc"]) if r["kickoff_utc"] else None
        g = {"date": r["date"], "ko_et": ko.astimezone(ET).strftime("%a %m/%d %I:%M%p").replace(" 0", " ").replace("AM", "a").replace("PM", "p") if ko else "", "home": r["home"], "away": r["away"],
             "hc": codes.get(r["home"], ""), "ac": codes.get(r["away"], ""), "status": r["status"], "score": "", "pin": None, "pin_raw": None, "model": None, "gap": None, "g_model": None, "g_pin": None}
        rr = resmap.get(key)
        if rr and str(rr.get("hg", "")) != "":
            g["score"] = f"{rr['hg']}-{rr['ag']}"
        line = closemap.get(key)
        if line is None:
            p = predmap.get(key)
            if p and p.get("pinn_h"):
                g["pin"] = [float(p["pinn_h"]), float(p["pinn_d"]), float(p["pinn_a"])]
                g["g_pin"] = float(p["g_pinn"]) if p.get("g_pinn") else None
        else:
            try:
                ph, pdr, pa = power_devig([float(line["h"]), float(line["d"]), float(line["a"])])
                g["pin"] = [float(ph), float(pdr), float(pa)]; g["pin_raw"] = [float(line["h"]), float(line["d"]), float(line["a"])]
                g["g_pin"] = float(line["gd_fit"]) if str(line.get("gd_fit", "")) not in ("", "nan") else None
            except (ValueError, TypeError):
                pass
        if g["score"]:
            # walk-forward: what the model said before kickoff, from closes strictly before the date
            if r["date"] not in fits:
                fits[r["date"]] = market_fit(closes, T, r["date"], kn["half_life_days"], kn["market_ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True, club_deltas=rat.get("club_deltas"))["ratings"]
            Rw = fits[r["date"]]
            gm = float(Rw[idx[r["home"]]] - Rw[idx[r["away"]]] + home_edge_for(r["home"], kn["home_edge_goals"], rat.get("club_deltas")))
            Tt = float(line["T_fit"]) if line is not None and str(line.get("T_fit", "")) not in ("", "nan") else kn["avg_total_goals"]
            g["model"] = list(hda(gm, Tt, kn["goal_floor"], kn["shared_goals_mean"])); g["g_model"] = round(gm, 3)
        else:
            p = predmap.get(key)
            if p:
                g["model"] = [float(p["p_home"]), float(p["p_draw"]), float(p["p_away"])]; g["g_model"] = float(p["g_model"])
        if g["model"] and g["pin"]:
            g["gap"] = round((g["model"][0] - g["pin"][0]) * 100, 1)
        games.append(g)
    # ----- conferences / markets -----
    conf_rows = []
    pts = markets["points"]
    for t in T:
        conf_rows.append({"team": t, "conf": cm[t], "exp_points": round(pts[t]["mean"], 1), "p10": pts[t]["p10"], "p90": pts[t]["p90"],
                          "playoffs": markets["playoffs"][t], "top_seed": markets["east" if cm[t] == "East" else "west"][t],
                          "conf_final": markets["east_final" if cm[t] == "East" else "west_final"][t], "cup": markets["cup"][t],
                          "shield": markets["shield"][t], "spoon": markets["spoon"][t], "bottom": markets["east_bottom" if cm[t] == "East" else "west_bottom"][t],
                          "top4": markets["conf_top4"][t], "top7": markets["conf_top7"][t]})
    # ----- injuries -----
    inj = data.load("injuries"); cal = data.load("callups")
    next_fx = {}
    for r in sch[sch["status"] != "final"].sort_values("kickoff_utc").to_dict("records"):
        for t in (r["home"], r["away"]):
            next_fx.setdefault(t, r)
    inj_rows = []
    for t in T:
        nf = next_fx.get(t)
        pen = team_penalty(t, nf["date"], inj, cal, season_closes, asof, kn["half_life_days"], kn["injury_tiers"], True, True) if nf else {"injury": 0, "callup": 0, "detail": []}
        rows = inj[inj["team"] == t].to_dict("records"); crow = cal[cal["team"] == t].to_dict("records")
        out_now = [x for x in rows if x["out_from"] <= asof and (not x["expected_return"] or x["expected_return"] > asof)]
        inj_rows.append({"team": t, "out": len(out_now), "listed": len(rows), "next": f"{nf['date']} {'v' if nf['home']==t else '@'} {codes.get(nf['away'] if nf['home']==t else nf['home'],'')}" if nf else "",
                         "penalty": round(pen["injury"] + pen["callup"], 3) if kn["injury_layer_enabled"] or kn["callup_layer_enabled"] else 0.0,
                         "raw": round(pen["injury"] + pen["callup"], 3), "players": rows, "callups": crow, "detail": pen["detail"]})
    # ----- scenarios: sample of the football-only run (no scenarios) for the page's re-ranking -----
    scen = data.load("scenarios").to_dict("records")
    n_sample = int(min(kn["site_sample_seasons"], arcd["points"].shape[0]))
    sample = {"n": n_sample, "points": b64(arcd["points"][:n_sample], np.int16), "league_pos": b64(arcd["league_pos"][:n_sample], np.int8),
              "conf_seed": b64(arcd["conf_seed"][:n_sample], np.int8), "stage": b64(arcd["stage"][:n_sample], np.int8)}
    # cup rate conditional on (team, seed) from the full archive: the Scenarios tab's no-resim approximation
    cup_by_seed = {}
    for i, t in enumerate(T):
        cs = arcd["conf_seed"][:, i]; st = arcd["stage"][:, i]
        cup_by_seed[t] = [float((st[cs == s] == 6).mean()) if (cs == s).sum() > 50 else 0.0 for s in range(1, 10)]
    # football-only sample when scenarios are on file: rerun without scenarios at the sample size
    if scen:
        conf = np.array([0 if cm[t] == "East" else 1 for t in T])
        from sim.season import Fixture
        fx = []
        for p in preds.to_dict("records"):
            s = float(p["shrink"] or 0); fx.append(Fixture(idx[p["home"]], idx[p["away"]], p["date"], adj=float(p["g_model"]) - float(R[idx[p["home"]]] - R[idx[p["away"]]]), s=s, g_pinn=float(p["g_pinn"]) if s > 0 else 0.0, T=float(p["T"])))
        o = run_seasons(SeasonInputs(T, conf, R, fx, played_stats(res[res["competition"].isin(["MLS", ""])], T)), kn, n_seasons=n_sample)
        sample.update(points=b64(o["points"], np.int16), league_pos=b64(o["league_pos"], np.int8), conf_seed=b64(o["conf_seed"], np.int8), stage=b64(o["stage"], np.int8))
    # Pinnacle futures on file (for "Pinnacle implies")
    fut = data.load("futures_odds")
    fut_out = {}
    if len(fut):
        fut = fut.sort_values("fetched_at").drop_duplicates(["market", "team", "line"], keep="last")
        for mkt, g in fut.groupby("market"):
            dec = []
            for r in g.to_dict("records"):
                try:
                    dec.append((r["team"], float(r["price_decimal"]) if r["price_decimal"] else 1 + (float(r["price_american"]) / 100 if float(r["price_american"]) > 0 else 100 / abs(float(r["price_american"])))))
                except (ValueError, TypeError):
                    pass
            if len(dec) >= 2:
                fair = power_devig([d for _, d in dec])
                fut_out[mkt] = {t: float(p) for (t, _), p in zip(dec, fair)}
    # ----- settings / engine inputs for the worker -----
    engine = {"teams": T, "conf": [0 if cm[t] == "East" else 1 for t in T], "sources": {k: [round(float(x), 4) for x in v] for k, v in rat["sources"].items()},
              "weights": rat["weights"], "played": {k: [int(x) for x in v] for k, v in played_stats(res[res["competition"].isin(["MLS", ""])], T).items()},
              "fixtures": [{"h": idx[p["home"]], "a": idx[p["away"]], "date": p["date"], "adj": round(float(p["g_model"]) - float(R[idx[p["home"]]] - R[idx[p["away"]]]), 4),
                            "s": float(p["shrink"] or 0), "gp": float(p["g_pinn"]) if p.get("g_pinn") else 0.0, "T": float(p["T"])} for p in preds.to_dict("records")],
              "knobs": {k: kn[k] for k in ("rating_sd", "drift_k_sim", "drift_cap", "home_edge_goals", "avg_total_goals", "goal_floor", "shared_goals_mean", "shade")}, "seed": kn["seed"]}
    odds_at = summ.get("odds_fetched_at")
    header = {"odds_at": et_str(parse_utc(odds_at)) if odds_at else "no capture", "results_through": summ.get("results_through") or "none",
              "run_at": et_str(parse_utc(summ["run_utc"])), "asof": asof, "n_seasons": summ["n_seasons"]}
    out = {"header": header, "teams": teams_out, "games": games, "conferences": conf_rows, "markets": markets, "injuries": inj_rows,
           "scenarios": scen, "sample": sample, "cup_by_seed": cup_by_seed, "futures": fut_out, "engine": engine,
           "forecast": summ.get("forecast_check"), "fit": {"n": summ.get("closes_in_fit"), "resid_sd": summ.get("fit_resid_sd")}, "shade": kn["shade"], "layers": {"injuries": kn["injury_layer_enabled"], "callups": kn["callup_layer_enabled"]}}
    with open(os.path.join(LATEST, "site_data.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(f"site_data: {len(games)} games, {len(T)} teams, sample {n_sample} seasons, {os.path.getsize(os.path.join(LATEST,'site_data.json'))//1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
