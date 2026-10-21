#!/usr/bin/env python3
"""Value of today's absences going forward (CLAUDE.md section 14, step 5): every club, every player listed out (data/ratings/injuries.csv
plus the latest OpticOdds injury feed), his value in goals per game (scripts/absences.py: g+ per 96 above replacement, shrunk) weighted
by his regular weight (ramp on the share of the club's minutes over its last ten league games: 0 at 0.3, 1 at 0.6), his return date and the league games
he misses. Writes data/ratings/absence_values.csv (the live sim reads it when `factors_enabled`) and outputs/calibration/absence_values.md.

Name matching: accent-stripped lower-case exact match within the club's ASA roster, then unique surname match. A listed player who has
appeared for the club since his `out_from` and is not in the latest Optic feed is stale (sportsgambler keeps old rows): value 0, flagged.
A doubt / game-time decision counts prob_out 0.5 (Optic "gtd"), "out" and "suspended" 1.0.

Usage: python3 scripts/absence_values.py [--asof 2026-10-19]"""
from __future__ import annotations
import argparse, glob, json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.teams import ROOT, canon
from scripts.absences import values_asof
from scripts.common import today_et

OUT_CSV = os.path.join(ROOT, "data", "ratings", "absence_values.csv")
OUT_MD = os.path.join(ROOT, "outputs", "calibration", "absence_values.md")
COLS = ["team", "player", "asa_player", "value_per96", "share_trailing10", "regular", "status", "prob_out", "out_from", "expected_return", "games_missed", "cost_per_game", "cost_remaining", "stale", "source", "note", "asof"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def optic_listed(asof: str) -> tuple[pd.DataFrame, str | None]:
    """Latest Optic injury feed on or before asof: (team, player, status, type, first_seen) with first_seen = the earliest daily file
    listing that player with that status."""
    files = sorted(glob.glob(os.path.join(ROOT, "data", "optic", "raw", "injuries", "*.json")))
    files = [f for f in files if os.path.basename(f)[:8] <= asof.replace("-", "")]
    # the OpticOdds feed stopped on 2026-10-18 (no key; Zac: do not rely on it): a feed more than two days old is not a current list
    if files:
        last = os.path.basename(files[-1])[:8]
        if (pd.Timestamp(asof) - pd.Timestamp(f"{last[:4]}-{last[4:6]}-{last[6:]}")).days > 2:
            files = []
    if not files:
        return pd.DataFrame(columns=["team", "player", "status", "type", "first_seen"]), None
    first = {}
    for f in files:
        day = os.path.basename(f)[:8]; day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        for r in json.load(open(f)).get("data", []):
            k = (r["team"]["name"], r["player"]["name"])
            first.setdefault(k, day)
    latest = json.load(open(files[-1])).get("data", [])
    rows = []
    for r in latest:
        t = canon(r["team"]["name"], strict=False)
        if t is None:
            continue
        rows.append({"team": t, "player": r["player"]["name"], "status": r["status"], "type": r.get("type", ""), "first_seen": first[(r["team"]["name"], r["player"]["name"])]})
    day = os.path.basename(files[-1])[:8]
    return pd.DataFrame(rows), f"{day[:4]}-{day[4:6]}-{day[6:]}"


def match_name(name: str, roster: pd.DataFrame) -> pd.Series | None:
    n = _norm(name)
    if len(roster) == 0:
        return None
    rn = roster["player"].map(_norm)
    hit = roster[rn == n]
    if len(hit) == 1:
        return hit.iloc[0]
    toks = n.split()
    if toks:
        last = toks[-1]
        hit = roster[rn.map(lambda x: x.split()[-1] if x else "") == last]
        if len(hit) == 1:
            return hit.iloc[0]
        if len(hit) > 1 and len(toks) > 1:
            hit2 = hit[rn[hit.index].map(lambda x: x.split()[0][:1]) == toks[0][:1]]
            if len(hit2) == 1:
                return hit2.iloc[0]
        # any token of the listed name equal to the ASA surname, or the ASA full name contained in the listed one
        hit = roster[rn.map(lambda x: x in n or (x.split()[-1] in toks if x else False))]
        if len(hit) == 1:
            return hit.iloc[0]
    return None


def remaining_games(team: str, asof: str) -> list[str]:
    sched = data.load("schedule"); res = data.load("results")
    played = set(zip(res["date"], res["home"], res["away"]))
    s = sched[(sched["competition"] == "MLS") & ((sched["home"] == team) | (sched["away"] == team))]
    return sorted(d for d, h, a in zip(s["date"], s["home"], s["away"]) if (d, h, a) not in played and d >= asof)


def build(asof: str) -> tuple[pd.DataFrame, list[str]]:
    vals = values_asof(asof)
    inj = data.load("injuries")
    opt, opt_day = optic_listed(asof)
    notes = [f"ASA players with minutes in the last 365 days: {len(vals)}; Optic feed {opt_day or 'none'} lists {len(opt)}; injuries.csv rows {len(inj)}"]
    rows = []; unmatched = []
    seen = set()
    # 1. injuries.csv rows (dated, tiers are Zac's; value here comes from the data, the tier is kept for the record)
    for r in inj.to_dict("records"):
        team = r["team"]; roster = vals[vals["team"] == team]
        m = match_name(r["player"], roster)
        key = (team, _norm(r["player"]))
        seen.add(key)
        if m is not None:
            seen.add((team, _norm(m["player"])))
        status = "doubt" if str(r.get("prob_out", "1")) in ("0.5",) or "doubt" in str(r.get("note", "")).lower() or "gtd" in str(r.get("note", "")).lower() else ("suspension" if "susp" in str(r.get("note", "")).lower() else "out")
        try:
            p = float(r.get("prob_out") or 1.0)
        except ValueError:
            p = 1.0
        o = opt[(opt["team"] == team) & (opt["player"].map(_norm) == _norm(r["player"]))] if len(opt) else opt
        in_optic = len(o) > 0
        if in_optic:
            st = o.iloc[0]["status"]; p = 0.5 if st == "gtd" else 1.0; status = st
        of = str(r.get("out_from", "")); lg = str(m["last_game"]) if m is not None else ""
        # stale: he has played since he was listed (an undated row from the listing day on; a dated row only after it, so a player
        # hurt in the game he was listed on is not cleared by that game) and the live feed does not still list him (2026-10-21)
        stale = int(m is not None and of != "" and not in_optic and (lg > of if str(r.get("expected_return", "")) else lg >= of))
        rows.append(_row(team, r["player"], m, status, p, r.get("out_from", ""), r.get("expected_return", ""), stale, "injuries.csv" + ("+optic" if in_optic else ""), r.get("note", ""), asof))
        if m is None:
            unmatched.append(f"{team}: {r['player']} (injuries.csv)")
    # 2. Optic rows not in injuries.csv
    for r in opt.to_dict("records") if len(opt) else []:
        team = r["team"]; key = (team, _norm(r["player"]))
        if key in seen:
            continue
        roster = vals[vals["team"] == team]; m = match_name(r["player"], roster)
        if m is not None and (team, _norm(m["player"])) in seen:
            continue
        p = 0.5 if r["status"] == "gtd" else 1.0
        rows.append(_row(team, r["player"], m, r["status"], p, r["first_seen"], "", 0, "optic", r.get("type", ""), asof))
        if m is None:
            unmatched.append(f"{team}: {r['player']} (optic)")
    df = pd.DataFrame(rows, columns=COLS)
    # games missed and cost over the rest of the season
    gm = []; cr = []
    for r in df.itertuples(index=False):
        rem = remaining_games(r.team, asof)
        d0 = str(r.out_from) if str(r.out_from) else "0000"; d1 = str(r.expected_return) if str(r.expected_return) else "9999"
        miss = [d for d in rem if d0 <= d < d1]
        gm.append(len(miss)); cr.append(round(float(r.cost_per_game) * len(miss), 3))
    df["games_missed"] = gm; df["cost_remaining"] = cr
    notes.append(f"unmatched to an ASA name ({len(unmatched)}): " + "; ".join(unmatched))
    return df.sort_values(["team", "cost_per_game"], ascending=[True, False]).reset_index(drop=True), notes


def _row(team, player, m, status, p, out_from, ret, stale, source, note, asof) -> dict:
    value = float(m["value_per96"]) if m is not None else 0.0
    share = float(m["share_trailing10"]) if m is not None else 0.0
    regular = float(m["regular"]) if m is not None else 0.0
    cost = 0.0 if stale else round(value * p * regular, 4)
    return {"team": team, "player": player, "asa_player": m["player"] if m is not None else "", "value_per96": round(value, 4), "share_trailing10": share, "regular": regular, "status": status, "prob_out": p,
            "out_from": out_from, "expected_return": ret, "games_missed": 0, "cost_per_game": cost, "cost_remaining": 0.0, "stale": stale, "source": source, "note": note, "asof": asof}


def report(df: pd.DataFrame, notes: list[str], asof: str) -> str:
    L = [f"# Absence values as of {asof} (scripts/absence_values.py)", ""] + notes + [""]
    L.append("Per club: current absence value (goals per game, regulars listed out today x prob_out), cost over the remaining league games, and the players that carry it.")
    L.append("")
    L.append("| club | games left | absence value now (goals/game) | cost rest of season (goals) | players (value/96 x prob, games missed) |")
    L.append("|---|---|---|---|---|")
    for team, g in df.groupby("team"):
        rem = len(remaining_games(team, asof))
        now = g[(g["cost_per_game"] > 0) & (g["games_missed"] > 0)]
        cur = float(now[now["out_from"].astype(str) <= asof]["cost_per_game"].sum())
        tot = float(g["cost_remaining"].sum())
        parts = "; ".join(f"{r.player} {r.value_per96:+.2f}x{r.prob_out:.1f}x{r.regular:.2f}, {r.games_missed}g" + (f" to {r.expected_return}" if str(r.expected_return) else "") for r in now.sort_values("cost_per_game", ascending=False).itertuples(index=False))
        L.append(f"| {team} | {rem} | {cur:.3f} | {tot:.2f} | {parts} |")
    L.append("")
    L.append("Listed players carrying no cost (not a regular: under 30% of the club's minutes over its last ten games; or value at or below replacement) or stale rows (appeared since out_from, not on the Optic feed):")
    low = df[(df["cost_per_game"] <= 0) | (df["stale"] == 1)]
    L.append(", ".join(f"{r.team}: {r.player}" + (" (stale)" if r.stale else "") + (f" [{r.asa_player} share {r.share_trailing10:.2f}, {r.value_per96:+.2f}]" if r.asa_player else " [no ASA match]") for r in low.itertuples(index=False)))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--asof", default=today_et().isoformat()); a = ap.parse_args()
    df, notes = build(a.asof)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True); df.to_csv(OUT_CSV, index=False)
    txt = report(df, notes, a.asof); print(txt)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True); open(OUT_MD, "w").write(txt + "\n")
    print(f"\nabsence_values: {len(df)} rows -> {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
