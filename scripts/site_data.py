#!/usr/bin/env python3
"""One JSON of everything the page needs -> outputs/latest/site_data.json (embedded into the page by build_site.py).
Ratings (both conferences: rating, hand, Conf 1st / Playoffs / Reach semis / Reach conf final / Reach MLS Cup / Win MLS Cup, sources, Pinnacle-implied grid,
the previous run for deltas), Games (Tue-Mon weeks: Pinnacle fair, our ratings' price, the gap; played and upcoming games
alike from the ratings before that round's Pinnacle lines), Conferences (expected points and
fair odds), Injuries, Settings (run knobs and the engine inputs for the page worker), Risk (outputs/latest/risk.json), header
stamps in ET. Only keys the page reads are written."""
from __future__ import annotations
import base64, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.teams import ROOT, teams, conference_of, code_of, load_teams
from sim.engine import hda
from sim.devig import power_devig
from sim.ratings import market_fit, gd_fit_row, home_edge_for
from sim.layers import team_penalty, week_of, hand_week_values
from scripts.refresh_ratings import closes_with_targets, build_ratings, with_posted_lines, team_totals, ratings_without_lines, implied_pair
from sim.playoffs import real_playoff_results
from scripts.run_sim import played_stats, latest_posted
from scripts.common import ET, parse_utc, et_str

LATEST = os.path.join(ROOT, "outputs", "latest")
LOGOS = os.path.join(ROOT, "data", "logos.csv")


def clean(x):
    """NaN/inf -> None, so the file is valid JSON (the page embeds it, other tools parse it)."""
    if isinstance(x, float):
        return x if np.isfinite(x) else None
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def prob_of(row) -> float:
    """prob_out as the injury layer reads it: blank = fully out, anything unreadable = fully out."""
    try:
        v = str(row.get("prob_out", "")).strip()
        return 1.0 if v == "" else float(v)
    except (TypeError, ValueError):
        return 1.0


def week_start(d: dt.date) -> dt.date:
    """Weeks run Tuesday to Monday (ET)."""
    return d - dt.timedelta(days=(d.weekday() - 1) % 7)



def opta_anchor(T: list, R: np.ndarray) -> tuple[dict, dict]:
    """The public sanity anchor (Zac, do 2, 2026-10-15): Opta Power Rankings' latest snapshot, centred and rescaled to the blend's
    spread (the PDF blend step), never weighted. Returns ({team: value or None}, {date, spearman, n})."""
    p = os.path.join(ROOT, "data", "public", "opta", "snapshots.csv")
    if not os.path.exists(p):
        return {t: None for t in T}, {}
    o = pd.read_csv(p); o = o[o["date"] == o["date"].max()].set_index("team")["rating"]
    v = np.array([o.get(t, np.nan) for t in T], float)
    ok = np.isfinite(v)
    if ok.sum() < 20:
        return {t: None for t in T}, {}
    v = v - np.nanmean(v); v = v * (float(np.std(R)) / float(np.nanstd(v)))
    rb = pd.Series(R[ok]).rank(); ro = pd.Series(v[ok]).rank()
    info = {"snapshot": str(pd.read_csv(p)["date"].max()), "spearman": round(float(np.corrcoef(rb, ro)[0, 1]), 3), "n": int(ok.sum())}
    return {t: (round(float(v[i]), 3) if ok[i] else None) for i, t in enumerate(T)}, info

def _nkey(name: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", s).strip()


def headshots(names_by_team: dict) -> dict:
    """{"Team|Player": data URI} for every named player with a photo in data/headshots (36 px PNG, about 1.5 KB each). A name is
    matched to the ESPN roster of the same club: exact (accents and punctuation ignored), then last name + first initial, then a
    last name that is unique on the roster. Players without a photo on the CDN are left out (the page shows initials)."""
    rp = os.path.join(ROOT, "data", "headshots", "roster.csv")
    if not os.path.exists(rp):
        return {}
    roster = pd.read_csv(rp, dtype=str, keep_default_na=False)
    by_team = {}
    for r in roster.to_dict("records"):
        by_team.setdefault(r["team"], []).append((_nkey(r["player"]), r["espn_id"]))
    out, cache = {}, {}
    for team, names in names_by_team.items():
        ros = by_team.get(team, [])
        for name in names:
            k = _nkey(name); parts = k.split()
            if not parts:
                continue
            hit = [pid for nk, pid in ros if nk == k]
            if not hit:
                hit = [pid for nk, pid in ros if nk.split()[-1] == parts[-1] and nk[:1] == k[:1]]
            if not hit:
                hit = [pid for nk, pid in ros if nk.split()[-1] == parts[-1]]
                if len(hit) != 1:
                    hit = []
            if not hit:
                continue
            pid = hit[0]; fp = os.path.join(ROOT, "data", "headshots", f"{pid}.png")
            if pid not in cache:
                cache[pid] = "data:image/png;base64," + base64.b64encode(open(fp, "rb").read()).decode() if os.path.exists(fp) and os.path.getsize(fp) else ""
            if cache[pid]:
                out[f"{team}|{name}"] = cache[pid]
    return out


def main():
    cfg = load_config(); kn = knobs(cfg)
    summ = json.load(open(os.path.join(LATEST, "run_summary.json")))
    markets = json.load(open(os.path.join(LATEST, "markets.json")))
    preds = pd.read_csv(os.path.join(LATEST, "predictions.csv"), dtype=str, keep_default_na=False)
    T = teams(); cm = conference_of(); codes = code_of(); idx = {t: i for i, t in enumerate(T)}
    asof = summ["asof"]
    rat = build_ratings(asof, cfg, write=False)
    R = rat["ratings"]
    rho = float(kn.get("dc_rho", 0.0) or 0.0)
    # our ratings before this round's Pinnacle lines: the Games tab prices upcoming games off these, so the gap to the line is the
    # ratings' own view and not the line fed back through the filter (Zac, 2026-10-19: "what price would our team ratings give")
    R_nl = ratings_without_lines(asof, cfg)["ratings"] if kn.get("posted_in_fit") else R
    logos = {}
    if os.path.exists(LOGOS):
        logos = {r["team"]: r["logo"] for r in pd.read_csv(LOGOS, dtype=str).to_dict("records")}
    # crests embedded as data URIs (data/logos/<code>.png, 96 px, fetched once from the ESPN URLs): the published page cannot rely on external images
    for t in list(logos):
        lp = os.path.join(ROOT, "data", "logos", f"{codes.get(t, '')}.png")
        if os.path.exists(lp):
            logos[t] = "data:image/png;base64," + base64.b64encode(open(lp, "rb").read()).decode()
    opta, _ = opta_anchor(T, R)
    colp = os.path.join(ROOT, "data", "club_colours.csv")   # one matte colour per club (scripts/club_colours.py): row bars, sparklines
    colours = {r["team"]: r["hex"] for r in pd.read_csv(colp, dtype=str).to_dict("records")} if os.path.exists(colp) else {}
    teams_out = [{"team": t, "code": codes[t], "conf": cm[t], "rating": round(float(R[i]), 3), "hand": round(float((rat.get("hand") or {}).get(t, 0.0)), 3), "blend_raw": round(float(rat["blend_raw"][i]), 3) if rat.get("blend_raw") is not None else None, "logo": logos.get(t, ""), "color": colours.get(t, "#8a9099"), "opta": opta.get(t),
                  "sources": {k: round(float(v[i]), 3) for k, v in rat["sources"].items()}, "n_closes": int(rat["n_closes"][i]),
                  "sd": round(float(rat["market_fit"]["kalman_sd"][i]), 3) if rat["market_fit"].get("kalman_sd") is not None else None,  # the filter's posterior sd (Glicko's RD): the Ratings tab's 95% band
                  "note": next((r["note"] for r in load_teams() if r["team"] == t), ""), "home_delta": round(float((rat.get("club_deltas") or {}).get(t, 0.0)), 3)} for i, t in enumerate(T)]
    # ----- games: schedule with results, Pinnacle fair (power devig), model HDA, gap -----
    sch = data.load("schedule"); res = data.load("results"); closes = closes_with_targets(cfg)
    season_closes = closes[closes["season"].astype(str) == str(cfg["season"])]
    layer_closes = season_closes
    if kn.get("posted_in_fit"):  # the layer's absorption counts the current round's posted lines too (they are in the ratings since 2026-10-15)
        pl = with_posted_lines(closes, asof, kn); layer_closes = pd.concat([season_closes, pl[pl["season"].astype(str) == "posted"]], ignore_index=True)
    resmap = {(r["date"], r["home"], r["away"]): r for r in res.to_dict("records")}
    predmap = {(r["date"], r["home"], r["away"]): r for r in preds.to_dict("records")}
    closemap = {(r["date"], r["home"], r["away"]): r for r in season_closes.to_dict("records")}
    # other books' latest posted lines (OpticOdds daily pull), display-only fallback for fixtures Pinnacle has not lined: sharpest first
    BOOK_ORDER = ["ps3838", "betfair", "bet365", "draftkings", "fanduel"]
    bookmap = {}
    cro = data.load("current_round_odds")
    if len(cro):
        cro = cro[cro["book"].str.lower().isin(BOOK_ORDER)].sort_values("fetched_at")
        for rr_ in cro.to_dict("records"):
            k = (rr_["date"], rr_["home"], rr_["away"]); b = rr_["book"].lower()
            cur = bookmap.get(k)
            if cur is None or BOOK_ORDER.index(b) <= BOOK_ORDER.index(cur["book"].lower()):
                bookmap[k] = rr_
    # Pinnacle-implied rating per club from each of this season's closes (opponent held at today's rating), windows of the last 4/8/12 and the season,
    # plus the current round's posted Pinnacle line(s)
    implied = {}
    cl_season = season_closes.copy(); cl_season["gd"] = pd.to_numeric(cl_season["gd_fit"], errors="coerce"); cl_season = cl_season.dropna(subset=["gd"]).sort_values("date")
    posted_now = latest_posted(data.load("current_round_odds"), asof=asof)
    deltas_ = rat.get("club_deltas") or {}
    # net of each game's factors (refresh_ratings.implied_pair): played closes with the lineups as they were, this round's lines
    # with today's injury list, rest and table; opponent at today's rating
    from sim.factors import betas_from_knobs as _bfk, factor_vector as _fv, factors as _facs, live_factors as _lf
    _b = _bfk(kn); _Fh = _facs() if _b else None; _Fl = _lf(asof) if _b else None
    def _implied(team, date, home, away, gd, posted=False):
        fac = _fv(_b, (_Fl.x(date, home, away) if posted else _Fh.x_actual(date, home, away))) if _b else 0.0
        ih, ia = implied_pair(gd, kn["home_edge_goals"], deltas_.get(home, 0.0), fac, float(R[idx[home]]), float(R[idx[away]]))
        return ih if home == team else ia
    for t in T:
        m = cl_season[(cl_season["home"] == t) | (cl_season["away"] == t)]
        rows_ = [{"date": r["date"], "opp": r["away"] if r["home"] == t else r["home"], "ha": "v" if r["home"] == t else "@", "close": round(float(r["gd"]), 2),
                  "implied": round(_implied(t, r["date"], r["home"], r["away"], r["gd"]), 2)} for r in m.to_dict("records")]
        vals = [x["implied"] for x in rows_]
        win = {k: (round(float(np.mean(vals[-n:])), 2) if len(vals) >= 1 else None) for k, n in (("w4", 4), ("w8", 8), ("w12", 12))}
        win["season"] = round(float(np.mean(vals)), 2) if vals else None
        posted_rows = []
        for (d_, h_, a_), ln in posted_now.items():
            if t in (h_, a_) and (d_, h_, a_) not in closemap:  # a posted line is superseded once the close is on file
                gf = gd_fit_row(ln.get("h"), ln.get("d"), ln.get("a"), ln.get("ah_line") or None, ln.get("ah_home"), ln.get("ah_away"), ln.get("total_line") or None, ln.get("over"), ln.get("under"),
                                kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
                if np.isfinite(gf["gd_fit"]):
                    posted_rows.append({"date": d_, "opp": a_ if h_ == t else h_, "ha": "v" if h_ == t else "@", "close": round(float(gf["gd_fit"]), 2), "implied": round(_implied(t, d_, h_, a_, gf["gd_fit"], posted=True), 2)})
        implied[t] = {"posted": posted_rows, **win, "n": len(vals)}
    for to_ in teams_out:
        to_["implied"] = implied.get(to_["team"])
    # weekly hand log for the Ratings tab: every week on file plus the current and next weeks (Tue-Mon), each with its own values or the
    # carried-over set; the run uses the current week's
    hlog = data.load("hand_log")
    cur_week = week_of(asof); next_week = (dt.date.fromisoformat(cur_week) + dt.timedelta(days=7)).isoformat()
    weeks = sorted(set(hlog["week"].astype(str)) | {cur_week, next_week}) if len(hlog) else [cur_week, next_week]
    hand_weeks = []
    for w in weeks:
        vals, used = hand_week_values(hlog, w)
        own = hlog[hlog["week"].astype(str) == w] if len(hlog) else hlog
        saved = str(own["saved_at"].max()) if len(own) else ""
        hand_weeks.append({"week": w, "own": bool(len(own)), "carried_from": None if (used == w or used is None) else used, "saved_at": saved,
                           "values": {t: round(float(v), 2) for t, v in vals.items()}, "past": w < cur_week, "current": w == cur_week})
    today = dt.date.fromisoformat(asof)
    lo, hi = week_start(today) - dt.timedelta(days=28), week_start(today) + dt.timedelta(days=35)
    fits = {}; fits_lines = {}; fits_stats = {}
    from sim.factors import betas_from_knobs, factor_vector, factors as _factors
    betas = betas_from_knobs(kn); Fz = _factors() if betas else None
    if str(kn.get("rating_method", "wls")) == "kalman":  # one filter pass gives the state before every played date (site_detail.replay_fits)
        from scripts.site_detail import replay_fits
        fits, fits_lines, fits_stats = replay_fits(kn, rat, closes, sch, resmap, T, hlog, variants=True)
    Xsrc = rat["sources"].get("xg")   # the stats-only version of an upcoming game (xG source alone, no Pinnacle data, no hand)
    Xsrc = None if Xsrc is None else np.asarray(Xsrc, float) - float(np.mean(Xsrc))
    alt = lambda gm, Tt: {"g": round(gm, 3), "p": [round(float(x), 4) for x in hda(gm, Tt, kn["goal_floor"], kn["shared_goals_mean"], rho)]}
    # what the factors net out of / add back to each game (Games tab detail, CLAUDE.md 14): played games from the lineups, upcoming
    # games from today's injury list, the schedule and the table
    from scripts.site_detail import PlayedAbsences, ListedAbsences, played_breakdown, upcoming_breakdown, as_fielded, history as history_payload
    PA = PlayedAbsences(cfg["season"]) if betas else None; LA = ListedAbsences() if betas else None
    LF = None
    if betas:
        from sim.factors import live_factors
        LF = live_factors(asof)
    docked = (summ.get("dock") or {}).get("docked_share") or {}
    games = []
    for r in sch.sort_values("kickoff_utc").to_dict("records"):
        if r["competition"] != "MLS" or not r["date"]:
            continue
        d = dt.date.fromisoformat(r["date"])
        if d < lo or d >= hi:
            continue
        key = (r["date"], r["home"], r["away"])
        ko = parse_utc(r["kickoff_utc"]) if r["kickoff_utc"] else None
        g = {"date": r["date"], "ko_et": ko.astimezone(ET).strftime("%a %m/%d %I:%M%p").replace(" 0", " ").replace("AM", "a").replace("PM", "p") if ko else "", "home": r["home"], "away": r["away"],
             "score": "", "pin": None, "pin_raw": None, "model": None, "g_model": None, "g_pin": None}
        rr = resmap.get(key)
        if rr and str(rr.get("hg", "")) != "":
            g["score"] = f"{rr['hg']}-{rr['ag']}"
        line = closemap.get(key)
        if line is None:
            p = predmap.get(key)
            if p and p.get("pinn_h"):
                g["pin"] = [float(p["pinn_h"]), float(p["pinn_d"]), float(p["pinn_a"])]
                g["g_pin"] = float(p["g_pinn"]) if p.get("g_pinn") else None
                pl = posted_now.get(key)  # raw decimals of the posted Pinnacle line, so the Games detail shows the gap v the line before kickoff too
                if pl is not None and all(str(pl.get(c, "")) not in ("", "nan") for c in ("h", "d", "a")):
                    g["pin_raw"] = [float(pl["h"]), float(pl["d"]), float(pl["a"])]
            elif key in bookmap and not g["score"]:
                bl = bookmap[key]
                try:
                    gf = gd_fit_row(bl.get("h"), bl.get("d"), bl.get("a"), bl.get("ah_line") or None, bl.get("ah_home"), bl.get("ah_away"), bl.get("total_line") or None, bl.get("over"), bl.get("under"),
                                    kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], float(kn.get("dc_rho", 0.0) or 0.0))
                    if all(str(bl.get(c, "")) not in ("", "nan") for c in ("h", "d", "a")):
                        ph, pdr, pa = power_devig([float(bl["h"]), float(bl["d"]), float(bl["a"])])
                        g["pin"] = [float(ph), float(pdr), float(pa)]; g["pin_raw"] = [float(bl["h"]), float(bl["d"]), float(bl["a"])]
                    g["g_pin"] = float(gf["gd_fit"]) if np.isfinite(gf["gd_fit"]) else None
                    g["book"] = bl["book"]
                except (ValueError, TypeError):
                    pass
        else:
            try:
                ph, pdr, pa = power_devig([float(line["h"]), float(line["d"]), float(line["a"])])
                g["pin"] = [float(ph), float(pdr), float(pa)]; g["pin_raw"] = [float(line["h"]), float(line["d"]), float(line["a"])]
                g["g_pin"] = float(line["gd_fit"]) if str(line.get("gd_fit", "")) not in ("", "nan") else None
                if not str(line.get("book", "")).startswith("pinnacle"):  # 34 games of 2026 have only football-data's market-average close
                    g["book"] = "market-average close"
            except (ValueError, TypeError):
                pass
        if g["score"]:
            if r["date"] not in fits:  # wls fallback (the Kalman pass above fills every played date)
                fits[r["date"]] = market_fit(closes, T, r["date"], kn["half_life_days"], kn["ridge_lambda"], fit_home_edge=False, home_edge_fixed=kn["home_edge_goals"], before=True, club_deltas=rat.get("club_deltas"))["ratings"]
            Rw = fits[r["date"]]
            gm = float(Rw[idx[r["home"]]] - Rw[idx[r["away"]]] + home_edge_for(r["home"], kn["home_edge_goals"], rat.get("club_deltas")))
            if str(kn.get("rating_method", "wls")) == "kalman" and betas:  # that game's factors added back: rest, short week, eliminated status
                fac = factor_vector(betas, Fz.x_expected(r["date"], r["home"], r["away"], r["date"], "actual"))  # and the absences as the lineups were (the close knew them)
                gm += fac
                g["fx"] = {**played_breakdown(betas, Fz, PA, r["date"], r["home"], r["away"]), "factor": round(fac, 3)}
                g["g_fh"] = round(gm - fac, 3); g["model_fh"] = list(hda(gm - fac, float(line["T_fit"]) if line is not None and str(line.get("T_fit", "")) not in ("", "nan") else kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"], rho))
            Tt = float(line["T_fit"]) if line is not None and str(line.get("T_fit", "")) not in ("", "nan") else kn["avg_total_goals"]
            g["model"] = list(hda(gm, Tt, kn["goal_floor"], kn["shared_goals_mean"], rho)); g["g_model"] = round(gm, 3)
            # the Games tab's other two versions (Zac 2026-10-19): the match-morning ratings with that round's lines in, and stats only
            he_fac = gm - float(Rw[idx[r["home"]]] - Rw[idx[r["away"]]])   # home edge + club delta + that game's factors
            g["alt"] = {}
            if r["date"] in fits_lines:
                Rl = fits_lines[r["date"]]; g["alt"]["lines"] = alt(float(Rl[idx[r["home"]]] - Rl[idx[r["away"]]]) + he_fac, Tt)
            if r["date"] in fits_stats:
                X = fits_stats[r["date"]]; g["alt"]["stats"] = alt(float(X[idx[r["home"]]] - X[idx[r["away"]]]) + he_fac, Tt)
        else:
            p = predmap.get(key)
            if p:  # the run's fixture adjustments (home edge, club delta, fixture hand, layers) on the ratings before this round's lines
                h_, a_ = idx[r["home"]], idx[r["away"]]
                gm = float(p["g_model"]) - float(R[h_] - R[a_]) + float(R_nl[h_] - R_nl[a_])
                g["T"] = float(p["T"]); g["g_model"] = round(gm, 3)
                g["model"] = list(hda(gm, g["T"], kn["goal_floor"], kn["shared_goals_mean"], rho))
                g["alt"] = {"lines": alt(float(p["g_model"]), g["T"])}   # the live ratings, this round's lines included
                if Xsrc is not None:  # xG source alone: the hand and the line-fed ratings swapped out, factors and home edge kept
                    g["alt"]["stats"] = alt(float(p["g_model"]) - float(R[h_] - R[a_]) + float(Xsrc[h_] - Xsrc[a_]), g["T"])
                g["sim_uses_line"] = float(p.get("shrink") or 0) >= 1.0
                if betas and LF is not None:
                    fac = float(p.get("factor_goals") or 0.0)
                    g["fx"] = {**upcoming_breakdown(betas, LF, LA, r["date"], r["home"], r["away"], docked), "factor": round(fac, 3)}
                    g["g_fh"] = round(gm - fac, 3); g["model_fh"] = list(hda(gm - fac, g["T"], kn["goal_floor"], kn["shared_goals_mean"], rho))
        games.append(g)
    if betas and LF is not None:
        nfx = {}
        for r in sch[sch["competition"] == "MLS"].sort_values("kickoff_utc").to_dict("records"):
            if (r["date"], r["home"], r["away"]) in resmap or r["date"] < asof:
                continue
            for t in (r["home"], r["away"]):
                nfx.setdefault(t, r)
        fielded = as_fielded(betas, LF, LA, T, R, nfx)
        for to_ in teams_out:
            to_["fielded"] = fielded.get(to_["team"])
    # season track record (morning.py): every played game of the season with a close, our match-morning price (ratings without that
    # round's lines, factors as fielded) v the close and the result; [date, home, away, our margin, close margin, our H/D/A, close H/D/A, result, book]
    track = []
    for key, line in sorted(closemap.items()):
        rr = resmap.get(key)
        if key[0] not in fits or not rr or str(rr.get("hg", "")) == "" or str(line.get("gd_fit", "")) in ("", "nan"):
            continue
        try:
            pin3 = [float(x) for x in power_devig([float(line["h"]), float(line["d"]), float(line["a"])])]
        except (ValueError, TypeError):
            continue
        Rw = fits[key[0]]
        gm = float(Rw[idx[key[1]]] - Rw[idx[key[2]]] + home_edge_for(key[1], kn["home_edge_goals"], rat.get("club_deltas")))
        if str(kn.get("rating_method", "wls")) == "kalman" and betas:
            gm += factor_vector(betas, Fz.x_expected(key[0], key[1], key[2], key[0], "actual"))
        Tt = float(line["T_fit"]) if str(line.get("T_fit", "")) not in ("", "nan") else kn["avg_total_goals"]
        hg, ag = int(float(rr["hg"])), int(float(rr["ag"]))
        track.append([key[0], codes[key[1]], codes[key[2]], round(gm, 3), round(float(line["gd_fit"]), 3), [round(float(x), 4) for x in hda(gm, Tt, kn["goal_floor"], kn["shared_goals_mean"], rho)],
                      [round(x, 4) for x in pin3], 0 if hg > ag else (1 if hg == ag else 2), "pin" if str(line.get("book", "")).startswith("pinnacle") else "avg"])
    history_out = history_payload(T, codes, fits, season_closes, res, kn, betas, Fz, rat.get("club_deltas") or {}, et_str)
    # ----- conferences / markets -----
    conf_rows = []
    pts = markets["points"]
    pr = lambda pool, t: round(float(markets[pool][t]["prob"]), 5)
    for t in T:
        e = cm[t] == "East"
        conf_rows.append({"team": t, "conf": cm[t], "exp_points": round(pts[t]["mean"], 1), "p10": pts[t]["p10"], "p90": pts[t]["p90"],
                          "playoffs": pr("playoffs", t), "top_seed": pr("east" if e else "west", t), "conf_final": pr("east_final" if e else "west_final", t),
                          "cup": pr("cup", t), "spoon": pr("spoon", t), "bottom": pr("east_bottom" if e else "west_bottom", t), "top4": pr("conf_top4", t)})
    # the pools the Ratings tab reads, as plain probabilities (the shade is off, so prob == prob_raw)
    PAGE_POOLS = ("east", "west", "playoffs", "conf_semi", "conf_final", "cup_finalist", "cup")
    markets_out = {k: {t: round(float(v["prob"]), 5) for t, v in markets[k].items()} for k in PAGE_POOLS if k in markets}
    # ----- injuries -----
    inj = data.load("injuries"); cal = data.load("callups")
    avp = os.path.join(ROOT, "data", "ratings", "absence_values.csv")   # absence values in goals (CLAUDE.md 14, proposal 5)
    av = pd.read_csv(avp, dtype=str, keep_default_na=False) if os.path.exists(avp) else pd.DataFrame()
    av_key = {(r["team"], r["player"]): r for r in av.to_dict("records")} if len(av) else {}
    next_fx = {}
    for r in sch[sch["status"] != "final"].sort_values("kickoff_utc").to_dict("records"):
        for t in (r["home"], r["away"]):
            next_fx.setdefault(t, r)
    inj_rows = []
    for t in T:
        nf = next_fx.get(t)
        pen = team_penalty(t, nf["date"], inj, cal, layer_closes, asof, kn["half_life_days"], kn["injury_tiers"], True, True) if nf else {"injury": 0, "callup": 0, "detail": []}
        rows = inj[inj["team"] == t].to_dict("records"); crow = cal[cal["team"] == t].to_dict("records")
        live = [x for x in rows if x["out_from"] <= asof and (not x["expected_return"] or x["expected_return"] > asof)]
        out_now = [x for x in live if prob_of(x) >= 1.0]
        PLAYER = ("player", "note", "tier", "prob_out", "out_from", "expected_return")
        ABS = ("value_per96", "regular", "cost_per_game", "games_missed", "stale", "asa_player")  # from absence_values.csv (full-health ratings)
        players = [{**{k: x.get(k, "") for k in PLAYER}, **{k: av_key.get((t, x["player"]), {}).get(k, "") for k in ABS}} for x in rows]
        abs_now = round(sum(float(a.get("cost_per_game") or 0) for (tt, _), a in av_key.items() if tt == t and str(a.get("stale", "0")) != "1" and (a.get("out_from") or "0000") <= asof and (not a.get("expected_return") or a.get("expected_return") > asof)), 3)
        inj_rows.append({"team": t, "out": len(out_now), "doubt": len(live) - len(out_now), "listed": len(rows),
                         "next": f"{nf['date']} {'v' if nf['home']==t else '@'} {codes.get(nf['away'] if nf['home']==t else nf['home'],'')}" if nf else "",
                         "penalty": round(pen["injury"] + pen["callup"], 3) if kn["injury_layer_enabled"] or kn["callup_layer_enabled"] else 0.0,
                         "raw": round(pen["injury"] + pen["callup"], 3), "absence_value": abs_now, "players": players, "callups": crow,
                         "detail": [{k: x.get(k) for k in ("player", "kind", "penalty", "absorbed")} for x in pen["detail"]]})
    # ----- headshots (data/headshots, scripts/fetch_headshots.py): every player named on the page, matched to the ESPN roster -----
    names = {}
    for r in inj_rows:
        for p in r["players"]:
            names.setdefault(r["team"], set()).add(p["player"])
    for g in games:
        for side, t in (("home", g["home"]), ("away", g["away"])):
            fx = (g.get("fx") or {}).get(side) or {}
            for p in list(fx.get("players") or []) + list(fx.get("left") or []):
                names.setdefault(t, set()).add(p["player"])
    for t_ in teams_out:
        for p in ((t_.get("fielded") or {}).get("players") or []):
            names.setdefault(t_["team"], set()).add(p["player"])
    heads = headshots(names)
    # ----- settings / engine inputs for the worker -----
    engine = {"teams": T, "conf": [0 if cm[t] == "East" else 1 for t in T], "sources": {k: [round(float(x), 4) for x in v] for k, v in rat["sources"].items()},
              "weights": rat["weights"], "played": {k: [int(x) for x in v] for k, v in played_stats(res[res["competition"].isin(["MLS", ""])], T).items()},
              "fixtures": [{"h": idx[p["home"]], "a": idx[p["away"]], "date": p["date"], "adj": round(float(p["g_model"]) - float(R[idx[p["home"]]] - R[idx[p["away"]]]), 4),
                            "s": float(p["shrink"] or 0), "gp": float(p["g_pinn"]) if p.get("g_pinn") else 0.0, "T": float(p["T"])} for p in preds.to_dict("records")],
              "pt": (lambda tt: {"base": round(tt["base"], 4), "u": [round(float(tt["offsets"].get(t, 0.0)), 4) for t in T]} if tt else None)(team_totals(closes, T, asof, kn)),
              "locked": [list(x) for x in real_playoff_results(res, T, cfg["season"])],
              "hand_weeks": hand_weeks, "hand_week": cur_week, "knobs": {k: kn[k] for k in ("rating_sd", "drift_k_sim", "drift_cap", "home_edge_goals", "avg_total_goals", "goal_floor", "shared_goals_mean", "dc_rho")}, "seed": kn["seed"]}
    odds_at = summ.get("odds_fetched_at")
    header = {"odds_at": et_str(parse_utc(odds_at)) if odds_at else "no capture", "results_through": summ.get("results_through") or "none",
              "run_at": et_str(parse_utc(summ["run_utc"])), "asof": asof, "n_seasons": summ["n_seasons"]}
    # top-corner stamp (Zac 2026-10-19): the last full refresh and the last Pinnacle close on file with when it was taken
    sp = os.path.join(LATEST, "weekly_steps.json")
    if os.path.exists(sp):
        try:
            header["refresh_at"] = et_str(parse_utc(json.load(open(sp))["utc"]))
        except (ValueError, KeyError):
            pass
    cl_all = data.load("closing_lines")
    cl_all = cl_all[cl_all["book"].isin(["pinnacle_close", "pinnacle_last", "pinnacle_lastposted"]) & (cl_all["kickoff_utc"] != "")]
    if len(cl_all):
        last = cl_all.sort_values(["kickoff_utc", "fetched_at"]).iloc[-1]
        same = cl_all[cl_all["kickoff_utc"] == last["kickoff_utc"]]
        header["last_close"] = {"games": [f"{codes.get(r['home'], r['home'])} v {codes.get(r['away'], r['away'])}" for r in same.to_dict("records")],
                                "kickoff": et_str(parse_utc(last["kickoff_utc"])),
                                # a 10-minute capture is stamped when it was taken; Pinnacle's official close (pulled the next morning) is the line at kickoff
                                "at": et_str(parse_utc(last["fetched_at"] if last["book"] != "pinnacle_close" else last["kickoff_utc"])),
                                "how": {"pinnacle_last": "10-minute capture", "pinnacle_lastposted": "missed capture: last line fetched before kickoff"}.get(last["book"], "Pinnacle's official close (OpticOdds, historical)")}
    # the run before this one (ratings and markets), so the Ratings tab always shows what changed since the last run: a saved hand
    # edit's effect stays visible after its run instead of vanishing with the preview
    prev = None
    runs_dir = os.path.join(ROOT, "outputs", "runs")
    cur_stamp = str(summ.get("stamp", ""))
    if os.path.isdir(runs_dir):
        stamps = sorted(d for d in os.listdir(runs_dir) if os.path.exists(os.path.join(runs_dir, d, "markets.json")) and os.path.exists(os.path.join(runs_dir, d, "ratings.csv")))
        earlier = [d for d in stamps if d < cur_stamp] if cur_stamp else stamps[:-1]
        if earlier:
            pst = earlier[-1]
            try:
                pr = pd.read_csv(os.path.join(runs_dir, pst, "ratings.csv"))
                pm = json.load(open(os.path.join(runs_dir, pst, "markets.json")))
                psum = json.load(open(os.path.join(runs_dir, pst, "run_summary.json"))) if os.path.exists(os.path.join(runs_dir, pst, "run_summary.json")) else {}
                prev = {"run": pst, "run_at": et_str(parse_utc(psum["run_utc"])) if psum.get("run_utc") else pst, "asof": psum.get("asof"),
                        "ratings": {str(r["team"]): round(float(r["rating"]), 3) for r in pr.to_dict("records")},
                        "markets": {k: {t: round(float(v.get("prob", v.get("prob_raw", 0.0))), 5) for t, v in pm[k].items()} for k in PAGE_POOLS if isinstance(pm.get(k), dict)}}
            except Exception as e:  # a malformed archive must not stop the page
                print(f"site_data: previous run {pst} unreadable ({e})")
    out = {"history": history_out, "track": track, "header": header, "teams": teams_out, "games": games, "conferences": conf_rows, "markets": markets_out, "injuries": inj_rows, "engine": engine, "heads": heads,
           "prev": prev, "forecast": summ.get("forecast_check"), "fit": {"n": summ.get("closes_in_fit")}, "layers": {"injuries": kn["injury_layer_enabled"], "callups": kn["callup_layer_enabled"],
                                                                                         "factors": bool(kn.get("factors_enabled", False)), "factor_abs": kn.get("factor_abs", 0),
                                                                                         "betas": betas or {}}}
    if any(float(v) != 1.0 for v in kn["shade"].values()):
        print("site_data: WARNING a shade is on; the page shows the shaded prob (the Shaded/Raw toggle was removed while the shade was off)")
    rp = os.path.join(LATEST, "risk.json")  # Risk tab (scripts/risk.py); marked stale when it was built for an earlier run
    if os.path.exists(rp):
        try:
            rk = json.load(open(rp)); rk.pop("misses", None); rk["stale"] = rk.get("stamp") != summ.get("stamp"); out["risk"] = rk
        except ValueError as e:
            print(f"site_data: risk.json unreadable ({e})")
    ep = os.path.join(LATEST, "edges.json")  # Edges tab (scripts/edges.py); marked stale when built for an earlier run
    if os.path.exists(ep):
        try:
            ed = json.load(open(ep)); ed["run_stale"] = ed.get("run_utc") != summ.get("run_utc"); out["edges"] = ed
        except ValueError as e:
            print(f"site_data: edges.json unreadable ({e})")
    with open(os.path.join(LATEST, "site_data.json"), "w") as f:
        json.dump(clean(out), f, separators=(",", ":"), default=str, allow_nan=False)
    print(f"site_data: {len(games)} games, {len(T)} teams, {os.path.getsize(os.path.join(LATEST,'site_data.json'))//1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
