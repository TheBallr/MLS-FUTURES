"""Season engine: N simulated seasons from today's state, vectorised over seasons."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .engine import sample_goals
from .standings import rank_table, EAST, WEST
from .playoffs import conference_bracket, mls_cup, STAGE


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


def empty_played(T):
    z = lambda: np.zeros(T, dtype=np.int32)
    return {k: z() for k in ("points", "wins", "gd", "gf", "away_gd", "away_gf", "home_gd", "home_gf")}


def run_seasons(inp: SeasonInputs, kn: dict, n_seasons: int | None = None, seed: int | None = None, rating_override=None) -> dict:
    N = int(n_seasons or kn["n_seasons"])
    rng = np.random.default_rng(int(kn["seed"] if seed is None else seed))
    T = len(inp.teams)
    base = np.asarray(inp.ratings if rating_override is None else rating_override, dtype=float)
    R = base[None, :] + rng.normal(0.0, kn["rating_sd"], size=(N, T))
    floor, shared = kn["goal_floor"], kn["shared_goals_mean"]
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

    rows = np.arange(N)
    for fx in inp.fixtures:
        h, a = fx.home, fx.away
        pen_h = np.zeros(N); pen_a = np.zeros(N)
        for (t, d0, d1, pen) in avail:
            if d0 <= fx.date <= d1:
                if t == h:
                    pen_h += pen
                elif t == a:
                    pen_a += pen
        g_model = R[:, h] - R[:, a] + fx.adj - pen_h + pen_a
        g = (1.0 - fx.s) * g_model + fx.s * fx.g_pinn
        xh, xa = sample_goals(rng, g, np.full(N, fx.T), floor, shared)
        m = (xh - xa).astype(np.int32)
        hw = xh > xa; dr = xh == xa
        acc["points"][:, h] += np.where(hw, 3, np.where(dr, 1, 0)); acc["points"][:, a] += np.where(~hw & ~dr, 3, np.where(dr, 1, 0))
        acc["wins"][:, h] += hw; acc["wins"][:, a] += (~hw & ~dr)
        acc["gd"][:, h] += m; acc["gd"][:, a] -= m
        acc["gf"][:, h] += xh; acc["gf"][:, a] += xa
        acc["home_gd"][:, h] += m; acc["home_gf"][:, h] += xh
        acc["away_gd"][:, a] -= m; acc["away_gf"][:, a] += xa
        # drift: simulated results only; surprise = actual margin - expected margin (model's own g)
        delta = np.clip(k_drift * (m - g_model), -cap, cap)
        R[:, h] += delta; R[:, a] -= delta

    points = acc["points"] - ded
    disc = np.tile((inp.disc if inp.disc is not None else np.zeros(T)).astype(np.int32), (N, 1))
    coin = rng.integers(0, 1 << 20, size=(N, T))
    order, league_pos, conf_seed = rank_table(points, acc["wins"], acc["gd"], acc["gf"], disc,
                                              acc["away_gd"], acc["away_gf"], acc["home_gd"], acc["home_gf"], coin, inp.conf)
    # playoffs (the 2026 bracket needs nine teams per conference; smaller historical conferences skip it)
    stage = np.zeros((N, T), dtype=np.int8)
    champs = {}
    if min(int((inp.conf == EAST).sum()), int((inp.conf == WEST).sum())) >= 9:
        for c in (EAST, WEST):
            mask = inp.conf[order] == c                      # (N,T)
            conf_order = order[mask].reshape(N, -1)          # (N, 15) by seed
            seeds = conf_order[:, :9]
            champs[c] = conference_bracket(rng, R, seeds, kn["home_edge_goals"], kn["avg_total_goals"], floor, shared, stage)
        mls_cup(rng, R, champs[EAST], champs[WEST], league_pos, kn["home_edge_goals"], kn["avg_total_goals"], floor, shared, stage)
    return {
        "points": points.astype(np.int16), "wins": acc["wins"].astype(np.int8), "gd": acc["gd"].astype(np.int16),
        "league_pos": league_pos.astype(np.int8), "conf_seed": conf_seed.astype(np.int8), "stage": stage,
        "teams": np.array(inp.teams), "conf": inp.conf.astype(np.int8), "final_ratings_mean": R.mean(axis=0),
    }
