#!/usr/bin/env python3
"""Rebuild data/ratings/sources.csv (every source side by side) and blend.csv (generated, never edited) for a date.
Sources: market_recent (WLS on Pinnacle closes, half-life weights), xg (ASA match xG, rescaled to the market's spread).
Usage: python3 scripts/refresh_ratings.py [--asof 2026-10-12]"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import teams, load_teams, ROOT
from sim.ratings import fit_targets, market_fit, xg_fit, blend, apply_expansion_prior, load_club_home_edges, gd_fit_row, xg_with_goals

CACHE = os.path.join(ROOT, "outputs", "cache", "gd_fit.csv")
LINE_COLS = ["h", "d", "a", "ah_line", "ah_home", "ah_away", "total_line", "over", "under"]


def _key(r, rho=0.0) -> str:
    return hashlib.md5(("|".join(str(r.get(c, "")) for c in ["date", "home", "away", "book"] + LINE_COLS) + (f"|rho{rho}" if rho else "")).encode()).hexdigest()


def closes_with_targets(cfg: dict, include_history=True) -> pd.DataFrame:
    """One close per match (pinnacle_close > pinnacle_last > avg_close), this season plus history, with gd_fit (cached)."""
    kn = knobs(cfg)
    cl = data.load("closing_lines")
    frames = [cl.assign(season=str(cfg["season"]))]
    if include_history:
        h = data.load_history()
        if len(h):
            h = h.rename(columns={})
            for c in LINE_COLS:
                if c not in h.columns:
                    h[c] = ""
            frames.append(h[["season", "date", "home", "away", "book"] + LINE_COLS])
    df = pd.concat(frames, ignore_index=True)
    if len(df) == 0:
        return pd.DataFrame(columns=["season", "date", "home", "away", "book"] + LINE_COLS + ["gd_fit", "gd_3way", "gd_ah", "T_fit", "ph", "pd", "pa"])
    pri = {"pinnacle_close": 0, "pinnacle_last": 1, "avg_close": 2}
    df["_p"] = df["book"].map(pri).fillna(3)
    df["_ah"] = (df["ah_line"].astype(str) == "").astype(int)  # a close with the handicap outranks the same book's three-way-only row
    df = df.sort_values(["_p", "_ah"]).drop_duplicates(["date", "home", "away"]).drop(columns=["_p", "_ah"])
    rho = float(kn.get("dc_rho", 0.0) or 0.0)
    df["_k"] = [_key(r, rho) for r in df.to_dict("records")]
    cache = pd.read_csv(CACHE, dtype={"_k": str}) if os.path.exists(CACHE) else pd.DataFrame(columns=["_k", "gd_fit", "gd_3way", "gd_ah", "T_fit", "ph", "pd", "pa"])
    have = df["_k"].isin(cache["_k"])
    todo = df[~have]
    if len(todo):
        fitted = fit_targets(todo[LINE_COLS], kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], rho)
        fitted["_k"] = todo["_k"].to_numpy()
        cache = pd.concat([cache, fitted[["_k", "gd_fit", "gd_3way", "gd_ah", "T_fit", "ph", "pd", "pa"]]], ignore_index=True)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        cache.to_csv(CACHE, index=False)
    out = df.merge(cache.drop_duplicates("_k"), on="_k", how="left").drop(columns="_k")
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def with_posted_lines(closes: pd.DataFrame, asof: str, kn: dict, fresh_days: float = 3.0) -> pd.DataFrame:
    """Append the latest posted Pinnacle line per unplayed fixture (fetched within fresh_days of asof) to the closes, dated the day
    before asof, with gd_fit from the same targets as a close. Fixtures that already have a close are left to the close."""
    from scripts.run_sim import latest_posted
    posted = latest_posted(data.load("current_round_odds"), fresh_days=fresh_days, asof=asof)
    if not posted:
        return closes
    have = set(zip(closes["date"], closes["home"], closes["away"]))
    rows = []
    yday = (pd.Timestamp(asof) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    for (d, h, a), r in posted.items():
        if (d, h, a) in have or d < asof:
            continue
        gf = gd_fit_row(r.get("h"), r.get("d"), r.get("a"), r.get("ah_line") or None, r.get("ah_home"), r.get("ah_away"), r.get("total_line") or None, r.get("over"), r.get("under"),
                        kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
        if np.isfinite(gf["gd_fit"]):
            rows.append({"season": "posted", "date": yday, "home": h, "away": a, "book": "pinnacle_posted", "gd_fit": gf["gd_fit"], "T_fit": gf["T_fit"], "fixture_date": d})
    if not rows:
        return closes
    return pd.concat([closes, pd.DataFrame(rows)], ignore_index=True)


def kalman_market(fit_frame: pd.DataFrame, T: list, asof: str, kn: dict, deltas: dict, before: bool) -> tuple[np.ndarray, dict]:
    """Market ratings from the Kalman filter: every close on file (plus posted lines when posted_in_fit, which arrive in
    fit_frame dated asof-1) net of the league home edge as known month by month and the home club's delta, filtered to asof.
    Knobs: kalman_q_day, kalman_s, kalman_p0, kalman_q_off, kalman_openers, kalman_xg_sd (xG differences fused as noisy
    measurements), kalman_s_posted."""
    from scripts.close_track import obs_cached, he_table_cached, kalman_states
    from sim.kalman import measurements
    closes = fit_frame[fit_frame["season"].astype(str) != "posted"]
    posted_rows = fit_frame[fit_frame["season"].astype(str) == "posted"]
    xg = data.num(data.load("xg_history"), ["home_xg", "away_xg"]) if float(kn.get("kalman_xg_sd", 0) or 0) > 0 else None
    from sim.factors import betas_from_knobs, factor_vector
    betas = betas_from_knobs(kn)   # full-health ratings (CLAUDE.md 14): every close net of its match-day factors
    obs = obs_cached(closes, bool(kn.get("kalman_openers", False)), float(kn.get("kalman_xg_sd", 0) or 0), xg, deltas or None, 0.0, betas)
    knk = {"q_day": kn["kalman_q_day"], "s": kn["kalman_s"], "p0": kn["kalman_p0"], "q_off": kn["kalman_q_off"], "prior_new": kn["expansion_prior_rating"],
           "s_posted": kn.get("kalman_s_posted", kn["kalman_s"]), "off_shrink": float(kn.get("kalman_off_shrink", 1.0)), "s_open": kn.get("kalman_s_open", 0.3)}
    cutoff = asof if before else (pd.Timestamp(asof) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    posted = None
    if len(posted_rows):
        tab = he_table_cached(closes); he = he_at_date(tab, asof)
        fac = 0.0
        if betas:  # the posted lines carry the current round's factors (absences from the live list, rest, eliminated status): net them out too
            from sim.factors import live_factors
            LF = live_factors(asof)
            fd = posted_rows["fixture_date"] if "fixture_date" in posted_rows.columns else posted_rows["date"]
            fac = np.array([factor_vector(betas, LF.x(str(d), h, a)) for d, h, a in zip(fd, posted_rows["home"], posted_rows["away"])])
        posted = {cutoff: pd.DataFrame({"home": posted_rows["home"], "away": posted_rows["away"],
                                       "y": posted_rows["gd_fit"].astype(float) - he - posted_rows["home"].map(deltas or {}).fillna(0.0).astype(float) - fac})}
    universe = sorted(set(obs["home"]) | set(obs["away"]))
    st, sd = kalman_states(obs, universe, [cutoff], knk, posted)[cutoff]
    uidx = {t: i for i, t in enumerate(universe)}
    R = np.array([st[uidx[t]] if t in uidx else float(knk["prior_new"]) for t in T]); R = R - R.mean()
    this = closes[(closes["season"].astype(str) == str(closes["season"].max())) & (closes["date"] < cutoff)]
    idx = {t: i for i, t in enumerate(T)}
    n_closes = np.bincount(np.concatenate([this["home"].map(idx).dropna().astype(int).to_numpy(), this["away"].map(idx).dropna().astype(int).to_numpy()]), minlength=len(T)) if len(this) else np.zeros(len(T), int)
    return R, {"ratings": R, "n": int((obs["date"] < cutoff).sum()), "resid_sd": np.nan, "n_closes": n_closes, "home_edge": kn["home_edge_goals"], "kalman_sd": np.array([sd[uidx[t]] if t in uidx else knk["p0"] for t in T])}


def team_totals(closes: pd.DataFrame, T: list, asof: str, kn: dict) -> dict:
    """Per-club total offsets for the run (empty when team_totals_enabled is off): fixture total = base + u_h + u_a, clipped to
    [2.0, 4.5]. Returns {"base": float, "offsets": {team: goals}} or {} when off / too few totals."""
    if not kn.get("team_totals_enabled", False):
        return {}
    from sim.ratings import totals_fit
    f = totals_fit(closes, T, asof, float(kn.get("team_totals_half_life", 30)), float(kn.get("team_totals_ridge", 0.25)))
    if not np.isfinite(f["base"]):
        return {}
    return {"base": float(f["base"]), "offsets": {t: float(u) for t, u in zip(T, f["offsets"])}}


def fixture_total(tt: dict, home: str, away: str, default: float) -> float:
    if not tt:
        return float(default)
    return float(np.clip(tt["base"] + tt["offsets"].get(home, 0.0) + tt["offsets"].get(away, 0.0), 2.0, 4.5))


def he_table_cached_safe(closes: pd.DataFrame) -> dict:
    from scripts.close_track import he_table_cached
    return he_table_cached(closes[closes["season"].astype(str) != "posted"])


def he_at_date(table: dict, date: str) -> float:
    keys = [k for k in table if k <= date]
    return table[max(keys)] if keys else 0.45


def build_ratings(asof: str, cfg: dict, closes: pd.DataFrame | None = None, xg_hist: pd.DataFrame | None = None, write=True, before=False) -> dict:
    kn = knobs(cfg)
    T = teams()
    closes = closes_with_targets(cfg) if closes is None else closes
    deltas = load_club_home_edges(kn.get("club_home_edge_enabled", False))
    ridge = float(kn["ridge_lambda"]); fade = float(kn.get("ridge_fade_mw", 0) or 0)
    if fade > 0:  # ridge phases out with this season's data: full at matchweek 0, zero from matchweek `fade`
        this = closes[(closes["season"].astype(str) == str(cfg["season"])) & (closes["date"] < asof)]
        ridge = ridge * max(0.0, 1.0 - (2.0 * len(this) / max(1, len(T))) / fade)
    fit_frame = closes
    if kn.get("posted_in_fit"):  # the current round's fresh Pinnacle lines enter the fit as closes dated yesterday (PDF: every posted spread is one equation)
        fit_frame = with_posted_lines(closes, asof, kn)
    if str(kn.get("rating_method", "wls")) == "kalman":  # Kalman-filter ratings on the closes (sim/kalman.py; CLAUDE.md section 13)
        R_m, mk = kalman_market(fit_frame, T, asof, kn, deltas, before)
    else:
        mk = market_fit(fit_frame, T, asof, kn["half_life_days"], ridge, fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=before, club_deltas=deltas)
        R_m = mk["ratings"]
    n_closes = mk["n_closes"]
    exp_mask = np.array([int(r["expansion_year"]) >= int(cfg["season"]) - 1 for r in load_teams()])
    R_m = apply_expansion_prior(R_m, n_closes, kn["expansion_prior_rating"], kn["expansion_closes_threshold"], exp_mask)
    sources = {"market_recent": R_m}
    xg_hist = data.load("xg_history") if xg_hist is None else xg_hist
    xg_hist = xg_with_goals(data.num(xg_hist, ["home_xg", "away_xg"]), data.load("results"), float(kn.get("xg_goal_mix", 0) or 0)) if len(xg_hist) else xg_hist
    xg = xg_fit(xg_hist, T, asof, kn["xg_half_life_days"], kn["ridge_lambda"], float(R_m.std()) if mk["n"] else None) if len(xg_hist) else {"ratings": np.zeros(len(T)), "n": 0}
    if xg["n"] > 0:
        sources["xg"] = xg["ratings"]
    sc = data.load("source_config")
    if len(sc) == 0:
        sc = pd.DataFrame([{"source": "market_recent", "enabled": "y", "weight": 1.0, "note": "backbone"}, {"source": "xg", "enabled": "y", "weight": 1.0, "note": "ASA xG; weight after scorecard"}])
    R, used = blend(sources, sc)
    from sim.layers import rating_adjustments, week_of, hand_week_values
    hand_log = data.load("hand_log")
    hand = rating_adjustments(data.load("adjustments"), asof, hand_log)  # the week's hand adjustments (Zac's word) sit on top of the blend
    hand_week = week_of(asof); _, hand_week_used = hand_week_values(hand_log, hand_week)
    hand_vec = np.array([hand.get(t, 0.0) for t in T])
    R_used = R + hand_vec
    out = {"asof": asof, "ratings": R_used, "blend_raw": R, "hand": hand, "hand_week": hand_week, "hand_week_used": hand_week_used, "sources": sources, "weights": used, "n_closes": n_closes, "market_fit": mk, "xg_n": xg["n"], "teams": T, "club_deltas": deltas}
    if write:
        src = pd.DataFrame({"team": T, **{k: np.round(v, 4) for k, v in sources.items()}, "n_closes": n_closes})
        data.save("sources", src)
        data.save("blend", pd.DataFrame({"team": T, "rating": np.round(R_used, 4), "blend_raw": np.round(R, 4), "hand_adj": np.round(hand_vec, 4), "n_closes": n_closes, "generated": asof}))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--asof", default=dt.date.today().isoformat()); a = ap.parse_args()
    cfg = load_config()
    out = build_ratings(a.asof, cfg)
    mk = out["market_fit"]
    print(f"refresh_ratings: {mk['n']} closes in fit, residual sd {mk['resid_sd']:.3f} goals, xg games {out['xg_n']}, weights {out['weights']}")
    order = np.argsort(-out["ratings"])
    print("  " + ", ".join(f"{out['teams'][i]} {out['ratings'][i]:+.2f}" for i in order[:5]) + " ... " + ", ".join(f"{out['teams'][i]} {out['ratings'][i]:+.2f}" for i in order[-3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
