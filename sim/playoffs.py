"""MLS Cup Playoffs (2026 format, verified Oct 2026): top 9 per conference; 8 v 9 Wild Card single match hosted by 8;
Round One best-of-three (1 v WC, 2 v 7, 3 v 6, 4 v 5; higher seed hosts games 1 and 3; every game has a winner);
conference semis and finals single matches hosted by the higher seed; MLS Cup hosted by the finalist with the better
regular-season record. A drawn knockout match is a coin flip (penalties)."""
from __future__ import annotations
import numpy as np
from .engine import sample_goals

STAGE = {"missed": 0, "wild_card": 1, "round_one": 2, "conf_semi": 3, "conf_final": 4, "cup_final": 5, "cup_winner": 6}
STAGE_NAME = {v: k for k, v in STAGE.items()}


def knockout(rng, R, home_idx, away_idx, home_edge, T, floor, shared):
    """One match per season; returns bool array home_wins."""
    n = np.arange(R.shape[0])
    g = R[n, home_idx] - R[n, away_idx] + home_edge
    xh, xa = sample_goals(rng, g, np.full_like(g, T), floor, shared)
    draw = xh == xa
    coin = rng.random(len(g)) < 0.5
    return np.where(draw, coin, xh > xa)


def best_of_three(rng, R, hi_idx, lo_idx, home_edge, T, floor, shared):
    """Higher seed hosts games 1 and 3, lower seed hosts game 2. No draws, so first-to-two == majority of three."""
    w1 = knockout(rng, R, hi_idx, lo_idx, home_edge, T, floor, shared)
    w2 = ~knockout(rng, R, lo_idx, hi_idx, home_edge, T, floor, shared)
    w3 = knockout(rng, R, hi_idx, lo_idx, home_edge, T, floor, shared)
    return (w1.astype(int) + w2.astype(int) + w3.astype(int)) >= 2


def conference_bracket(rng, R, seeds, home_edge, T, floor, shared, stage):
    """seeds: (N, 9) team indices by seed 1..9. Fills `stage` (N, T_teams) in place. Returns champion idx (N,) and its seed."""
    N = R.shape[0]
    rows = np.arange(N)
    s = {k: seeds[:, k - 1] for k in range(1, 10)}
    for k in range(1, 10):
        stage[rows, s[k]] = np.maximum(stage[rows, s[k]], STAGE["round_one"] if k <= 7 else STAGE["wild_card"])
    # Wild Card: 8 hosts 9
    w8 = knockout(rng, R, s[8], s[9], home_edge, T, floor, shared)
    wc = np.where(w8, s[8], s[9])
    stage[rows, wc] = STAGE["round_one"]
    # Round One: 1 v WC, 2 v 7, 3 v 6, 4 v 5
    pairs = [(s[1], wc), (s[2], s[7]), (s[3], s[6]), (s[4], s[5])]
    r1 = []
    for hi, lo in pairs:
        hw = best_of_three(rng, R, hi, lo, home_edge, T, floor, shared)
        r1.append(np.where(hw, hi, lo))
    for w in r1:
        stage[rows, w] = STAGE["conf_semi"]
    # Conference semis: (1/WC) v (4/5), (2/7) v (3/6); higher seed hosts
    seed_of = np.empty_like(stage)
    for k in range(1, 10):
        seed_of[rows, s[k]] = k
    def host_order(a, b):
        a_hi = seed_of[rows, a] < seed_of[rows, b]
        return np.where(a_hi, a, b), np.where(a_hi, b, a)
    sf = []
    for a, b in ((r1[0], r1[3]), (r1[1], r1[2])):
        h, v = host_order(a, b)
        hw = knockout(rng, R, h, v, home_edge, T, floor, shared)
        sf.append(np.where(hw, h, v))
    for w in sf:
        stage[rows, w] = STAGE["conf_final"]
    h, v = host_order(sf[0], sf[1])
    hw = knockout(rng, R, h, v, home_edge, T, floor, shared)
    champ = np.where(hw, h, v)
    stage[rows, champ] = STAGE["cup_final"]
    return champ


def mls_cup(rng, R, east_champ, west_champ, league_pos, home_edge, T, floor, shared, stage):
    rows = np.arange(R.shape[0])
    east_hosts = league_pos[rows, east_champ] < league_pos[rows, west_champ]
    h = np.where(east_hosts, east_champ, west_champ)
    v = np.where(east_hosts, west_champ, east_champ)
    hw = knockout(rng, R, h, v, home_edge, T, floor, shared)
    winner = np.where(hw, h, v)
    stage[rows, winner] = STAGE["cup_winner"]
    return winner
