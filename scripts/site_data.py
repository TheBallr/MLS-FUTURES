#!/usr/bin/env python3
"""One JSON of everything the page needs -> outputs/latest/site_data.json (embedded into the page by build_site.py).
Ratings (both conferences: rating, hand, Conf 1st / Playoffs / Semi / Final / Win conf / Cup, sources, Pinnacle-implied grid,
the previous run for deltas), Games (Tue-Mon weeks: Pinnacle fair, our ratings' price, the gap; played and upcoming games
alike from the ratings before that round's Pinnacle lines), Conferences (expected points and
fair odds), Injuries, Settings (run knobs and the engine inputs for the page worker), Risk (outputs/latest/risk.json), header
stamps in ET. Only keys the page reads are written."""
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
from sim.layers import team_penalty, week_of, hand_week_values
from scripts.refresh_ratings import closes_with_targets, build_ratings, with_posted_lines, team_totals
from sim.playoffs import real_playoff_results
from scripts.run_sim import played_stats, latest_posted
from scripts.common import ET, parse_utc, et_str

LATEST = os.path.join(ROOT, "outputs", "latest")
LOGOS = os.path.join(ROOT, "data", "logos.csv")


def clean(x):
    """NaN/inf -> None, so the file is valid JSON (the page embeds it, other tools parse it)."""
    if isinstance(x, float):
        return x if np.isfinite(x) else None
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def prob_of(row) -> float:
    """prob_out as the injury layer reads it: blank = fully out, anything unreadable = fully out."""
    try:
        v = str(row.get("prob_out", "")).strip()
        return 1.0 if v == "" else float(v)
    except (TypeError, ValueError):
        return 1.0


def week_start(d: dt.date) -> dt.date:
    """Weeks run Tuesday to Monday (ET)."""
    return d - dt.timedelta(days=(d.weekday() - 1) % 7)



def opta_anchor(T: list, R: np.ndarray) -> tuple[dict, dict]:
    """The public sanity anchor (Zac, do 2, 2026-10-15): Opta Power Rankings' latest snapshot, centred and rescaled to the blend's
    spread (the PDF blend step), never weighted. Returns ({team: value or None}, {date, spearman, n})."""
    p = os.path.join(ROOT, "data", "public", "opta", "snapshots.csv")
    if not os.path.exists(p):
        return {t: None for t in T}, {}
    o = pd.read_csv(p); o = o[o["date"] == o["date"].max()].set_index("team")["rating"]
    v = np.array([o.get(t, np.nan) for t in T], float)
    ok = np.isfinite(v)
    if ok.sum() < 20:
        return {t: None for t in T}, {}
    v = v - np.nanmean(v); v = v * (float(np.std(R)) / float(np.nanstd(v)))
    rb = pd.Series(R[ok]).rank(); ro = pd.Series(v[ok]).rank()
    info = {"snapshot": str(pd.read_csv(p)["date"].max()), "spearman": round(float(np.corrcoef(rb, ro)[0, 1]), 3), "n": int(ok.sum())}
    return {t: (round(float(v[i]), 3) if ok[i] else None) for i, t in enumerate(T)}, info

def main():
    cfg = load_config(); kn = knobs(cfg)
    summ = json.load(open(os.path.join(LATEST, "run_summary.json")))
    markets = json.load(open(os.path.join(LATEST, "markets.json")))
    preds = pd.read_csv(os.path.join(LATEST, "predictions.csv"), dtype=str, keep_default_na=False)
    T = teams(); cm = conference_of(); codes = code_of(); idx = {t: i for i, t in enumerate(T)}
    asof = summ["asof"]
    rat = build_ratings(asof, cfg, write=False)
    R = rat["ratings"]
    rho = float(kn.get("dc_rho", 0.0) or 0.0)
    # our ratings before this round's Pinnacle lines: the Games tab prices upcoming games off these, so the gap to the line is the
    # ratings' own view and not the line fed back through the filter (Zac, 2026-10-19: "what price would our team ratings give")
    if kn.get("posted_in_fit"):
        cfg_nl = json.loads(json.dumps(cfg)); cfg_nl["knobs"]["posted_in_fit"]["value"] = False
        R_nl = build_ratings(asof, cfg_nl, write=False)["ratings"]
    else:
        R_nl = R
    logos = {}
    if os.path.exists(LOGOS):
        logos = {r["team"]: r["logo"] for r in pd.read_csv(LOGOS, dtype=str).to_dict("records")}
    # crests embedded as data URIs (data/logos/<code>.png, 96 px, fetched once from the ESPN URLs): the published page cannot rely on external images
    for t in list(logos):
        lp = os.path.join(ROOT, "data", "logos", f"{codes.get(t, '')}.png")
        if os.path.exists(lp):
            logos[t] = "data:image/png;base64," + base64.b64encode(open(lp, "rb").read()).decode()
    opta, _ = opta_anchor(T, R)
    teams_out = [{"team": t, "code": codes[t], "conf": cm[t], "rating": round(float(R[i]), 3), "hand": round(float((rat.get("hand") or {}).get(t, 0.0)), 3), "blend_raw": round(float(rat["blend_raw"][i]), 3) if rat.get("blend_raw") is not None else None, "logo": logos.get(t, ""), "opta": opta.get(t),
                  "sources": {k: round(float(v[i]), 3) for k, v in rat["sources"].items()}, "n_closes": int(rat["n_closes"][i]),
                  "note": next((r["note"] for r in load_teams() if r["team"] == t), ""), "home_delta": round(float((rat.get("club_deltas") or {}).get(t, 0.0)), 3)} for i, t in enumerate(T)]
    # ----- games: schedule with results, Pinnacle fair (power devig), model HDA, gap -----
    sch = data.load("schedule"); res = data.load("results"); closes = closes_with_targets(cfg)
    season_closes = closes[closes["season"].astype(str) == str(cfg["season"])]
    layer_closes = season_closes
    if kn.get("posted_in_fit"):  # the layer's absorption counts the current round's posted lines too (they are in the ratings since 2026-10-15)
        pl = with_posted_lines(closes, asof, kn); layer_closes = pd.concat([season_closes, pl[pl["season"].astype(str) == "posted"]], ignore_index=True)
    resmap = {(r["date"], r["home"], r["away"]): r for r in res.to_dict("records")}
    predmap = {(r["date"], r["home"], r["away"]): r for r in preds.to_dict("records")}
    closemap = {(r["date"], r["home"], r["away"]): r for r in season_closes.to_dict("records")}
    # other books' latest posted lines (OpticOdds daily pull), display-only fallback for fixtures Pinnacle has not lined: sharpest first
    BOOK_ORDER = ["ps3838", "betfair", "bet365", "draftkings", "fanduel"]
    bookmap = {}
    cro = data.load("current_round_odds")
    if len(cro):
        cro = cro[cro["book"].str.lower().isin(BOOK_ORDER)].sort_values("fetched_at")
        for rr_ in cro.to_dict("records"):
            k = (rr_["date"], rr_["home"], rr_["away"]); b = rr_["book"].lower()
            cur = bookmap.get(k)
            if cur is None or BOOK_ORDER.index(b) <= BOOK_ORDER.index(cur["book"].lower()):
                bookmap[k] = rr_
    # Pinnacle-implied rating per club from each of this season's closes (opponent held at today's rating), windows of the last 4/8/12 and the season,
    # plus the current round's posted Pinnacle line(s)
    implied = {}
    cl_season = season_closes.copy(); cl_season["gd"] = pd.to_numeric(cl_season["gd_fit"], errors="coerce"); cl_season = cl_season.dropna(subset=["gd"]).sort_values("date")
    posted_now = latest_posted(data.load("current_round_odds"), asof=asof)
    deltas_ = rat.get("club_deltas") or {}
    def _implied(team, home, away, gd):
        if home == team:
            return float(gd) - kn["home_edge_goals"] - deltas_.get(team, 0.0) + float(R[idx[away]])
        return float(R[idx[home]]) + kn["home_edge_goals"] + deltas_.get(home, 0.0) - float(gd)
    for t in T:
        m = cl_season[(cl_season["home"] == t) | (cl_season["away"] == t)]
        rows_ = [{"date": r["date"], "opp": r["away"] if r["home"] == t else r["home"], "ha": "v" if r["home"] == t else "@", "close": round(float(r["gd"]), 2), "implied": round(_implied(t, r["home"], r["away"], r["gd"]), 2)} for r in m.to_dict("records")]
        vals = [x["implied"] for x in rows_]
        win = {k: (round(float(np.mean(vals[-n:])), 2) if len(vals) >= 1 else None) for k, n in (("w4", 4), ("w8", 8), ("w12", 12))}
        win["season"] = round(float(np.mean(vals)), 2) if vals else None
        posted_rows = []
        for (d_, h_, a_), ln in posted_now.items():
            if t in (h_, a_) and (d_, h_, a_) not in closemap:  # a posted line is superseded once the close is on file
                gf = gd_fit_row(ln.get("h"), ln.get("d"), ln.get("a"), ln.get("ah_line") or None, ln.get("ah_home"), ln.get("ah_away"), ln.get("total_line") or None, ln.get("over"), ln.get("under"),
                                kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
                if np.isfinite(gf["gd_fit"]):
                    posted_rows.append({"date": d_, "opp": a_ if h_ == t else h_, "ha": "v" if h_ == t else "@", "close": round(float(gf["gd_fit"]), 2), "implied": round(_implied(t, h_, a_, gf["gd_fit"]), 2)})
        implied[t] = {"posted": posted_rows, **win, "n": len(vals)}
    for to_ in teams_out:
        to_["implied"] = implied.get(to_["team"])
    # weekly hand log for the Ratings tab: every week on file plus the current and next weeks (Tue-Mon), each with its own values or the
    # carried-over set; the run uses the current week's
    hlog = data.load("hand_log")
    cur_week = week_of(asof); next_week = (dt.date.fromisoformat(cur_week) + dt.timedelta(days=7)).isoformat()
    weeks = sorted(set(hlog["week"].astype(str)) | {cur_week, next_week}) if len(hlog) else [cur_week, next_week]
    hand_weeks = []
    for w in weeks:
        vals, used = hand_week_values(hlog, w)
        own = hlog[hlog["week"].astype(str) == w] if len(hlog) else hlog
        saved = str(own["saved_at"].max()) if len(own) else ""
        hand_weeks.append({"week": w, "own": bool(len(own)), "carried_from": None if (used == w or used is None) else used, "saved_at": saved,
                           "values": {t: round(float(v), 2) for t, v in vals.items()}, "past": w < cur_week, "current": w == cur_week})
    today = dt.date.fromisoformat(asof)
    lo, hi = week_start(today) - dt.timedelta(days=28), week_start(today) + dt.timedelta(days=35)
    fits = {}
    from sim.factors import betas_from_knobs, factor_vector, factors as _factors
    betas = betas_from_knobs(kn); Fz = _factors() if betas else None
    if str(kn.get("rating_method", "wls")) == "kalman":  # one filter pass gives the state before every played date
        from scripts.close_track import kalman_states, obs_cached
        played_dates = sorted({x["date"] for x in sch.to_dict("records") if (x["date"], x["home"], x["away"]) in resmap})
        # full-health ratings (CLAUDE.md 14): every close net of its match-day factors, as the live build fits them
        obs = obs_cached(closes[closes["season"].astype(str) != "posted"], bool(kn.get("kalman_openers", False)), 0.0, None, rat.get("club_deltas") or None, 0.0, betas)
        universe = sorted(set(obs["home"]) | set(obs["away"])); uidx = {t: i for i, t in enumerate(universe)}
        knk = {"q_day": kn["kalman_q_day"], "s": kn["kalman_s"], "p0": kn["kalman_p0"], "q_off": kn["kalman_q_off"], "prior_new": kn["expansion_prior_rating"], "off_shrink": float(kn.get("kalman_off_shrink", 1.0)),
               "s_posted": kn.get("kalman_s_posted", kn["kalman_s"])}
        # match morning WITHOUT that round's Pinnacle lines (Zac, 2026-10-19; was with them since 2026-10-15): the same
        # price an upcoming game shows, so a played game's gap to its close is the ratings' own miss, not near zero by
        # construction. The xG blend at the source weights and that week's hand adjustments, as the run on that day used them.
        from sim.ratings import xg_fit
        w_used = rat.get("weights", {}); w_x = float(w_used.get("xg", 0.0)) / max(1e-9, sum(float(v) for v in w_used.values())) if w_used else 0.0
        hand_at = lambda d_: hand_week_values(hlog, week_of(d_))[0] if len(hlog) else {}
        xg_hist = data.num(data.load("xg_history"), ["home_xg", "away_xg"]) if w_x > 0 else None
        for d, (st, _) in kalman_states(obs, universe, played_dates, knk, None).items():
            v = np.array([st[uidx[t]] if t in uidx else knk["prior_new"] for t in T]); v = v - v.mean()
            if w_x > 0 and xg_hist is not None and len(xg_hist):
                xr = xg_fit(xg_hist, T, d, kn["xg_half_life_days"], kn["ridge_lambda"], float(v.std()))
                if xr["n"] > 0:
                    v = (1 - w_x) * v + w_x * xr["ratings"]; v = v - v.mean()
            hv = hand_at(d)  # that week's hand adjustments, as the run on that day used them
            fits[d] = v + np.array([float(hv.get(t, 0.0)) for t in T])
    # what the factors net out of / add back to each game (Games tab detail, CLAUDE.md 14): played games from the lineups, upcoming
    # games from today's injury list, the schedule and the table
    from scripts.site_detail import PlayedAbsences, ListedAbsences, played_breakdown, upcoming_breakdown, as_fielded, history as history_payload
    PA = PlayedAbsences(cfg["season"]) if betas else None; LA = ListedAbsences() if betas else None
    LF = None
    if betas:
        from sim.factors import live_factors
        LF = live_factors(asof)
    docked = (summ.get("dock") or {}).get("docked_share") or {}
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
             "score": "", "pin": None, "pin_raw": None, "model": None, "g_model": None, "g_pin": None}
        rr = resmap.get(key)
        if rr and str(rr.get("hg", "")) != "":
            g["score"] = f"{rr['hg']}-{rr['ag']}"
        line = closemap.get(key)
        if line is None:
            p = predmap.get(key)
            if p and p.get("pinn_h"):
                g["pin"] = [float(p["pinn_h"]), float(p["pinn_d"]), float(p["pinn_a"])]
                g["g_pin"] = float(p["g_pinn"]) if p.get("g_pinn") else None
                pl = posted_now.get(key)  # raw decimals of the posted Pinnacle line, so the Games detail shows the gap v the line before kickoff too
                if pl is not None and all(str(pl.get(c, "")) not in ("", "nan") for c in ("h", "d", "a")):
                    g["pin_raw"] = [float(pl["h"]), float(pl["d"]), float(pl["a"])]
            elif key in bookmap and not g["score"]:
                bl = bookmap[key]
                try:
                    gf = gd_fit_row(bl.get("h"), bl.get("d"), bl.get("a"), bl.get("ah_line") or None, bl.get("ah_home"), bl.get("ah_away"), bl.get("total_line") or None, bl.get("over"), bl.get("under"),
                                    kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
                    if all(str(bl.get(c, "")) not in ("", "nan") for c in ("h", "d", "a")):
                        ph, pdr, pa = power_devig([float(bl["h"]), float(bl["d"]), float(bl["a"])])
                        g["pin"] = [float(ph), float(pdr), float(pa)]; g["pin_raw"] = [float(bl["h"]), float(bl["d"]), float(bl["a"])]
                    g["g_pin"] = float(gf["gd_fit"]) if np.isfinite(gf["gd_fit"]) else None
                    g["book"] = bl["book"]
                except (ValueError, TypeError):
                    pass
        else:
            try:
                ph, pdr, pa = power_devig([float(line["h"]), float(line["d"]), float(line["a"])])
                g["pin"] = [float(ph), float(pdr), float(pa)]; g["pin_raw"] = [float(line["h"]), float(line["d"]), float(line["a"])]
                g["g_pin"] = float(line["gd_fit"]) if str(line.get("gd_fit", "")) not in ("", "nan") else None
                if not str(line.get("book", "")).startswith("pinnacle"):  # 34 games of 2026 have only football-data's market-average close
                    g["book"] = "market-average close"
            except (ValueError, TypeError):
                pass
        if g["score"]:
            if r["date"] not in fits:  # wls fallback (the Kalman pass above fills every played date)
                fits[r["date"]] = market_fit(closes, T, r["date"], kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True, club_deltas=rat.get("club_deltas"))["ratings"]
            Rw = fits[r["date"]]
            gm = float(Rw[idx[r["home"]]] - Rw[idx[r["away"]]] + home_edge_for(r["home"], kn["home_edge_goals"], rat.get("club_deltas")))
            if str(kn.get("rating_method", "wls")) == "kalman" and betas:  # that game's factors added back: rest, short week, eliminated status
                fac = factor_vector(betas, Fz.x_expected(r["date"], r["home"], r["away"], r["date"], "actual"))  # and the absences as the lineups were (the close knew them)
                gm += fac
                g["fx"] = {**played_breakdown(betas, Fz, PA, r["date"], r["home"], r["away"]), "factor": round(fac, 3)}
                g["g_fh"] = round(gm - fac, 3); g["model_fh"] = list(hda(gm - fac, float(line["T_fit"]) if line is not None and str(line.get("T_fit", "")) not in ("", "nan") else kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], rho))
            Tt = float(line["T_fit"]) if line is not None and str(line.get("T_fit", "")) not in ("", "nan") else kn["avg_total_goals"]
            g["model"] = list(hda(gm, Tt, kn["goal_floor"], kn["shared_goals_mean"], rho)); g["g_model"] = round(gm, 3)
        else:
            p = predmap.get(key)
            if p:  # the run's fixture adjustments (home edge, club delta, fixture hand, layers) on the ratings before this round's lines
                h_, a_ = idx[r["home"]], idx[r["away"]]
                gm = float(p["g_model"]) - float(R[h_] - R[a_]) + float(R_nl[h_] - R_nl[a_])
                g["T"] = float(p["T"]); g["g_model"] = round(gm, 3)
                g["model"] = list(hda(gm, g["T"], kn["goal_floor"], kn["shared_goals_mean"], rho))
                g["sim_uses_line"] = float(p.get("shrink") or 0) >= 1.0
                if betas and LF is not None:
                    fac = float(p.get("factor_goals") or 0.0)
                    g["fx"] = {**upcoming_breakdown(betas, LF, LA, r["date"], r["home"], r["away"], docked), "factor": round(fac, 3)}
                    g["g_fh"] = round(gm - fac, 3); g["model_fh"] = list(hda(gm - fac, g["T"], kn["goal_floor"], kn["shared_goals_mean"], rho))
        games.append(g)
    if betas and LF is not None:
        nfx = {}
        for r in sch[sch["competition"] == "MLS"].sort_values("kickoff_utc").to_dict("records"):
            if (r["date"], r["home"], r["away"]) in resmap or r["date"] < asof:
                continue
            for t in (r["home"], r["away"]):
                nfx.setdefault(t, r)
        fielded = as_fielded(betas, LF, LA, T, R, nfx)
        for to_ in teams_out:
            to_["fielded"] = fielded.get(to_["team"])
    history_out = history_payload(T, codes, fits, season_closes, res, kn, betas, Fz, rat.get("club_deltas") or {}, et_str)
    # ----- conferences / markets -----
    conf_rows = []
    pts = markets["points"]
    pr = lambda pool, t: round(float(markets[pool][t]["prob"]), 5)
    for t in T:
        e = cm[t] == "East"
        conf_rows.append({"team": t, "conf": cm[t], "exp_points": round(pts[t]["mean"], 1), "p10": pts[t]["p10"], "p90": pts[t]["p90"],
                          "playoffs": pr("playoffs", t), "top_seed": pr("east" if e else "west", t), "conf_final": pr("east_final" if e else "west_final", t),
                          "cup": pr("cup", t), "spoon": pr("spoon", t), "bottom": pr("east_bottom" if e else "west_bottom", t), "top4": pr("conf_top4", t)})
    # the pools the Ratings tab reads, as plain probabilities (the shade is off, so prob == prob_raw)
    PAGE_POOLS = ("east", "west", "playoffs", "conf_semi", "conf_final", "cup_finalist", "cup")
    markets_out = {k: {t: round(float(v["prob"]), 5) for t, v in markets[k].items()} for k in PAGE_POOLS if k in markets}
    # ----- injuries -----
    inj = data.load("injuries"); cal = data.load("callups")
    avp = os.path.join(ROOT, "data", "ratings", "absence_values.csv")   # absence values in goals (CLAUDE.md 14, proposal 5)
    av = pd.read_csv(avp, dtype=str, keep_default_na=False) if os.path.exists(avp) else pd.DataFrame()
    av_key = {(r["team"], r["player"]): r for r in av.to_dict("records")} if len(av) else {}
    next_fx = {}
    for r in sch[sch["status"] != "final"].sort_values("kickoff_utc").to_dict("records"):
        for t in (r["home"], r["away"]):
            next_fx.setdefault(t, r)
    inj_rows = []
    for t in T:
        nf = next_fx.get(t)
        pen = team_penalty(t, nf["date"], inj, cal, layer_closes, asof, kn["half_life_days"], kn["injury_tiers"], True, True) if nf else {"injury": 0, "callup": 0, "detail": []}
        rows = inj[inj["team"] == t].to_dict("records"); crow = cal[cal["team"] == t].to_dict("records")
        live = [x for x in rows if x["out_from"] <= asof and (not x["expected_return"] or x["expected_return"] > asof)]
        out_now = [x for x in live if prob_of(x) >= 1.0]
        PLAYER = ("player", "note", "tier", "prob_out", "out_from", "expected_return")
        ABS = ("value_per96", "regular", "cost_per_game", "games_missed", "stale", "asa_player")  # from absence_values.csv (full-health ratings)
        players = [{**{k: x.get(k, "") for k in PLAYER}, **{k: av_key.get((t, x["player"]), {}).get(k, "") for k in ABS}} for x in rows]
        abs_now = round(sum(float(a.get("cost_per_game") or 0) for (tt, _), a in av_key.items() if tt == t and str(a.get("stale", "0")) != "1" and (a.get("out_from") or "0000") <= asof and (not a.get("expected_return") or a.get("expected_return") > asof)), 3)
        inj_rows.append({"team": t, "out": len(out_now), "doubt": len(live) - len(out_now), "listed": len(rows),
                         "next": f"{nf['date']} {'v' if nf['home']==t else '@'} {codes.get(nf['away'] if nf['home']==t else nf['home'],'')}" if nf else "",
                         "penalty": round(pen["injury"] + pen["callup"], 3) if kn["injury_layer_enabled"] or kn["callup_layer_enabled"] else 0.0,
                         "raw": round(pen["injury"] + pen["callup"], 3), "absence_value": abs_now, "players": players, "callups": crow,
                         "detail": [{k: x.get(k) for k in ("player", "kind", "penalty", "absorbed")} for x in pen["detail"]]})
    # ----- settings / engine inputs for the worker -----
    engine = {"teams": T, "conf": [0 if cm[t] == "East" else 1 for t in T], "sources": {k: [round(float(x), 4) for x in v] for k, v in rat["sources"].items()},
              "weights": rat["weights"], "played": {k: [int(x) for x in v] for k, v in played_stats(res[res["competition"].isin(["MLS", ""])], T).items()},
              "fixtures": [{"h": idx[p["home"]], "a": idx[p["away"]], "date": p["date"], "adj": round(float(p["g_model"]) - float(R[idx[p["home"]]] - R[idx[p["away"]]]), 4),
                            "s": float(p["shrink"] or 0), "gp": float(p["g_pinn"]) if p.get("g_pinn") else 0.0, "T": float(p["T"])} for p in preds.to_dict("records")],
              "pt": (lambda tt: {"base": round(tt["base"], 4), "u": [round(float(tt["offsets"].get(t, 0.0)), 4) for t in T]} if tt else None)(team_totals(closes, T, asof, kn)),
              "locked": [list(x) for x in real_playoff_results(res, T, cfg["season"])],
              "hand_weeks": hand_weeks, "hand_week": cur_week, "knobs": {k: kn[k] for k in ("rating_sd", "drift_k_sim", "drift_cap", "home_edge_goals", "avg_total_goals", "goal_floor", "shared_goals_mean", "dc_rho")}, "seed": kn["seed"]}
    odds_at = summ.get("odds_fetched_at")
    header = {"odds_at": et_str(parse_utc(odds_at)) if odds_at else "no capture", "results_through": summ.get("results_through") or "none",
              "run_at": et_str(parse_utc(summ["run_utc"])), "asof": asof, "n_seasons": summ["n_seasons"]}
    # the run before this one (ratings and markets), so the Ratings tab always shows what changed since the last run: a saved hand
    # edit's effect stays visible after its run instead of vanishing with the preview
    prev = None
    runs_dir = os.path.join(ROOT, "outputs", "runs")
    cur_stamp = str(summ.get("stamp", ""))
    if os.path.isdir(runs_dir):
        stamps = sorted(d for d in os.listdir(runs_dir) if os.path.exists(os.path.join(runs_dir, d, "markets.json")) and os.path.exists(os.path.join(runs_dir, d, "ratings.csv")))
        earlier = [d for d in stamps if d < cur_stamp] if cur_stamp else stamps[:-1]
        if earlier:
            pst = earlier[-1]
            try:
                pr = pd.read_csv(os.path.join(runs_dir, pst, "ratings.csv"))
                pm = json.load(open(os.path.join(runs_dir, pst, "markets.json")))
                psum = json.load(open(os.path.join(runs_dir, pst, "run_summary.json"))) if os.path.exists(os.path.join(runs_dir, pst, "run_summary.json")) else {}
                prev = {"run": pst, "run_at": et_str(parse_utc(psum["run_utc"])) if psum.get("run_utc") else pst, "asof": psum.get("asof"),
                        "ratings": {str(r["team"]): round(float(r["rating"]), 3) for r in pr.to_dict("records")},
                        "markets": {k: {t: round(float(v.get("prob", v.get("prob_raw", 0.0))), 5) for t, v in pm[k].items()} for k in PAGE_POOLS if isinstance(pm.get(k), dict)}}
            except Exception as e:  # a malformed archive must not stop the page
                print(f"site_data: previous run {pst} unreadable ({e})")
    out = {"history": history_out, "header": header, "teams": teams_out, "games": games, "conferences": conf_rows, "markets": markets_out, "injuries": inj_rows, "engine": engine,
           "prev": prev, "forecast": summ.get("forecast_check"), "fit": {"n": summ.get("closes_in_fit")}, "layers": {"injuries": kn["injury_layer_enabled"], "callups": kn["callup_layer_enabled"],
                                                                                         "factors": bool(kn.get("factors_enabled", False)), "factor_abs": kn.get("factor_abs", 0),
                                                                                         "betas": betas or {}}}
    if any(float(v) != 1.0 for v in kn["shade"].values()):
        print("site_data: WARNING a shade is on; the page shows the shaded prob (the Shaded/Raw toggle was removed while the shade was off)")
    rp = os.path.join(LATEST, "risk.json")  # Risk tab (scripts/risk.py); marked stale when it was built for an earlier run
    if os.path.exists(rp):
        try:
            rk = json.load(open(rp)); rk.pop("misses", None); rk["stale"] = rk.get("stamp") != summ.get("stamp"); out["risk"] = rk
        except ValueError as e:
            print(f"site_data: risk.json unreadable ({e})")
    with open(os.path.join(LATEST, "site_data.json"), "w") as f:
        json.dump(clean(out), f, separators=(",", ":"), default=str, allow_nan=False)
    print(f"site_data: {len(games)} games, {len(T)} teams, {os.path.getsize(os.path.join(LATEST,'site_data.json'))//1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
