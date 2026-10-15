"""Match engine: expected margin + total -> goal means with a shared Poisson component; analytic score grid; sampling."""
from __future__ import annotations
import math
import numpy as np

GRID = 11  # 0..10 goals each side for the analytic grid


def goal_means(g, T, floor: float, shared: float):
    """home mean, away mean, shared c (arrays or scalars). E[X-Y] == g exactly."""
    g = np.asarray(g, dtype=float)
    T = np.asarray(T, dtype=float)
    mu_h = np.maximum(T / 2.0 + g / 2.0, floor)
    mu_a = np.maximum(T / 2.0 - g / 2.0, floor)
    c = np.clip(np.minimum(shared, np.minimum(mu_h, mu_a) - floor), 0.0, None)
    return mu_h, mu_a, c


_LGAMMA = np.array([math.lgamma(i + 1) for i in range(64)])
_K = np.arange(64, dtype=float)


def _pois_pmf(lam: float, n: int) -> np.ndarray:
    if lam <= 0:
        out = np.zeros(n)
        out[0] = 1.0
        return out
    return np.exp(-lam + _K[:n] * math.log(lam) - _LGAMMA[:n])


def dc_tau(mu_h, mu_a, rho):
    """Dixon-Coles multipliers for the 0-0, 1-0, 0-1 and 1-1 cells (rho < 0 adds draws at the low scorelines)."""
    return {(0, 0): 1.0 - mu_h * mu_a * rho, (1, 0): 1.0 + mu_a * rho, (0, 1): 1.0 + mu_h * rho, (1, 1): 1.0 - rho}


def score_grid(g: float, T: float, floor: float, shared: float, n: int = GRID, rho: float = 0.0) -> np.ndarray:
    """P[x, y] for home goals x and away goals y, 0..n-1. Bivariate Poisson via common component c, with the Dixon-Coles
    correction (rho, knob dc_rho) on the four low scorelines, renormalised."""
    mu_h, mu_a, c = goal_means(g, T, floor, shared)
    mu_h, mu_a, c = float(mu_h), float(mu_a), float(c)
    ph = _pois_pmf(mu_h - c, n)
    pa = _pois_pmf(mu_a - c, n)
    pc = _pois_pmf(c, n)
    P = np.zeros((n, n))
    for k in range(n):
        if pc[k] < 1e-15:
            break
        P[k:, k:] += pc[k] * np.outer(ph[: n - k], pa[: n - k])
    if rho:
        for (x, y), t in dc_tau(mu_h, mu_a, rho).items():
            P[x, y] *= max(t, 0.0)
    return P / P.sum()


def hda_from_grid(P: np.ndarray) -> tuple[float, float, float]:
    x = np.arange(P.shape[0])[:, None]
    y = np.arange(P.shape[1])[None, :]
    return float(P[x > y].sum()), float(P[x == y].sum()), float(P[x < y].sum())


def hda(g: float, T: float, floor: float, shared: float, rho: float = 0.0) -> tuple[float, float, float]:
    return hda_from_grid(score_grid(g, T, floor, shared, rho=rho))


def margin_dist(P: np.ndarray) -> dict[int, float]:
    n = P.shape[0]
    d = {}
    for x in range(n):
        for y in range(n):
            d[x - y] = d.get(x - y, 0.0) + P[x, y]
    return d


def total_dist(P: np.ndarray) -> dict[int, float]:
    n = P.shape[0]
    d = {}
    for x in range(n):
        for y in range(n):
            d[x + y] = d.get(x + y, 0.0) + P[x, y]
    return d


def _two_way_fair(win: float, lose: float) -> float:
    """Fair probability a two-way devig would produce for a side with win and lose stake fractions (pushes excluded)."""
    if win + lose <= 0:
        return 0.5
    return win / (win + lose)


def ah_home_fair(P: np.ndarray, line: float) -> float:
    """Fair (devigged-equivalent) probability of the home side at Asian handicap `line` (home gives `line`, e.g. -0.5, -0.25, 0, +0.25)."""
    md = margin_dist(P)
    q = round(line * 4)
    if q % 2 == 0:  # half or whole line
        lines = [line]
    else:  # quarter line: split across neighbouring lines
        lines = [(q - 1) / 4.0, (q + 1) / 4.0]
    win = lose = 0.0
    for L in lines:
        for m, p in md.items():
            v = m + L
            if v > 1e-9:
                win += p / len(lines)
            elif v < -1e-9:
                lose += p / len(lines)
    return _two_way_fair(win, lose)


def total_over_fair(P: np.ndarray, line: float) -> float:
    td = total_dist(P)
    q = round(line * 4)
    lines = [line] if q % 2 == 0 else [(q - 1) / 4.0, (q + 1) / 4.0]
    win = lose = 0.0
    for L in lines:
        for t, p in td.items():
            v = t - L
            if v > 1e-9:
                win += p / len(lines)
            elif v < -1e-9:
                lose += p / len(lines)
    return _two_way_fair(win, lose)


def _bisect(f, lo, hi, target, iters=36):
    flo = f(lo) - target
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid) - target
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def margin_from_three_way(ph: float, pa: float, T: float, floor: float, shared: float, rho: float = 0.0) -> float:
    """Solve g such that the grid's P(H) - P(A) equals the devigged ph - pa at total T."""
    target = ph - pa
    f = lambda g: (lambda h: h[0] - h[2])(hda(g, T, floor, shared, rho))
    return _bisect(f, -4.0, 4.0, target)


def margin_from_ah(p_home: float, line: float, T: float, floor: float, shared: float, rho: float = 0.0) -> float:
    """Solve g such that the model's fair home price at AH `line` equals the devigged p_home."""
    f = lambda g: ah_home_fair(score_grid(g, T, floor, shared, rho=rho), line)
    return _bisect(f, -4.0, 4.0, p_home)


def total_from_ou(p_over: float, line: float, g: float, floor: float, shared: float, rho: float = 0.0) -> float:
    f = lambda T: total_over_fair(score_grid(g, T, floor, shared, rho=rho), line)
    return _bisect(f, 0.8, 7.0, p_over)


def sample_goals(rng: np.random.Generator, g, T, floor: float, shared: float, rho: float = 0.0):
    """Vectorised sampling: returns (home_goals, away_goals) int arrays shaped like g. With rho, the Dixon-Coles cells are
    imposed by rejection (accept with tau / tau_max; the accepted sample follows the renormalised corrected grid)."""
    mu_h, mu_a, c = goal_means(g, T, floor, shared)
    x3 = rng.poisson(c)
    xh = rng.poisson(mu_h - c) + x3
    xa = rng.poisson(mu_a - c) + x3
    if rho:
        mu_h = np.broadcast_to(mu_h, xh.shape); mu_a = np.broadcast_to(mu_a, xh.shape); c = np.broadcast_to(c, xh.shape)
        t00 = 1.0 - mu_h * mu_a * rho; t10 = 1.0 + mu_a * rho; t01 = 1.0 + mu_h * rho; t11 = 1.0 - rho
        tmax = np.maximum.reduce([np.ones_like(t00), t00, t10, t01, np.full_like(t00, t11)])
        pending = np.ones(xh.shape, dtype=bool)  # each candidate is tested once; only rejected ones are redrawn
        for _ in range(40):
            tau = np.ones_like(t00)
            tau = np.where((xh == 0) & (xa == 0), t00, tau); tau = np.where((xh == 1) & (xa == 0), t10, tau)
            tau = np.where((xh == 0) & (xa == 1), t01, tau); tau = np.where((xh == 1) & (xa == 1), t11, tau)
            rej = pending & (rng.random(xh.shape) * tmax > tau)
            pending = rej
            if not rej.any():
                break
            x3r = rng.poisson(c[rej]); xh[rej] = rng.poisson(mu_h[rej] - c[rej]) + x3r; xa[rej] = rng.poisson(mu_a[rej] - c[rej]) + x3r
    return xh, xa
