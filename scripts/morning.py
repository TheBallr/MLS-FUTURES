#!/usr/bin/env python3
"""The morning report (Zac 2026-10-19: "monitor how we look across the upcoming games every morning ... a tab that shows each
morning's report"). Runs in weekly.py after site_data.py, every morning; build_site.py embeds the reports (Morning tab).

- Upcoming games: our ratings' own price (built WITHOUT this round's Pinnacle lines, the Games tab's Model) v Pinnacle's posted line,
  the gap in goals of home margin (ours minus Pinnacle), a flag (watch 0.15, big 0.25) and the reasons in plain words: a factor we add
  (eliminated, absences, rest) that the line may not price, Pinnacle's recent closes rating a club away from us, the xG share, a hand
  adjustment, and how the line has moved since it was first posted and since yesterday's report (toward us or away).
- Track record: every played game of the season priced on its match morning without that round's lines (site_data.json "track")
  v the close (margin rmse, bias, home-win gap) and v the results (log-loss, ours v Pinnacle's devigged close): last 7 days, 30, season.
- What's new since the previous report: results and how far we were off, rating moves, futures moves, injury list changes, model changes.
Writes outputs/reports/morning_<date ET>.json (a rerun the same day overwrites it and still compares with the day before) and
outputs/latest/morning.json. Usage: python3 scripts/morning.py"""
from __future__ import annotations
import datetime as dt, glob, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.ratings import gd_fit_row
from sim.teams import ROOT, code_of
from scripts.common import today_et, et_str, parse_utc

LATEST = os.path.join(ROOT, "outputs", "latest")
REPORTS = os.path.join(ROOT, "outputs", "reports")
WATCH, BIG = 0.15, 0.25          # flag thresholds, goals of home margin (the season's typical miss on the close is about 0.24)
POOLS = (("cup", "Win MLS Cup"), ("cup_finalist", "Reach MLS Cup"), ("conf_final", "Reach conf final"), ("playoffs", "Playoffs"), ("east", "East 1st"), ("west", "West 1st"))
r2 = lambda x: None if x is None or not np.isfinite(x) else round(float(x), 2)


def previous_report(today: str) -> dict | None:
    """The newest report from an earlier day (a same-day rerun compares with yesterday, so the morning's "new" list is stable)."""
    files = sorted(f for f in glob.glob(os.path.join(REPORTS, "morning_*.json")) if os.path.basename(f)[8:18] < today)
    return json.load(open(files[-1])) if files else None


def line_paths(kn: dict, codes: dict) -> dict:
    """Pinnacle's posted lines per fixture over time: (date, home, away) -> [(fetched_at, home margin)], oldest first."""
    o = data.load("current_round_odds")
    if len(o) == 0:
        return {}
    o = o[o["book"].str.lower() == "pinnacle"].sort_values("fetched_at")
    out = {}
    for r in o.to_dict("records"):
        try:
            g = gd_fit_row(r.get("h"), r.get("d"), r.get("a"), r.get("ah_line") or None, r.get("ah_home"), r.get("ah_away"), r.get("total_line") or None, r.get("over"), r.get("under"),
                           kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))["gd_fit"]
        except (ValueError, TypeError):
            continue
        if np.isfinite(g):
            out.setdefault((r["date"], r["home"], r["away"]), []).append((str(r["fetched_at"]), float(g)))
    return out


def track_stats(rows: list) -> dict | None:
    """rows: site_data track entries. Margin v the close and log-loss on the results, ours v Pinnacle's devigged close."""
    if not rows:
        return None
    miss = np.array([r[3] - r[4] for r in rows])
    hw = np.array([abs(r[5][0] - r[6][0]) for r in rows])
    ll_o = np.array([-math.log(max(1e-9, r[5][r[7]])) for r in rows]); ll_p = np.array([-math.log(max(1e-9, r[6][r[7]])) for r in rows])
    freq = np.bincount([r[7] for r in rows], minlength=3) / len(rows)   # no-skill reference: the same H/D/A rates for every game
    ll_b = float(np.mean([-math.log(max(1e-9, freq[r[7]])) for r in rows]))
    return {"n": len(rows), "rmse": round(float(np.sqrt(np.mean(miss ** 2))), 3), "bias": round(float(np.mean(miss)), 3),
            "mae": round(float(np.mean(np.abs(miss))), 3), "hw_gap": round(float(np.mean(hw)) * 100, 1), "hw_max": round(float(np.max(hw)) * 100, 1),
            "ll_ours": round(float(np.mean(ll_o)), 4), "ll_pin": round(float(np.mean(ll_p)), 4), "ll_diff": round(float(np.mean(ll_o - ll_p)), 4), "ll_base": round(ll_b, 4),
            "edge_share": round((ll_b - float(np.mean(ll_o))) / (ll_b - float(np.mean(ll_p))), 2) if ll_b - float(np.mean(ll_p)) > 0.005 else None,
            "ll_se": round(float(np.std(ll_o - ll_p) / math.sqrt(len(rows))), 4) if len(rows) > 1 else None, "n_avg": sum(1 for r in rows if r[8] != "pin")}


def reasons(g: dict, gap: float, th: dict, ta: dict, w_x: float, move: dict) -> list[str]:
    """Plain-word reasons for a gap (ours minus Pinnacle, home margin). Each candidate is a signed contribution to the gap; only the
    ones pushing the same way as the gap and big enough to matter are kept, largest first."""
    cand = []
    fx = g.get("fx") or {}
    for side, t, sgn in (("home", th, 1), ("away", ta, -1)):
        term = ((fx.get(side) or {}).get("term") or {})
        if (term.get("elim") or 0) != 0:
            cand.append((sgn * term["elim"], f"{t['code']} are eliminated: we take {abs(term['elim']):.2f} off them (eliminated clubs play below their rating); Pinnacle may not price all of it"))
        if abs(term.get("abs") or 0) >= 0.02:
            names = ", ".join(p["player"] for p in (fx.get(side) or {}).get("players", [])[:3])
            cand.append((sgn * term["abs"], f"{t['code']} absences cost them {abs(term['abs']):.2f} in our price ({names})"))
        if abs((term.get("rest") or 0) + (term.get("short") or 0)) >= 0.03:
            cand.append((sgn * ((term.get("rest") or 0) + (term.get("short") or 0)), f"{t['code']} on {(fx.get(side) or {}).get('rest')} days' rest{' (short week)' if term.get('short') else ''}"))
    for t, sgn in ((th, 1), (ta, -1)):
        imp = (t.get("implied") or {}).get("w4")
        if imp is not None:
            d = float(imp) - float(t["rating"])   # Pinnacle's last 4 closes v our rating (+ = Pinnacle likes them more)
            cand.append((-sgn * d, f"Pinnacle's last 4 closes rate {t['code']} {d:+.2f} v our rating ({imp:+.2f} v {t['rating']:+.2f})"))
        src = t.get("sources") or {}
        m, x = src.get("market_recent"), src.get("xg")
        if m is not None and x is not None and w_x > 0:
            cand.append((sgn * w_x * (x - m), f"xG rates {t['code']} {x - m:+.2f} v the market; at {w_x:.0%} it moves our rating {w_x * (x - m):+.2f}"))
        if abs(t.get("hand") or 0) >= 0.01:
            cand.append((sgn * t["hand"], f"your hand adjustment on {t['code']} ({t['hand']:+.2f})"))
    out = [txt for c, txt in sorted(cand, key=lambda z: -abs(z[0])) if c * gap > 0 and abs(c) >= 0.05][:3]
    if not out:
        out.append(f"no single input explains it: our ratings of the two clubs sit {abs(gap):.2f} goals further {'toward the home side' if gap > 0 else 'toward the away side'} than Pinnacle's line")
    if move.get("first") is not None and abs(move["first"]) >= 0.08:
        out.append(f"the line has moved {move['first']:+.2f} since first posted ({'toward' if move['first'] * gap > 0 else 'away from'} us)")
    return out


def confidence(sd: dict, w_x: float) -> list[dict]:
    """Where to be least confident in the ratings (Zac 2026-10-19): each club's rating against what Pinnacle's own lines imply for
    it (last 4 / 8 / 12 closes and this round's posted line, net of each game's absences, rest and eliminated status since 2026-10-21). Flags, in goals:
    outside every Pinnacle window by 0.04+; 0.12+ from the longer windows (8 and 12) with the xG share pulling the same way by 0.05+;
    Pinnacle's own windows 0.25+ apart; the last 4 closes 0.40+ from the season's; a hand of 0.05+. Only clubs with a live futures
    price (playoffs 2-98% or Cup 1%+); doubt = the largest of the gaps, the club's plausible range = Pinnacle's window range plus ours."""
    mk = sd["markets"]; out = []
    for t in sd["teams"]:
        po_p = mk.get("playoffs", {}).get(t["team"], 0); cup = mk.get("cup", {}).get(t["team"], 0)
        if not (0.02 <= po_p <= 0.98 or cup >= 0.01):
            continue
        im = t.get("implied") or {}
        po = [x["implied"] for x in im.get("posted", []) if x.get("implied") is not None]
        win = {k: im.get(k) for k in ("w4", "w8", "w12")}
        if any(v is None for v in win.values()):
            continue
        pts = list(win.values()) + ([float(np.mean(po))] if po else [])
        lo, hi = min(pts), max(pts); R = float(t["rating"]); hand = float(t.get("hand") or 0)
        drag = w_x * ((t["sources"].get("xg") or 0) - (t["sources"].get("market_recent") or 0))
        elim = abs(((t.get("fielded") or {}).get("term") or {}).get("elim") or 0) > 0.01
        why, doubt = [], 0.0
        outside = R - hi if R > hi else (R - lo if R < lo else 0.0)
        if abs(outside) >= 0.04 and not elim:
            why.append(f"{abs(outside):.2f} {'above' if outside > 0 else 'below'} every Pinnacle window ({lo:+.2f} to {hi:+.2f})"
                       + (f"; the xG share pulls it {drag:+.2f}" if abs(drag) >= 0.03 and drag * outside > 0 else "")); doubt = max(doubt, abs(outside))
        longer = (win["w8"] + win["w12"]) / 2 - R
        if abs(longer) >= 0.12 and abs(drag) >= 0.05 and drag * longer < 0:
            why.append(f"Pinnacle's last 8-12 closes say {R + longer:+.2f}; the xG share ({drag:+.2f}) holds us {'below' if longer > 0 else 'above'} them"
                       + (f" (last 4 {win['w4']:+.2f} and this round's line agree with us)" if abs(win["w4"] - R) < 0.06 else "")); doubt = max(doubt, abs(longer))
        if hi - lo >= 0.25:
            why.append(f"Pinnacle itself is unsettled: its windows run {lo:+.2f} to {hi:+.2f}"); doubt = max(doubt, (hi - lo) / 2)
        if im.get("season") is not None and abs(win["w4"] - im["season"]) >= 0.40:
            why.append(f"a sharp {'rise' if win['w4'] > im['season'] else 'fall'}: last 4 closes {win['w4']:+.2f} v the season's {im['season']:+.2f}"); doubt = max(doubt, abs(win["w4"] - im["season"]) / 4)
        if abs(hand) >= 0.05:
            why.append(f"{hand:+.2f} of the rating is your hand (without it {R - hand:+.2f})"); doubt = max(doubt, abs(hand))
        if why:
            out.append({"code": t["code"], "rating": round(R, 2), "hand": round(hand, 2), "lo": round(min(lo, R), 2), "hi": round(max(hi, R), 2),
                        "w4": win["w4"], "w8": win["w8"], "w12": win["w12"], "posted": round(float(np.mean(po)), 2) if po else None,
                        "season": im.get("season"), "xg_pull": round(drag, 2), "doubt": round(doubt, 2), "why": why,
                        "cup": round(cup * 100, 1), "playoffs": round(po_p * 100, 1)})
    out.sort(key=lambda x: -x["doubt"])
    return out[:8]


def main():
    cfg = load_config(); kn = knobs(cfg); codes = code_of()
    sd = json.load(open(os.path.join(LATEST, "site_data.json")))
    summ = json.load(open(os.path.join(LATEST, "run_summary.json")))
    risk = json.load(open(os.path.join(LATEST, "risk.json"))) if os.path.exists(os.path.join(LATEST, "risk.json")) else {}
    today = today_et().isoformat(); asof = summ["asof"]
    prev = previous_report(today)
    tm = {t["team"]: t for t in sd["teams"]}
    w = sd["engine"]["weights"]; w_x = float(w.get("xg", 0.0)) / max(1e-9, sum(float(v) for v in w.values()))
    paths = line_paths(kn, codes)
    prev_lines = (prev or {}).get("snap", {}).get("lines", {})
    horizon = (dt.date.fromisoformat(asof) + dt.timedelta(days=8)).isoformat()

    # ----- upcoming games -----
    games, unlined = [], []
    for g in sd["games"]:
        if g["score"] or g["date"] < asof or g["date"] > horizon or g.get("g_model") is None:
            continue
        th, ta = tm[g["home"]], tm[g["away"]]
        row = {"date": g["date"], "ko": g["ko_et"], "home": th["code"], "away": ta["code"], "ours": r2(g["g_model"]), "ours_fh": r2(g.get("g_fh")),
               "factor": r2((g.get("fx") or {}).get("factor")), "ours_hda": [round(x, 3) for x in g["model"]]}
        key = (g["date"], g["home"], g["away"]); kstr = "|".join(key)
        if g.get("g_pin") is None or g.get("book"):   # no Pinnacle line yet (another book's line is display-only)
            unlined.append(row); continue
        p = paths.get(key, [])
        move = {"first": r2(g["g_pin"] - p[0][1]) if p else None, "first_at": et_str(parse_utc(p[0][0])) if p else None,
                "prev": r2(g["g_pin"] - prev_lines[kstr]) if kstr in prev_lines else None}
        gap = float(g["g_model"]) - float(g["g_pin"])
        row.update({"line": r2(g["g_pin"]), "gap": r2(gap), "pin_hda": [round(x, 3) for x in g["pin"]], "hw_gap": round((g["model"][0] - g["pin"][0]) * 100, 1),
                    "flag": "big" if abs(gap) >= BIG else ("watch" if abs(gap) >= WATCH else ""), "move": move, "sim_uses_line": bool(g.get("sim_uses_line")),
                    "lean": th["code"] if gap > 0 else ta["code"]})
        row["why"] = reasons(g, gap, th, ta, w_x, move) if abs(gap) >= 0.10 else []
        games.append(row)
    games.sort(key=lambda r: -abs(r["gap"]))
    gaps = np.array([r["gap"] for r in games]) if games else np.array([])

    # ----- track record -----
    tr = sd.get("track", [])
    d7 = (dt.date.fromisoformat(asof) - dt.timedelta(days=7)).isoformat(); d30 = (dt.date.fromisoformat(asof) - dt.timedelta(days=30)).isoformat()
    track = {"7d": track_stats([r for r in tr if r[0] >= d7]), "30d": track_stats([r for r in tr if r[0] >= d30]), "season": track_stats(tr)}
    # monthly rmse so the trend is visible
    months = {}
    for r in tr:
        months.setdefault(r[0][:7], []).append(r)
    track["by_month"] = [{"month": m, **track_stats(v)} for m, v in sorted(months.items())]

    # ----- what's new since the previous report -----
    since = (prev or {}).get("results_through") or d7
    new_results = [{"date": r[0], "home": r[1], "away": r[2], "ours": r2(r[3]), "close": r2(r[4]), "miss": r2(r[3] - r[4]),
                    "res": ["H", "D", "A"][r[7]], "p_ours": round(r[5][r[7]] * 100, 1), "p_pin": round(r[6][r[7]] * 100, 1)} for r in tr if r[0] > since]
    res = data.load("results")
    score = {(x["date"], codes.get(x["home"]), codes.get(x["away"])): f"{x['hg']}-{x['ag']}" for x in res.to_dict("records") if str(x.get("hg", "")) != ""}
    for x in new_results:
        x["score"] = score.get((x["date"], x["home"], x["away"]), "")
    ratings_now = {t["code"]: round(t["rating"], 3) for t in sd["teams"]}
    parts_now = {t["code"]: {"market": round(float(w.get("market_recent", 0)) / sum(w.values()) * (t["sources"].get("market_recent") or 0), 3),
                             "xg": round(w_x * (t["sources"].get("xg") or 0), 3), "hand": t.get("hand") or 0} for t in sd["teams"]}
    pr = (prev or {}).get("snap", {})
    rating_moves = []
    for c, v in ratings_now.items():
        b = (pr.get("ratings") or {}).get(c)
        if b is not None and abs(v - b) >= 0.02:
            pp = (pr.get("parts") or {}).get(c, {}); pn = parts_now[c]
            rating_moves.append({"code": c, "then": b, "now": v, "d": round(v - b, 3), **{f"d_{k}": round(pn[k] - pp.get(k, pn[k]), 3) for k in ("market", "xg", "hand")}})
    rating_moves.sort(key=lambda x: -abs(x["d"]))
    mk_now = {k: {codes[t]: round(p * 100, 1) for t, p in sd["markets"].get(k, {}).items()} for k, _ in POOLS}
    fut_moves = []
    for k, lab in POOLS:
        for c, v in mk_now[k].items():
            b = (pr.get("markets") or {}).get(k, {}).get(c)
            if b is not None and abs(v - b) >= 1.0:
                fut_moves.append({"pool": lab, "code": c, "then": b, "now": v, "d": round(v - b, 1)})
    fut_moves.sort(key=lambda x: -abs(x["d"]))
    av_p = os.path.join(ROOT, "data", "ratings", "absence_values.csv")
    abs_now = {}
    if os.path.exists(av_p):
        av = pd.read_csv(av_p, dtype=str, keep_default_na=False)
        for a in av.to_dict("records"):
            cost = float(a.get("cost_per_game") or 0)
            live = str(a.get("stale", "0")) != "1" and (a.get("out_from") or "0000") <= asof and (not a.get("expected_return") or a.get("expected_return") > asof)
            if live and cost >= 0.005:
                abs_now.setdefault(codes.get(a["team"], a["team"]), {})[a["player"]] = round(cost, 3)
    inj_changes = []
    if prev is not None:
        pa = pr.get("absences") or {}
        for c in sorted(set(abs_now) | set(pa)):
            n, o = abs_now.get(c, {}), pa.get(c, {})
            for p_ in sorted(set(n) - set(o)):
                inj_changes.append({"code": c, "player": p_, "kind": "new", "cost": n[p_]})
            for p_ in sorted(set(o) - set(n)):
                inj_changes.append({"code": c, "player": p_, "kind": "back or off the list", "cost": o[p_]})
    mlp = os.path.join(ROOT, "data", "ratings", "method_log.csv")
    ml = pd.read_csv(mlp, dtype=str, keep_default_na=False) if os.path.exists(mlp) else pd.DataFrame()
    prev_at = (prev or {}).get("made_utc") or (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    model_changes = [{"at": et_str(parse_utc(r["utc"])), "kind": r["kind"], "change": r["change"]} for r in ml.to_dict("records") if str(r["utc"]) > prev_at] if len(ml) else []

    # ----- headline -----
    # hand adjustments in force v the evidence (Zac 2026-10-19, CLAUDE.md 14j): each club's average miss v Pinnacle's close over the
    # games played since the hand was set (measured with the hand in, so the games it was sized from are not counted twice);
    # 0.3 x that is the size of a further move; judged once two closes have come in
    from sim.layers import week_of
    cur_week = week_of(asof); hl = data.load("hand_log")
    set_on = {}
    for r in hl.to_dict("records"):
        if r["team"] and str(r["week"]) <= cur_week:
            set_on[r["team"]] = max(set_on.get(r["team"], ""), str(r["saved_at"])[:10])
    misses = {}
    for r in tr:
        misses.setdefault(r[1], []).append((r[0], r[4] - r[3])); misses.setdefault(r[2], []).append((r[0], -(r[4] - r[3])))
    hands = []
    for t in sd["teams"]:
        if abs(t.get("hand") or 0) < 0.005:
            continue
        h_since = set_on.get(t["team"], "")
        v = [m for d, m in sorted(misses.get(t["code"], [])) if d > h_since][-4:]
        l4 = float(np.mean(v)) if v else None; nxt = 0.3 * l4 if l4 is not None else 0.0
        verdict = "too early" if len(v) < 2 else ("keep" if abs(nxt) < 0.03 else ("raise" if nxt * t["hand"] > 0 else ("trim" if abs(t["hand"]) > abs(nxt) else "drop")))
        hands.append({"code": t["code"], "hand": t["hand"], "since": h_since, "n": len(v), "last4": None if l4 is None else round(l4, 3),
                      "suggest": round(t["hand"] + nxt, 2), "verdict": verdict})
    head = []
    fp = os.path.join(LATEST, "freshness.json")   # data checks (scripts/freshness.py), first line of the report
    checks = json.load(open(fp))["checks"] if os.path.exists(fp) else []
    issues = [c for c in checks if c["status"] in ("bad", "warn")]
    if checks:
        head.append("Data: every input current and today's run built on it" if not issues else
                    f"Data: {len(issues)} issue{'s' if len(issues) != 1 else ''} — " + "; ".join(f"{c['label']}: {c['text']}" for c in issues[:3]))
    big = [r for r in games if r["flag"] == "big"]; wat = [r for r in games if r["flag"] == "watch"]
    if games:
        head.append(f"{len(games)} lined games in the next 8 days: ours v Pinnacle typical gap {float(np.sqrt(np.mean(gaps ** 2))):.2f} goals; "
                    + (f"{len(big)} big, {len(wat)} to watch" if big or wat else "none flagged"))
    for r in (big + wat)[:3]:
        head.append(f"{r['home']} v {r['away']} {r['date'][5:]}: we lean {r['lean']} by {abs(r['gap']):.2f} goals ({abs(r['hw_gap']):.0f} pts on the home win) — {r['why'][0] if r['why'] else ''}")
    s30 = track["30d"]
    if s30:
        head.append(f"Last 30 days ({s30['n']} games): our match-morning price missed the close by {s30['rmse']:.2f} goals (typical 0.24); on results ours {s30['ll_ours']:.3f} v Pinnacle {s30['ll_pin']:.3f} log-loss")
    if unlined:
        head.append(f"{len(unlined)} game{'s' if len(unlined) != 1 else ''} in the next 8 days not lined by Pinnacle yet")
    if new_results:
        worst = max(new_results, key=lambda x: abs(x["miss"]))
        head.append(f"{len(new_results)} new results; biggest miss {worst['home']} v {worst['away']} {worst['miss']:+.2f} goals v the close")
    if model_changes:
        head.append(f"{len(model_changes)} model change(s) since the last report")

    conf = confidence(sd, w_x)
    if conf:
        head.append("Least confident ratings: " + "; ".join(f"{c['code']} {c['rating']:+.2f} (could be {c['lo']:+.2f} to {c['hi']:+.2f})" for c in conf[:4]))
    for h in hands:
        if h["verdict"] not in ("keep", "too early"):
            head.append(f"Hand {h['code']} {h['hand']:+.2f}: Pinnacle's closes since it was set ({h['n']}) sit {h['last4']:+.2f} from us with the hand in; the evidence says {h['verdict']} to {h['suggest']:+.2f}")
    rep = {"date": today, "made_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "made_et": et_str(dt.datetime.now(dt.timezone.utc)),
           "run": summ.get("stamp"), "asof": asof, "results_through": summ.get("results_through"), "odds_at": sd["header"].get("odds_at"),
           "prev": (prev or {}).get("date"), "head": head, "games": games, "unlined": unlined, "track": track,
           "checks": checks, "hands": hands, "confidence": conf, "health": [{k: h.get(k) for k in ("label", "value", "unit", "status", "sub")} for h in risk.get("health", [])],
           "watch": [{"team": codes.get(x["team"], x["team"]), "flags": [f["text"] for f in x.get("flags", [])]} for x in risk.get("watch", [])],
           "new": {"results": new_results, "ratings": rating_moves, "futures": fut_moves[:15], "injuries": inj_changes, "model": model_changes},
           "snap": {"ratings": ratings_now, "parts": parts_now, "markets": mk_now, "absences": abs_now,
                    "lines": {"|".join(k): v[-1][1] for k, v in paths.items() if k[0] >= asof}}}
    os.makedirs(REPORTS, exist_ok=True)
    for p in (os.path.join(REPORTS, f"morning_{today}.json"), os.path.join(LATEST, "morning.json")):
        json.dump(rep, open(p, "w"), indent=1, default=str)
    print(f"morning: {len(games)} lined games ({len(big)} big, {len(wat)} watch), {len(unlined)} unlined; 30-day rmse "
          f"{s30['rmse'] if s30 else 'n/a'}; {len(new_results)} new results since {since}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
