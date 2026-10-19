#!/usr/bin/env python3
"""Historical absences from ASA minutes (CLAUDE.md section 14, step 1): for every MLS team-game 2013-2026, which regulars did not
play and what they are worth in goals.

Regular: a player whose share of the club's minutes over the club's trailing 10 league games is at least `share_min` (0.5).
Roster rule: for the club's first five games of a season a trailing regular counts only once he has appeared for the club that
season within the next five games (an off-season departure is not an absence); later, a departed regular fades out of the
window within five games (accepted, noted).
Absent: did not start, judged pre-match: 0 minutes = fully absent; under 60 minutes = partly (1 - minutes/60, a late sub was
not fit to start); 60 minutes or more = present (a starter subbed off is an in-game event, not a pre-match absence).
Value: goals added (raw) per 96 minutes over the trailing 365 days of league games, shrunk toward the club's minutes-weighted
mean rate with `m0` pseudo-minutes, minus the league replacement rate (minutes-weighted rate of non-regulars over the previous
season). Goalkeepers (their own file; shot-stopping g+ is noisy: regular keepers spread 0.15 goals per 96 within a season) are
shrunk toward the league keeper mean with `m0_gk` pseudo-minutes, and the backup-keeper replacement rate (a few thousand
minutes a season) is itself shrunk toward the league keeper mean with 5000 pseudo-minutes. Walk-forward: every number for a
game uses games strictly before it (replacement and league-keeper rates use the previous season).
Missing value of a team-game = sum over absent regulars of value x absent fraction, in goals.

Outputs: data/public/asa_gplus/absences.csv (one row per team-game), absence_players.csv (one row per absent regular).
Usage: python3 scripts/absences.py build [--share-min 0.5] [--m0 900]
       python3 scripts/absences.py report      (distribution, sanity checks -> outputs/calibration/absences.md)"""
from __future__ import annotations
import argparse, json, os, sys, unicodedata
from collections import defaultdict, deque
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim.teams import ROOT, canon, UnknownTeam

PUB = os.path.join(ROOT, "data", "public", "asa_gplus")
RAW = os.path.join(PUB, "raw")
OUT_TEAM = os.path.join(PUB, "absences.csv")
OUT_PLAYERS = os.path.join(PUB, "absence_players.csv")
GAME_MIN = 96.0
SEASONS = list(range(2013, 2027))


def _canon(name: str) -> str | None:
    try:
        return canon(name, historical=True)
    except UnknownTeam:
        return None


def load_player_games(seasons=SEASONS) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Every player appearance (season, game_id, date, team, opp, home, player_id, minutes, gplus, gk) for regular-season MLS games,
    plus the games frame (season, game_id, date, home, away, game_minutes) and the player-name directory."""
    teams = {t["team_id"]: t["team_name"] for t in json.load(open(os.path.join(RAW, "teams.json")))}
    names = {p["player_id"]: p.get("player_name", "") for p in json.load(open(os.path.join(RAW, "players.json")))}
    rows = []; games = []
    for y in seasons:
        gp = os.path.join(RAW, f"games_{y}.json"); pp = os.path.join(RAW, f"players_{y}.json"); kp = os.path.join(RAW, f"goalkeepers_{y}.json")
        if not all(os.path.exists(p) and os.path.getsize(p) > 100 for p in (gp, pp, kp)):
            print(f"absences: season {y} raw files missing, skipped", file=sys.stderr); continue
        gl = {}
        for g in json.load(open(gp)):
            if g.get("knockout_game") or int(g.get("matchday") or 0) <= 0 or g.get("status") != "FullTime":
                continue
            h, a = _canon(teams.get(g["home_team_id"], "")), _canon(teams.get(g["away_team_id"], ""))
            if h is None or a is None:
                continue
            d = str((pd.Timestamp(g["date_time_utc"].replace(" UTC", "")) - pd.Timedelta(hours=4)).date())
            gl[g["game_id"]] = {"season": y, "game_id": g["game_id"], "date": d, "home": h, "away": a, "home_id": g["home_team_id"], "away_id": g["away_team_id"]}
        per = []
        for is_gk, path in ((False, pp), (True, kp)):
            for r in json.load(open(path)):
                g = gl.get(r["game_id"])
                if g is None:
                    continue
                side = "home" if r["team_id"] == g["home_id"] else ("away" if r["team_id"] == g["away_id"] else None)
                if side is None:
                    continue
                v = sum(float(x.get("goals_added_raw") or 0.0) for x in r.get("data", []))
                per.append((y, r["game_id"], g["date"], g[side], g["away" if side == "home" else "home"], side == "home", r["player_id"], float(r.get("minutes_played") or 0), v, is_gk, r.get("general_position", "GK")))
        rows += per
        games += list(gl.values())
    pg = pd.DataFrame(rows, columns=["season", "game_id", "date", "team", "opp", "home", "player_id", "minutes", "gplus", "gk", "pos"])
    gm = pd.DataFrame(games)
    if len(pg):
        gmin = pg.groupby(["game_id", "team"])["minutes"].max().rename("game_minutes").reset_index()
        pg = pg.merge(gmin, on=["game_id", "team"], how="left")
        pg["game_minutes"] = pg["game_minutes"].clip(lower=90.0)
    return pg, gm, names


def replacement_rates(pg: pd.DataFrame, share_min: float) -> dict:
    """{(season, gk): league replacement rate (g+ per minute)}: minutes-weighted rate of non-regulars over the PREVIOUS season
    (the first season uses itself). Non-regular here: a player with under `share_min` of his club's minutes over that season."""
    out = {}
    seasons = sorted(pg["season"].unique())
    by = {}
    for (y, gk), g in pg.groupby(["season", "gk"]):
        team_min = g.groupby("team")["game_minutes"].sum() / 1.0  # each row carries the team-game length; summing over players overcounts: use per team-game
        tg = g.drop_duplicates(["game_id", "team"]).groupby("team")["game_minutes"].sum()
        pm = g.groupby(["team", "player_id"]).agg(minutes=("minutes", "sum"), gplus=("gplus", "sum")).reset_index()
        pm["share"] = pm["minutes"] / pm["team"].map(tg)
        bench = pm[pm["share"] < share_min]
        league = float(g["gplus"].sum() / max(1.0, g["minutes"].sum()))
        rate = float((bench["gplus"].sum() + 5000.0 * league) / (bench["minutes"].sum() + 5000.0)) if len(bench) else league
        by[(y, gk)] = (rate, league)
    for y in seasons:
        for gk in (False, True):
            prev = [s for s in seasons if s < y]
            out[(y, gk)] = by.get((prev[-1], gk), by.get((y, gk), (0.0, 0.0))) if prev else by.get((y, gk), (0.0, 0.0))
    return out  # (season, gk) -> (replacement rate, league mean rate), g+ per minute


def build(share_min: float = 0.5, m0: float = 900.0, window: int = 10, value_days: int = 365, roster_look: int = 5, m0_gk: float = 3000.0, present_min: float = 60.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    pg, gm, names = load_player_games()
    repl = replacement_rates(pg, share_min)
    pg = pg.sort_values(["date", "game_id"]).reset_index(drop=True)
    # per-player trailing-365-day sums: cumulative arrays by player (dates sorted); per-club trailing window of the last `window` games
    by_player = {pid: g[["date", "minutes", "gplus"]].to_numpy() for pid, g in pg.groupby("player_id")}
    p_dates = {pid: np.array(v[:, 0], dtype="datetime64[D]") for pid, v in by_player.items()}
    p_cum = {pid: (np.concatenate([[0.0], np.cumsum(v[:, 1].astype(float))]), np.concatenate([[0.0], np.cumsum(v[:, 2].astype(float))])) for pid, v in by_player.items()}
    pname = {pid: names.get(pid, pid) for pid in by_player}
    is_gk = pg.groupby("player_id")["gk"].max().to_dict()
    # first-season appearance index per (team, season, player): games (ordinal within the team's season) in which he appeared
    team_games = {}  # team -> list of (date, game_id, season, opp, home, game_minutes, {player: minutes})
    for (team, gid), g in pg.groupby(["team", "game_id"], sort=False):
        r0 = g.iloc[0]
        team_games.setdefault(team, []).append((r0["date"], gid, int(r0["season"]), r0["opp"], bool(r0["home"]), float(r0["game_minutes"]), dict(zip(g["player_id"], g["minutes"].astype(float)))))
    for t in team_games:
        team_games[t].sort(key=lambda x: (x[0], x[1]))

    def trailing(pid: str, d: np.datetime64) -> tuple[float, float]:
        """(minutes, g+) of the player over [d - value_days, d), games strictly before d."""
        ds = p_dates[pid]; cm, cg = p_cum[pid]
        hi = int(np.searchsorted(ds, d, side="left")); lo = int(np.searchsorted(ds, d - np.timedelta64(value_days, "D"), side="left"))
        return cm[hi] - cm[lo], cg[hi] - cg[lo]

    team_rows = []; player_rows = []
    for team, gl in team_games.items():
        win = deque()  # the club's last `window` games: (season, game_minutes, {player: minutes})
        season_app = defaultdict(dict)   # season -> player -> ordinal of first appearance for this club
        season_ord = defaultdict(int)
        for k, (date, gid, season, opp, home, gmin, mins) in enumerate(gl):
            season_ord[season] += 1; ordn = season_ord[season]
            for pid in mins:
                if mins[pid] > 0 and pid not in season_app[season]:
                    season_app[season][pid] = ordn
            d = np.datetime64(date)
            n_win = len(win); mv = 0.0; n_reg = 0; n_abs = 0; absent = []
            if n_win >= 3:
                tot_min = sum(w[1] for w in win)
                pmin = defaultdict(float)
                for w in win:
                    for pid, m in w[2].items():
                        pmin[pid] += m
                # club prior: minutes-weighted g+ rate of everyone who played in the window, from their trailing-365 totals
                club_m = club_g = 0.0; rates = {}
                for pid in pmin:
                    m, gv = trailing(pid, d); rates[pid] = (m, gv)
                    if not is_gk.get(pid, False):
                        club_m += m; club_g += gv
                for pid, m_w in pmin.items():
                    share = m_w / tot_min if tot_min > 0 else 0.0
                    if share < share_min:
                        continue
                    gk = bool(is_gk.get(pid, False))
                    # roster rule at the season start: the player must appear for the club in this season by game ordn + roster_look
                    first = season_app[season].get(pid)
                    if first is None or first > ordn + roster_look:
                        # not yet appeared this season: look ahead within the club's next games of this season
                        ahead = [g for g in gl[k + 1:k + 1 + roster_look] if g[2] == season and g[6].get(pid, 0) > 0]
                        if ordn <= roster_look and not ahead and first is None:
                            continue  # off-season departure
                    n_reg += 1
                    played = mins.get(pid, 0.0)
                    frac = max(0.0, 1.0 - played / present_min)
                    if frac < 0.05:
                        continue
                    m, gv = rates[pid]
                    repl_rate, league_rate = repl.get((season, gk), (0.0, 0.0))
                    if gk:
                        rate = (gv + m0_gk * league_rate) / (m + m0_gk)
                    else:
                        prior = club_g / club_m if club_m > 0 else 0.0
                        rate = (gv + m0 * prior) / (m + m0)
                    value = GAME_MIN * (rate - repl_rate)
                    mv += value * frac; n_abs += int(frac >= 0.5)
                    absent.append((pid, value, frac, played, share, m))
            team_rows.append({"season": season, "date": date, "game_id": gid, "team": team, "opp": opp, "home": int(home), "mv": round(mv, 4), "n_regular": n_reg, "n_absent": n_abs,
                              "early": int(n_win < 3), "game_ordinal": ordn, "absent": "; ".join(f"{pname[p]} {v:+.2f}x{f:.2f}" for p, v, f, *_ in sorted(absent, key=lambda x: -x[1] * x[2])[:4])})
            for pid, value, frac, played, share, m in absent:
                player_rows.append({"season": season, "date": date, "game_id": gid, "team": team, "opp": opp, "home": int(home), "player_id": pid, "player": pname[pid], "gk": int(bool(is_gk.get(pid, False))),
                                    "value_per96": round(value, 4), "absent_frac": round(frac, 3), "minutes": played, "share_trailing10": round(share, 3), "minutes_365": m})
            win.append((season, gmin, mins))
            if len(win) > window:
                win.popleft()
    tm = pd.DataFrame(team_rows).sort_values(["date", "team"]).reset_index(drop=True)
    pl = pd.DataFrame(player_rows).sort_values(["date", "team"]).reset_index(drop=True)
    return tm, pl


def match_frame(tm: pd.DataFrame) -> pd.DataFrame:
    """One row per match: (season, date, home, away, mv_home, mv_away, early) from the team rows."""
    h = tm[tm["home"] == 1][["season", "date", "game_id", "team", "opp", "mv", "early", "n_absent", "absent"]].rename(columns={"team": "home", "opp": "away", "mv": "mv_home", "early": "early_h", "n_absent": "n_abs_h", "absent": "absent_h"})
    a = tm[tm["home"] == 0][["game_id", "mv", "early", "n_absent", "absent"]].rename(columns={"mv": "mv_away", "early": "early_a", "n_absent": "n_abs_a", "absent": "absent_a"})
    m = h.merge(a, on="game_id", how="inner")
    m["early"] = ((m["early_h"] + m["early_a"]) > 0).astype(int)
    return m


def load_matches() -> pd.DataFrame:
    tm = pd.read_csv(OUT_TEAM, dtype={"season": str})
    return match_frame(tm)


def report(tm: pd.DataFrame, pl: pd.DataFrame) -> str:
    L = ["# Absence dataset from ASA minutes (scripts/absences.py)", ""]
    L.append(f"team-games {len(tm)} over seasons {tm['season'].min()}-{tm['season'].max()}; absent-regular rows {len(pl)}; share of team-games with no window yet (early) {tm['early'].mean():.3f}")
    ok = tm[tm["early"] == 0]
    L.append(f"missing value (goals), team-games with a window: mean {ok['mv'].mean():.3f}, sd {ok['mv'].std():.3f}, median {ok['mv'].median():.3f}, p90 {ok['mv'].quantile(0.9):.3f}, p99 {ok['mv'].quantile(0.99):.3f}, max {ok['mv'].max():.3f}; share zero {(ok['mv'].abs() < 1e-9).mean():.3f}; regulars per team-game {ok['n_regular'].mean():.1f}, absent regulars {ok['n_absent'].mean():.2f}")
    L.append(f"match-level difference (home mv - away mv): sd {(match_frame(tm).eval('mv_home - mv_away')).std():.3f}")
    L.append("\nby season (mean mv, p90, regulars, absent):")
    for s, g in ok.groupby("season"):
        L.append(f"  {s}: {g['mv'].mean():.3f}, {g['mv'].quantile(0.9):.3f}, {g['n_regular'].mean():.1f}, {g['n_absent'].mean():.2f} (n {len(g)})")
    L.append("\nlargest single-player absences (value per 96 x absent fraction), top 25:")
    pl = pl.assign(cost=pl["value_per96"] * pl["absent_frac"])
    for r in pl.sort_values("cost", ascending=False).head(25).itertuples(index=False):
        L.append(f"  {r.date} {r.team} v {r.opp}: {r.player} {r.cost:+.3f} (value {r.value_per96:+.2f}/96, absent {r.absent_frac:.2f}, share {r.share_trailing10:.2f}, {int(r.minutes_365)} min in 365d)")
    L.append("\nmost valuable players by season (value per 96 at their last absence of the season), top 3 per season from 2020:")
    for s, g in pl[pl["season"].astype(int) >= 2020].groupby("season"):
        top = g.sort_values("date").groupby("player_id").last().sort_values("value_per96", ascending=False).head(3)
        L.append(f"  {s}: " + ", ".join(f"{r.player} ({r.team}) {r.value_per96:+.2f}" for r in top.itertuples()))
    L.append("\nplayers absent most often (games missed as a regular, fully absent), top 10:")
    for p, g in sorted(pl[pl["absent_frac"] >= 0.5].groupby("player"), key=lambda x: -len(x[1]))[:10]:
        L.append(f"  {p}: {len(g)} games, mean value {g['value_per96'].mean():+.2f}")
    L.append("\nteam-games with the largest missing value, top 15:")
    for r in ok.sort_values("mv", ascending=False).head(15).itertuples(index=False):
        L.append(f"  {r.date} {r.team} v {r.opp}: {r.mv:+.2f} [{r.absent}]")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stage", choices=["build", "report"]); ap.add_argument("--share-min", type=float, default=0.5); ap.add_argument("--m0", type=float, default=900.0); ap.add_argument("--m0-gk", type=float, default=3000.0)
    a = ap.parse_args()
    if a.stage == "build":
        tm, pl = build(a.share_min, a.m0, m0_gk=a.m0_gk)
        tm.to_csv(OUT_TEAM, index=False); pl.to_csv(OUT_PLAYERS, index=False)
        print(f"absences: {len(tm)} team-games, {len(pl)} absent-regular rows -> {OUT_TEAM}")
    tm = pd.read_csv(OUT_TEAM, dtype={"season": str}); pl = pd.read_csv(OUT_PLAYERS, dtype={"season": str})
    txt = report(tm, pl); print(txt)
    os.makedirs(os.path.join(ROOT, "outputs", "calibration"), exist_ok=True)
    open(os.path.join(ROOT, "outputs", "calibration", "absences.md"), "w").write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
