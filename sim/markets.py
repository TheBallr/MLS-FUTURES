"""Price every futures market from the season archive. The shade lives here only; prob_raw is always kept."""
from __future__ import annotations
import numpy as np
from .playoffs import STAGE


def _logit(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def shade_pool(p_raw: np.ndarray, b: float, size: float, exempt: np.ndarray | None = None) -> np.ndarray:
    """logit(p') = b logit(p) + c with c solved so the pool keeps its size. Exempt teams keep their raw price."""
    p_raw = np.asarray(p_raw, dtype=float)
    if b is None or abs(b - 1.0) < 1e-12:
        return p_raw.copy()
    ex = np.zeros(len(p_raw), bool) if exempt is None else np.asarray(exempt, bool)
    target = size - p_raw[ex].sum()
    L = _logit(p_raw[~ex])
    lo, hi = -20.0, 20.0
    for _ in range(100):
        c = 0.5 * (lo + hi)
        s = _sig(b * L + c).sum()
        if s > target:
            hi = c
        else:
            lo = c
    out = p_raw.copy()
    out[~ex] = _sig(b * L + 0.5 * (lo + hi))
    return out


class Archive:
    def __init__(self, arc: dict):
        self.teams = [str(t) for t in arc["teams"]]
        self.idx = {t: i for i, t in enumerate(self.teams)}
        self.conf = np.asarray(arc["conf"])
        self.points = np.asarray(arc["points"])
        self.league_pos = np.asarray(arc["league_pos"])
        self.conf_seed = np.asarray(arc["conf_seed"])
        self.stage = np.asarray(arc["stage"])
        self.N = self.points.shape[0]

    # ----- pools (each returns dict team -> prob) -----
    def shield(self):
        return dict(zip(self.teams, (self.league_pos == 1).mean(axis=0)))

    def spoon(self):
        return dict(zip(self.teams, (self.league_pos == len(self.teams)).mean(axis=0)))

    def conference_winner(self):
        return dict(zip(self.teams, (self.conf_seed == 1).mean(axis=0)))

    def bottom_of_conference(self):
        return dict(zip(self.teams, (self.conf_seed == 15).mean(axis=0)))

    def playoffs(self):
        return dict(zip(self.teams, (self.conf_seed <= 9).mean(axis=0)))

    def conf_top(self, n):
        return dict(zip(self.teams, (self.conf_seed <= n).mean(axis=0)))

    def seed_range(self, lo, hi):
        return dict(zip(self.teams, ((self.conf_seed >= lo) & (self.conf_seed <= hi)).mean(axis=0)))

    def position_range(self, lo, hi):
        return dict(zip(self.teams, ((self.league_pos >= lo) & (self.league_pos <= hi)).mean(axis=0)))

    def cup_winner(self):
        return dict(zip(self.teams, (self.stage == STAGE["cup_winner"]).mean(axis=0)))

    def cup_finalist(self):
        return dict(zip(self.teams, (self.stage >= STAGE["cup_final"]).mean(axis=0)))

    def stage_at_least(self, s):
        return dict(zip(self.teams, (self.stage >= s).mean(axis=0)))

    def points_summary(self):
        p = self.points.astype(float)
        return {t: {"mean": float(p[:, i].mean()), "sd": float(p[:, i].std()), "p10": float(np.percentile(p[:, i], 10)),
                    "p50": float(np.median(p[:, i])), "p90": float(np.percentile(p[:, i], 90))} for i, t in enumerate(self.teams)}

    def points_over(self, team, line):
        i = self.idx[team]
        p = self.points[:, i]
        over = (p > line).mean(); under = (p < line).mean(); push = (p == line).mean()
        return {"over": float(over), "under": float(under), "push": float(push), "over_no_push": float(over / (over + under)) if over + under > 0 else 0.5}

    def above(self, a, b):
        return float((self.league_pos[:, self.idx[a]] < self.league_pos[:, self.idx[b]]).mean())

    def best_of(self, group):
        ids = [self.idx[t] for t in group]
        sub = self.league_pos[:, ids]
        best = sub.argmin(axis=1)
        return {t: float((best == j).mean()) for j, t in enumerate(group)}

    def cup_without(self, team):
        i = self.idx[team]
        keep = self.stage[:, i] != STAGE["cup_winner"]
        sub = self.stage[keep]
        return dict(zip(self.teams, (sub == STAGE["cup_winner"]).mean(axis=0)))

    def conditional(self, mask):
        """Return an Archive restricted to seasons where mask (N,) holds."""
        return Archive({"teams": self.teams, "conf": self.conf, "points": self.points[mask], "league_pos": self.league_pos[mask],
                        "conf_seed": self.conf_seed[mask], "stage": self.stage[mask]})


def all_markets(arc: Archive, shade: dict | None = None, exempt: set | None = None) -> dict:
    """Every published pool with prob_raw and prob (shaded where a shade applies)."""
    shade = shade or {}
    exempt = exempt or set()
    teams = arc.teams
    east = arc.conf == 0
    ex = np.array([t in exempt for t in teams])
    out = {}

    def pool(name, raw: dict, mask=None, size=None):
        raw_v = np.array([raw[t] for t in teams])
        m = np.ones(len(teams), bool) if mask is None else mask
        b = shade.get(name)
        shaded = raw_v.copy()
        if b is not None:
            sz = size if size is not None else float(raw_v[m].sum())
            shaded[m] = shade_pool(raw_v[m], b, sz, ex[m])
        out[name] = {t: {"prob_raw": float(raw_v[i]), "prob": float(shaded[i])} for i, t in enumerate(teams) if m[i]}

    pool("shield", arc.shield(), size=1)
    pool("spoon", arc.spoon(), size=1)
    pool("cup", arc.cup_winner(), size=1)
    pool("cup_finalist", arc.cup_finalist(), size=2)
    pool("east", arc.conference_winner(), east, 1)
    pool("west", arc.conference_winner(), ~east, 1)
    pool("east_bottom", arc.bottom_of_conference(), east, 1)
    pool("west_bottom", arc.bottom_of_conference(), ~east, 1)
    pool("playoffs", arc.playoffs(), size=18)
    for n in (2, 4, 7):
        pool(f"conf_top{n}", arc.conf_top(n), size=2 * n)
    pool("conf_semi", arc.stage_at_least(STAGE["conf_semi"]), size=8)      # reaches the conference semifinals (wins Round One or the bye)
    pool("conf_final", arc.stage_at_least(STAGE["conf_final"]), size=4)    # reaches the conference final
    pool("east_final", arc.stage_at_least(STAGE["cup_final"]), east, 1)
    pool("west_final", arc.stage_at_least(STAGE["cup_final"]), ~east, 1)
    out["points"] = arc.points_summary()
    return out
