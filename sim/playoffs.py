"""MLS Cup Playoffs (2026 format, verified Oct 2026): top 9 per conference; 8 v 9 Wild Card single match hosted by 8;
Round One best-of-three (1 v WC, 2 v 7, 3 v 6, 4 v 5; higher seed hosts games 1 and 3; every game has a winner);
conference semis and finals single matches hosted by the higher seed; MLS Cup hosted by the finalist with the better
regular-season record. A level Wild Card or Round One game goes straight to penalties (a coin flip); a level conference semi,
conference final or MLS Cup plays 30 minutes of extra time first (the 2026 guidelines: two 15-minute periods in their entirety,
then penalties), simulated as a mini-match at a third of the goal means (`extra_time`). Each match is played at the two clubs' team total
(the regular season's rule) and a playoff match already played is locked to its real winner (`locked_tables`)."""
from __future__ import annotations
import numpy as np
from .engine import sample_goals

STAGE = {"missed": 0, "wild_card": 1, "round_one": 2, "conf_semi": 3, "conf_final": 4, "cup_final": 5, "cup_winner": 6}
STAGE_NAME = {v: k for k, v in STAGE.items()}


def pair_totals(teams, tt, default) -> np.ndarray:
    """(n, n) match totals for the knockouts by the regular season's rule (scripts/refresh_ratings.fixture_total): league base
    plus both clubs' offsets, clipped to [2.0, 4.5]; the flat default when team totals are off (tt empty)."""
    n = len(teams)
    if not tt:
        return np.full((n, n), float(default))
    u = np.array([float(tt["offsets"].get(t, 0.0)) for t in teams])
    return np.clip(float(tt["base"]) + u[:, None] + u[None, :], 2.0, 4.5)


def real_playoff_results(res, teams, season) -> list:
    """The season's played playoff matches (results.csv rows with competition "MLS Cup Playoffs") as [(home, away, winner)]
    team indices in date order. The winner is the feed's (penalties included); a level score without one cannot be locked
    and is skipped with a warning."""
    import sys
    idx = {t: i for i, t in enumerate(teams)}
    out = []
    rows = res[(res["competition"] == "MLS Cup Playoffs") & (res["date"].astype(str).str[:4] == str(season))] if len(res) else res
    for r in sorted(rows.to_dict("records"), key=lambda r: r["date"]):
        h, a = r["home"], r["away"]
        if h not in idx or a not in idx:
            continue
        w = str(r.get("winner") or "")
        if not w:
            try:
                hg, ag = int(r["hg"]), int(r["ag"])
            except (TypeError, ValueError):
                continue
            w = h if hg > ag else (a if ag > hg else "")
        if w not in (h, a):
            print(f"playoffs: {r['date']} {h} v {a} has no winner on file; not locked", file=sys.stderr); continue
        out.append((idx[h], idx[a], idx[w]))
    return out


def locked_tables(n, results) -> np.ndarray | None:
    """results [(home, away, winner)] in date order -> (3, n, n): L[k, a, b] = the winner of the k-th meeting of a and b in
    either order, -1 when not played. Single-match rounds read k 0; a Round One series reads k 0, 1, 2 for games 1-3."""
    if not results:
        return None
    L = np.full((3, n, n), -1, dtype=np.int16); seen = {}
    for h, a, w in results:
        k = seen.get(frozenset((h, a)), 0); seen[frozenset((h, a))] = k + 1
        if k < 3:
            L[k, h, a] = L[k, a, h] = w
    return L


def knockout(rng, R, home_idx, away_idx, home_edge, T, floor, shared, rho=0.0, locked=None, extra_time=False, club_he=None, rng2=None):
    """One match per season; returns bool array home_wins. T is a scalar or the (n, n) pair_totals table; locked is one
    (n, n) slice of locked_tables (or None). With extra_time (semis, finals, the Cup) a level game plays 30 more minutes at a
    third of the goal means (same margin, so the stronger side keeps its edge) before the penalty coin; without it (Wild Card,
    Round One) straight to the coin. The dice are thrown either way, so a locked game leaves the stream unchanged."""
    n = np.arange(R.shape[0])
    g = R[n, home_idx] - R[n, away_idx] + home_edge + (club_he[home_idx] if club_he is not None else 0.0)   # club_he: the host's home delta (review 2026-10-27, proposal 7)
    Tg = T[home_idx, away_idx] if np.ndim(T) == 2 else np.full_like(g, T)
    xh, xa = sample_goals(rng, g, Tg, floor, shared, rho, rng2)
    draw = xh == xa
    coin = rng.random(len(g)) < 0.5
    settled = coin
    if extra_time:
        eh, ea = sample_goals(rng, g / 3.0, Tg / 3.0, floor / 3.0, shared / 3.0, 0.0, rng2)
        settled = np.where(eh > ea, True, np.where(eh < ea, False, coin))
    hw = np.where(draw, settled, xh > xa)
    if locked is not None:
        lw = locked[home_idx, away_idx]
        hw = np.where(lw >= 0, lw == home_idx, hw)
    return hw


def best_of_three(rng, R, hi_idx, lo_idx, home_edge, T, floor, shared, rho=0.0, L=None, club_he=None, rng2=None):
    """Higher seed hosts games 1 and 3, lower seed hosts game 2. No draws, so first-to-two == majority of three."""
    lk = (lambda k: None) if L is None else (lambda k: L[k])
    w1 = knockout(rng, R, hi_idx, lo_idx, home_edge, T, floor, shared, rho, lk(0), club_he=club_he, rng2=rng2)
    w2 = ~knockout(rng, R, lo_idx, hi_idx, home_edge, T, floor, shared, rho, lk(1), club_he=club_he, rng2=rng2)
    w3 = knockout(rng, R, hi_idx, lo_idx, home_edge, T, floor, shared, rho, lk(2), club_he=club_he, rng2=rng2)
    return (w1.astype(int) + w2.astype(int) + w3.astype(int)) >= 2


def conference_bracket(rng, R, seeds, home_edge, T, floor, shared, stage, rho=0.0, L=None, club_he=None, rng2=None):
    """seeds: (N, 9) team indices by seed 1..9. Fills `stage` (N, T_teams) in place. Returns champion idx (N,). L: locked_tables
    or None."""
    N = R.shape[0]
    L0 = None if L is None else L[0]
    rows = np.arange(N)
    s = {k: seeds[:, k - 1] for k in range(1, 10)}
    for k in range(1, 10):
        stage[rows, s[k]] = np.maximum(stage[rows, s[k]], STAGE["round_one"] if k <= 7 else STAGE["wild_card"])
    # Wild Card: 8 hosts 9
    w8 = knockout(rng, R, s[8], s[9], home_edge, T, floor, shared, rho, L0, club_he=club_he, rng2=rng2)
    wc = np.where(w8, s[8], s[9])
    stage[rows, wc] = STAGE["round_one"]
    # Round One: 1 v WC, 2 v 7, 3 v 6, 4 v 5
    pairs = [(s[1], wc), (s[2], s[7]), (s[3], s[6]), (s[4], s[5])]
    r1 = []
    for hi, lo in pairs:
        hw = best_of_three(rng, R, hi, lo, home_edge, T, floor, shared, rho, L, club_he=club_he, rng2=rng2)
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
        hw = knockout(rng, R, h, v, home_edge, T, floor, shared, rho, None if L is None else L[0], extra_time=True, club_he=club_he, rng2=rng2)
        sf.append(np.where(hw, h, v))
    for w in sf:
        stage[rows, w] = STAGE["conf_final"]
    h, v = host_order(sf[0], sf[1])
    hw = knockout(rng, R, h, v, home_edge, T, floor, shared, rho, None if L is None else L[0], extra_time=True, club_he=club_he, rng2=rng2)
    champ = np.where(hw, h, v)
    stage[rows, champ] = STAGE["cup_final"]
    return champ


def mls_cup(rng, R, east_champ, west_champ, league_pos, home_edge, T, floor, shared, stage, rho=0.0, L=None, club_he=None, rng2=None):
    rows = np.arange(R.shape[0])
    east_hosts = league_pos[rows, east_champ] < league_pos[rows, west_champ]
    h = np.where(east_hosts, east_champ, west_champ)
    v = np.where(east_hosts, west_champ, east_champ)
    hw = knockout(rng, R, h, v, home_edge, T, floor, shared, rho, None if L is None else L[0], extra_time=True, club_he=club_he, rng2=rng2)
    winner = np.where(hw, h, v)
    stage[rows, winner] = STAGE["cup_winner"]
    return winner
