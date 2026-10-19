#!/usr/bin/env python3
"""Does Pinnacle price absences? (CLAUDE.md section 14, step 2.)

Residual = the close's expected margin minus the plain Kalman filter's state on the morning of the match (a close_track
per-close file, recipe `kf_plain` at lag 0, both net of the home edge), regressed on the home-minus-away missing value from
scripts/absences.py, with the rest difference (days, capped 10), the short-week difference and the eliminated-status
difference alongside. Coefficients are goals of expected margin per goal of missing value (per day, per flag). Reported
pooled, by season, and walk-forward (the coefficient a season would have used, fitted on the seasons before it).
The filter's morning state has already absorbed part of a long absence through earlier closes, so this coefficient is the
part the state does NOT carry; the full price is read in step 3 (netting grid) as the beta at which the netted filter's
residual no longer loads on absences.

Usage: python3 scripts/absence_price.py --track outputs/calibration/close_track/fh_base.csv --recipe kf_plain"""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim.teams import ROOT
from scripts.absences import load_matches
from scripts.congestion import ols

OUT = os.path.join(ROOT, "outputs", "calibration")
_ELIM = None


def eliminated_table() -> pd.DataFrame:
    """(season, date, team) -> 1 for clubs eliminated from the playoffs before that date (last ten rounds, as scripts/dead_teams.py
    classifies them; every earlier date is 0). Past seasons are cached to outputs/calibration/eliminated.csv; the current season is
    rebuilt on every call from the FULL schedule (played and unplayed fixtures), because a club's remaining fixtures decide whether it
    can still reach the line. (Bug fixed 2026-10-19: the current season was classified from played games only, so every club looked
    like it had no games left and Columbus, Atlanta, Montreal, Portland, RSL, San Diego, Minnesota and Austin were flagged eliminated.)"""
    global _ELIM
    if _ELIM is not None:
        return _ELIM
    from sim import data
    from sim.knobs import load_config
    from scripts.replay import season_teams, conf_map_for, playoff_spots
    from scripts.dead_teams import classify
    cfg = load_config(); cur = str(cfg["season"]); per_season = int(cfg.get("mls", {}).get("matches_per_club", 34))
    p = os.path.join(OUT, "eliminated.csv")
    past = pd.read_csv(p, dtype={"season": str}) if os.path.exists(p) else pd.DataFrame()
    past = past[past["season"] != cur] if len(past) else past
    rows = []
    if not len(past):
        from scripts.backtest_season import load_inputs
        inp = load_inputs()
        for season, df in sorted(inp["seasons"].items()):
            if len(df) < 200 or season == cur:
                continue
            T = season_teams(df); cm = conf_map_for(season); spots = playoff_spots(season)
            df = df.sort_values("date").reset_index(drop=True)
            for c in ("hg", "ag"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
            dates = sorted(df["date"].unique()); n_teams = len(T)
            per_club = df.groupby("date").size().cumsum() * 2 / n_teams
            late = [d for d in dates if per_club[d] >= per_club.iloc[-1] - 10]
            for d in late:
                st = classify(df[df["date"] < d], df, d, T, cm, spots)
                for t, s_ in st.items():
                    rows.append({"season": season, "date": d, "team": t, "status": s_, "eliminated": int(s_ == "eliminated")})
        past = pd.DataFrame(rows)
        past.to_csv(p, index=False)
    # current season: results so far, the whole schedule for what is left
    res = data.load("results"); res = res[res["competition"].isin(["MLS", ""])].copy()
    sch = data.load("schedule"); sch = sch[sch["competition"] == "MLS"]
    for c in ("hg", "ag"):
        res[c] = pd.to_numeric(res[c], errors="coerce")
    res = res.dropna(subset=["hg", "ag"])
    cur_rows = []
    if len(res):
        T = sorted(set(sch["home"]) | set(sch["away"])); cm = conf_map_for(cur); spots = playoff_spots(cur)
        allfx = sch[["date", "home", "away"]]
        dates = sorted(res["date"].unique()); n_teams = len(T)
        per_club = res.groupby("date").size().cumsum() * 2 / n_teams
        late = [d for d in dates if per_club[d] >= per_season - 10]
        for d in late:
            st = classify(res[res["date"] < d], allfx, d, T, cm, spots)
            for t, s_ in st.items():
                cur_rows.append({"season": cur, "date": d, "team": t, "status": s_, "eliminated": int(s_ == "eliminated")})
    _ELIM = pd.concat([past, pd.DataFrame(cur_rows)], ignore_index=True) if cur_rows else past
    return _ELIM


def features(tr: pd.DataFrame, absences_path: str | None = None) -> pd.DataFrame:
    """Join the scored closes with absences, rest and eliminated status; returns the frame with dmv, drest, dshort, delim and e."""
    from scripts.close_track import rest_table
    from scripts.absences import match_frame
    m = match_frame(pd.read_csv(absences_path, dtype={"season": str})) if absences_path else load_matches()
    d = tr.merge(m[["date", "home", "away", "mv_home", "mv_away", "early", "n_abs_h", "n_abs_a"]], on=["date", "home", "away"], how="left")
    d["matched"] = d["mv_home"].notna().astype(int)
    d["mv_home"] = d["mv_home"].fillna(0.0); d["mv_away"] = d["mv_away"].fillna(0.0)
    d["dmv"] = d["mv_home"] - d["mv_away"]
    rt = rest_table()
    d["rest_h"] = [rt.get((x, h), 7.0) for x, h in zip(d["date"], d["home"])]; d["rest_a"] = [rt.get((x, a), 7.0) for x, a in zip(d["date"], d["away"])]
    d["drest"] = d["rest_h"].clip(upper=10) - d["rest_a"].clip(upper=10)
    d["dshort"] = (d["rest_h"] <= 3).astype(float) - (d["rest_a"] <= 3).astype(float)
    el = eliminated_table()
    key = {(s, x, t): v for s, x, t, v in zip(el["season"].astype(str), el["date"], el["team"], el["eliminated"])}
    d["elim_h"] = [key.get((str(s), x, h), 0) for s, x, h in zip(d["season"], d["date"], d["home"])]
    d["elim_a"] = [key.get((str(s), x, a), 0) for s, x, a in zip(d["season"], d["date"], d["away"])]
    d["delim"] = d["elim_h"].astype(float) - d["elim_a"].astype(float)
    d["e"] = d["y_close"] - d["y_model"]
    return d


NAMES = ["abs (goals per goal of missing value)", "rest (per day diff)", "short week (flag diff)", "eliminated (flag diff)"]
COLS = ["dmv", "drest", "dshort", "delim"]


def fit(d: pd.DataFrame, cols=COLS, names=NAMES):
    b, s = ols(d["e"], [d[c] for c in cols], names)
    return b, s


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--track", default=os.path.join(OUT, "close_track", "fh_base.csv")); ap.add_argument("--recipe", default="kf_plain"); ap.add_argument("--lag", type=int, default=0); ap.add_argument("--absences", default=None, help="absences csv (default data/public/asa_gplus/absences.csv)"); ap.add_argument("--tag", default="")
    a = ap.parse_args()
    tr = pd.read_csv(a.track, dtype={"season": str}); tr = tr[(tr["recipe"] == a.recipe) & (tr["lag"] == a.lag)].copy()
    d = features(tr, a.absences)
    L = [f"# Does Pinnacle price absences? residual = close minus {a.recipe} at lag {a.lag} (scripts/absence_price.py)", ""]
    L.append(f"{len(d)} scored closes; matched to an ASA team-game {d['matched'].mean():.3f}; residual sd {d['e'].std():.3f}; sd of dmv {d['dmv'].std():.3f}, drest {d['drest'].std():.3f}, dshort {d['dshort'].std():.3f}, delim {d['delim'].std():.3f}")
    dm = d[(d["matched"] == 1) & (d["early"] == 0)]
    L.append(f"\nPooled, matched closes with an absence window ({len(dm)}):")
    b, s = fit(dm); L.append("  " + "; ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b.items()) + f"; resid sd {s:.4f}")
    b1, _ = ols(dm["e"], [dm["dmv"]], ["abs alone"]); L.append("  " + "; ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b1.items()))
    b2, _ = ols(dm["y_close"], [dm["y_model"], dm["dmv"], dm["drest"], dm["dshort"], dm["delim"]], ["model", "abs", "rest", "short", "elim"]); L.append("  close on model + factors: " + "; ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b2.items()))
    # home and away separately (is the price symmetric?)
    b3, _ = ols(dm["e"], [dm["mv_home"], dm["mv_away"], dm["drest"], dm["dshort"], dm["delim"]], ["mv_home", "mv_away", "rest", "short", "elim"]); L.append("  home and away separately: " + "; ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b3.items()))
    L.append("\nresidual by dmv bucket (home minus away missing value):")
    tab = dm.groupby(pd.cut(dm["dmv"], [-5, -0.3, -0.1, -0.02, 0.02, 0.1, 0.3, 5]), observed=True)["e"].agg(["mean", "count"]); L.append(tab.to_string())
    L.append("\nBy season (abs coefficient, se; rest; short; elim; n):")
    rows = []
    for s_, g in dm.groupby("season"):
        if len(g) < 100:
            continue
        b, _ = fit(g); rows.append((s_, b[NAMES[0]][0], b[NAMES[0]][1], b[NAMES[1]][0], b[NAMES[2]][0], b[NAMES[3]][0], len(g)))
        L.append(f"  {s_}: abs {b[NAMES[0]][0]:+.3f} (se {b[NAMES[0]][1]:.3f}); rest {b[NAMES[1]][0]:+.4f}; short {b[NAMES[2]][0]:+.3f}; elim {b[NAMES[3]][0]:+.3f}; n {len(g)}")
    bs = pd.DataFrame(rows, columns=["season", "abs", "se", "rest", "short", "elim", "n"])
    L.append(f"  seasons with abs > 0: {int((bs['abs'] > 0).sum())}/{len(bs)}; mean of season coefficients {bs['abs'].mean():+.3f} (sd across seasons {bs['abs'].std():.3f}, mean se {bs['se'].mean():.3f})")
    L.append("\nWalk-forward (coefficients fitted on the seasons before each season; what a live netting would have used):")
    for s_ in sorted(dm["season"].unique()):
        prev = dm[dm["season"] < s_]
        if len(prev) < 500:
            continue
        b, _ = fit(prev); L.append(f"  {s_}: abs {b[NAMES[0]][0]:+.3f} (se {b[NAMES[0]][1]:.3f}); rest {b[NAMES[1]][0]:+.4f}; short {b[NAMES[2]][0]:+.3f}; elim {b[NAMES[3]][0]:+.3f} (on {len(prev)} closes)")
    L.append("\nBy phase (early < mw 10, mid, late):")
    for ph, g in dm.groupby("phase"):
        b, _ = fit(g, COLS[:3], NAMES[:3]); L.append(f"  {ph}: abs {b[NAMES[0]][0]:+.3f} (se {b[NAMES[0]][1]:.3f}); rest {b[NAMES[1]][0]:+.4f}; short {b[NAMES[2]][0]:+.3f}; n {len(g)}")
    L.append("\nAbsences of a keeper vs field players (abs coefficient with mv split; needs absence_players.csv):")
    pl = pd.read_csv((a.absences or os.path.join(ROOT, "data", "public", "asa_gplus", "absences.csv")).replace("absences", "absence_players"), dtype={"season": str})
    pl["cost"] = pl["value_per96"] * pl["absent_frac"]
    gk = pl.groupby(["date", "team", "gk"])["cost"].sum().unstack("gk").fillna(0.0).reset_index().rename(columns={0: "field", 1: "keeper"})
    for col in ("field", "keeper"):
        if col not in gk.columns:
            gk[col] = 0.0
    x = dm.merge(gk.rename(columns={"team": "home", "field": "f_h", "keeper": "k_h"}), on=["date", "home"], how="left").merge(gk.rename(columns={"team": "away", "field": "f_a", "keeper": "k_a"}), on=["date", "away"], how="left").fillna({"f_h": 0, "k_h": 0, "f_a": 0, "k_a": 0})
    x["dfield"] = x["f_h"] - x["f_a"]; x["dkeep"] = x["k_h"] - x["k_a"]
    b4, _ = ols(x["e"], [x["dfield"], x["dkeep"], x["drest"], x["dshort"], x["delim"]], ["field", "keeper", "rest", "short", "elim"]); L.append("  " + "; ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in b4.items()))
    txt = "\n".join(L); print(txt)
    open(os.path.join(OUT, f"absence_price{a.tag}.md"), "w").write(txt + "\n")
    d.to_csv(os.path.join(OUT, f"absence_price_rows{a.tag}.csv"), index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
