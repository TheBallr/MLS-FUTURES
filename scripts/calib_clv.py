#!/usr/bin/env python3
"""Calibration 9 and the shrink: opener/close pairs. Sources: the CLV log (live) and the OpticOdds historical odds (Pinnacle opener and
close per fixture). (a) CLV test: where the model disagrees with the opener by >= 0.15 goals, how often and how far the close moves
the model's way. (b) Shrink grid: s in {0,.2,.35,.5,.7}, half-life, openers-in-the-fit, scored on the closes. Needs 150 pairs.
Report: outputs/calibration/clv.md"""
import os, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT, teams, canon
from sim.ratings import market_fit, gd_fit_row
from scripts.clv_log import summary
from scripts.replay import seasons_on_file
from scripts.fetch_optic import closing_row_from_history, odds_to_row, main_line_from_odds, _norm_market, MONEYLINE, HANDICAP, TOTAL

OUT = os.path.join(ROOT, "outputs", "calibration")
S_GRID = [0.0, 0.2, 0.35, 0.5, 0.7]


def pairs_from_optic(kn) -> pd.DataFrame:
    """Opener and close per fixture from raw/odds_historical/mls/pinnacle/*.json (first and last price per market)."""
    rows = []
    fx_index = {}
    for f in glob.glob(os.path.join(ROOT, "data", "optic", "fixtures_mls.csv")):
        fx_index = {r["fixture_id"]: r for r in pd.read_csv(f, dtype=str, keep_default_na=False).to_dict("records")}
    for p in glob.glob(os.path.join(ROOT, "data", "optic", "raw", "odds_historical", "mls", "pinnacle", "*.json")):
        fid = os.path.basename(p)[:-5]
        fx = fx_index.get(fid)
        if not fx:
            continue
        j = json.load(open(p))
        entries = j.get("data", j) if isinstance(j, dict) else j
        first, last = ({}, {}, {}), ({}, {}, {})
        for e in entries if isinstance(entries, list) else []:
            hist = e.get("history") or e.get("price_history") or []
            if not hist:
                continue
            hist = sorted(hist, key=lambda x: x.get("timestamp", 0))
            mk = _norm_market(e.get("market")); sel = (e.get("normalized_selection") or e.get("selection") or "").lower(); pts = e.get("points")
            for store, h in ((first, hist[0]), (last, hist[-1])):
                ml, ah, tot = store
                if mk in MONEYLINE:
                    ml[sel] = h.get("price")
                elif mk in HANDICAP and pts is not None:
                    ah.setdefault(pts, {})[sel] = h.get("price")
                elif mk in TOTAL and pts is not None:
                    tot.setdefault(pts, {})[sel] = h.get("price")
        try:
            home, away = canon(fx["home"]), canon(fx["away"])
        except Exception:
            continue
        fxd = {"id": fid, "start_date": fx["start_date"]}
        o = odds_to_row(fxd, "open", *first, home, away, ""); c = odds_to_row(fxd, "close", *last, home, away, "")
        if o and c:
            go = gd_fit_row(o["h"], o["d"], o["a"], o["ah_line"] or None, o["ah_home"], o["ah_away"], o["total_line"] or None, o["over"], o["under"], kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"])
            gc = gd_fit_row(c["h"], c["d"], c["a"], c["ah_line"] or None, c["ah_home"], c["ah_away"], c["total_line"] or None, c["over"], c["under"], kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"])
            if np.isfinite(go["gd_fit"]) and np.isfinite(gc["gd_fit"]):
                rows.append({"date": o["date"], "home": home, "away": away, "g_open": go["gd_fit"], "g_close": gc["gd_fit"]})
    return pd.DataFrame(rows)


def main():
    cfg = load_config(); kn = knobs(cfg)
    lines = ["# CLV test and the posted-line shrink", ""]
    live = summary(data.load("clv_log")); lines.append(f"Live CLV log: {live}")
    pairs = pairs_from_optic(kn)
    lines.append(f"OpticOdds opener/close pairs: {len(pairs)}")
    if len(pairs) < 150:
        lines.append("Fewer than 150 pairs: the shrink stays at the EPL value 0.35 and the CLV test waits.")
    else:
        seasons = seasons_on_file(cfg); allc = pd.concat(seasons.values()) if seasons else None
        T = teams(); idx = {t: i for i, t in enumerate(T)}
        pairs = pairs.sort_values("date")
        res = {s: [] for s in S_GRID}; clv = []
        for r in pairs.itertuples(index=False):
            if allc is None:
                break
            mk = market_fit(allc, T, r.date, kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True)
            if mk["n"] < 60 or r.home not in idx or r.away not in idx:
                continue
            gm = mk["ratings"][idx[r.home]] - mk["ratings"][idx[r.away]] + kn["home_edge_goals"]
            for s in S_GRID:
                res[s].append(((1 - s) * gm + s * r.g_open - r.g_close) ** 2)
            d = gm - r.g_open
            if abs(d) >= kn["clv_attack_threshold"]:
                mv = r.g_close - r.g_open; clv.append((np.sign(mv) == np.sign(d), abs(mv) if np.sign(mv) == np.sign(d) else -abs(mv)))
        lines += ["", "| s | rmse vs close |", "|---|---|"] + [f"| {s:.2f} | {np.sqrt(np.mean(res[s])):.4f} |" for s in S_GRID if res[s]]
        if clv:
            ours = np.array([c[0] for c in clv]); mv = np.array([c[1] for c in clv])
            lines += ["", f"CLV: {len(clv)} attacks (|model - opener| >= {kn['clv_attack_threshold']}), close moved our way {ours.mean():.1%}, mean signed move {mv.mean():+.3f} goals."]
    os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "clv.md"), "w").write("\n".join(lines))
    print("\n".join(lines[-3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
