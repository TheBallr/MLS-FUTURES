"""MLS standings: points then the tiebreaker chain, vectorised over simulated seasons.
Chain (2026 Competition Guidelines): points, wins, gd, gf, head-to-head (intraconference), fewest disciplinary points, away gd,
away gf, home gd, home gf, coin toss."""
from __future__ import annotations
import numpy as np

EAST, WEST = 0, 1


def _composite(points, wins, gd, gf, disc, away_gd, away_gf, home_gd, home_gf, coin, h2h=None):
    """Two int64 keys (hi, lo) whose lexicographic order equals the tiebreaker chain, larger = better.
    Chain (2026 Competition Guidelines): points, wins, gd, gf, head-to-head (key h2h, intraconference), fewest disciplinary
    points, away gd, away gf, home gd, home gf, coin toss."""
    points = points.astype(np.int64); wins = wins.astype(np.int64); gd = gd.astype(np.int64); gf = gf.astype(np.int64)
    disc = disc.astype(np.int64); away_gd = away_gd.astype(np.int64); away_gf = away_gf.astype(np.int64)
    home_gd = home_gd.astype(np.int64); home_gf = home_gf.astype(np.int64); coin = coin.astype(np.int64)
    h2h = np.zeros_like(points) if h2h is None else h2h.astype(np.int64)
    hi = ((((((np.clip(points, 0, 1023)) * 64 + np.clip(wins, 0, 63)) * 1024 + np.clip(gd + 512, 0, 1023)) * 512
           + np.clip(gf, 0, 511)) * 32 + np.clip(h2h, 0, 31)) * 4096 + np.clip(4095 - disc, 0, 4095))
    lo = ((((np.clip(away_gd + 512, 0, 1023)) * 512 + np.clip(away_gf, 0, 511)) * 1024 + np.clip(home_gd + 512, 0, 1023)) * 512
          + np.clip(home_gf, 0, 511)) * 1048576 + np.clip(coin, 0, 1048575)
    return hi, lo


def _h2h_key(points, wins, gd, gf, conf, h2h_pts, h2h_gd, same_conf_only=True):
    """Head-to-head step (2026 Competition Guidelines, intraconference only): among clubs level on points, wins, gd and gf,
    rank by points then goal difference in the matches between them; after the top club is settled the rest are re-ranked
    among themselves (the guidelines' second round). Returns an int8 key (N, T): higher is better, 0 where no tie."""
    N, T = points.shape
    key = np.zeros((N, T), dtype=np.int8)
    if h2h_pts is None:
        return key
    base = (points.astype(np.int64) * 64 + wins) * 1024 + (gd + 512)
    base = (base * 512 + gf) * 2 + np.asarray(conf, dtype=np.int64)[None, :]  # ties are grouped within a conference, so a level
    # club in the other conference never switches the step off for two clubs of the same conference (fixed 2026-10-19)
    srt = np.sort(base, axis=1)
    has_tie = (srt[:, 1:] == srt[:, :-1]).any(axis=1)
    for n in np.where(has_tie)[0]:
        vals, inv, cnt = np.unique(base[n], return_inverse=True, return_counts=True)
        for g in np.where(cnt > 1)[0]:
            members = list(np.where(inv == g)[0])
            if same_conf_only and len(set(conf[m] for m in members)) > 1:
                continue
            rank = len(members)
            while len(members) > 1:
                # a club that is not strictly ahead on h2h keeps key 0 along with the rest (next tiebreakers decide)
                pts_i = [sum(h2h_pts[n, i, j] for j in members if j != i) for i in members]
                gd_i = [sum(h2h_gd[n, i, j] for j in members if j != i) for i in members]
                top = [i for i, p_, d_ in zip(members, pts_i, gd_i) if (p_, d_) == max(zip(pts_i, gd_i))]
                if len(top) == len(members):
                    break
                for i in top:
                    key[n, i] = rank
                members = [i for i in members if i not in top]
                rank -= 1
            if len(members) == 1:
                key[n, members[0]] = rank
    return key


def rank_table(points, wins, gd, gf, disc, away_gd, away_gf, home_gd, home_gf, coin, conf, h2h_pts=None, h2h_gd=None):
    """All inputs (N, T). conf is (T,) with 0=East 1=West. h2h_pts / h2h_gd (N, T, T): points and goal difference of team i
    against team j in the matches between them (optional: the head-to-head step is skipped when None).
    Returns order (N,T) team indices best->worst, league_pos (N,T) 1-based, conf_seed (N,T) 1-based within conference."""
    N, T = points.shape
    h2h = _h2h_key(points, wins, gd, gf, conf, h2h_pts, h2h_gd)
    hi, lo = _composite(points, wins, gd, gf, disc, away_gd, away_gf, home_gd, home_gf, coin, h2h)
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
