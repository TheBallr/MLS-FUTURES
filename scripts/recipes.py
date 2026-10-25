#!/usr/bin/env python3
"""Ratings recipes for the yardsticks (close_track.py, backtest_season.py).

`live_recipe()` is the configuration the live build runs, read from config.json and data/ratings/source_config.csv at call
time, so the "live" baseline of every test is the model on the page (it was the retired least-squares fit until 2026-10-21).
A recipe file may name {"base": "live", ...} and override keys; "kalman" and "factors" dicts merge key by key.
`club_he: true` puts the per-club home deltas (data/ratings/home_edges.csv) into the measurements and every priced fixture, as
the live build does. Caveat: the deltas were fitted on 2012-2025, so for past seasons they are in sample (small: +-0.05 goals)."""
from __future__ import annotations
import copy, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RETIRED = {  # the least-squares era (retired 2026-10-15), kept for the record
    "market_wls_retired": {"half_life": 28, "ridge": 0.5},
    "wls_retired": {"half_life": 28, "ridge": 0.5, "xg_w": 0.25, "xg_hl": 45},
    "posted_wls_retired": {"half_life": 28, "ridge": 0.5, "xg_w": 0.25, "xg_hl": 45, "posted_in_fit": True},
    "kalman_plain": {"kalman": {}},
}


def live_recipe() -> dict:
    from sim.knobs import load_config, knobs
    from sim import data
    kn = knobs(load_config())
    sc = data.load("source_config")
    w = {r.source: float(r.weight) for r in sc.itertuples(index=False) if str(r.enabled).lower().startswith("y")} if len(sc) else {}
    tot = sum(w.values()) or 1.0
    rec = {"kalman": {"q_day": kn["kalman_q_day"], "s": kn["kalman_s"], "p0": kn["kalman_p0"], "q_off": kn["kalman_q_off"],
                      "off_shrink": kn["kalman_off_shrink"], "s_posted": kn.get("kalman_s_posted", kn["kalman_s"]),
                      "prior_new": kn["expansion_prior_rating"]},
           "posted_in_fit": bool(kn.get("posted_in_fit", False)), "xg_w": round(w.get("xg", 0.0) / tot, 4),
           "xg_hl": kn["xg_half_life_days"], "xg_ridge": kn["ridge_lambda"], "club_he": bool(kn.get("club_home_edge_enabled", False))}
    if kn.get("xg_goal_mix"):
        rec["xg_goal_mix"] = float(kn["xg_goal_mix"])
    if kn.get("factors_enabled"):
        rec["factors"] = {"abs": kn["factor_abs"], "rest": kn["factor_rest"], "short": kn["factor_short"], "elim": kn["factor_elim"]}
        rec["abs_mode"] = "trail10"
    return rec


def default_recipes() -> dict:
    return {"live": live_recipe(), **RETIRED}


def resolve(recipes: dict) -> dict:
    """{"base": name} recipes merged onto the named recipe (live or a retired one); dict-valued keys merge one level deep."""
    bases = default_recipes()
    out = {}
    for name, rec in recipes.items():
        rec = dict(rec)
        b = rec.pop("base", None)
        if b:
            base = copy.deepcopy(out.get(b) or bases[b])
            for k, v in rec.items():
                base[k] = {**base[k], **v} if isinstance(v, dict) and isinstance(base.get(k), dict) else v
            rec = base
        out[name] = rec
    return out


def club_deltas(rec: dict) -> dict | None:
    if not rec.get("club_he"):
        return None
    from sim.ratings import load_club_home_edges
    return load_club_home_edges(True) or None
