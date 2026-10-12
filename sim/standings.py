"""MLS standings: points then the tiebreaker chain, vectorised over simulated seasons.
Chain (config.mls.tiebreakers): points, wins, gd, gf, fewest disciplinary points, away gd, away gf, home gd, home gf, coin toss."""
from __future__ import annotations
import numpy as np

EAST, WEST = 0, 1


def _composite(points, wins, gd, gf, disc, away_gd, away_gf, home_gd, home_gf, coin):
    """Two int64 keys (hi, lo) whose lexicographic order equals the tiebreaker chain, larger = better."""
    points = points.astype(np.int64); wins = wins.astype(np.int64); gd = gd.astype(np.int64); gf = gf.astype(np.int64)
    disc = disc.astype(np.int64); away_gd = away_gd.astype(np.int64); away_gf = away_gf.astype(np.int64)
    home_gd = home_gd.astype(np.int64); home_gf = home_gf.astype(np.int64); coin = coin.astype(np.int64)
    hi = (((((np.clip(points, 0, 1023)) * 64 + np.clip(wins, 0, 63)) * 1024 + np.clip(gd + 512, 0, 1023)) * 512
           + np.clip(gf, 0, 511)) * 4096 + np.clip(4095 - disc, 0, 4095))
    lo = ((((np.clip(away_gd + 512, 0, 1023)) * 512 + np.clip(away_gf, 0, 511)) * 1024 + np.clip(home_gd + 512, 0, 1023)) * 512
          + np.clip(home_gf, 0, 511)) * 1048576 + np.clip(coin, 0, 1048575)
    return hi, lo


def rank_table(points, wins, gd, gf, disc, away_gd, away_gf, home_gd, home_gf, coin, conf):
    """All inputs (N, T). conf is (T,) with 0=East 1=West.
    Returns order (N,T) team indices best->worst, league_pos (N,T) 1-based, conf_seed (N,T) 1-based within conference."""
    N, T = points.shape
    hi, lo = _composite(points, wins, gd, gf, disc, away_gd, away_gf, home_gd, home_gf, coin)
    season = np.repeat(np.arange(N, dtype=np.int64), T)
    order_flat = np.lexsort((-lo.ravel(), -hi.ravel(), season))
    order = (order_flat % T).reshape(N, T)
    league_pos = np.empty((N, T), dtype=np.int16)
    np.put_along_axis(league_pos, order, np.tile(np.arange(1, T + 1, dtype=np.int16), (N, 1)), axis=1)
    conf_of_order = conf[order]  # (N,T)
    seed_in_conf = np.zeros((N, T), dtype=np.int16)
    for c in (EAST, WEST):
        m = conf_of_order == c
        seed_in_conf += (np.cumsum(m, axis=1) * m).astype(np.int16)
    conf_seed = np.empty((N, T), dtype=np.int16)
    np.put_along_axis(conf_seed, order, seed_in_conf, axis=1)
    return order, league_pos, conf_seed


def rank_single(table: list[dict], conf: dict[str, str]) -> list[dict]:
    """Rank one real table (list of dicts with team, points, wins, gd, gf, disc, away_gd, away_gf, home_gd, home_gf).
    Coin toss is a stable tie on name. Returns rows sorted best->worst with league_pos and conf_seed."""
    key = lambda r: (-r["points"], -r["wins"], -r["gd"], -r["gf"], r.get("disc", 0), -r.get("away_gd", 0), -r.get("away_gf", 0), -r.get("home_gd", 0), -r.get("home_gf", 0), r["team"])
    rows = sorted(table, key=key)
    seeds = {"East": 0, "West": 0}
    for i, r in enumerate(rows):
        r["league_pos"] = i + 1
        c = conf.get(r["team"], "East")
        seeds[c] += 1
        r["conf_seed"] = seeds[c]
    return rows
