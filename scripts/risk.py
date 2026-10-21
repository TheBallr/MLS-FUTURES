#!/usr/bin/env python3
"""Risk tab (Zac, 2026-10-19: "more vision" on where the ratings could be off). Writes outputs/latest/risk.json, which
site_data.py embeds, and keeps data/ratings/ratings_history.csv (one row per club per run: rating and its parts) up to date.

Sections, each kept to what changes a decision:
  health      four tiles: ratings v Pinnacle's close a week out (last 30 days), spread (close on ratings slope), draws
              (model v Pinnacle v actual), inputs (missing closes, lines, results, xG, stale files)
  watch       only clubs with a live futures price and a flag: a persistent miss v the close (last 8 games), or the sources
              disagreeing (market / xG / Opta) on a club where +0.10 goals moves a price by 2 points or more
  confidence  each live futures price under plausible alternatives (no recent lines, xG 0% / 30%, spread +6%) and the
              effect of +0.10 goals on the club; same seed throughout, so the differences are not noise
  changes     every club's rating change since the last run / 7 days / the first archived run, split into the part from
              Pinnacle's closes, from xG and from the hand adjustment, with the futures move and the model changes
              (data/ratings/method_log.csv) inside the window
  blind       what the model does not see, short and dated
Usage: python3 scripts/risk.py [--n 20000] [--quick] [--backfill]"""
from __future__ import annotations
import argparse, datetime as dt, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT, teams, conference_of, code_of
from sim.engine import hda
from sim.ratings import xg_fit, xg_with_goals
from sim.season import SeasonInputs, run_seasons, dock_exempt_from_prepass
from sim.playoffs import real_playoff_results
from sim.markets import Archive, all_markets
from sim.layers import scenarios_for_engine, week_of, hand_week_values
from scripts.refresh_ratings import build_ratings, ratings_without_lines, closes_with_targets, he_table_cached_safe, he_at_date, team_totals
from scripts.run_sim import played_h2h, disc_points

LATEST = os.path.join(ROOT, "outputs", "latest")
RUNS = os.path.join(ROOT, "outputs", "runs")
HIST = os.path.join(ROOT, "data", "ratings", "ratings_history.csv")
METHOD_LOG = os.path.join(ROOT, "data", "ratings", "method_log.csv")
HIST_COLS = ["stamp", "asof", "team", "rating", "market", "xg", "hand", "w_market", "w_xg"]

# yardsticks (CLAUDE.md 13: live recipe, 15 seasons, a week out) and thresholds
NORMAL_RMSE, NORMAL_SLOPE = 0.243, 1.02   # 15-season close-tracking normal (CLAUDE.md 13); 0.240 with full-health ratings (14d, honest)
NORMAL_RMSE_FH = 0.240
PINNACLE_BOOKS = ("pinnacle_close", "pinnacle_last")
MISS_MEAN, MISS_SAME = 0.15, 6          # persistent miss: |mean of last 8| >= 0.15 goals with >= 6 of 8 the same sign
SPLIT_XG, SPLIT_OPTA = 0.50, 0.40       # sources disagree by this much (goals) ...
IMPACT_MIN = 2.0                        # ... on a club where +0.10 goals moves one of its live futures by >= 2 points
WIDE_PTS, WIDE_REL, WIDE_MIN = 3.0, 0.30, 1.0   # a futures range is wide at >= 3 points, or >= 1 point and >= 30% of the price (of 100 - price above 50%)
MARKETS = [("cup", "Win MLS Cup"), ("cup_finalist", "Reach MLS Cup"), ("playoffs", "Playoffs"), ("seed1", "Conf 1st")]
ALTS = [("no_lines", "No recent Pinnacle lines"), ("xg0", "xG 0%"), ("xg30", "xG 30%"), ("stretch", "Spread +6%")]


def stamp_utc(stamp: str) -> dt.datetime:
    return dt.datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)


def parse_utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))


# ---------------------------------------------------------------- rating history

def _hist_rows(stamp, asof, sources: pd.DataFrame, blend: pd.DataFrame, sc: pd.DataFrame) -> list[dict]:
    w = {r["source"]: float(r["weight"]) for r in sc.to_dict("records") if str(r["enabled"]).strip().lower() in ("y", "yes", "1", "true") and float(r["weight"] or 0) > 0}
    tot = sum(w.values()) or 1.0
    s = sources.set_index("team"); b = blend.set_index("team")
    rows = []
    for t in b.index:
        rows.append({"stamp": stamp, "asof": asof, "team": t, "rating": float(b.loc[t, "rating"]),
                     "market": float(s.loc[t, "market_recent"]) if "market_recent" in s.columns else np.nan,
                     "xg": float(s.loc[t, "xg"]) if "xg" in s.columns else np.nan,
                     "hand": float(b.loc[t, "hand_adj"]) if "hand_adj" in b.columns and str(b.loc[t, "hand_adj"]) not in ("", "nan") else 0.0,
                     "w_market": w.get("market_recent", 0.0) / tot, "w_xg": w.get("xg", 0.0) / tot})
    return rows


def backfill() -> pd.DataFrame:
    """One-off: every archived run's ratings and parts from the commit that added it (the last run of a commit when it holds several)."""
    from io import StringIO
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout
    by_commit = {}
    for stamp in sorted(os.listdir(RUNS)):
        c = git("log", "--diff-filter=A", "--format=%h", "-1", "--", f"outputs/runs/{stamp}/ratings.csv").strip()
        if c:
            by_commit[c] = stamp  # sorted, so the last run of a commit wins
    rows = []
    for c, stamp in by_commit.items():
        src, bl, sc = (git("show", f"{c}:data/ratings/{f}.csv") for f in ("sources", "blend", "source_config"))
        if not (src and bl and sc):
            continue
        summ = os.path.join(RUNS, stamp, "run_summary.json")
        asof = json.load(open(summ)).get("asof", stamp[:8]) if os.path.exists(summ) else stamp[:8]
        rows += _hist_rows(stamp, asof, pd.read_csv(StringIO(src)), pd.read_csv(StringIO(bl)), pd.read_csv(StringIO(sc)))
    h = pd.DataFrame(rows, columns=HIST_COLS).sort_values(["stamp", "team"])
    h.to_csv(HIST, index=False, float_format="%.4f")
    return h


def update_history(stamp: str, asof: str) -> pd.DataFrame:
    h = pd.read_csv(HIST) if os.path.exists(HIST) else pd.DataFrame(columns=HIST_COLS)
    h = h[h["stamp"] != stamp]
    new = pd.DataFrame(_hist_rows(stamp, asof, data.load("sources"), data.load("blend"), data.load("source_config")), columns=HIST_COLS)
    h = pd.concat([h, new], ignore_index=True).sort_values(["stamp", "team"])
    h.to_csv(HIST, index=False, float_format="%.4f")
    return h


def parts(df: pd.DataFrame) -> pd.DataFrame:
    """rating = market part + xG part + hand, each part = weight x (source - its mean over the clubs)."""
    out = df.set_index("team")[["rating", "hand"]].copy()
    m, x = df.set_index("team")["market"], df.set_index("team")["xg"]
    wm, wx = df["w_market"].iloc[0], df["w_xg"].iloc[0]
    out["p_market"] = wm * (m - m.mean())
    out["p_xg"] = (wx * (x - x.mean())).fillna(0.0)
    return out


def run_markets(stamp: str) -> dict | None:
    p = os.path.join(RUNS, stamp, "markets.json")
    return json.load(open(p)) if os.path.exists(p) else None


def changes(h: pd.DataFrame, now_stamp: str, cm: dict) -> list[dict]:
    stamps = sorted(h["stamp"].unique())
    if now_stamp not in stamps or len(stamps) < 2:
        return []
    now_t = stamp_utc(now_stamp)
    earlier = [s for s in stamps if s < now_stamp]
    week = min(earlier, key=lambda s: abs((stamp_utc(s) - (now_t - dt.timedelta(days=7))).total_seconds()))
    first_lbl = "Since " + stamp_utc(earlier[0]).strftime("%b %-d")
    windows = [("last", "Since the last run", earlier[-1])]
    windows += [("week", "Last 7 days", week)] if week != earlier[0] else []
    windows += [("all", first_lbl if week != earlier[0] else "Last 7 days", earlier[0])] if earlier[0] != earlier[-1] else []
    log = pd.read_csv(METHOD_LOG) if os.path.exists(METHOD_LOG) else pd.DataFrame(columns=["utc", "kind", "change"])
    res = data.load("results"); res = res[res["competition"].isin(["MLS", ""])]
    codes = code_of()

    def through(stamp):
        p = os.path.join(RUNS, stamp, "run_summary.json")
        return json.load(open(p)).get("results_through", "") if os.path.exists(p) else ""

    def played(team, lo, hi):
        g = res[(res["date"] > lo) & (res["date"] <= hi) & ((res["home"] == team) | (res["away"] == team))].sort_values("date")
        out = []
        for r in g.to_dict("records"):
            home = r["home"] == team; f, a_ = (int(r["hg"]), int(r["ag"])) if home else (int(r["ag"]), int(r["hg"]))
            out.append(f"{'W' if f > a_ else 'D' if f == a_ else 'L'} {f}-{a_} {'v' if home else 'at'} {codes.get(r['away'] if home else r['home'], '')}")
        return out
    M1 = run_markets(now_stamp)
    P1 = parts(h[h["stamp"] == now_stamp])
    out = []
    hi = through(now_stamp)
    for key, label, s0 in windows:
        P0 = parts(h[h["stamp"] == s0]); M0 = run_markets(s0); lo = through(s0)
        rows = []
        for t in P1.index:
            if t not in P0.index:
                continue
            d = {"team": t, "now": round(P1.loc[t, "rating"], 3), "then": round(P0.loc[t, "rating"], 3), "d": round(P1.loc[t, "rating"] - P0.loc[t, "rating"], 3),
                 "d_market": round(P1.loc[t, "p_market"] - P0.loc[t, "p_market"], 3), "d_xg": round(P1.loc[t, "p_xg"] - P0.loc[t, "p_xg"], 3),
                 "d_hand": round(P1.loc[t, "hand"] - P0.loc[t, "hand"], 3), "played": played(t, lo, hi) if lo and hi else []}
            for pool in ("cup", "playoffs"):
                a = (M1 or {}).get(pool, {}).get(t, {}).get("prob"); b = (M0 or {}).get(pool, {}).get(t, {}).get("prob")
                d["d_" + pool] = round((a - b) * 100, 1) if a is not None and b is not None else None
            rows.append(d)
        rows.sort(key=lambda r: -abs(r["d"]))
        t0 = stamp_utc(s0)
        ev = [{"date": parse_utc(r["utc"]).strftime("%b %d").replace(" 0", " "), "kind": r["kind"], "change": r["change"]}
              for r in log.to_dict("records") if t0 < parse_utc(r["utc"]) <= now_t]
        out.append({"key": key, "label": label, "from": s0, "from_utc": t0.isoformat().replace("+00:00", "Z"), "rows": rows, "events": ev})
    return out


# ---------------------------------------------------------------- ratings v the close, a week out

def tracking(cfg: dict, kn: dict, asof: str, closes: pd.DataFrame, rat: dict, T: list, days: int = 75) -> pd.DataFrame:
    """Walk-forward: every Pinnacle close of this season in the last `days`, priced from the ratings as they stood 7 days before
    the match (filter state with the round then posted, the xG blend, that week's hand adjustments). Same recipe as the live
    build, so the number is comparable with CLAUDE.md 13's 0.243 normal. With full-health ratings on (CLAUDE.md 14) the closes
    and the posted round enter net of their match-day factors and each priced close gets its factors back as known a week out
    (rest and short week from the schedule, eliminated status then, absences as the club's last-ten average: close_track's honest
    recipe, normal 0.240)."""
    from scripts.close_track import kalman_states, obs_cached, factor_adj
    from sim.factors import betas_from_knobs, factor_vector, factors
    betas = betas_from_knobs(kn); F = factors() if betas else None
    hist = closes[closes["season"].astype(str) != "posted"].copy()
    hist["date"] = pd.to_datetime(hist["date"]).dt.strftime("%Y-%m-%d")
    deltas = rat.get("club_deltas") or {}
    tab = he_table_cached_safe(closes)
    lo = (pd.Timestamp(asof) - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    tgt = hist[(hist["season"].astype(str) == str(cfg["season"])) & (hist["date"] >= lo) & (hist["date"] < asof) & hist["book"].isin(PINNACLE_BOOKS)].dropna(subset=["gd_fit"])
    if not len(tgt):
        return pd.DataFrame()
    tgt = tgt.assign(asof_k=(pd.to_datetime(tgt["date"]) - pd.Timedelta(days=7)).dt.strftime("%Y-%m-%d"))
    asofs = sorted(tgt["asof_k"].unique())
    obs = obs_cached(hist, False, 0.0, None, deltas or None, 0.0, betas)
    universe = sorted(set(obs["home"]) | set(obs["away"])); uidx = {t: i for i, t in enumerate(universe)}
    knk = {"q_day": kn["kalman_q_day"], "s": kn["kalman_s"], "p0": kn["kalman_p0"], "q_off": kn["kalman_q_off"], "prior_new": kn["expansion_prior_rating"],
           "off_shrink": float(kn.get("kalman_off_shrink", 1.0)), "s_posted": kn.get("kalman_s_posted", kn["kalman_s"])}
    posted = {}
    if kn.get("posted_in_fit"):
        for a in asofs:
            hi = (pd.Timestamp(a) + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
            cur = hist[(hist["date"] >= a) & (hist["date"] < hi)].dropna(subset=["gd_fit"])
            if len(cur):
                posted[a] = pd.DataFrame({"home": cur["home"], "away": cur["away"],
                                          "y": cur["gd_fit"].astype(float) - cur["date"].map(lambda x: he_at_date(tab, x)) - cur["home"].map(deltas).fillna(0.0).astype(float)
                                          - (factor_adj(cur["date"], cur["home"], cur["away"], betas) if betas else 0.0)})
    w = rat.get("weights", {}); w_x = float(w.get("xg", 0.0)) / max(1e-9, sum(float(v) for v in w.values())) if w else 0.0
    xg_hist = xg_with_goals(data.num(data.load("xg_history"), ["home_xg", "away_xg"]), data.load("results"), float(kn.get("xg_goal_mix", 0) or 0)) if w_x > 0 else None
    hlog = data.load("hand_log")
    R_at = {}
    for a, (st, _) in kalman_states(obs, universe, asofs, knk, posted or None).items():
        v = np.array([st[uidx[t]] if t in uidx else knk["prior_new"] for t in T]); v = v - v.mean()
        if w_x > 0 and xg_hist is not None and len(xg_hist):
            xr = xg_fit(xg_hist, T, a, kn["xg_half_life_days"], kn["ridge_lambda"], float(v.std()))
            if xr["n"] > 0:
                v = (1 - w_x) * v + w_x * xr["ratings"]; v = v - v.mean()
        hv, _ = hand_week_values(hlog, week_of(a)) if len(hlog) else ({}, None)
        R_at[a] = v + np.array([float(hv.get(t, 0.0)) for t in T])
    idx = {t: i for i, t in enumerate(T)}
    rows = []
    for m in tgt.itertuples(index=False):
        if m.home not in idx or m.away not in idx:
            continue
        R = R_at[m.asof_k]; he = he_at_date(tab, m.date) + float(deltas.get(m.home, 0.0))
        fac = factor_vector(betas, F.x_expected(m.date, m.home, m.away, m.asof_k, "trail10")) if betas else 0.0
        rows.append({"date": m.date, "home": m.home, "away": m.away, "close": float(m.gd_fit), "model": float(R[idx[m.home]] - R[idx[m.away]] + he + fac), "he": he})
    df = pd.DataFrame(rows)
    df["miss"] = df["close"] - df["model"]
    return df


def club_misses(tr: pd.DataFrame, T: list, n: int = 8) -> dict:
    out = {}
    if not len(tr):
        return out
    for t in T:
        m = tr[(tr["home"] == t) | (tr["away"] == t)].sort_values("date").tail(n)
        if not len(m):
            continue
        v = np.where(m["home"] == t, m["miss"], -m["miss"]).astype(float)
        opp = [(("v " + a) if h == t else ("at " + h)) for h, a in zip(m["home"], m["away"])]
        mean = float(v.mean()); same = int((np.sign(v) == np.sign(mean)).sum()) if mean != 0 else 0
        out[t] = {"mean": round(mean, 3), "same": same, "n": len(v), "games": [{"date": d, "opp": o, "miss": round(float(x), 2)} for d, o, x in zip(m["date"], opp, v)]}
    return out


# ---------------------------------------------------------------- futures confidence

class Sim:
    """The season engine as run_sim runs it (what_if's fixture builder), with the fixtures built once: they depend on the posted
    lines and layers, not on the ratings, so every ratings variant reuses them."""
    def __init__(self, cfg, kn, asof, closes, rat, T, cm):
        from scripts.what_if import build_fixtures
        self.kn, self.T = kn, T
        self.conf = np.array([0 if cm[t] == "East" else 1 for t in T]); idx = {t: i for i, t in enumerate(T)}
        self.fixtures, self.played, _ = build_fixtures(cfg, kn, asof, rat, T, idx, closes)
        self.scen = scenarios_for_engine(data.load("scenarios"), T)
        res = data.load("results"); res = res[res["competition"].isin(["MLS", ""])]; hp, hg_ = played_h2h(res, T)
        h2h_on = bool(kn.get("tiebreak_h2h", False))
        self.extra = {"disc": disc_points(T, cfg["season"], bool(kn.get("disc_points_enabled", False))), "h2h_pts": hp if h2h_on else None, "h2h_gd": hg_ if h2h_on else None,
                      "totals": team_totals(closes, T, asof, kn), "playoff_results": real_playoff_results(data.load("results"), T, cfg["season"])}

    def run(self, R, n) -> dict:
        inp = SeasonInputs(self.T, self.conf, np.asarray(R, float), self.fixtures, self.played, self.scen, **self.extra)
        if float(self.kn.get("dead_dock_goals", 0.0) or 0.0) > 0:
            inp.dock_exempt = dock_exempt_from_prepass(inp, self.kn)
        out = run_seasons(inp, self.kn, n_seasons=n)
        return all_markets(Archive(out), self.kn["shade"], {s["team"] for s in self.scen})


def market_prob(mk: dict, key: str, team: str, cm: dict) -> float | None:
    if key == "seed1":
        key = "east" if cm[team] == "East" else "west"
    v = mk.get(key, {}).get(team)
    return None if v is None else float(v["prob"])


def confidence(cfg, kn, asof, closes, rat, n, T, cm, live: dict) -> dict:
    idx = {t: i for i, t in enumerate(T)}
    sim = Sim(cfg, kn, asof, closes, rat, T, cm)
    R0 = np.asarray(rat["ratings"], float)
    base = sim.run(R0, n)
    hand_vec = R0 - np.asarray(rat["blend_raw"], float)
    src = rat["sources"]

    def mix(wx):  # hand adjustments kept (what_if's xg_w drops them)
        R = (1 - wx) * src["market_recent"] + wx * src.get("xg", src["market_recent"]); return R - R.mean() + hand_vec

    alts = {}
    c2 = json.loads(json.dumps(cfg)); c2["knobs"]["posted_in_fit"]["value"] = False
    kn2 = dict(kn); kn2["posted_in_fit"] = False; kn2["posted_line_shrink"] = 0.0
    rat2 = ratings_without_lines(asof, cfg, closes=closes)
    alts["no_lines"] = Sim(c2, kn2, asof, closes, rat2, T, cm).run(rat2["ratings"], n)
    alts["xg0"] = sim.run(mix(0.0), n)
    alts["xg30"] = sim.run(mix(0.30), n)
    alts["stretch"] = sim.run(R0 * 1.06, n)
    rows = []
    for t in T:
        cells = {}
        for key, _ in MARKETS:
            p = market_prob(live, key, t, cm)
            if p is None or not (0.02 <= p <= 0.98):
                continue
            b = market_prob(base, key, t, cm)
            by = {a: round((market_prob(alts[a], key, t, cm) - b) * 100, 1) for a, _ in ALTS}
            vals = [p * 100] + [p * 100 + v for v in by.values()]
            lo, hi = max(0.0, min(vals)), min(100.0, max(vals))
            wd = hi - lo; wide = wd >= WIDE_PTS or (wd >= WIDE_MIN and wd >= WIDE_REL * min(p * 100, 100 - p * 100))
            cells[key] = {"live": round(p * 100, 1), "lo": round(lo, 1), "hi": round(hi, 1), "by": by, "wide": bool(wide)}
        if cells:
            rows.append({"team": t, "cells": cells})
    # +0.10 goals on each club with a live price (common seed: the difference is the effect, not noise)
    for r in rows:
        R = R0.copy(); R[idx[r["team"]]] += 0.10
        mk = sim.run(R, n)
        for key, c in r["cells"].items():
            c["bump"] = round((market_prob(mk, key, r["team"], cm) - market_prob(base, key, r["team"], cm)) * 100, 1)
        r["impact"] = max(abs(c["bump"]) for c in r["cells"].values())
    rows.sort(key=lambda r: (-r["cells"].get("cup", {}).get("live", 0), -r["cells"].get("cup_finalist", {}).get("live", 0), -max(c["live"] for c in r["cells"].values())))
    return {"n": n, "alts": [{"key": k, "label": l} for k, l in ALTS], "markets": [{"key": k, "label": l} for k, l in MARKETS], "rows": rows}


# ---------------------------------------------------------------- health tiles

def status_of(x, ok, warn):
    return "ok" if x <= ok else ("warn" if x <= warn else "bad")


def health(tr: pd.DataFrame, cfg, kn, asof, closes) -> list[dict]:
    tiles = []
    if len(tr):
        lo30 = (pd.Timestamp(asof) - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        rec = tr[tr["date"] >= lo30]
        if len(rec) < 25:
            rec = tr.sort_values("date").tail(40)
        rmse = float(np.sqrt((rec["miss"] ** 2).mean())); bias = float(rec["miss"].mean())
        tiles.append({"key": "tracking", "label": "Ratings v Pinnacle", "value": f"{rmse:.3f}", "unit": "goals",
                      "status": status_of(rmse, 0.27, 0.31),
                      "sub": f"typical miss on the close, priced a week out · normal {NORMAL_RMSE_FH if kn.get('factors_enabled') else NORMAL_RMSE:.3f} · {len(rec)} games since {pd.Timestamp(rec['date'].min()).strftime('%b %-d')}",
                      "note": f"bias {bias:+.3f} (close minus ratings, home side)"})
        y = tr["close"] - tr["he"]; x = tr["model"] - tr["he"]
        slope = float(np.polyfit(x, y, 1)[0]) if len(tr) >= 20 else float("nan")
        dev = abs(slope - 1.0)
        tiles.append({"key": "spread", "label": "Spread", "value": f"{slope:.2f}", "unit": "",
                      "status": status_of(dev, 0.08, 0.15),
                      "sub": f"close on ratings, last {len(tr)} games · 1.00 = right · 15-season normal {NORMAL_SLOPE:.2f}",
                      "note": "above 1: ratings too flat, favourites' futures run low" if slope > 1.0 else "below 1: ratings too wide, favourites' futures run high"})
    # draws: model at Pinnacle's own margin and total v Pinnacle's devigged draw v what happened
    s = closes[(closes["season"].astype(str) == str(cfg["season"])) & closes["book"].isin(PINNACLE_BOOKS)].dropna(subset=["gd_fit", "pd"])
    rho = float(kn.get("dc_rho", 0.0) or 0.0)
    T_col = pd.to_numeric(s["T_fit"], errors="coerce").fillna(kn["avg_total_goals"])
    model_d = float(np.mean([hda(g, t, kn["goal_floor"], kn["shared_goals_mean"], rho)[1] for g, t in zip(s["gd_fit"].astype(float), T_col)])) if len(s) else float("nan")
    pin_d = float(pd.to_numeric(s["pd"], errors="coerce").mean()) if len(s) else float("nan")
    res = data.load("results"); res = res[(res["competition"].isin(["MLS", ""])) & (res["date"].astype(str).str[:4] == str(cfg["season"]))]
    hg, ag = pd.to_numeric(res["hg"], errors="coerce"), pd.to_numeric(res["ag"], errors="coerce"); ok = hg.notna() & ag.notna()
    act = float((hg[ok] == ag[ok]).mean()) if ok.any() else float("nan"); res = res[ok]
    gap = abs(model_d - pin_d) * 100
    tiles.append({"key": "draws", "label": "Draws", "value": f"{model_d*100:.1f}%", "unit": f"v {pin_d*100:.1f}%",
                  "status": status_of(gap, 1.0, 2.0),
                  "sub": f"model v Pinnacle on this season's {len(s)} closes · actual {act*100:.1f}% of {len(res)}",
                  "note": "knockout draws go to a coin flip, so a draw gap moves every playoff round"})
    issues = inputs_check(cfg, kn, asof, closes)
    worst = "bad" if any(i["status"] == "bad" for i in issues) else ("warn" if issues else "ok")
    tiles.append({"key": "inputs", "label": "Inputs", "value": str(len(issues)) if issues else "OK", "unit": "issue" + ("" if len(issues) == 1 else "s") if issues else "",
                  "status": worst, "sub": "closes, lines, results, xG, Opta, injuries", "issues": issues})
    return tiles


def inputs_check(cfg, kn, asof, closes) -> list[dict]:
    out = []
    today = pd.Timestamp(asof)
    season = closes[closes["season"].astype(str) == str(cfg["season"])]
    sch = data.load("schedule"); sch = sch[sch["competition"] == "MLS"]
    res = data.load("results"); played = set(zip(res["date"], res["home"], res["away"]))
    past = [r for r in sch.to_dict("records") if r["date"] < asof]
    missing_res = [r for r in past if (r["date"], r["home"], r["away"]) not in played]
    if missing_res:
        out.append({"status": "bad", "text": f"{len(missing_res)} played game{'s' if len(missing_res) != 1 else ''} with no result on file",
                    "detail": ", ".join(f"{r['home']} v {r['away']} {r['date'][5:]}" for r in missing_res[:4])})
    have_pin = set(zip(season[season["book"].isin(PINNACLE_BOOKS)]["date"], season[season["book"].isin(PINNACLE_BOOKS)]["home"], season[season["book"].isin(PINNACLE_BOOKS)]["away"]))
    no_pin = [r for r in past if (r["date"], r["home"], r["away"]) in played and (r["date"], r["home"], r["away"]) not in have_pin]
    if no_pin:
        avg = season[season["book"] == "avg_close"]
        out.append({"status": "warn" if len(no_pin) <= 40 else "bad",
                    "text": f"{len(no_pin)} games this season have no Pinnacle close" + (f" ({len(avg)} use the market-average close, {pd.Timestamp(avg['date'].min()).strftime('%b %-d')} to {pd.Timestamp(avg['date'].max()).strftime('%b %-d')})" if len(avg) else ""),
                    "detail": "OpticOdds has an opener but no close for them (suspended markets) and the 10-minute capture only began on Oct 14, so they cannot be recovered; the average close is within about 1 point of Pinnacle's on the home win"})
    from scripts.run_sim import latest_posted
    posted = latest_posted(data.load("current_round_odds"), asof=asof)
    soon = [r for r in sch.to_dict("records") if asof <= r["date"] <= (today + pd.Timedelta(days=2)).strftime("%Y-%m-%d") and (r["date"], r["home"], r["away"]) not in played]
    unl = [r for r in soon if (r["date"], r["home"], r["away"]) not in posted]
    if unl:
        out.append({"status": "warn", "text": f"{len(unl)} game{'s' if len(unl) != 1 else ''} in the next 2 days without a Pinnacle line",
                    "detail": ", ".join(f"{r['home']} v {r['away']} {r['date'][5:]}" for r in unl[:4])})
    xg = data.load("xg_history")
    if len(xg) and len(res):
        lastres = str(res[res["competition"].isin(["MLS", ""])]["date"].max())
        lo = (today - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
        have_x = {(h, a): set() for h, a in zip(xg["home"], xg["away"])}
        for d, h_, a_ in zip(xg["date"], xg["home"], xg["away"]):
            have_x[(h_, a_)].add(pd.Timestamp(d))
        mls = set(zip(sch["date"], sch["home"], sch["away"]))
        miss_x = [k for k in played if lo <= k[0] <= lastres and k in mls and not any(abs((x - pd.Timestamp(k[0])).days) <= 1 for x in have_x.get((k[1], k[2]), ()))]
        if len(miss_x) >= 3:
            out.append({"status": "warn", "text": f"{len(miss_x)} games in the last 14 days with no xG yet", "detail": "ASA usually posts within a day"})
    op = os.path.join(ROOT, "data", "public", "opta", "snapshots.csv")
    if os.path.exists(op):
        od = pd.read_csv(op)["date"].max(); age = (today - pd.Timestamp(od)).days
        if age > 8:
            out.append({"status": "warn", "text": f"Opta snapshot is {age} days old", "detail": f"latest {od}"})
    dp = os.path.join(ROOT, "data", "discipline", f"disc_points_{cfg['season']}.csv")
    if kn.get("disc_points_enabled") and os.path.exists(dp):
        dpm = pd.read_csv(dp); res_mls = res[res["competition"].isin(["MLS", ""])]
        played_n = pd.concat([res_mls["home"], res_mls["away"]]).value_counts()
        lag = int((played_n.reindex(dpm["team"]).fillna(0) - dpm.set_index("team")["matches"]).max()) if len(dpm) else 0
        if lag >= 2:
            out.append({"status": "warn", "text": f"Discipline tiebreak totals are up to {lag} games behind",
                        "detail": "data/discipline is refreshed by hand (disc_points.py on fresh OpticOdds team stats); it decides a seed in about 0.1-0.2% of seasons"})
    inj = data.load("injuries")
    if len(inj):
        upd = pd.to_datetime(inj["updated"], errors="coerce").max()
        stale = inj[pd.to_datetime(inj["updated"], errors="coerce") < today - pd.Timedelta(days=21)]
        if len(stale) >= 10:
            out.append({"status": "warn", "text": f"{len(stale)} of {len(inj)} injury rows not refreshed in 3 weeks",
                        "detail": f"last update {upd.strftime('%b %-d') if pd.notna(upd) else '?'}; the injury layer is " + ("on" if kn.get("injury_layer_enabled") else "off, so this does not move prices")})
    return out


# ---------------------------------------------------------------- watchlist and blind spots

def watchlist(T, rat, opta, misses, h: pd.DataFrame, now_stamp: str, conf_rows: list) -> list[dict]:
    R = {t: float(v) for t, v in zip(T, rat["ratings"])}
    src = {k: {t: float(v) for t, v in zip(T, a)} for k, a in rat["sources"].items()}
    impact = {r["team"]: r for r in conf_rows}
    now_t = stamp_utc(now_stamp)
    wk = [s for s in sorted(h["stamp"].unique()) if stamp_utc(s) <= now_t - dt.timedelta(days=7)]
    r7 = h[h["stamp"] == (wk[-1] if wk else sorted(h["stamp"].unique())[0])].set_index("team")["rating"] if len(h) else pd.Series(dtype=float)
    out = []
    for t in T:
        flags = []
        cr = impact.get(t); imp = cr["impact"] if cr else 0.0
        mm = misses.get(t)
        if cr is None:
            continue  # no live futures price: nothing to bet is exposed
        if mm and mm["n"] >= 6 and abs(mm["mean"]) >= MISS_MEAN and mm["same"] >= MISS_SAME:
            flags.append({"kind": "miss", "status": "bad" if abs(mm["mean"]) >= 0.25 else "warn",
                          "text": f"Pinnacle rated them {'higher' if mm['mean'] > 0 else 'lower'} than we did in {mm['same']} of their last {mm['n']} (avg {mm['mean']:+.2f})"})
        xg_gap = src.get("xg", {}).get(t, np.nan) - src["market_recent"][t]
        if np.isfinite(xg_gap) and abs(xg_gap) >= SPLIT_XG and imp >= IMPACT_MIN:
            flags.append({"kind": "split", "status": "warn", "text": f"xG {'above' if xg_gap > 0 else 'below'} the market by {abs(xg_gap):.2f}"})
        o = opta.get(t)
        if o is not None and abs(o - R[t]) >= SPLIT_OPTA and imp >= IMPACT_MIN:
            flags.append({"kind": "split", "status": "warn", "text": f"Opta {'above' if o > R[t] else 'below'} us by {abs(o - R[t]):.2f}"})
        mv = R[t] - float(r7.get(t, R[t]))
        if not flags:
            continue
        top = max(cr["cells"].items(), key=lambda kv: abs(kv[1].get("bump", 0))) if cr else None
        out.append({"team": t, "rating": round(R[t], 3), "flags": flags, "miss": mm, "market": round(src["market_recent"][t], 3),
                    "xg": round(src["xg"][t], 3) if "xg" in src else None, "opta": o, "hand": round(float(rat.get("hand", {}).get(t, 0.0)), 3), "move7": round(mv, 3),
                    "impact": {"market": top[0], "bump": top[1].get("bump")} if top else None,
                    "rank": (2 if any(f["status"] == "bad" for f in flags) else 1) * (1 + imp)})
    out.sort(key=lambda r: -r["rank"])
    return out


def blind_spots(kn, asof, rat) -> list[dict]:
    out = []
    hand = {t: v for t, v in (rat.get("hand") or {}).items() if abs(v) > 1e-9}
    if hand:
        out.append({"status": "info", "text": "Your hand adjustments in the ratings: " + ", ".join(f"{t} {v:+.2f}" for t, v in sorted(hand.items(), key=lambda kv: -abs(kv[1])))})
    if asof < "2026-11-18":
        out.append({"status": "warn", "text": "FIFA window Nov 9-17 ends the day before the Wild Card: call-ups, travel and knocks are not in the ratings"})
    out.append({"status": "info", "text": "A level knockout game after 90 minutes is a coin flip (extra time not modelled)"})
    if not kn.get("injury_layer_enabled"):
        out.append({"status": "info", "text": "Injury layer off: absences reach the ratings only through Pinnacle's closes, so a fresh injury shows up one game late"})
    if float(kn.get("dead_dock_goals", 0) or 0) > 0:
        out.append({"status": "ok", "text": f"Eliminated clubs are docked {kn['dead_dock_goals']:.1f} goals in the sim (they underperform the ratings by 0.36 goals, 2012-2025)"})
    out.append({"status": "ok", "text": "Playoff games: Pinnacle prices them off the same ratings as the regular season (13 seasons), so no playoff adjustment is needed"})
    return out


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=20000); ap.add_argument("--quick", action="store_true"); ap.add_argument("--backfill", action="store_true")
    a = ap.parse_args()
    if a.backfill:
        h = backfill(); print(f"risk: backfilled {h['stamp'].nunique()} runs into {os.path.relpath(HIST, ROOT)}")
    t0 = dt.datetime.now()
    summ = json.load(open(os.path.join(LATEST, "run_summary.json")))
    live = json.load(open(os.path.join(LATEST, "markets.json")))
    stamp, asof = summ["stamp"], summ["asof"]
    cfg = load_config(); kn = knobs(cfg); T = teams(); cm = conference_of()
    # quick runs are not archived (no outputs/runs/<stamp>/), so they stay out of the rating history
    h = update_history(stamp, asof) if os.path.isdir(os.path.join(RUNS, stamp)) else (pd.read_csv(HIST) if os.path.exists(HIST) else pd.DataFrame(columns=HIST_COLS))
    closes = closes_with_targets(cfg)
    rat = build_ratings(asof, cfg, closes=closes, write=False)
    from scripts.site_data import opta_anchor
    opta, _ = opta_anchor(T, rat["ratings"])
    tr = tracking(cfg, kn, asof, closes, rat, T)
    misses = club_misses(tr, T)
    n = 4000 if a.quick else a.n
    conf = confidence(cfg, kn, asof, closes, rat, n, T, cm, live)
    tiles = health(tr, cfg, kn, asof, closes)
    watch = watchlist(T, rat, opta, misses, h, stamp, conf["rows"])
    out = {"asof": asof, "stamp": stamp, "run_utc": summ.get("run_utc"), "health": tiles, "watch": watch, "confidence": conf,
           "changes": changes(h, stamp, cm), "blind": blind_spots(kn, asof, rat),
           "misses": {t: v for t, v in misses.items()}}
    n_flags = sum(t["status"] != "ok" for t in tiles) + len(watch) + sum(c["wide"] for r in conf["rows"] for c in r["cells"].values())
    out["flags"] = n_flags
    from scripts.site_data import clean
    with open(os.path.join(LATEST, "risk.json"), "w") as f:
        json.dump(clean(out), f, indent=1, allow_nan=False)
    secs = (dt.datetime.now() - t0).total_seconds()
    tile_txt = ", ".join(t["label"] + " " + t["value"] for t in tiles)
    print(f"risk: {n_flags} flags ({tile_txt}; {len(watch)} clubs on the watchlist; "
          f"{sum(c['wide'] for r in conf['rows'] for c in r['cells'].values())} wide futures ranges) in {secs:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
