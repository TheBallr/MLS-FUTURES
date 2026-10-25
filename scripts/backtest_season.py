#!/usr/bin/env python3
"""Rest-of-season backtest (the method PDF's season-level backtest, extended as Zac asked): from checkpoints in every past
season, build ratings by a recipe from data strictly before the checkpoint, lock the results before it, simulate the remainder,
and score (a) final points: log-pmf of the actual total, rmse of expected points, PIT tails (share of teams in the sim's 10%
tails each side; 20% combined is honest), (b) the remaining matches: H/D/A log-loss of the actual results from the static
ratings and rmse against the closes, (c) playoff qualification, conference winner, Shield and Spoon log-loss.

Two stages. `ratings` scores recipes without a sim (match log-loss, close rmse, analytic expected-points rmse, spread) over a
grid of half-life, ridge, xG weight and half-life, rescaling. `sim` runs the season engine for named recipes over a grid of
(rating_sd, drift_k_sim) pairs. Every row is one (recipe, variant, season, checkpoint) and goes to outputs/calibration/backtest/.
Comparisons are paired: the same seed at the same checkpoint for every recipe.

Usage:
  python3 scripts/backtest_season.py ratings --name grid1 [--recipes recipes.json]
  python3 scripts/backtest_season.py sim --name sd_drift --recipes recipes.json --sd 0,0.15,0.3 --drift 0,0.005,0.01 [--n 4000]
  python3 scripts/backtest_season.py summary outputs/calibration/backtest/grid1.csv --baseline market_live --metric match_ll
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, os, pickle, sys, time
from functools import lru_cache
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT
from sim.ratings import market_fit, xg_fit
from sim.engine import hda
from sim.markets import Archive
from scripts.replay import seasons_on_file, season_teams, simulate_from, actual_table, score_archive, conf_array, conf_map_for, playoff_spots
from scripts.refresh_ratings import closes_with_targets


def _he_at(table: dict, date: str) -> float:
    keys = [k for k in table if k <= date]
    return table[max(keys)] if keys else 0.45


def obs_universe(obs: pd.DataFrame) -> list:
    return sorted(set(obs["home"]) | set(obs["away"]))

OUT = os.path.join(ROOT, "outputs", "calibration", "backtest")
CACHE = os.path.join(ROOT, "outputs", "cache", "backtest_inputs.pkl")
CHECK_MW = [4, 9, 14, 19, 24, 29]   # average matches per club already played at each checkpoint
PHASE = {4: "early", 9: "early", 14: "mid", 19: "mid", 24: "late", 29: "late"}

# Named recipes. Keys: half_life, ridge (market fit); xg_w (blend weight of xG), xg_hl, xg_ridge, xg_rescale (xG spread set to the
# market's before blending); blend_rescale ("market": blend spread set back to the market fit's spread); spread_mult (final multiplier).
# "live" = the model on the page, read from config at run time (scripts/recipes.py); the least-squares recipes that carried the
# name until 2026-10-21 are *_wls_retired. Recipe files may use {"base": "live", ...overrides}.
from scripts.recipes import default_recipes, resolve, club_deltas
RECIPES = default_recipes()


def _sig(paths):
    h = hashlib.md5()
    for p in paths:
        if os.path.exists(p):
            h.update(f"{p}:{os.path.getsize(p)}:{int(os.path.getmtime(p))}".encode())
    return h.hexdigest()


def load_inputs(refresh=False) -> dict:
    """seasons (season -> matches with closes and results), closes (every close on file), xg (every xG game). Cached on disk."""
    cfg = load_config()
    paths = [os.path.join(ROOT, "data", "history", f) for f in sorted(os.listdir(os.path.join(ROOT, "data", "history")))]
    paths += [data.path("closing_lines"), data.path("results"), data.path("xg_history")]
    sig = _sig(paths)
    if not refresh and os.path.exists(CACHE):
        try:
            with open(CACHE, "rb") as f:
                c = pickle.load(f)
            if c.get("sig") == sig:
                return c
        except Exception:
            pass
    seasons = seasons_on_file(cfg)
    closes = closes_with_targets(cfg)
    closes["date"] = pd.to_datetime(closes["date"]).dt.strftime("%Y-%m-%d")
    xg = data.num(data.load("xg_history"), ["home_xg", "away_xg"])
    xg["date"] = pd.to_datetime(xg["date"]).dt.strftime("%Y-%m-%d")
    c = {"sig": sig, "seasons": seasons, "closes": closes, "xg": xg}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "wb") as f:
        pickle.dump(c, f)
    return c


def checkpoints_mw(df: pd.DataFrame, mws=CHECK_MW) -> list[tuple[int, str]]:
    """(matchweek, date) pairs: the first date by which every club has played about `mw` matches on average."""
    n = len(season_teams(df))
    per_date = df.groupby("date").size().sort_index()
    before = (per_date.cumsum().shift(1).fillna(0) * 2 / n)
    out = []
    for mw in mws:
        hit = before[before >= mw]
        if len(hit):
            out.append((mw, str(hit.index[0])))
    return out


def season_context(df: pd.DataFrame, cp: str, closes: pd.DataFrame, T: list) -> dict:
    """Home edge and average total for the season as known at the checkpoint: HE from a 180-day-half-life fit on every close
    before cp (jointly with ratings), the total from this season's results before cp (fallback: all closes' T_fit)."""
    mk = market_fit(closes, T, cp, 180.0, 0.0, fit_home_edge=True, before=True)
    he = float(mk["home_edge"]) if mk["n"] >= 60 else 0.45
    bef = df[df["date"] < cp]
    tot = (bef["hg"].astype(float) + bef["ag"].astype(float))
    if len(tot) >= 40:
        T_avg = float(tot.mean())
    else:
        prev = closes[(closes["date"] < cp)].tail(400)
        T_avg = float(pd.to_numeric(prev["T_fit"], errors="coerce").mean()) if len(prev) else 3.0
        if not np.isfinite(T_avg):
            T_avg = 3.0
    return {"he": he, "T_avg": T_avg}


def ratings_for(recipe: dict, T: list, cp: str, closes: pd.DataFrame, xg: pd.DataFrame, he: float, extra: dict | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
    """Returns (blend, market-only, info). `extra` may carry a public source: {"name": {"ratings": vector aligned to T, "w": weight}}."""
    ridge = float(recipe.get("ridge", 0.5)); fade = recipe.get("ridge_fade_mw")
    season = str(pd.Timestamp(cp).year); this = closes[(closes["season"].astype(str) == season) & (closes["date"] < cp)]
    mw_played = 2.0 * len(this) / max(1, len(T))
    if fade:  # ridge phases out with the season's data: full at matchweek 0, zero from matchweek `fade`
        ridge = ridge * max(0.0, 1.0 - mw_played / float(fade))
    fit_frame = closes
    if recipe.get("posted_in_fit"):  # the current round's lines (closes dated within 3 days of the checkpoint) enter the fit as fresh closes (age 1 day)
        cur = closes[(closes["date"] >= cp) & (closes["date"] <= (pd.Timestamp(cp) + pd.Timedelta(days=3)).strftime("%Y-%m-%d"))].copy()
        cur["date"] = (pd.Timestamp(cp) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        fit_frame = pd.concat([closes[closes["date"] < cp], cur], ignore_index=True)
    if "kalman" in recipe:  # Kalman-filter ratings (sim/kalman.py) in place of the half-life fit; posted_in_fit applies the current round's lines to a copy of the state
        from scripts.close_track import kalman_states, he_table_cached, obs_cached
        knk = dict(recipe["kalman"]); tab = he_table_cached(closes)
        fac = recipe.get("factors") or None   # named factors netted out of every close (sim/factors.py, CLAUDE.md 14)
        dl = club_deltas(recipe)
        obs = obs_cached(closes, bool(recipe.get("openers")), float(recipe.get("kf_xg_sd", 0) or 0), xg, dl, 0.0, fac)
        posted = None
        if recipe.get("posted_in_fit"):
            cur = closes[(closes["date"] >= cp) & (closes["date"] <= (pd.Timestamp(cp) + pd.Timedelta(days=3)).strftime("%Y-%m-%d"))]
            if len(cur):
                from scripts.close_track import factor_adj
                posted = {cp: pd.DataFrame({"home": cur["home"], "away": cur["away"], "y": cur["gd_fit"].astype(float) - cur["date"].map(lambda x: _he_at(tab, x)) - (factor_adj(cur["date"], cur["home"], cur["away"], fac) if fac else 0.0)
                                        - (cur["home"].map(dl).fillna(0.0).astype(float) if dl else 0.0)})}
        universe = obs_universe(obs)
        st = kalman_states(obs, universe, [cp], knk, posted)[cp][0]
        uidx = {t: i for i, t in enumerate(universe)}
        Rm = np.array([st[uidx[t]] if t in uidx else float(knk.get("prior_new", -0.25)) for t in T]); Rm = Rm - Rm.mean()
        mk = {"n": int(len(fit_frame[fit_frame["date"] < cp])), "ratings": Rm}
    else:
        mk = market_fit(fit_frame, T, cp, float(recipe.get("half_life", 28)), ridge, fit_home_edge=False, home_edge_fixed=he, before=True)
        Rm = mk["ratings"].copy()
    if recipe.get("conf_offset_hl"):  # conference mean difference taken from a longer window (cross-conference links are few in 28 days)
        mk2 = market_fit(fit_frame, T, cp, float(recipe["conf_offset_hl"]), 0.0, fit_home_edge=False, home_edge_fixed=he, before=True)
        from scripts.replay import conf_array
        cf = conf_array(T, season)
        for c in (0, 1):
            Rm[cf == c] += mk2["ratings"][cf == c].mean() - Rm[cf == c].mean()
        Rm -= Rm.mean()
    parts = [(1.0, Rm)]
    info = {"n_closes": mk["n"], "market_sd": float(Rm.std()), "ridge_used": ridge, "mw_played": mw_played}
    w_x = float(recipe.get("xg_w", 0.0))
    if w_x > 0:
        xr = xg_fit(xg, T, cp, float(recipe.get("xg_hl", 45)), float(recipe.get("xg_ridge", recipe.get("ridge", 0.5))),
                    float(Rm.std()) if recipe.get("xg_rescale", True) and mk["n"] else None)
        if xr["n"] > 0:
            parts = [(1.0 - w_x, Rm), (w_x, xr["ratings"])]
            info["xg_n"] = xr["n"]; info["xg_sd_raw"] = float(xr["ratings"].std())
    for name, src in (extra or {}).items():
        w_p = float(src.get("w", 0.0))
        if w_p > 0 and src.get("ratings") is not None:
            v = np.asarray(src["ratings"], float); v = v - v.mean()
            if src.get("rescale", True) and v.std() > 1e-9:
                v = v * (Rm.std() / v.std())
            parts = [(w * (1.0 - w_p), r) for w, r in parts] + [(w_p, v)]
            info[f"{name}_sd"] = float(v.std())
    R = sum(w * r for w, r in parts); R = R - R.mean()
    if recipe.get("blend_rescale") == "market" and R.std() > 1e-9:
        R = R * (Rm.std() / R.std())
    R = R * float(recipe.get("spread_mult", 1.0))
    info["blend_sd"] = float(R.std()); info["spread_ratio"] = float(R.std() / Rm.std()) if Rm.std() > 1e-9 else np.nan
    return R, Rm, info


@lru_cache(maxsize=400000)
def _hda_cached(g: float, Tt: float, floor: float, shared: float, rho: float = 0.0):
    return hda(g, Tt, floor, shared, rho)


def match_metrics(R: np.ndarray, after: pd.DataFrame, idx: dict, he: float, T_avg: float, kn: dict, locked: np.ndarray, fixture_adj: dict | None = None) -> dict:
    """Static ratings on the remaining matches: H/D/A log-loss of the actual results, rmse against the closes' gd_fit,
    analytic expected final points (locked + sum of 3p_w + p_d)."""
    ll = []; sq = []; exp_pts = locked.astype(float).copy(); ll_later = []
    floor, shared = kn["goal_floor"], kn["shared_goals_mean"]
    Tt = round(float(T_avg), 2)
    cur_end = (pd.Timestamp(after["date"].min()) + pd.Timedelta(days=3)).strftime("%Y-%m-%d") if len(after) else ""
    for r in after.itertuples(index=False):
        h, a = idx[r.home], idx[r.away]
        g = R[h] - R[a] + he + (fixture_adj.get((r.date, r.home, r.away), 0.0) if fixture_adj else 0.0)
        ph, pdr, pa = _hda_cached(round(float(g), 3), Tt, floor, shared, float(kn.get("dc_rho", 0.0) or 0.0))
        hg, ag = int(float(r.hg)), int(float(r.ag))
        p = ph if hg > ag else (pdr if hg == ag else pa)
        ll.append(-np.log(max(p, 1e-6)))
        if r.date > cur_end:
            ll_later.append(-np.log(max(p, 1e-6)))
        gf = float(r.gd_fit)
        if np.isfinite(gf):
            sq.append((gf - g) ** 2)
        exp_pts[h] += 3 * ph + pdr; exp_pts[a] += 3 * pa + pdr
    return {"match_ll": float(np.mean(ll)) if ll else np.nan, "match_ll_later": float(np.mean(ll_later)) if ll_later else np.nan, "close_rmse": float(np.sqrt(np.mean(sq))) if sq else np.nan, "n_matches": len(ll), "exp_points": exp_pts}


def pit_tails(points: np.ndarray, actual: np.ndarray) -> dict:
    """Expected share of teams in the sim's 10% tails (randomised PIT for the discrete points total, u integrated out)."""
    below = (points < actual[None, :]).mean(axis=0); pmf = (points == actual[None, :]).mean(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        lo = np.where(pmf > 0, np.clip((0.10 - below) / pmf, 0, 1), (below < 0.10).astype(float))
        hi = np.where(pmf > 0, np.clip((below + pmf - 0.90) / pmf, 0, 1), (below >= 0.90).astype(float))
    pit = below + 0.5 * pmf
    return {"tail_lo": float(lo.mean()), "tail_hi": float(hi.mean()), "tails": float(lo.mean() + hi.mean()), "pit_mean": float(pit.mean()),
            "pit_sd": float(pit.std()), "pit_mid": float(((pit > 0.25) & (pit < 0.75)).mean())}


_XG_MIXED = {}


def _xg_for(rec: dict, xg: pd.DataFrame) -> pd.DataFrame:
    """The xG frame a recipe sees: `xg_goal_mix` m replaces each match's xG with (1-m) x xG + m x goals (close_track's _mix_xg,
    the goal-difference source of CLAUDE.md 14l)."""
    mix = float(rec.get("xg_goal_mix", 0.0) or 0.0)
    if mix <= 0:
        return xg
    if mix not in _XG_MIXED:
        from scripts.close_track import _mix_xg
        goals = pd.concat([df[["date", "home", "away", "hg", "ag"]] for df in _INPUTS["seasons"].values()], ignore_index=True)
        _XG_MIXED[mix] = _mix_xg(xg, goals.drop_duplicates(["date", "home", "away"]), mix)
    return _XG_MIXED[mix]


def _fixture_adj(rec: dict, after: pd.DataFrame, cp: str) -> dict | None:
    """Per remaining fixture, goals on the home margin: the factors added back as forecast at the checkpoint (abs_mode: actual =
    ceiling, trail10 = honest) plus the home club's delta when the recipe has club_he (the live build prices both)."""
    fac = rec.get("factors"); dl = club_deltas(rec) or {}
    if not fac and not dl:
        return None
    if fac:
        from sim.factors import factors as _factors, factor_vector
        F = _factors(); mode = str(rec.get("abs_mode", "trail10"))
    return {(r.date, r.home, r.away): (factor_vector(fac, F.x_expected(r.date, r.home, r.away, cp, mode)) if fac else 0.0) + dl.get(r.home, 0.0)
            for r in after.itertuples(index=False)}


def _job(args):
    """One (season, checkpoint): every recipe (and variant) scored. Runs in a worker; inputs come from the module global."""
    season, mw, cp, recipes, variants, n_seasons, seed, stage = args
    inp = _INPUTS
    df = inp["seasons"][season]; closes = inp["closes"]; xg = inp["xg"]
    cfg = load_config(); kn0 = knobs(cfg); kn0.update(json.loads(os.environ.get("BT_KNOBS", "{}")))  # e.g. BT_KNOBS='{"dc_rho": -0.05}'
    T = season_teams(df); idx = {t: i for i, t in enumerate(T)}; conf = conf_array(T, season)
    ctx = season_context(df, cp, closes, T)
    before = df[df["date"] < cp]; after = df[df["date"] >= cp]
    actual = actual_table(df, T, conf_map_for(season)); act_pts = np.array([actual[t]["points"] for t in T])
    from scripts.run_sim import played_stats
    locked = played_stats(before, T)["points"]
    spots = playoff_spots(season)
    rows = []
    for name, rec in recipes.items():
        R, Rm, info = ratings_for(rec, T, cp, closes, _xg_for(rec, xg), ctx["he"], extra=_public_for(rec, season, cp, T))
        mm_adj = _fixture_adj(rec, after, cp)
        mm = match_metrics(R, after, idx, ctx["he"], ctx["T_avg"], kn0, locked, mm_adj)
        base = {"recipe": name, "season": season, "mw": mw, "phase": PHASE.get(mw, ""), "cp": cp, "n_matches": mm["n_matches"], "match_ll": mm["match_ll"], "match_ll_later": mm["match_ll_later"],
                "close_rmse": mm["close_rmse"], "pts_rmse_static": float(np.sqrt(((mm["exp_points"] - act_pts) ** 2).mean())),
                "he": ctx["he"], "T_avg": ctx["T_avg"], **{k: v for k, v in info.items()}}
        if stage == "ratings":
            rows.append(base); continue
        fx_adj = mm_adj
        for (sd, k) in variants:
            kn = dict(kn0); kn["rating_sd"] = sd; kn["drift_k_sim"] = k; kn["home_edge_goals"] = ctx["he"]; kn["avg_total_goals"] = ctx["T_avg"]; kn["playoff_spots"] = spots
            out = simulate_from(df, cp, kn, T, conf, n_seasons=n_seasons, seed=seed, ratings=R, use_closes_as_lines=float(os.environ.get("BT_CURRENT", "0")) or False, fixture_adj=fx_adj)
            arc = Archive(out)
            sc = score_archive(arc, actual, T, spots)
            tails = pit_tails(arc.points.astype(int), act_pts)
            rows.append({**base, "rating_sd": sd, "drift_k": k, **sc, **tails})
    return rows


_INPUTS = None
_PUBLIC = {}


def _public_for(rec: dict, season: str, cp: str, T: list) -> dict | None:
    """Public-source ratings for a recipe at a checkpoint: rec["public"] = {"name": weight}; the vectors come from _PUBLIC
    loaders registered by scripts that add a source (name -> callable(season, cp, T) -> vector or None)."""
    pub = rec.get("public")
    if not pub:
        return None
    out = {}
    for name, w in pub.items():
        fn = _PUBLIC.get(name)
        if fn is None:
            continue
        v = fn(season, cp, T)
        if v is not None:
            out[name] = {"ratings": v, "w": w, "rescale": rec.get("public_rescale", True)}
    return out or None


def run(stage: str, name: str, recipes: dict, variants=None, n_seasons=4000, seed=11, seasons=None, workers=4, mws=CHECK_MW) -> pd.DataFrame:
    global _INPUTS
    _INPUTS = load_inputs()
    jobs = []
    for s, df in sorted(_INPUTS["seasons"].items()):
        if seasons and s not in seasons:
            continue
        if len(df) < 200:
            continue
        for mw, cp in checkpoints_mw(df, mws):
            if len(df[df["date"] >= cp]) < 20:
                continue
            jobs.append((s, mw, cp, recipes, variants or [], n_seasons, seed, stage))
    t0 = time.time()
    if workers > 1:
        with Pool(workers) as pool:
            res = pool.map(_job, jobs, chunksize=1)
    else:
        res = [_job(j) for j in jobs]
    rows = [r for rr in res for r in rr]
    out = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    out.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    print(f"backtest {stage} '{name}': {len(jobs)} season-checkpoints, {len(out)} rows, {time.time() - t0:.0f}s -> {os.path.join(OUT, name + '.csv')}")
    return out


METRICS_LOWER = {"match_ll": True, "close_rmse": True, "pts_rmse_static": True, "points_rmse": True, "points_logpmf": False, "playoffs_ll": True,
                 "conf_ll": True, "shield_ll": True, "spoon_ll": True}


def summarize(df: pd.DataFrame, baseline: str | None = None, metric: str = "match_ll", by=("recipe",), phases=False, mws=None) -> str:
    """Pooled means per recipe (and variant), plus per-season wins against the baseline on `metric`."""
    if mws:
        df = df[df["mw"].isin(mws)]
    by = list(by)
    if "rating_sd" in df.columns and "rating_sd" not in by:
        by += ["rating_sd", "drift_k"]
    cols = [c for c in ("match_ll", "close_rmse", "pts_rmse_static", "points_rmse", "points_logpmf", "tails", "tail_lo", "tail_hi", "playoffs_ll", "conf_ll", "shield_ll", "spoon_ll", "spread_ratio", "blend_sd") if c in df.columns]
    g = df.groupby(by)[cols].mean()
    lines = []
    if baseline is not None and metric in df.columns:
        per = df.groupby(by + ["season"])[metric].mean().unstack(by)
        base_key = tuple(baseline) if isinstance(baseline, (list, tuple)) else baseline
        wins = {}
        for key in g.index:
            k = key if isinstance(key, tuple) else (key,)
            bk = (base_key,) + tuple(k[1:]) if len(k) > 1 and not isinstance(base_key, tuple) else (base_key if isinstance(base_key, tuple) else (base_key,))
            try:
                a = per[k if len(k) > 1 else k[0]]; b = per[bk if len(bk) > 1 else bk[0]]
            except KeyError:
                wins[key] = ""; continue
            better = (a < b) if METRICS_LOWER.get(metric, True) else (a > b)
            wins[key] = f"{int(better.sum())}/{int(a.notna().sum())}"
        g[f"wins_vs_{baseline}"] = pd.Series(wins)
    with pd.option_context("display.width", 250, "display.max_columns", 40, "display.float_format", lambda x: f"{x:.4f}"):
        lines.append(g.to_string())
    if phases and "phase" in df.columns:
        gp = df.groupby(by + ["phase"])[cols].mean()
        with pd.option_context("display.width", 250, "display.max_columns", 40, "display.float_format", lambda x: f"{x:.4f}"):
            lines.append("\nby phase:\n" + gp.to_string())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["ratings", "sim", "summary"])
    ap.add_argument("target", nargs="?", help="summary: csv path")
    ap.add_argument("--name", default="run"); ap.add_argument("--recipes", help="json file {name: recipe}")
    ap.add_argument("--sd", default="0.3"); ap.add_argument("--drift", default="0.0"); ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--seasons", help="comma list"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--baseline"); ap.add_argument("--metric", default="match_ll"); ap.add_argument("--phases", action="store_true"); ap.add_argument("--mws")
    a = ap.parse_args()
    if a.stage == "summary":
        df = pd.read_csv(a.target)
        print(summarize(df, a.baseline, a.metric, phases=a.phases, mws=[int(x) for x in a.mws.split(",")] if a.mws else None)); return 0
    recipes = resolve(json.load(open(a.recipes))) if a.recipes else RECIPES
    variants = list(itertools.product([float(x) for x in a.sd.split(",")], [float(x) for x in a.drift.split(",")]))
    df = run(a.stage, a.name, recipes, variants, a.n, seasons=a.seasons.split(",") if a.seasons else None, workers=a.workers)
    print(summarize(df, "market_live" if "market_live" in recipes else None, "match_ll" if a.stage == "ratings" else "points_logpmf"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
