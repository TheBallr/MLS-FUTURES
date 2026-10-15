#!/usr/bin/env python3
"""Close-tracking yardstick (Zac, 2026-10-15: "we are trying to track the close and match Pinnacle's close").

Walk-forward over every match date of every season on file: ratings are built from the closes strictly before `asof`, and
each close dated d is scored from asof = d - lag days (lag 0: the ratings on the morning of the match; lag 7: the ratings a
week out, which is what the futures sim actually uses because the current round is priced off Pinnacle's posted line).
The score is the gap between the close's expected margin (gd_fit) and the model's (R_h - R_a + home edge): rmse, bias, the
slope of the close on the model (1.0 = right spread; above 1 = the model is too flat), the cross-conference and
within-conference rmse, by season and phase (early: before matchweek 10; mid: 10-22; late: after 22).

Recipes: the half-life least-squares fit (`half_life`, `ridge`, `xg_w`, `xg_hl`, `posted_in_fit`, as in backtest_season) and
the Kalman filter (`kalman`: {q_day, s, p0, q_off, ...}, plus `openers` to feed Pinnacle's openers as earlier measurements,
`xg_w` for the xG blend, `posted_in_fit` for the current round's lines, `kf_xg_sd` to fuse xG inside the filter).
Posted-in-fit recipes are only honest at lag >= 4 (at lag 0 the scored close is the posted line).

Usage: python3 scripts/close_track.py --name track1 [--recipes recipes.json] [--lags 0,7] [--workers 4] [--seasons 2024,2025,2026]
       python3 scripts/close_track.py summary outputs/calibration/close_track/track1.csv [--lag 7] [--baseline live]
"""
from __future__ import annotations
import argparse, json, os, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim.teams import ROOT
from sim.ratings import market_fit, xg_fit
from sim.kalman import KalmanRatings, measurements
from scripts.replay import season_teams, conf_array
from scripts.backtest_season import load_inputs, ratings_for

OUT = os.path.join(ROOT, "outputs", "calibration", "close_track")
RECIPES = {
    "market_live": {"half_life": 28, "ridge": 0.5},
    "live": {"half_life": 28, "ridge": 0.5, "xg_w": 0.25, "xg_hl": 45},
    "posted": {"half_life": 28, "ridge": 0.5, "xg_w": 0.25, "xg_hl": 45, "posted_in_fit": True},
    "kalman": {"kalman": {}},
}
_INPUTS = None


def phase_of(mw: float) -> str:
    return "early" if mw < 10 else ("mid" if mw < 22 else "late")


def home_edge_by_season(closes: pd.DataFrame, seasons: list) -> dict:
    """League home edge as known at the time: on the first of every month a plain fit (ridge 0, 90-day half-life) on every close
    before it; the value for a date is the latest monthly value. Returns {season: {month_start: he}} flattened to a lookup
    function via `he_at`. Kept simple on purpose: the yardstick is the ratings, not the edge."""
    out = {}
    prev = 0.45
    months = pd.date_range(f"{min(seasons)}-02-01", f"{max(seasons)}-12-01", freq="MS")
    for m in months:
        cp = m.strftime("%Y-%m-%d")
        sub = closes[closes["date"] < cp]
        T = sorted(set(sub["home"]) | set(sub["away"]))
        mk = market_fit(sub, T, cp, 90.0, 0.0, fit_home_edge=True, before=True) if len(sub) >= 60 else {"n": 0}
        out[cp] = float(mk["home_edge"]) if mk["n"] >= 60 else prev
        prev = out[cp]
    return out


def he_at(table: dict, date: str) -> float:
    keys = [k for k in table if k <= date]
    return table[max(keys)] if keys else 0.45


_HE_CACHE = {}
_OBS_CACHE = {}


def he_table_cached(closes: pd.DataFrame) -> dict:
    """The monthly home-edge table for a closes frame (keyed on its size and date range), built once per process."""
    key = (len(closes), str(closes["date"].min()), str(closes["date"].max()))
    if key not in _HE_CACHE:
        seasons = sorted(set(closes["season"].astype(str)) - {"posted"})
        _HE_CACHE[key] = home_edge_by_season(closes, seasons)
    return _HE_CACHE[key]


def obs_cached(closes: pd.DataFrame, openers: bool, xg_sd: float, xg: pd.DataFrame | None = None, club_deltas: dict | None = None) -> pd.DataFrame:
    """Measurement frame for the Kalman filter from a closes frame: closes net of the monthly home edge (plus the home club's
    delta when given), optionally Pinnacle's openers (sd s_open) and the xG differences (sd xg_sd), built once per process."""
    key = (len(closes), str(closes["date"].max()), openers, xg_sd, bool(club_deltas))
    if key not in _OBS_CACHE:
        tab = he_table_cached(closes)
        c = closes.assign(he=closes["date"].map(lambda x: he_at(tab, x)))
        op = None
        if openers:
            op = openers_frame()
            op = op.assign(he=op["date"].map(lambda x: he_at(tab, x))) if len(op) else None
        obs = measurements(c, "he", club_deltas=club_deltas, openers=op)
        if xg_sd > 0 and xg is not None and len(xg):
            x = xg.dropna(subset=["home_xg", "away_xg"])
            dx = x["home_xg"].astype(float) - x["away_xg"].astype(float)
            ox = pd.DataFrame({"date": x["date"], "home": x["home"], "away": x["away"], "y": dx - float(dx.mean()), "sd": float(xg_sd)})
            obs = pd.concat([obs, ox], ignore_index=True).sort_values("date", kind="stable").reset_index(drop=True)
        _OBS_CACHE[key] = obs
    return _OBS_CACHE[key]


def openers_frame() -> pd.DataFrame:
    """Pinnacle openers from the OpticOdds harvest with their gd_fit (same targets as a close) and the date the opener was
    posted (the fixture's date minus the typical lead of 5 days; the feed does not carry the opener's timestamp)."""
    p = os.path.join(ROOT, "data", "optic", "lines_pinnacle.csv")
    if not os.path.exists(p):
        return pd.DataFrame()
    from sim.knobs import load_config, knobs
    from sim.ratings import fit_targets
    kn = knobs(load_config())
    d = pd.read_csv(p, dtype=str, keep_default_na=False)
    d = d[d["phase"] == "open"].copy()
    from sim.teams import canon
    d["home"] = d["home"].map(lambda x: canon(x) or x); d["away"] = d["away"].map(lambda x: canon(x) or x)
    f = fit_targets(d[["h", "d", "a", "ah_line", "ah_home", "ah_away", "total_line", "over", "under"]], kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"])
    d = d.reset_index(drop=True); d["gd_fit"] = f["gd_fit"].to_numpy()
    d["date_open"] = (pd.to_datetime(d["date"]) - pd.Timedelta(days=5)).dt.strftime("%Y-%m-%d")
    return d[["season", "date", "date_open", "home", "away", "gd_fit"]]


def kalman_states(obs: pd.DataFrame, universe: list, asofs: list, kn: dict, posted: dict | None = None) -> dict:
    """One forward pass; returns {asof: (ratings over universe, sds)} for every asof in `asofs` (sorted). When `posted` is given
    ({asof: frame of (home, away, y)}), the state at asof is copied, the posted lines applied as measurements, then read."""
    kf = KalmanRatings(universe, kn)
    asofs = sorted(asofs); out = {}; j = 0
    rows = list(obs.itertuples(index=False)); has_sd = "sd" in obs.columns
    i = 0
    while j < len(asofs):
        a = asofs[j]
        while i < len(rows) and rows[i].date < a:
            r = rows[i]; kf._advance_to(r.date)
            sd = r.sd if has_sd else None
            kf.observe(r.home, r.away, float(r.y), float(sd) if sd is not None and sd == sd else None)
            i += 1
        kf._advance_to(a)
        if posted and a in posted:
            r0, P0 = kf.r.copy(), kf.P.copy()
            for pr in posted[a].itertuples(index=False):
                kf.observe(pr.home, pr.away, float(pr.y), float(kn.get("s_posted", kn.get("s", 0.22))))
            out[a] = (kf.r.copy(), np.sqrt(np.diag(kf.P)))
            kf.r, kf.P = r0, P0
        else:
            out[a] = (kf.r.copy(), np.sqrt(np.diag(kf.P)))
        j += 1
    return out


def _season_job(args):
    season, recipes, lags = args
    inp = _INPUTS
    df = inp["seasons"][season]; closes = inp["closes"]; xg = inp["xg"]
    T = season_teams(df); idx = {t: i for i, t in enumerate(T)}; conf = conf_array(T, season)
    dates = sorted(df["date"].unique())
    he_d = {d: he_at(inp["he"], d) for d in dates}
    n_t = len(T)
    per_date = df.groupby("date").size().reindex(dates).cumsum() * 2.0 / n_t   # matches per club played through that date
    mw_before = (per_date.shift(1).fillna(0.0)).to_dict()
    asof_needed = {}
    for d in dates:
        for L in lags:
            a = (pd.Timestamp(d) - pd.Timedelta(days=L)).strftime("%Y-%m-%d")
            asof_needed.setdefault(a, []).append((d, L))
    asofs = sorted(asof_needed)
    # posted lines per asof: closes in [asof, asof+3) of this season (what the live pipeline would hold as the current round)
    posted_by_asof = {}
    this = closes[closes["season"].astype(str) == season]
    for a in asofs:
        hi = (pd.Timestamp(a) + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        cur = this[(this["date"] >= a) & (this["date"] < hi)]
        posted_by_asof[a] = cur.assign(he=cur["date"].map(lambda x: he_at(inp["he"], x)))
    universe = inp["universe"]
    out_rows = []
    for name, rec in recipes.items():
        R_by_asof = {}
        if "kalman" in rec:
            kn = dict(rec["kalman"])
            obs = inp["obs_open"] if rec.get("openers") else inp["obs"]
            if rec.get("kf_xg_sd"):
                obs = pd.concat([obs, inp["obs_xg"].assign(sd=float(rec["kf_xg_sd"]))], ignore_index=True).sort_values("date", kind="stable")
            posted = None
            if rec.get("posted_in_fit"):
                posted = {a: pd.DataFrame({"home": c["home"], "away": c["away"], "y": c["gd_fit"].astype(float) - c["he"]}) for a, c in posted_by_asof.items() if len(c)}
            states = kalman_states(obs, universe, asofs, kn, posted)
            uidx = {t: i for i, t in enumerate(universe)}
            for a, (r, sd) in states.items():
                v = np.array([r[uidx[t]] for t in T]); v = v - v.mean()
                w_x = float(rec.get("xg_w", 0.0))
                if w_x > 0:
                    xr = xg_fit(xg, T, a, float(rec.get("xg_hl", 45)), float(rec.get("xg_ridge", 0.5)), float(v.std()))
                    if xr["n"] > 0:
                        v = (1 - w_x) * v + w_x * xr["ratings"]; v = v - v.mean()
                R_by_asof[a] = v * float(rec.get("spread_mult", 1.0))
        else:
            for a in asofs:
                R, Rm, info = ratings_for(rec, T, a, closes, xg, he_at(inp["he"], a))
                R_by_asof[a] = R
        for a, pairs in asof_needed.items():
            R = R_by_asof[a]
            for d, L in pairs:
                mw = mw_before[d]; he = he_d[d]
                for m in df[df["date"] == d].itertuples(index=False):
                    gf = float(m.gd_fit)
                    if not np.isfinite(gf):
                        continue
                    g = R[idx[m.home]] - R[idx[m.away]] + he
                    out_rows.append((name, L, season, d, phase_of(mw), m.home, m.away, int(conf[idx[m.home]] != conf[idx[m.away]]), gf - he, g - he))
    return out_rows


def run(name: str, recipes: dict, lags=(0, 7), seasons=None, workers=4) -> pd.DataFrame:
    global _INPUTS
    inp = load_inputs()
    closes = inp["closes"]
    seasons_all = sorted(s for s, df in inp["seasons"].items() if len(df) >= 200)
    inp["he"] = home_edge_by_season(closes, seasons_all)
    closes = closes.assign(he=closes["date"].map(lambda x: he_at(inp["he"], x)))
    inp["universe"] = sorted(set(closes["home"]) | set(closes["away"]) | set(inp["xg"]["home"]) | set(inp["xg"]["away"]))
    inp["obs"] = measurements(closes, "he")
    op = openers_frame()
    if len(op):
        op = op.assign(he=op["date"].map(lambda x: he_at(inp["he"], x)))
    inp["obs_open"] = measurements(closes, "he", openers=op) if len(op) else inp["obs"]
    xg = inp["xg"].dropna(subset=["home_xg", "away_xg"]).copy()
    xg["season"] = pd.to_datetime(xg["date"]).dt.year.astype(str)
    he_xg = float((xg["home_xg"].astype(float) - xg["away_xg"].astype(float)).mean())
    inp["obs_xg"] = pd.DataFrame({"date": xg["date"], "home": xg["home"], "away": xg["away"], "y": xg["home_xg"].astype(float) - xg["away_xg"].astype(float) - he_xg})
    _INPUTS = inp
    jobs = [(s, recipes, tuple(lags)) for s in seasons_all if not seasons or s in seasons]
    t0 = time.time()
    if workers > 1:
        with Pool(workers) as pool:
            res = pool.map(_season_job, jobs, chunksize=1)
    else:
        res = [_season_job(j) for j in jobs]
    rows = [r for rr in res for r in rr]
    out = pd.DataFrame(rows, columns=["recipe", "lag", "season", "date", "phase", "home", "away", "cross", "y_close", "y_model"])
    os.makedirs(OUT, exist_ok=True)
    out.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    print(f"close_track '{name}': {len(jobs)} seasons, {len(recipes)} recipes, {len(out)} scored closes, {time.time() - t0:.0f}s -> {os.path.join(OUT, name + '.csv')}")
    return out


def _agg(g: pd.DataFrame) -> pd.Series:
    e = g["y_close"] - g["y_model"]
    x = g["y_model"]; y = g["y_close"]
    vx = float(((x - x.mean()) ** 2).sum())
    slope = float(((x - x.mean()) * (y - y.mean())).sum() / vx) if vx > 0 else np.nan
    cr = g[g["cross"] == 1]; wi = g[g["cross"] == 0]
    return pd.Series({"n": len(g), "rmse": float(np.sqrt((e ** 2).mean())), "mae": float(e.abs().mean()), "bias": float(e.mean()), "slope": slope,
                      "sd_model": float(x.std()), "sd_close": float(y.std()), "corr": float(np.corrcoef(x, y)[0, 1]) if len(g) > 2 else np.nan,
                      "rmse_cross": float(np.sqrt(((cr["y_close"] - cr["y_model"]) ** 2).mean())) if len(cr) else np.nan,
                      "rmse_within": float(np.sqrt(((wi["y_close"] - wi["y_model"]) ** 2).mean())) if len(wi) else np.nan})


def summarize(df: pd.DataFrame, lag: int = 7, baseline: str | None = None, phases=False, seasons=None, by_season=False) -> str:
    d = df[df["lag"] == lag]
    if seasons:
        d = d[d["season"].astype(str).isin(seasons)]
    g = d.groupby("recipe").apply(_agg, include_groups=False)
    if baseline and baseline in set(d["recipe"]):
        per = d.groupby(["recipe", "season"]).apply(lambda x: float(np.sqrt(((x["y_close"] - x["y_model"]) ** 2).mean())), include_groups=False).unstack("recipe")
        wins = {r: f"{int((per[r] < per[baseline]).sum())}/{int(per[r].notna().sum())}" for r in per.columns}
        g[f"wins_vs_{baseline}"] = pd.Series(wins)
    g = g.sort_values("rmse")
    lines = []
    with pd.option_context("display.width", 250, "display.max_columns", 40, "display.max_rows", 500, "display.float_format", lambda v: f"{v:.4f}"):
        lines.append(f"lag {lag} days, {len(d)} scored closes\n" + g.to_string())
        if phases:
            gp = d.groupby(["recipe", "phase"]).apply(_agg, include_groups=False)[["n", "rmse", "bias", "slope", "rmse_cross", "rmse_within"]]
            lines.append("\nby phase:\n" + gp.to_string())
        if by_season:
            gs = d.groupby(["recipe", "season"]).apply(_agg, include_groups=False)["rmse"].unstack("recipe")
            lines.append("\nrmse by season:\n" + gs.to_string())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", default="run", choices=["run", "summary"])
    ap.add_argument("target", nargs="?")
    ap.add_argument("--name", default="track"); ap.add_argument("--recipes"); ap.add_argument("--lags", default="0,7")
    ap.add_argument("--seasons"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--lag", type=int, default=7); ap.add_argument("--baseline", default="live"); ap.add_argument("--phases", action="store_true"); ap.add_argument("--by-season", action="store_true")
    a = ap.parse_args()
    if a.stage == "summary":
        df = pd.read_csv(a.target, dtype={"season": str})
        print(summarize(df, a.lag, a.baseline, a.phases, a.seasons.split(",") if a.seasons else None, a.by_season)); return 0
    recipes = json.load(open(a.recipes)) if a.recipes else RECIPES
    df = run(a.name, recipes, [int(x) for x in a.lags.split(",")], a.seasons.split(",") if a.seasons else None, a.workers)
    for L in sorted(df["lag"].unique()):
        print(summarize(df, int(L), "live" if "live" in recipes else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
