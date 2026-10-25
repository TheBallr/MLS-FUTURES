"""Detail payloads for the page (Zac 2026-10-19: "more vision and more understanding of what's going on"), built by site_data.py:

- fixture breakdowns (Games tab): what the full-health ratings net out of a played game's close and add back to its price, and
  what is added back to (or left out of) an upcoming game's price: per side the absences (player by player), rest, short week
  and eliminated status in goals, the price at full health and with the factors, Pinnacle's.
- club "as fielded" (Ratings tab): full-health rating v strength in the club's next fixture.
- history (History tab): every published run's rating and its Pinnacle / xG / hand parts (data/ratings/ratings_history.csv),
  today's method replayed on every match morning of the season (the Games tab's walk-forward ratings), what each of the club's
  Pinnacle closes implied for it at full health, model changes (data/ratings/method_log.csv), and per run what happened since
  the run before (games, model changes, hand edits).
Club term of a fixture factor: term = b_abs x missing value + b_rest x (min(rest, 10) - 7) + b_short x short week + b_elim x eliminated;
the fixture's factor is the home term minus the away term (sim/factors.py factor_vector), so the parts add up exactly."""
from __future__ import annotations
import datetime as dt, json, os
import numpy as np
import pandas as pd
from sim.teams import ROOT

ABS_PLAYERS = os.path.join(ROOT, "data", "public", "asa_gplus", "absence_players.csv")
ABS_VALUES = os.path.join(ROOT, "data", "ratings", "absence_values.csv")
HIST = os.path.join(ROOT, "data", "ratings", "ratings_history.csv")
METHOD_LOG = os.path.join(ROOT, "data", "ratings", "method_log.csv")
RUNS = os.path.join(ROOT, "outputs", "runs")
HX_MARKETS = ["conf1", "playoffs", "conf_semi", "conf_final", "cup_finalist", "cup"]   # the Ratings tab's columns: Conf 1st, Playoffs, Reach semis, Reach conf final, Reach MLS Cup, Win MLS Cup
R3 = lambda x: None if x is None or not np.isfinite(x) else round(float(x), 3)


def club_term(betas: dict, mv: float, rest: float, short: float, elim: float) -> dict:
    """The club's own share of a fixture factor, by part (goals; negative = weaker)."""
    b = lambda k: float(betas.get(k, 0.0) or 0.0)
    # rest relative to a normal 7-day week: only the difference between the sides enters the fixture, so the constant cancels and a
    # normal week reads as zero
    p = {"abs": b("abs") * mv, "rest": b("rest") * (min(rest, 10.0) - 7.0), "short": b("short") * short, "elim": b("elim") * elim}
    p["total"] = sum(p.values())
    return {k: R3(v) for k, v in p.items()}


class PlayedAbsences:
    """Absent regulars of a played game from the absence dataset (who missed it, value per 96, absent share incl. regular weight)."""

    def __init__(self, season: str):
        self.by = {}
        if os.path.exists(ABS_PLAYERS):
            a = pd.read_csv(ABS_PLAYERS, dtype={"season": str})
            a = a[a["season"] == str(season)]
            for (d, t), g in a.groupby(["date", "team"]):
                g = g.assign(cost=g["value_per96"] * g["absent_frac"]).sort_values("cost", ascending=False)
                self.by[(d, t)] = [{"player": r.player, "value": R3(r.value_per96), "share": R3(r.absent_frac), "cost": R3(r.cost), "gk": int(r.gk)}
                                   for r in g.itertuples(index=False) if abs(r.cost) >= 0.0005]

    def get(self, date: str, team: str) -> list:
        return self.by.get((date, team), [])


class ListedAbsences:
    """Today's injury list in goals (data/ratings/absence_values.csv): counted rows and rows on the list that carry nothing, with why."""

    def __init__(self):
        self.rows = pd.read_csv(ABS_VALUES, dtype=str, keep_default_na=False) if os.path.exists(ABS_VALUES) else pd.DataFrame()

    def on(self, team: str, date: str) -> tuple[list, list]:
        if not len(self.rows):
            return [], []
        g = self.rows[self.rows["team"] == team]
        counted, left = [], []
        for r in g.to_dict("records"):
            d0, d1 = r.get("out_from") or "0000", r.get("expected_return") or "9999"
            if not (d0 <= date < d1):
                continue
            f = lambda k: float(r.get(k) or 0.0)
            item = {"player": r["player"], "status": r.get("status", ""), "p": f("prob_out"), "value": R3(f("value_per96")), "regular": R3(f("regular")),
                    "cost": R3(f("cost_per_game")), "back": r.get("expected_return", "")}
            if str(r.get("stale", "0")) == "1":
                left.append({**item, "why": "has played since he was listed"})
            elif f("cost_per_game") > 0:
                counted.append(item)
            elif not r.get("asa_player"):
                left.append({**item, "why": "no MLS minutes in the last year"})
            elif f("regular") <= 0:
                left.append({**item, "why": "not a regular (under 30% of minutes)"})
            else:
                left.append({**item, "why": "value at or below a replacement"})
        counted.sort(key=lambda x: -(x["cost"] or 0))
        return counted, left


def played_breakdown(betas: dict, F, PA: PlayedAbsences, date: str, home: str, away: str) -> dict:
    x = F.x_actual(date, home, away)
    rh, ra = F.rest.get((date, home), 7.0), F.rest.get((date, away), 7.0)
    season = date[:4]
    eh, ea = float(F.elim.get((season, date, home), 0)), float(F.elim.get((season, date, away), 0))
    side = lambda t, mv, rest, el: {"term": club_term(betas, mv, rest, float(rest <= 3), el), "mv": R3(mv), "rest": int(rest), "elim": int(el), "players": PA.get(date, t)}
    return {"home": side(home, x["mv_home"], rh, eh), "away": side(away, x["mv_away"], ra, ea)}


def upcoming_breakdown(betas: dict, LF, LA: ListedAbsences, date: str, home: str, away: str, docked: dict) -> dict:
    def side(t):
        counted, left = LA.on(t, date)
        mv = LF.mv(t, date); rest = LF.rest(t, date); el = float(LF.elim.get(t, 0))
        return {"term": club_term(betas, mv, rest, float(rest <= 3), el), "mv": R3(mv), "rest": int(rest), "elim": int(el), "players": counted, "left": left,
                "dock": R3(docked.get(t))}
    return {"home": side(home), "away": side(away)}


def as_fielded(betas: dict, LF, LA: ListedAbsences, T: list, R: np.ndarray, next_fx: dict) -> dict:
    """team -> full-health rating v strength in its next fixture (the club's own factor term added)."""
    out = {}
    for i, t in enumerate(T):
        nf = next_fx.get(t)
        if not nf or not betas:
            continue
        counted, left = LA.on(t, nf["date"])
        mv = LF.mv(t, nf["date"]); rest = LF.rest(t, nf["date"]); el = float(LF.elim.get(t, 0))
        term = club_term(betas, mv, rest, float(rest <= 3), el)
        out[t] = {"date": nf["date"], "opp": nf["away"] if nf["home"] == t else nf["home"], "ha": "v" if nf["home"] == t else "@", "full": R3(R[i]),
                  "fielded": R3(R[i] + (term["total"] or 0.0)), "term": term, "rest": int(rest), "players": counted, "left": len(left)}
    return out


def _stamp_utc(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)


def history(T: list, codes: dict, fits: dict, closes: pd.DataFrame, results: pd.DataFrame, kn: dict, betas: dict | None, F, deltas: dict, et_str) -> dict:
    """The History tab's payload (see the module docstring)."""
    idx = {t: i for i, t in enumerate(T)}
    out = {"runs": [], "replay": {}, "implied": {t: [] for t in T}, "log": []}
    # published runs
    if os.path.exists(HIST):
        h = pd.read_csv(HIST)
        for s, g in h.groupby("stamp"):
            g = g.set_index("team")
            m, x = g["market"], g["xg"]
            wm, wx = float(g["w_market"].iloc[0]), float(g["w_xg"].iloc[0])
            pm = wm * (m - m.mean()); px = (wx * (x - x.mean())).fillna(0.0)
            summ = os.path.join(RUNS, s, "run_summary.json")
            js = json.load(open(summ)) if os.path.exists(summ) else {}
            utc = _stamp_utc(s)
            out["runs"].append({"stamp": s, "utc": utc.isoformat().replace("+00:00", "Z"), "et": et_str(utc), "asof": str(g["asof"].iloc[0]),
                                "through": js.get("results_through") or "", "w_xg": round(wx, 3),
                                "r": {t: [R3(g.loc[t, "rating"]), R3(pm.get(t)), R3(px.get(t)), R3(g.loc[t, "hand"])] for t in g.index if t in idx}})
    # each run's own futures prices (outputs/runs/<stamp>/markets.json), per club in HX_MARKETS order; None where a run had no such pool
    from sim.teams import conference_of
    cm = conference_of()
    for run in out["runs"]:
        mp = os.path.join(RUNS, run["stamp"], "markets.json")
        mk = json.load(open(mp)) if os.path.exists(mp) else {}
        def _p(name, t):
            v = (mk.get(name) or {}).get(t)
            return None if v is None else round(float(v.get("prob", v.get("prob_raw")) if isinstance(v, dict) else v), 4)
        run["m"] = {t: [_p("east" if cm.get(t) == "East" else "west", t)] + [_p(k, t) for k in HX_MARKETS[1:]] for t in run["r"]}
    out["runs"].sort(key=lambda r: r["stamp"])
    # today's method on every match morning (the Games tab's walk-forward ratings: no posted lines, the xG blend, that week's hand)
    dates = sorted(fits)
    out["replay"] = {"dates": dates, "r": {t: [R3(fits[d][idx[t]]) for d in dates] for t in T}}
    # each close: score, the close's margin, what it implied for each side at full health (opponent at its match-morning rating)
    he = float(kn["home_edge_goals"])
    res = {(r["date"], r["home"], r["away"]): r for r in results.to_dict("records")}
    c = closes.copy(); c["gd"] = pd.to_numeric(c["gd_fit"], errors="coerce")
    for r in c.dropna(subset=["gd"]).sort_values("date").to_dict("records"):
        d, hm, aw = r["date"], r["home"], r["away"]
        if d not in fits or hm not in idx or aw not in idx:
            continue
        Rw = fits[d]
        fac = 0.0
        if betas:
            from sim.factors import factor_vector
            fac = factor_vector(betas, F.x_actual(d, hm, aw))
        from scripts.refresh_ratings import implied_pair
        ih, ia = implied_pair(float(r["gd"]), he, float(deltas.get(hm, 0.0)), fac, float(Rw[idx[hm]]), float(Rw[idx[aw]]))   # full-health, opponent at its match-morning rating
        rr = res.get((d, hm, aw)); ok = rr is not None and str(rr.get("hg", "")) != ""
        score, score_a = (f"{rr['hg']}-{rr['ag']}", f"{rr['ag']}-{rr['hg']}") if ok else ("", "")
        book = "" if str(r.get("book", "")).startswith("pinnacle") else "market-average close"
        out["implied"][hm].append([d, codes.get(aw, ""), "v", R3(ih), R3(float(r["gd"])), R3(fac), score, book])
        out["implied"][aw].append([d, codes.get(hm, ""), "@", R3(ia), R3(float(r["gd"])), R3(-fac), score_a, book])
    # model changes
    if os.path.exists(METHOD_LOG):
        lg = pd.read_csv(METHOD_LOG)
        for r in lg.to_dict("records"):
            u = dt.datetime.fromisoformat(str(r["utc"]).replace("Z", "+00:00"))
            out["log"].append({"utc": str(r["utc"]), "et": et_str(u), "kind": r["kind"], "change": r["change"]})
    return out


def replay_fits(kn: dict, rat: dict, closes: pd.DataFrame, sch: pd.DataFrame, resmap: dict, T: list, hlog: pd.DataFrame, variants: bool = False):
    """date -> ratings over T on the morning of every played date of the season, by today's method: the full-health Kalman filter
    on every close before the date WITHOUT that round's Pinnacle lines (Zac, 2026-10-19), the xG blend at the source weights and that
    week's hand adjustments. The Games tab prices played games off these, the History tab draws them, morning.py scores them.
    With variants=True also returns the Games tab's two alternative versions (Zac 2026-10-19): `lines`, the same morning state with
    that round's Pinnacle lines applied as measurements (what the live ratings carry), and `stats`, the xG source alone (no
    Pinnacle data ever; rescaled to the filter's spread, no hand) -> (fits, fits_lines, fits_stats)."""
    from sim import data
    from sim.factors import betas_from_knobs
    from sim.layers import week_of, hand_week_values
    from sim.ratings import xg_fit, xg_with_goals
    from scripts.close_track import kalman_states, obs_cached
    betas = betas_from_knobs(kn)
    played_dates = sorted({x["date"] for x in sch.to_dict("records") if (x["date"], x["home"], x["away"]) in resmap})
    obs = obs_cached(closes[closes["season"].astype(str) != "posted"], bool(kn.get("kalman_openers", False)), 0.0, None, rat.get("club_deltas") or None, 0.0, betas)
    universe = sorted(set(obs["home"]) | set(obs["away"])); uidx = {t: i for i, t in enumerate(universe)}
    knk = {"q_day": kn["kalman_q_day"], "s": kn["kalman_s"], "p0": kn["kalman_p0"], "q_off": kn["kalman_q_off"], "prior_new": kn["expansion_prior_rating"],
           "off_shrink": float(kn.get("kalman_off_shrink", 1.0)), "s_posted": kn.get("kalman_s_posted", kn["kalman_s"])}
    w_used = rat.get("weights", {}); w_x = float(w_used.get("xg", 0.0)) / max(1e-9, sum(float(v) for v in w_used.values())) if w_used else 0.0
    xg_hist = xg_with_goals(data.num(data.load("xg_history"), ["home_xg", "away_xg"]), data.load("results"), float(kn.get("xg_goal_mix", 0) or 0)) if w_x > 0 else None
    def blend(states, keep_x=None):
        out = {}
        for d, (st, _) in states.items():
            v = np.array([st[uidx[t]] if t in uidx else knk["prior_new"] for t in T]); v = v - v.mean()
            if w_x > 0 and xg_hist is not None and len(xg_hist):
                xr = xg_fit(xg_hist, T, d, kn["xg_half_life_days"], kn["ridge_lambda"], float(v.std()))
                if xr["n"] > 0:
                    if keep_x is not None:
                        keep_x[d] = xr["ratings"] - xr["ratings"].mean()
                    v = (1 - w_x) * v + w_x * xr["ratings"]; v = v - v.mean()
            hv = hand_week_values(hlog, week_of(d))[0] if len(hlog) else {}
            out[d] = v + np.array([float(hv.get(t, 0.0)) for t in T])
        return out
    xonly = {}
    fits = blend(kalman_states(obs, universe, played_dates, knk, None), xonly if variants else None)
    if not variants:
        return fits
    # that round's lines (the closes of the next three days, already net of home edge, club delta and factors) as posted measurements
    posted = {}
    for d in played_dates:
        hi = (pd.Timestamp(d) + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        cur = obs[(obs["date"] >= d) & (obs["date"] < hi)]
        if len(cur):
            posted[d] = cur[["home", "away", "y"]]
    knp = dict(knk, s_posted=kn.get("kalman_s_posted", kn["kalman_s"]))
    fits_lines = blend(kalman_states(obs, universe, played_dates, knp, posted))
    return fits, fits_lines, xonly
