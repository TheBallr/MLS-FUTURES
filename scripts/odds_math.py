#!/usr/bin/env python3
"""Odds conversions, power devig of a futures field, and log-odds pooling (used by fetch_odds.py and edges.py).
Probabilities are 0-1 throughout; decimal odds include the stake."""
from __future__ import annotations
import math


def american_to_decimal(a: float) -> float:
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / -a


def decimal_to_american(d: float) -> int:
    d = float(d)
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))


def prob_to_american(p: float) -> int:
    return decimal_to_american(1 / p)


def hold(implied: list[float]) -> float:
    """Overround of a field: sum of break-even probabilities minus one (0.25 = 25% hold)."""
    return sum(implied) - 1


def power_devig(implied: list[float], tol: float = 1e-10) -> list[float]:
    """Power method: fair_i = q_i ** k with k chosen so the field sums to one (k > 1 when the field holds).
    Shrinks longshots more than favourites, the standard fit to the favourite-longshot pattern in futures pools."""
    q = [min(max(x, 1e-9), 1 - 1e-9) for x in implied]
    s = sum(q)
    if abs(s - 1) < tol:
        return q
    lo, hi = (1.0, 50.0) if s > 1 else (0.02, 1.0)
    for _ in range(200):
        k = (lo + hi) / 2
        t = sum(x ** k for x in q)
        if abs(t - 1) < tol:
            break
        if (t > 1) == (s > 1):
            lo = k
        else:
            hi = k
    out = [x ** k for x in q]
    z = sum(out)
    return [x / z for x in out]


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def expit(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def pool(ours: float, market: float, w: float) -> float:
    """Log-odds pool of our fair with the market's devigged fair: w = weight on ours (docs/bayesian_methods.md)."""
    return expit(w * logit(ours) + (1 - w) * logit(market))
