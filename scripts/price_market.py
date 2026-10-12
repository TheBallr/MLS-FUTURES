#!/usr/bin/env python3
"""Price any market after the fact from outputs/latest/seasons.npz.
  --above A B            P(A finishes above B in the league table)
  --best-of "A,B,C"      best league finish within the group
  --points-over Team L   P(points > L), under, push
  --position Team lo hi  P(league position in [lo, hi])
  --seed Team lo hi      P(conference seed in [lo, hi])
  --conference East top N   P(conference seed <= N) for every team in the conference
  --playoffs Team        P(make playoffs)
  --cup-without Team     MLS Cup pool conditional on Team not winning
  --stage Team           distribution of playoff exit stage
Prices print as probability and fair American odds."""
from __future__ import annotations
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sim.markets import Archive
from sim.playoffs import STAGE_NAME
from sim.devig import prob_to_american
from sim.teams import canon, ROOT, conference_of


def fmt(p):
    if p < 0.0005:
        return f"{p*100:6.2f}%  >+20000"
    if p > 0.9995:
        return f"{p*100:6.2f}%  <-20000"
    return f"{p*100:6.2f}%  {prob_to_american(p):+d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(ROOT, "outputs", "latest", "seasons.npz"))
    ap.add_argument("--above", nargs=2); ap.add_argument("--best-of"); ap.add_argument("--points-over", nargs=2)
    ap.add_argument("--position", nargs=3); ap.add_argument("--seed", nargs=3); ap.add_argument("--conference", nargs=3)
    ap.add_argument("--playoffs"); ap.add_argument("--cup-without"); ap.add_argument("--stage")
    a = ap.parse_args()
    arc = Archive(dict(np.load(a.file, allow_pickle=False)))
    if a.above:
        x, y = canon(a.above[0]), canon(a.above[1]); print(f"{x} above {y}: {fmt(arc.above(x, y))}")
    if a.best_of:
        grp = [canon(t.strip()) for t in a.best_of.split(",")]
        for t, p in sorted(arc.best_of(grp).items(), key=lambda kv: -kv[1]): print(f"best of group {t}: {fmt(p)}")
    if a.points_over:
        t, L = canon(a.points_over[0]), float(a.points_over[1]); r = arc.points_over(t, L)
        print(f"{t} points over {L}: {fmt(r['over'])}  under {fmt(r['under'])}  push {r['push']*100:.2f}%  (no-push over {fmt(r['over_no_push'])})")
    if a.position:
        t, lo, hi = canon(a.position[0]), int(a.position[1]), int(a.position[2]); print(f"{t} league position {lo}-{hi}: {fmt(arc.position_range(lo, hi)[t])}")
    if a.seed:
        t, lo, hi = canon(a.seed[0]), int(a.seed[1]), int(a.seed[2]); print(f"{t} conference seed {lo}-{hi}: {fmt(arc.seed_range(lo, hi)[t])}")
    if a.conference:
        c, _, n = a.conference[0].title(), a.conference[1], int(a.conference[2]); cm = conference_of()
        for t, p in sorted(arc.conf_top(n).items(), key=lambda kv: -kv[1]):
            if cm[t] == c: print(f"{c} top {n} {t}: {fmt(p)}")
    if a.playoffs:
        t = canon(a.playoffs); print(f"{t} make playoffs: {fmt(arc.playoffs()[t])}")
    if a.cup_without:
        t = canon(a.cup_without)
        for k, p in sorted(arc.cup_without(t).items(), key=lambda kv: -kv[1])[:12]: print(f"cup without {t}: {k} {fmt(p)}")
    if a.stage:
        t = canon(a.stage); i = arc.idx[t]
        for s in range(7): print(f"{t} {STAGE_NAME[s]:12s} {((arc.stage[:, i] == s).mean())*100:6.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
