"""Odds conversion and devigging. Only complete pools are devigged (power method)."""
from __future__ import annotations
import numpy as np


def american_to_decimal(a) -> float:
    a = float(a)
    if a >= 100:
        return 1.0 + a / 100.0
    if a <= -100:
        return 1.0 + 100.0 / abs(a)
    raise ValueError(f"not an American price: {a}")


def decimal_to_american(d) -> int:
    d = float(d)
    if d >= 2.0:
        return int(round((d - 1.0) * 100))
    return int(round(-100.0 / (d - 1.0)))


def prob_to_american(p) -> int:
    p = float(p)
    if p <= 0 or p >= 1:
        raise ValueError(p)
    return decimal_to_american(1.0 / p)


def implied(decimals) -> np.ndarray:
    d = np.asarray(decimals, dtype=float)
    return 1.0 / d


def power_devig(decimals, tol=1e-10, max_iter=200) -> np.ndarray:
    """Power method: find k such that sum(q_i^k) = 1 where q_i = 1/odds_i. Returns fair probabilities.
    Requires a complete pool (all outcomes present)."""
    q = implied(decimals)
    if np.any(q <= 0) or len(q) < 2:
        raise ValueError("need a complete pool of positive prices")
    s = q.sum()
    if abs(s - 1.0) < 1e-12:
        return q
    lo, hi = 0.0, 1.0
    if s > 1.0:  # overround: k > 1 raises... q^k with q<1 shrinks probabilities, so k>1
        lo, hi = 1.0, 1.0
        while np.sum(q ** hi) > 1.0:
            hi *= 2.0
            if hi > 1e6:
                break
    else:  # under-round: k < 1
        lo, hi = 0.0, 1.0
    for _ in range(max_iter):
        k = 0.5 * (lo + hi)
        v = np.sum(q ** k)
        if abs(v - 1.0) < tol:
            break
        if v > 1.0:
            lo = k
        else:
            hi = k
    p = q ** k
    return p / p.sum()


def hold(decimals) -> float:
    return float(implied(decimals).sum() - 1.0)

