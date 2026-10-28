#!/usr/bin/env python3
"""Tests: determinism, devig, tiebreakers, playoff bracket, injury absorption, totals, shade, ratings fit recovery.
Synthetic inputs only; nothing here reads data/. Run: python3 tests/run_tests.py"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim.devig import power_devig, american_to_decimal, decimal_to_american, hold
from sim.engine import score_grid, hda_from_grid, margin_dist, ah_home_fair, total_over_fair, margin_from_three_way, margin_from_ah, total_from_ou, sample_goals, goal_means
from sim.standings import rank_table, rank_single
from sim.season import SeasonInputs, Fixture, run_seasons, empty_played
from sim.markets import Archive, all_markets, shade_pool
from sim.playoffs import STAGE
from sim.layers import absence_penalty, absorption_share
from sim.ratings import wls_fit, gd_fit_row, half_life_weights, blend, apply_expansion_prior
from sim.teams import teams, conference_of, canon
from sim.knobs import load_config, knobs

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'ok ' if cond else 'FAIL'} {name} {detail}")
    if not cond:
        FAILS.append(name)


def test_devig():
    p = power_devig([2.10, 3.40, 3.60])
    check("devig sums to one", abs(p.sum() - 1) < 1e-9)
    check("devig keeps order", p[0] > p[1] > p[2])
    check("power favourite-longshot: fav gains less than multiplicative", p[2] < (1/3.6)/(1/2.1+1/3.4+1/3.6) + 1e-12)
    check("american round trip", decimal_to_american(american_to_decimal(-150)) == -150 and decimal_to_american(american_to_decimal(+240)) == 240)
    check("hold", abs(hold([1.91, 1.91]) - (2/1.91 - 1)) < 1e-12)
    try:
        power_devig([2.0]); check("one-sided pool rejected", False)
    except ValueError:
        check("one-sided pool rejected", True)


def test_drift_surprise():
    """With drift on, a fixture priced partly off a posted line must not drift its sides on average (surprise vs the dice's g)."""
    kn = knobs(load_config()); kn = dict(kn); kn["drift_k_sim"] = 0.05; kn["rating_sd"] = 0.0; kn["drift_cap"] = 1.0
    T = ["A", "B", "C", "D"]; conf = np.array([0, 0, 1, 1])
    fx = [Fixture(0, 1, "2026-05-01", adj=0.4, s=0.6, g_pinn=1.5, T=3.0)] * 1
    out = run_seasons(SeasonInputs(T, conf, np.zeros(4), fx, empty_played(4)), kn, n_seasons=200000, seed=5)
    fr = out["final_ratings_mean"]
    check("drift mean surprise zero on a shrunk fixture", abs(fr[0]) < 0.01 and abs(fr[1]) < 0.01, f"{fr[0]:+.4f} {fr[1]:+.4f}")


def test_h2h():
    """Head-to-head step: three clubs level on points, wins, gd, gf; h2h decides before disciplinary points; a circular h2h falls through."""
    conf = np.array([0, 0, 0, 1]); z = np.zeros((1, 4), int)
    pts = np.array([[50, 50, 50, 40]]); w = np.array([[15, 15, 15, 10]]); gd = np.array([[10, 10, 10, 0]]); gf = np.array([[40, 40, 40, 30]]); disc = np.array([[100, 50, 10, 5]])
    hp = np.zeros((1, 4, 4), np.int8); hg = np.zeros((1, 4, 4), np.int8); hp[0, 0, 1] = 3; hp[0, 0, 2] = 3; hp[0, 1, 2] = 3
    o, _, _ = rank_table(pts, w, gd, gf, disc, z, z, z, z, z, conf, hp, hg); check("h2h decides a three-way tie", list(o[0]) == [0, 1, 2, 3], str(o[0]))
    o, _, _ = rank_table(pts, w, gd, gf, disc, z, z, z, z, z, conf, None, None); check("without h2h disc decides", list(o[0]) == [2, 1, 0, 3], str(o[0]))
    hp[:] = 0; hp[0, 0, 1] = 3; hp[0, 1, 2] = 3; hp[0, 2, 0] = 3
    o, _, _ = rank_table(pts, w, gd, gf, disc, z, z, z, z, z, conf, hp, hg); check("circular h2h falls to disc", list(o[0]) == [2, 1, 0, 3], str(o[0]))


def test_engine():
    P = score_grid(0.4, 3.1, 0.15, 0.15)
    md = margin_dist(P)
    check("E[margin] equals g", abs(sum(m * p for m, p in md.items()) - 0.4) < 1e-3)
    h, d, a = hda_from_grid(P)
    g = margin_from_three_way(h, a, 3.1, 0.15, 0.15); check("3-way inversion recovers g", abs(g - 0.4) < 1e-6, f"{g:.5f}")
    for L in (-0.5, -0.25, 0.0, 0.25, -1.0, -0.75):
        g2 = margin_from_ah(ah_home_fair(P, L), L, 3.1, 0.15, 0.15); check(f"AH {L:+.2f} inversion", abs(g2 - 0.4) < 1e-5, f"{g2:.5f}")
    T = total_from_ou(total_over_fair(P, 2.75), 2.75, 0.4, 0.15, 0.15); check("total inversion", abs(T - 3.1) < 1e-5, f"{T:.5f}")
    check("quarter line between neighbours", ah_home_fair(P, -0.5) < ah_home_fair(P, -0.25) < ah_home_fair(P, 0.0))
    rng = np.random.default_rng(3)
    xh, xa = sample_goals(rng, np.full(400000, 0.4), np.full(400000, 3.1), 0.15, 0.15)
    check("sampled means", abs(xh.mean() - 1.75) < 0.01 and abs(xa.mean() - 1.35) < 0.01, f"{xh.mean():.3f} {xa.mean():.3f}")
    check("sampled total", abs((xh + xa).mean() - 3.1) < 0.01)
    check("shared goals -> positive correlation", np.corrcoef(xh, xa)[0, 1] > 0.05)
    check("sampled draw rate matches grid", abs((xh == xa).mean() - d) < 0.004, f"{(xh==xa).mean():.4f} vs {d:.4f}")
    mh, ma, c = goal_means(3.0, 3.0, 0.15, 0.15); check("floor respected", ma >= 0.15 and c >= 0)
    Pd = score_grid(0.4, 3.1, 0.15, 0.15, rho=-0.05); xh, xa = sample_goals(np.random.default_rng(4), np.full(400000, 0.4), np.full(400000, 3.1), 0.15, 0.15, -0.05)
    check("dixon-coles grid adds draws", np.trace(Pd) > d + 0.005, f"{np.trace(Pd):.4f} vs {d:.4f}")
    check("dixon-coles sampler matches its grid", abs((xh == xa).mean() - np.trace(Pd)) < 0.004 and abs(((xh == 0) & (xa == 0)).mean() - Pd[0, 0]) < 0.003, f"{(xh == xa).mean():.4f} vs {np.trace(Pd):.4f}")
    check("rho 0 reproduces the base grid", np.allclose(score_grid(0.4, 3.1, 0.15, 0.15, rho=0.0), P))
    # gd_fit from a line
    r = gd_fit_row(1.95, 3.6, 4.0, -0.5, 1.98, 1.92, 2.75, 1.9, 1.95, 3.0, 0.15, 0.15)
    check("gd_fit prefers AH", abs(r["gd_fit"] - r["gd_ah"]) < 1e-12 and np.isfinite(r["gd_3way"]))
    check("gd_fit 3way and AH agree roughly", abs(r["gd_ah"] - r["gd_3way"]) < 0.25, f"{r['gd_ah']:.3f} vs {r['gd_3way']:.3f}")


def test_paired_sampling():
    """2026-10-28: one uniform per draw, inverted through the Poisson cdf, with the Dixon-Coles redraws on a second
    stream: a +0.01 nudge to every margin keeps about 99% of scorelines on one seed (was ~89%: data-dependent redraws)."""
    g = np.random.default_rng(0).normal(0, 0.5, 100000); T = np.full(100000, 3.2)
    a = sample_goals(np.random.default_rng(7), g, T, 0.15, 0.1, -0.05, np.random.default_rng(8))
    b = sample_goals(np.random.default_rng(7), g + 0.01, T, 0.15, 0.1, -0.05, np.random.default_rng(8))
    same = float(((a[0] == b[0]) & (a[1] == b[1])).mean())
    check("paired sampling: +0.01 keeps the scorelines", same >= 0.97, f"{same:.3f}")
    same0 = float(((a[0] == sample_goals(np.random.default_rng(7), g, T, 0.15, 0.1, -0.05, np.random.default_rng(8))[0])).mean())
    check("paired sampling: same inputs, same dice", same0 == 1.0, f"{same0:.3f}")


def test_tiebreakers():
    pts = np.array([[50, 50, 50, 50]]); wins = np.array([[14, 15, 15, 15]]); gd = np.array([[10, 5, 5, 5]]); gf = np.array([[40, 41, 40, 41]])
    disc = np.array([[0, 0, 0, 30]]); z = np.zeros((1, 4)); coin = np.zeros((1, 4))
    order, lp, cs = rank_table(pts, wins, gd, gf, disc, z, z, z, z, coin, np.array([0, 0, 1, 1]))
    check("chain: wins > gd > gf > disc", list(order[0]) == [1, 3, 2, 0], str(order[0]))
    check("conference seeds", list(cs[0]) == [2, 1, 2, 1], str(cs[0]))
    # away gd breaks a full tie
    agd = np.array([[0, 3, 0, 0]])
    order, _, _ = rank_table(pts, np.full((1,4),15), np.full((1,4),5), np.full((1,4),40), z, agd, z, z, z, coin, np.array([0, 0, 1, 1]))
    check("away gd tiebreak", order[0][0] == 1)
    rows = rank_single([{"team": "A", "points": 60, "wins": 18, "gd": 20, "gf": 50}, {"team": "B", "points": 60, "wins": 19, "gd": 10, "gf": 50}], {"A": "East", "B": "West"})
    check("rank_single wins before gd", rows[0]["team"] == "B")
    # head-to-head is decided within a conference even when a club of the other conference is level too (fixed 2026-10-19)
    lvl = lambda v: np.array([v], dtype=np.int64); z3 = lvl([0, 0, 0])
    h2p = np.zeros((1, 3, 3), np.int64); h2p[0, 0, 1] = 3; h2g = np.zeros((1, 3, 3), np.int64); h2g[0, 0, 1] = 1; h2g[0, 1, 0] = -1
    _, _, cs3 = rank_table(lvl([50, 50, 50]), lvl([14, 14, 14]), lvl([10, 10, 10]), lvl([40, 40, 40]), lvl([60, 40, 50]), z3, z3, z3, z3, lvl([1, 2, 3]), np.array([0, 0, 1]), h2p, h2g)
    check("head-to-head within a conference with a level club in the other", list(cs3[0][:2]) == [1, 2], str(cs3[0]))
    _, lp3, _ = rank_table(lvl([50, 50, 50]), lvl([14, 14, 14]), lvl([10, 10, 10]), lvl([40, 40, 40]), lvl([60, 40, 10]), z3, z3, z3, z3, lvl([1, 2, 3]), np.array([0, 0, 1]), h2p, h2g)
    check("league table ignores head-to-head (fewest disciplinary points leads)", list(lp3[0]) == [3, 2, 1], str(lp3[0]))


def _synthetic(n_fix=4, seed=0):
    T = teams(); cm = conference_of(); conf = np.array([0 if cm[t] == "East" else 1 for t in T])
    rng = np.random.default_rng(seed)
    R = rng.normal(0, 0.3, 30); R -= R.mean()
    fx = []
    for r in range(n_fix):
        perm = rng.permutation(30)
        for i in range(0, 30, 2):
            fx.append(Fixture(int(perm[i]), int(perm[i + 1]), f"2026-10-{15 + r:02d}", adj=0.35, T=3.0))
    pl = empty_played(30); pl["points"] += rng.integers(30, 60, 30); pl["wins"] += 10; pl["gd"] += rng.integers(-15, 20, 30); pl["gf"] += 40
    return T, conf, R, fx, pl


def test_season():
    kn = knobs(load_config())
    T, conf, R, fx, pl = _synthetic()
    inp = SeasonInputs(T, conf, R, fx, pl)
    t0 = time.time(); o1 = run_seasons(inp, kn, n_seasons=20000, seed=7); o2 = run_seasons(inp, kn, n_seasons=20000, seed=7); dt_ = time.time() - t0
    check("determinism", all(np.array_equal(o1[k], o2[k]) for k in ("points", "league_pos", "conf_seed", "stage")), f"({dt_/2:.1f}s per 20k)")
    st, cs, lp = o1["stage"], o1["conf_seed"], o1["league_pos"]
    check("one cup winner per season", ((st == STAGE["cup_winner"]).sum(axis=1) == 1).all())
    check("two finalists", ((st >= STAGE["cup_final"]).sum(axis=1) == 2).all())
    check("finalists from different conferences", (conf[np.argmax(st == STAGE["cup_final"], axis=1)] != conf[np.argmax(st == STAGE["cup_winner"], axis=1)]).all())
    check("18 playoff teams", ((st >= 1).sum(axis=1) == 18).all())
    check("playoff set is top nine", (((cs <= 9)) == (st >= 1)).all())
    check("wild card losers are seeds 8/9", ((st == 1) <= ((cs == 8) | (cs == 9))).all())
    check("four round-one losers per conference", (((st == 2) & (conf[None, :] == 0)).sum(axis=1) == 4).all())
    check("league positions are a permutation", (np.sort(lp, axis=1) == np.arange(1, 31)).all())
    check("conference seeds are permutations", all((np.sort(cs[:, conf == c], axis=1) == np.arange(1, 16)).all() for c in (0, 1)))
    arc = Archive(o1); m = all_markets(arc)
    for pool, size in (("shield", 1), ("cup", 1), ("east", 1), ("west", 1), ("playoffs", 18), ("cup_finalist", 2), ("spoon", 1), ("conf_top4", 8), ("conf_semi", 8), ("conf_final", 4)):
        s = sum(v["prob_raw"] for v in m[pool].values()); check(f"pool {pool} sums to {size}", abs(s - size) < 1e-9, f"{s:.4f}")
    # points locked in: a team with every fixture played keeps its points exactly
    T2, conf2, R2, fx2, pl2 = _synthetic(n_fix=0)
    o3 = run_seasons(SeasonInputs(T2, conf2, R2, fx2, pl2), kn, n_seasons=200, seed=1)
    check("real results locked in", (o3["points"] == pl2["points"][None, :]).all())
    # higher rating -> higher title chance
    strong = np.zeros(30); strong[0] = 1.5; strong -= strong.mean()
    T3, conf3, R3, fx3, pl3 = _synthetic(n_fix=12)
    o4 = run_seasons(SeasonInputs(T3, conf3, strong, fx3, empty_played(30)), kn, n_seasons=5000, seed=2)
    p_str = (o4["league_pos"][:, 0] == 1).mean()
    check("strong team wins shield most", p_str > 0.5 and p_str == max((o4["league_pos"] == 1).mean(axis=0)), f"{p_str:.2f}")
    # scenario: points deduction lowers expected points by about prob x mean
    sc = [{"team_idx": 3, "type": "points", "prob": 1.0, "mean": 6, "sd": 0, "min": 0}]
    o5 = run_seasons(SeasonInputs(T, conf, R, fx, pl, scenarios=sc), kn, n_seasons=5000, seed=7)
    o6 = run_seasons(SeasonInputs(T, conf, R, fx, pl), kn, n_seasons=5000, seed=7)
    check("points scenario deducts", abs((o6["points"][:, 3].mean() - o5["points"][:, 3].mean()) - 6) < 0.01)
    # best-of-three favours the higher seed more than one game would
    from sim.playoffs import best_of_three, knockout
    rng = np.random.default_rng(5); Rr = np.zeros((100000, 2)); Rr[:, 0] = 0.3
    hi = np.zeros(100000, int); lo = np.ones(100000, int)
    p_home = knockout(rng, Rr, hi, lo, 0.35, 3.0, 0.15, 0.15).mean(); p_neutral = knockout(rng, Rr, hi, lo, 0.0, 3.0, 0.15, 0.15).mean()
    p3 = best_of_three(rng, Rr, hi, lo, 0.35, 3.0, 0.15, 0.15).mean()
    check("best-of-three beats a neutral single game for the favourite", p3 > p_neutral and abs(p3 - p_home) < 0.03, f"neutral {p_neutral:.3f} home {p_home:.3f} series {p3:.3f}")
    # extra time (semis, finals, the Cup): a level game plays 30 minutes at a third of the means before the coin, so the favourite
    # wins more than under the coin alone; a level pair stays even
    p_et = knockout(np.random.default_rng(5), Rr, hi, lo, 0.35, 3.0, 0.15, 0.15, extra_time=True).mean()
    Re = np.zeros((100000, 2)); p_even = knockout(np.random.default_rng(6), Re, hi, lo, 0.0, 3.0, 0.15, 0.15, extra_time=True).mean()
    check("extra time favours the stronger side", 0.005 < p_et - p_home < 0.04 and abs(p_even - 0.5) < 0.01, f"coin {p_home:.3f} extra time {p_et:.3f} even {p_even:.3f}")
    # the host's club home delta and the playoff absence adjustment reach the knockouts (2026-10-27)
    p_delta = knockout(np.random.default_rng(5), Rr, hi, lo, 0.35, 3.0, 0.15, 0.15, club_he=np.array([0.10, 0.0])).mean()
    check("club home delta in a knockout", 0.01 < p_delta - p_home < 0.05, f"{p_home:.3f} -> {p_delta:.3f}")
    T2p = ["A", "B"] + [f"T{i}" for i in range(28)]; conf2p = np.array([0, 0] + [i % 2 for i in range(28)])
    # 15 per conference: A, B and 13 others East; 15 West
    conf2p = np.array([0] * 15 + [1] * 15); Rs = np.zeros(30); Rs[0] = 0.5
    o_a = run_seasons(SeasonInputs(T2p, conf2p, Rs, [], empty_played(30), playoff_adj=np.zeros(30)), kn, n_seasons=4000, seed=3)
    pa = np.zeros(30); pa[0] = -0.4
    o_b = run_seasons(SeasonInputs(T2p, conf2p, Rs, [], empty_played(30), playoff_adj=pa), kn, n_seasons=4000, seed=3)
    # the bracket's absence term: a dated return after the Wild Card counts, an undated short knock does not, an undated long one does
    from sim.factors import LiveFactors
    import pandas as pd
    av = pd.DataFrame([{"team": "A", "out_from": "2026-10-24", "expected_return": "", "cost_per_game": "0.10", "stale": "0", "note": "out Ankle"},
                       {"team": "A", "out_from": "2026-09-01", "expected_return": "", "cost_per_game": "0.05", "stale": "0", "note": "out Knee"},
                       {"team": "A", "out_from": "2026-10-24", "expected_return": "", "cost_per_game": "0.07", "stale": "0", "note": "out Knee (ACL)"},
                       {"team": "A", "out_from": "2026-10-24", "expected_return": "2026-12-01", "cost_per_game": "0.03", "stale": "0", "note": "out"},
                       {"team": "A", "out_from": "2026-10-24", "expected_return": "2026-11-10", "cost_per_game": "0.09", "stale": "0", "note": "out"}])
    sch = pd.DataFrame(columns=["date", "home", "away", "competition"]); res = pd.DataFrame(columns=["date", "home", "away", "competition"])
    LFt = LiveFactors("2026-10-27", sch, res, ["A", "B"], {"A": "East", "B": "West"}, 9, absence_values=av)
    pm = LFt.playoff_mv("A", "2026-11-18")
    check("bracket absences: dated-after and long-term undated rows only", abs(pm - (0.05 + 0.07 + 0.03)) < 1e-9, f"{pm:.3f} (want 0.150)")
    check("bracket absences: the regular season still counts the undated knock", abs(LFt.mv("A", "2026-10-28") - 0.34) < 1e-9, f"{LFt.mv('A', '2026-10-28'):.3f}")
    check("playoff absence adjustment lowers the club's Cup share", (o_b["stage"][:, 0] == 6).mean() < (o_a["stage"][:, 0] == 6).mean() - 0.03, f"{(o_a['stage'][:, 0] == 6).mean():.3f} -> {(o_b['stage'][:, 0] == 6).mean():.3f}")
    # playoff matches at the pair's team total; real playoff results locked into the bracket without moving the dice
    from sim.playoffs import pair_totals, locked_tables
    PT = pair_totals(["A", "B", "C"], {"base": 3.0, "offsets": {"A": 0.5, "B": -0.2, "C": 1.2}}, 3.2)
    check("pair totals: base + both offsets, clipped", abs(PT[0, 1] - 3.3) < 1e-12 and PT[0, 2] == 4.5 and (pair_totals(["A"], {}, 3.2) == 3.2).all())
    lk = locked_tables(2, [(1, 0, 1)])
    check("locked single match", not knockout(np.random.default_rng(1), Rr, hi, lo, 0.35, 3.0, 0.15, 0.15, 0.0, lk[0]).any())
    lk = locked_tables(2, [(0, 1, 1), (1, 0, 1)])
    check("locked series 2-0 to the lower seed", not best_of_three(np.random.default_rng(1), Rr, hi, lo, 0.35, 3.0, 0.15, 0.15, 0.0, lk).any())
    sd = {k: int(np.where((o3["conf_seed"][0] == k) & (conf2 == 0))[0][0]) for k in (1, 8, 9)}
    o3l = run_seasons(SeasonInputs(T2, conf2, R2, fx2, pl2, playoff_results=[(sd[8], sd[9], sd[9]), (sd[1], sd[9], sd[9]), (sd[9], sd[1], sd[9])]), kn, n_seasons=200, seed=1)
    check("real playoff results locked in (9 seed through, 1 seed out in Round One)", (o3l["stage"][:, sd[9]] >= STAGE["conf_semi"]).all() and (o3l["stage"][:, sd[1]] == STAGE["round_one"]).all())
    nb = [int(np.where((o3["conf_seed"][0] == k) & (conf2 == 0))[0][0]) for k in (14, 15)]
    o3n = run_seasons(SeasonInputs(T2, conf2, R2, fx2, pl2, playoff_results=[(nb[0], nb[1], nb[0])]), kn, n_seasons=200, seed=1)
    check("a lock outside the bracket changes nothing (the dice are thrown either way)", np.array_equal(o3n["stage"], o3["stage"]))


def test_shade():
    p = np.array([0.4, 0.3, 0.2, 0.08, 0.02])
    s = shade_pool(p, 1.2, 1.0); check("shade keeps pool size", abs(s.sum() - 1) < 1e-9)
    check("shade b>1 cuts longshots", s[-1] < p[-1] and s[0] > p[0])
    ex = np.array([False, True, False, False, False]); s2 = shade_pool(p, 1.2, 1.0, ex); check("exempt keeps raw", abs(s2[1] - 0.3) < 1e-12 and abs(s2.sum() - 1) < 1e-9)
    check("b=1 is identity", np.allclose(shade_pool(p, 1.0, 1.0), p))


def test_layers():
    check("fresh absence costs full value", abs(absence_penalty(0.2, 1.0, True, 0.0) + 0.2) < 1e-12)
    check("absorbed absence costs nothing", abs(absence_penalty(0.2, 1.0, True, 1.0)) < 1e-12)
    check("return bonus", abs(absence_penalty(0.2, 1.0, False, 0.5) - 0.1) < 1e-12)
    check("doubt halves", abs(absence_penalty(0.1, 0.5, True, 0.0) + 0.05) < 1e-12)
    closes = pd.DataFrame({"date": ["2026-09-01", "2026-09-20", "2026-10-05"], "home": ["Inter Miami"] * 3, "away": ["Nashville SC"] * 3})
    s = absorption_share("Inter Miami", pd.Timestamp("2026-09-15").date(), pd.Timestamp("2026-10-12").date(), closes, "2026-10-12", 14)
    w = half_life_weights(closes["date"], "2026-10-12", 14)
    check("absorption share", abs(s - (w[1] + w[2]) / w.sum()) < 1e-9, f"{s:.3f}")


def test_ratings_fit():
    rng = np.random.default_rng(11); n = 30
    true = rng.normal(0, 0.35, n); true -= true.mean(); HE = 0.3
    H = rng.integers(0, n, 3000); A = rng.integers(0, n, 3000); m = H != A; H, A = H[m], A[m]
    y = true[H] - true[A] + HE + rng.normal(0, 0.1, len(H))
    R, he, resid = wls_fit(H, A, y, np.ones(len(H)), n, ridge=0.01)
    check("WLS recovers ratings", np.abs(R - true).max() < 0.03, f"max err {np.abs(R-true).max():.3f}")
    check("WLS recovers home edge", abs(he - HE) < 0.02, f"{he:.3f}")
    R2, he2, _ = wls_fit(H, A, y, np.ones(len(H)), n, ridge=0.01, fit_home_edge=False, home_edge_fixed=HE)
    check("fixed home edge fit", np.abs(R2 - true).max() < 0.03)
    club = rng.normal(0, 0.05, n); club -= club.mean()
    y3 = true[H] - true[A] + HE + club[H] + rng.normal(0, 0.1, len(H))
    R3, _, _ = wls_fit(H, A, y3, np.ones(len(H)), n, ridge=0.01, fit_home_edge=False, home_edge_fixed=HE + club[H])
    check("per-club home edge fit recovers ratings", np.abs(R3 - true).max() < 0.03, f"max err {np.abs(R3-true).max():.3f}")
    src = {"market_recent": true, "xg": np.zeros(n)}
    cfgdf = pd.DataFrame([{"source": "market_recent", "enabled": "y", "weight": 1}, {"source": "xg", "enabled": "y", "weight": 1}])
    b, used = blend(src, cfgdf); check("50/50 blend halves", np.allclose(b, true / 2))
    cfgdf2 = pd.DataFrame([{"source": "market_recent", "enabled": "y", "weight": 1}, {"source": "xg", "enabled": "n", "weight": 1}])
    b2, used2 = blend(src, cfgdf2); check("disabled source ignored", np.allclose(b2, true) and used2 == {"market_recent": 1.0})
    Rp = apply_expansion_prior(true, np.array([0] + [20] * (n - 1)), -0.25, 10, np.array([True] + [False] * (n - 1)))
    check("expansion prior at zero closes", abs((Rp - Rp.mean())[0] - (-0.25 - (-0.25 + true[1:].sum()) / n)) < 1e-9)


def test_kalman():
    """The filter recovers a fixed strength vector from noisy difference measurements, a club with no closes stays wide,
    and posted lines applied to a copy of the state (kalman_states) leave the running state unchanged."""
    from sim.kalman import KalmanRatings
    from scripts.close_track import kalman_states
    rng = np.random.default_rng(3); n = 8; T = [f"T{i}" for i in range(n)]
    true = rng.normal(0, 0.4, n); true -= true.mean()
    rows = []
    d0 = pd.Timestamp("2025-03-01")
    for k in range(600):
        h, a = rng.choice(n, 2, replace=False)
        if 0 in (h, a) and k < 580:  # club 0 plays only late
            continue
        rows.append({"date": (d0 + pd.Timedelta(days=k // 4)).strftime("%Y-%m-%d"), "home": T[h], "away": T[a], "y": true[h] - true[a] + rng.normal(0, 0.2)})
    obs = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    kf = KalmanRatings(T, {"q_day": 0.0, "s": 0.2, "p0": 0.5, "q_off": 0.0, "prior_new": 0.0})
    kf.run(obs, until="2025-07-01")
    R = kf.ratings(T)
    R = R - R[1:].mean() + true[1:].mean()  # club 0 has no closes by July: compare the seven seen clubs on their own level
    check("kalman recovers strengths (q=0)", np.abs(R[1:] - true[1:]).max() < 0.08, f"max err {np.abs(R[1:] - true[1:]).max():.3f}")
    asof = "2025-04-01"
    kf2 = KalmanRatings(T, {"q_day": 0.0, "s": 0.2, "p0": 0.5, "q_off": 0.0, "prior_new": 0.0}); kf2.run(obs, until=asof)
    sds = kf2.sds(T)
    check("unseen club stays wide, seen clubs tight", sds[0] > 0.3 and sds[1:].max() < 0.1, f"sd0 {sds[0]:.3f}, others max {sds[1:].max():.3f}")
    posted = {asof: pd.DataFrame({"home": [T[1]], "away": [T[2]], "y": [true[1] - true[2] + 1.0]})}
    kn = {"q_day": 0.0, "s": 0.2, "p0": 0.5, "q_off": 0.0, "prior_new": 0.0}
    st_plain = kalman_states(obs, T, [asof, "2025-05-01"], kn)
    st_post = kalman_states(obs, T, [asof, "2025-05-01"], kn, posted)
    moved = st_post[asof][0][1] - st_plain[asof][0][1]
    check("posted line moves the state it is applied to", moved > 0.01, f"{moved:.3f}")
    check("posted line is applied to a copy (later state unchanged)", np.allclose(st_post["2025-05-01"][0], st_plain["2025-05-01"][0]))


def test_factors():
    """Netting a constant factor out of every measurement shifts the filter's state by exactly beta x x for the club that carries it,
    and factor_vector follows the sign convention (y - sum beta x; abs beta negative = an absent home regular lowers the close)."""
    from sim.kalman import KalmanRatings
    from sim.factors import factor_vector
    rng = np.random.default_rng(7); n = 6; T = [f"T{i}" for i in range(n)]
    true = rng.normal(0, 0.3, n); true -= true.mean()
    rows = []; d0 = pd.Timestamp("2025-03-01")
    for k in range(400):
        h, a = rng.choice(n, 2, replace=False)
        y = true[h] - true[a] + rng.normal(0, 0.2)
        x = 0.5 if h == 0 else (-0.5 if a == 0 else 0.0)   # club 0 always misses a regular worth 0.5 goals
        rows.append({"date": (d0 + pd.Timedelta(days=k // 3)).strftime("%Y-%m-%d"), "home": T[h], "away": T[a], "y": y + (-0.4) * x, "x": x})
    obs = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    kn = {"q_day": 0.0, "s": 0.2, "p0": 0.5, "q_off": 0.0, "prior_new": 0.0}
    kf = KalmanRatings(T, kn); kf.run(obs[["date", "home", "away", "y"]], until="2025-09-01"); R_raw = kf.ratings(T)
    net = obs.assign(y=obs["y"] - (-0.4) * obs["x"])
    kf2 = KalmanRatings(T, kn); kf2.run(net[["date", "home", "away", "y"]], until="2025-09-01"); R_net = kf2.ratings(T)
    check("netting restores the full-health strength of the club with absences", abs(R_net[0] - true[0]) < 0.06 and (R_raw[0] - true[0]) < -0.12, f"raw {R_raw[0] - true[0]:+.3f}, net {R_net[0] - true[0]:+.3f}")
    check("factor_vector sign convention", abs(factor_vector({"abs": -0.48, "rest": 0.005}, {"abs": 0.5, "rest": 2.0}) - (-0.23)) < 1e-9)


def test_teams():
    check("30 clubs, 15 per conference", len(teams()) == 30 and sum(1 for v in conference_of().values() if v == "East") == 15)
    check("aliases", canon("Los Angeles FC") == "LAFC" and canon("CF Montreal") == "CF Montréal" and canon("St. Louis City SC") == "St. Louis City")


if __name__ == "__main__":
    for t in (test_teams, test_kalman, test_factors, test_devig, test_engine, test_paired_sampling, test_drift_surprise, test_h2h, test_tiebreakers, test_layers, test_ratings_fit, test_shade, test_season):
        print(t.__name__); t()
    print(f"\n{'ALL PASS' if not FAILS else 'FAILED: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)
