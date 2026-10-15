"""Ratings: market fit on Pinnacle closes (weighted least squares, half-life weights), xG fit, blend, expansion prior, shrink."""
from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd
from .devig import power_devig
from .engine import margin_from_three_way, margin_from_ah, total_from_ou


def gd_fit_row(h, d, a, ah_line=None, ah_home=None, ah_away=None, total_line=None, over=None, under=None,
               avg_total=3.0, floor=0.15, shared=0.15, rho=0.0) -> dict:
    """The fit target for one match line: handicap-implied expected margin at the match's own total.
    Uses the main Asian handicap when it exists, else the three-way. Returns gd_3way, gd_ah, gd_fit, T_fit, ph, pd, pa."""
    out = {"gd_3way": np.nan, "gd_ah": np.nan, "gd_fit": np.nan, "T_fit": np.nan, "ph": np.nan, "pd": np.nan, "pa": np.nan}
    ok3 = all(_pos(x) for x in (h, d, a))
    T = float(avg_total)
    g0 = 0.0
    if ok3:
        ph, pdr, pa = power_devig([float(h), float(d), float(a)])
        out.update(ph=float(ph), pd=float(pdr), pa=float(pa))
        g0 = margin_from_three_way(ph, pa, T, floor, shared, rho)
    okT = _pos(total_line) and _pos(over) and _pos(under)
    if okT:
        po, pu = power_devig([float(over), float(under)])
        T = total_from_ou(po, float(total_line), g0, floor, shared, rho)
    elif _pos(total_line):
        T = float(total_line)
    out["T_fit"] = T
    if ok3:
        out["gd_3way"] = margin_from_three_way(out["ph"], out["pa"], T, floor, shared, rho)
    okA = ah_line is not None and ah_line == ah_line and str(ah_line) != "" and _pos(ah_home) and _pos(ah_away)
    if okA:
        pah, paa = power_devig([float(ah_home), float(ah_away)])
        out["gd_ah"] = margin_from_ah(pah, float(ah_line), T, floor, shared, rho)
    out["gd_fit"] = out["gd_ah"] if okA else out["gd_3way"]
    return out


def _pos(x) -> bool:
    try:
        return x is not None and str(x) != "" and float(x) > 0
    except (TypeError, ValueError):
        return False


def fit_targets(lines: pd.DataFrame, avg_total: float, floor: float, shared: float, rho: float = 0.0) -> pd.DataFrame:
    """Add gd_fit columns to a lines frame (one row per match with decimal prices)."""
    rows = []
    for r in lines.itertuples(index=False):
        rows.append(gd_fit_row(getattr(r, "h", None), getattr(r, "d", None), getattr(r, "a", None),
                               getattr(r, "ah_line", None), getattr(r, "ah_home", None), getattr(r, "ah_away", None),
                               getattr(r, "total_line", None), getattr(r, "over", None), getattr(r, "under", None),
                               avg_total, floor, shared, rho))
    return pd.concat([lines.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def wls_fit(home_idx, away_idx, target, weights, n_teams, ridge=0.5, fit_home_edge=True, home_edge_fixed=None):
    """Weighted least squares: target = R_h - R_a + HE. Ratings centred at zero. Returns (ratings, home_edge, residuals)."""
    home_idx = np.asarray(home_idx); away_idx = np.asarray(away_idx)
    y = np.asarray(target, dtype=float); w = np.asarray(weights, dtype=float)
    M = len(y)
    ncol = n_teams + (1 if fit_home_edge else 0)
    X = np.zeros((M, ncol))
    X[np.arange(M), home_idx] = 1.0
    X[np.arange(M), away_idx] -= 1.0
    if fit_home_edge:
        X[:, n_teams] = 1.0
    elif home_edge_fixed is not None:
        y = y - np.asarray(home_edge_fixed, dtype=float)  # a scalar league edge or a per-match edge (league + club delta)
    sw = np.sqrt(w)
    Xw = X * sw[:, None]; yw = y * sw
    # ridge on ratings only, plus a sum-to-zero row
    reg = np.zeros((n_teams + 1, ncol))
    reg[np.arange(n_teams), np.arange(n_teams)] = np.sqrt(ridge)
    reg[n_teams, :n_teams] = 10.0
    A = np.vstack([Xw, reg]); b = np.concatenate([yw, np.zeros(n_teams + 1)])
    beta, *_ = np.linalg.lstsq(A, b, rcond=None)
    R = beta[:n_teams]; R = R - R.mean()
    HE = float(beta[n_teams]) if fit_home_edge else (float(np.mean(home_edge_fixed)) if home_edge_fixed is not None else 0.0)
    resid = y - (R[home_idx] - R[away_idx] + (HE if fit_home_edge else 0.0))
    return R, HE, resid


def half_life_weights(dates, asof, half_life_days: float) -> np.ndarray:
    d = pd.to_datetime(pd.Series(dates)).dt.tz_localize(None)
    age = (pd.Timestamp(asof) - d).dt.total_seconds().to_numpy() / 86400.0
    age = np.clip(age, 0.0, None)
    return 0.5 ** (age / float(half_life_days))


def load_club_home_edges(enabled: bool) -> dict:
    """team -> delta goals on top of the league home edge (data/ratings/home_edges.csv), empty when the layer is off."""
    if not enabled:
        return {}
    import os
    from .teams import ROOT
    p = os.path.join(ROOT, "data", "ratings", "home_edges.csv")
    if not os.path.exists(p):
        return {}
    d = pd.read_csv(p, dtype=str, keep_default_na=False)
    out = {}
    for r in d.itertuples(index=False):
        try:
            out[r.team] = float(r.delta_goals)
        except (TypeError, ValueError):
            pass
    return out


def home_edge_for(home: str, league_edge: float, club_deltas: dict | None) -> float:
    return float(league_edge) + float((club_deltas or {}).get(home, 0.0))


def market_fit(closes: pd.DataFrame, teams: list, asof, half_life: float, ridge: float, fit_home_edge=True, home_edge_fixed=None,
               before: bool = True, club_deltas: dict | None = None) -> dict:
    """closes: frame with date, home, away, gd_fit. Fits on closes dated strictly before `asof` (walk-forward) when before=True.
    club_deltas (team -> goals) make the fixed home edge per match: league edge + the home club's delta."""
    idx = {t: i for i, t in enumerate(teams)}
    df = closes.dropna(subset=["gd_fit"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    cutoff = pd.Timestamp(asof)
    df = df[df["date"] < cutoff] if before else df[df["date"] <= cutoff]
    df = df[df["home"].isin(idx) & df["away"].isin(idx)]
    if len(df) == 0:
        return {"ratings": np.zeros(len(teams)), "home_edge": float(home_edge_fixed or 0.0), "n": 0, "resid_sd": np.nan, "n_closes": np.zeros(len(teams), int)}
    w = half_life_weights(df["date"], cutoff, half_life)
    he = home_edge_fixed
    if not fit_home_edge and club_deltas and home_edge_fixed is not None:
        he = float(home_edge_fixed) + df["home"].map(club_deltas).fillna(0.0).to_numpy()
    R, HE, resid = wls_fit(df["home"].map(idx).to_numpy(), df["away"].map(idx).to_numpy(), df["gd_fit"].to_numpy(), w, len(teams), ridge, fit_home_edge, he)
    n_closes = np.bincount(np.concatenate([df["home"].map(idx).to_numpy(), df["away"].map(idx).to_numpy()]), minlength=len(teams))
    wsd = float(np.sqrt(np.average(resid ** 2, weights=w)))
    return {"ratings": R, "home_edge": HE, "n": int(len(df)), "resid_sd": wsd, "n_closes": n_closes, "weights": w}


def apply_expansion_prior(R: np.ndarray, n_closes: np.ndarray, prior: float, threshold: int, expansion_mask: np.ndarray) -> np.ndarray:
    """A club with fewer than `threshold` closes sits at the mean-expansion prior, blended toward the fit as closes arrive."""
    R = R.copy()
    for i in np.where(expansion_mask)[0]:
        n = int(n_closes[i])
        if n < threshold:
            w = n / float(threshold)
            R[i] = w * R[i] + (1 - w) * prior
    return R - R.mean()


def xg_fit(xg: pd.DataFrame, teams: list, asof, half_life: float, ridge: float, market_spread: float | None) -> dict:
    """xG rating: WLS on match-level xG difference (home_xg - away_xg) with its own home effect, ridge toward zero,
    rescaled so its spread matches the market's. xg frame: date, home, away, home_xg, away_xg."""
    idx = {t: i for i, t in enumerate(teams)}
    df = xg.copy()
    df = df[df["home"].isin(idx) & df["away"].isin(idx)]
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] < pd.Timestamp(asof)]
    df = df.dropna(subset=["home_xg", "away_xg"])
    if len(df) == 0:
        return {"ratings": np.zeros(len(teams)), "n": 0}
    w = half_life_weights(df["date"], asof, half_life)
    y = df["home_xg"].astype(float).to_numpy() - df["away_xg"].astype(float).to_numpy()
    R, HE, resid = wls_fit(df["home"].map(idx).to_numpy(), df["away"].map(idx).to_numpy(), y, w, len(teams), ridge, True)
    if market_spread is not None and R.std() > 1e-9:
        R = R * (market_spread / R.std())
    return {"ratings": R, "n": int(len(df)), "home_effect": HE}


def blend(sources: dict[str, np.ndarray], config: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """Weighted mean of the enabled sources (weights from source_config.csv), re-centred. Returns (ratings, weights used)."""
    used = {}
    for r in config.itertuples(index=False):
        if str(r.enabled).strip().lower() in ("y", "yes", "1", "true") and r.source in sources:
            try:
                wgt = float(r.weight)
            except (TypeError, ValueError):
                wgt = 0.0
            if wgt > 0:
                used[r.source] = wgt
    if not used:
        raise ValueError("no enabled rating source with positive weight")
    tot = sum(used.values())
    R = sum(sources[s] * (w / tot) for s, w in used.items())
    return R - R.mean(), used


def shrink_to_posted(g_model: float, g_posted: float | None, s: float) -> float:
    if g_posted is None or not np.isfinite(g_posted):
        return g_model
    return (1.0 - s) * g_model + s * g_posted
