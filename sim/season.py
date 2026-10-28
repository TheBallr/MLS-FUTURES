"""Season engine: N simulated seasons from today's state, vectorised over seasons."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .engine import sample_goals
from .standings import rank_table, EAST, WEST
from .playoffs import conference_bracket, mls_cup, pair_totals, locked_tables


@dataclass
class Fixture:
    home: int
    away: int
    date: str            # ET date YYYY-MM-DD
    adj: float = 0.0     # home_edge + layers (goals, from the home side's view)
    s: float = 0.0       # posted-line shrink weight (0 when no fresh Pinnacle line)
    g_pinn: float = 0.0  # Pinnacle's implied margin when s > 0
    T: float = 3.0       # total goals for the fixture


@dataclass
class SeasonInputs:
    teams: list
    conf: np.ndarray                 # (T,) 0 East, 1 West
    ratings: np.ndarray              # (T,) blended ratings in goals
    fixtures: list                   # unplayed Fixture objects in date order
    played: dict = field(default_factory=dict)  # per-team arrays from real results
    scenarios: list = field(default_factory=list)  # dicts from scenarios.csv
    disc: np.ndarray | None = None   # (T,) disciplinary points to date (0 when unknown)
    h2h_pts: np.ndarray | None = None  # (T,T) points of i against j in the real matches played so far (None: no head-to-head step)
    h2h_gd: np.ndarray | None = None   # (T,T) goal difference of i against j, real matches so far
    dock_exempt: np.ndarray | None = None  # (T,) clubs never docked: playoff odds entering the run already below dead_dock_min_odds (priced as hopeless)
    totals: dict | None = None       # team totals {"base", "offsets"} (refresh_ratings.team_totals) for the playoff matches; None: avg_total_goals
    playoff_results: list = field(default_factory=list)  # real playoff matches [(home, away, winner)] in date order, locked into the bracket
    club_home_deltas: np.ndarray | None = None  # (T,) each club's home edge on top of the league's, used when it hosts a playoff game (2026-10-27)
    playoff_adj: np.ndarray | None = None       # (T,) goals added to each club's rating in the playoffs: the live absences that run past Decision Day x factor_abs (2026-10-27)


def empty_played(T):
    z = lambda: np.zeros(T, dtype=np.int32)
    return {k: z() for k in ("points", "wins", "gd", "gf", "away_gd", "away_gf", "home_gd", "home_gf")}


def run_seasons(inp: SeasonInputs, kn: dict, n_seasons: int | None = None, seed: int | None = None) -> dict:
    N = int(n_seasons or kn["n_seasons"])
    rng = np.random.default_rng(int(kn["seed"] if seed is None else seed))
    rng2 = np.random.default_rng(int(kn["seed"] if seed is None else seed) + 2_000_003)   # Dixon-Coles redraws (paired sampling, 2026-10-28)
    T = len(inp.teams)
    base = np.asarray(inp.ratings, dtype=float)
    # season-long uncertainty: one N(0, rating_sd) draw per club per season (the top-of-table and league-spread variants
    # tested on 2026-10-15 were rejected, 11h, and removed 2026-10-19)
    R = base[None, :] + rng.normal(0.0, 1.0, size=(N, T)) * float(kn["rating_sd"])
    floor, shared = kn["goal_floor"], kn["shared_goals_mean"]; rho = float(kn.get("dc_rho", 0.0) or 0.0)
    k_drift, cap = kn["drift_k_sim"], kn["drift_cap"]

    played = inp.played or empty_played(T)
    acc = {k: np.tile(played[k].astype(np.int32), (N, 1)) for k in played}

    # scenarios drawn once per season from their own stream, so the football-only run is unchanged by a points scenario
    rng_sc = np.random.default_rng(int(kn["seed"] if seed is None else seed) + 1_000_003)
    ded = np.zeros((N, T), dtype=np.int32)
    avail = []  # (team, from, to, pen (N,))
    for sc in inp.scenarios:
        t = sc["team_idx"]
        on = rng_sc.random(N) < float(sc.get("prob", 0.0))
        if sc["type"] == "points":
            d = rng_sc.normal(float(sc.get("mean", 0)), float(sc.get("sd", 0)), N)
            d = np.maximum(np.rint(d), float(sc.get("min", 0)))
            ded[:, t] += np.where(on, d, 0).astype(np.int32)
        elif sc["type"] == "availability":
            avail.append((t, sc["from"], sc["to"], np.where(on, float(sc.get("mean", 0.20)), 0.0)))

    # dead-team dock (method PDF): the moment a club is mathematically out of the playoffs inside a simulated season its
    # rating drops by dead_dock_goals for the rest of that season. Clubs already out at the start are assumed priced by the
    # market and are not docked. Elimination test after each match-day: max reachable points < current points of the last
    # playoff place in the conference. The dock lives in R, so the dice and the drift surprise both see it.
    dock = float(kn.get("dead_dock_goals", 0.0) or 0.0); spots = int(kn.get("playoff_spots", 9))
    if dock > 0:
        dates_sorted = sorted({fx.date for fx in inp.fixtures})
        rem_after = {}  # date -> (T,) fixtures per club strictly after that date
        for d in dates_sorted:
            rem_after[d] = np.bincount([fx.home for fx in inp.fixtures if fx.date > d] + [fx.away for fx in inp.fixtures if fx.date > d], minlength=T)
        docked = np.zeros((N, T), dtype=bool)
        conf_masks = [inp.conf == c for c in (EAST, WEST)]
        def eliminated(pts, rem):
            out = np.zeros((N, T), dtype=bool)
            for cm in conf_masks:
                k = int(cm.sum())
                if k <= spots:
                    continue
                pc = pts[:, cm]
                line = -np.partition(-pc, spots - 1, axis=1)[:, spots - 1]       # points of the last playoff place
                out[:, cm] = (pc + 3 * rem[cm][None, :]) < line[:, None]
            return out
        start_rem = np.bincount([fx.home for fx in inp.fixtures] + [fx.away for fx in inp.fixtures], minlength=T)
        already_out = eliminated(np.tile(played["points"].astype(np.int32), (N, 1)), start_rem)[0]
        if inp.dock_exempt is not None:
            already_out = already_out | np.asarray(inp.dock_exempt, dtype=bool)
        last_date = None
    use_h2h = inp.h2h_pts is not None and bool(kn.get("tiebreak_h2h", True))
    if use_h2h:
        H2P = np.tile(inp.h2h_pts.astype(np.int8), (N, 1, 1)); H2G = np.tile(inp.h2h_gd.astype(np.int8), (N, 1, 1))
    for fx in inp.fixtures:
        h, a = fx.home, fx.away
        if dock > 0 and last_date is not None and fx.date != last_date:
            new_out = eliminated(acc["points"], rem_after[last_date]) & ~docked & ~already_out[None, :]
            R[new_out] -= dock; docked |= new_out
        if dock > 0:
            last_date = fx.date
        pen_h = np.zeros(N); pen_a = np.zeros(N)
        for (t, d0, d1, pen) in avail:
            if d0 <= fx.date <= d1:
                if t == h:
                    pen_h += pen
                elif t == a:
                    pen_a += pen
        g_model = R[:, h] - R[:, a] + fx.adj - pen_h + pen_a
        g = (1.0 - fx.s) * g_model + fx.s * fx.g_pinn
        xh, xa = sample_goals(rng, g, np.full(N, fx.T), floor, shared, rho, rng2)
        m = (xh - xa).astype(np.int32)
        hw = xh > xa; dr = xh == xa
        acc["points"][:, h] += np.where(hw, 3, np.where(dr, 1, 0)); acc["points"][:, a] += np.where(~hw & ~dr, 3, np.where(dr, 1, 0))
        acc["wins"][:, h] += hw; acc["wins"][:, a] += (~hw & ~dr)
        acc["gd"][:, h] += m; acc["gd"][:, a] -= m
        acc["gf"][:, h] += xh; acc["gf"][:, a] += xa
        acc["home_gd"][:, h] += m; acc["home_gf"][:, h] += xh
        acc["away_gd"][:, a] -= m; acc["away_gf"][:, a] += xa
        if use_h2h:
            H2P[:, h, a] += np.where(hw, 3, np.where(dr, 1, 0)).astype(np.int8); H2P[:, a, h] += np.where(~hw & ~dr, 3, np.where(dr, 1, 0)).astype(np.int8)
            H2G[:, h, a] += m.astype(np.int8); H2G[:, a, h] -= m.astype(np.int8)
        # drift: simulated results only; surprise = actual margin - the expected margin the dice used (g, shrink included), so
        # the mean surprise is exactly zero and a shrunk fixture does not drift its sides (the method PDF's rule)
        delta = np.clip(k_drift * (m - g), -cap, cap)
        R[:, h] += delta; R[:, a] -= delta

    points = acc["points"] - ded
    disc = np.tile((inp.disc if inp.disc is not None else np.zeros(T)).astype(np.int32), (N, 1))
    coin = rng.integers(0, 1 << 20, size=(N, T))
    order, league_pos, conf_seed = rank_table(points, acc["wins"], acc["gd"], acc["gf"], disc,
                                              acc["away_gd"], acc["away_gf"], acc["home_gd"], acc["home_gf"], coin, inp.conf,
                                              H2P if use_h2h else None, H2G if use_h2h else None)
    # playoffs (the 2026 bracket needs nine teams per conference; smaller historical conferences skip it)
    stage = np.zeros((N, T), dtype=np.int8)
    champs = {}
    if min(int((inp.conf == EAST).sum()), int((inp.conf == WEST).sum())) >= 9:
        PT = pair_totals(inp.teams, inp.totals, kn["avg_total_goals"]); L = locked_tables(T, inp.playoff_results)
        Rp = R + np.asarray(inp.playoff_adj, float)[None, :] if inp.playoff_adj is not None else R   # the playoff absences (review 2026-10-27, proposal 7)
        che = np.asarray(inp.club_home_deltas, float) if inp.club_home_deltas is not None else None
        for c in (EAST, WEST):
            mask = inp.conf[order] == c                      # (N,T)
            conf_order = order[mask].reshape(N, -1)          # (N, 15) by seed
            seeds = conf_order[:, :9]
            champs[c] = conference_bracket(rng, Rp, seeds, kn["home_edge_goals"], PT, floor, shared, stage, rho, L, club_he=che, rng2=rng2)
        mls_cup(rng, Rp, champs[EAST], champs[WEST], league_pos, kn["home_edge_goals"], PT, floor, shared, stage, rho, L, club_he=che, rng2=rng2)
    return {
        "points": points.astype(np.int16), "wins": acc["wins"].astype(np.int8), "gd": acc["gd"].astype(np.int16), "gf": acc["gf"].astype(np.int16),
        "league_pos": league_pos.astype(np.int8), "conf_seed": conf_seed.astype(np.int8), "stage": stage,
        "teams": np.array(inp.teams), "conf": inp.conf.astype(np.int8), "final_ratings_mean": R.mean(axis=0),
        "docked_share": (docked.mean(axis=0) if dock > 0 else np.zeros(T)),
    }


def dock_exempt_from_prepass(inp, kn: dict, seed: int | None = None, n: int = 20000) -> np.ndarray:
    """Clubs whose playoff odds entering the run (a quick pass without the dock) are below dead_dock_min_odds: the market has
    priced them as hopeless, so the dock would count twice (the method PDF's rule)."""
    kn2 = dict(kn); kn2["dead_dock_goals"] = 0.0
    out = run_seasons(inp, kn2, n_seasons=n, seed=seed)
    spots = int(kn.get("playoff_spots", 9))
    po = (out["conf_seed"] <= spots).mean(axis=0)
    return po < float(kn.get("dead_dock_min_odds", 0.02))
