#!/usr/bin/env python3
"""Flatten the OpticOdds raw harvest into CSVs and feed the model's files:
  data/optic/lines_<book>.csv      one row per fixture and phase (open/close): h, d, a, main AH, main total (decimal)
  data/optic/ladders_pinnacle.csv  every Pinnacle handicap and total line at the close (shared-goals calibration)
  data/market/closing_lines.csv    Pinnacle closes for the current season (book pinnacle_close; outranks pinnacle_last)
  data/history/OPTIC_<season>.csv  Pinnacle closes with AH and totals for past seasons (preferred over football-data's three-way rows)
  data/optic/results_<league>.csv  scores and team stats from /fixtures/results
Usage: python3 scripts/optic_flatten.py"""
from __future__ import annotations
import glob, gzip, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from scripts.optic_lines import lines_from_odds, ladder_rows
from scripts.common import parse_utc, et_date, utc_iso
from sim import data
from sim.knobs import load_config
from sim.teams import ROOT, canon, UnknownTeam

OUT = os.path.join(ROOT, "data", "optic"); RAW = os.path.join(OUT, "raw")


def load_gz(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def flatten_lines(league_tag: str) -> dict[str, pd.DataFrame]:
    out = {}
    ladders = []
    unknown = set()
    for bookdir in sorted(glob.glob(os.path.join(RAW, "odds_historical", league_tag, "*"))):
        book = os.path.basename(bookdir)
        rows = []
        for p in sorted(glob.glob(os.path.join(bookdir, "*.json.gz"))):
            try:
                j = load_gz(p)
            except Exception:
                continue
            for fx in (j.get("data") or []):
                hn, an = fx.get("home_team_display"), fx.get("away_team_display")
                if league_tag == "mls":
                    try:
                        home, away = canon(hn), canon(an)
                    except UnknownTeam as e:
                        unknown.add(str(e)); continue
                else:
                    home, away = canon(hn, strict=False) or hn, canon(an, strict=False) or an
                ko = parse_utc(fx["start_date"])
                base = {"fixture_id": fx["id"], "date": et_date(ko), "kickoff_utc": utc_iso(ko), "home": home, "away": away, "season": fx.get("season_year") or ko.strftime("%Y"), "book": book}
                for phase, label in (("olv", "open"), ("clv", "close")):
                    r = lines_from_odds(fx.get("odds", []), hn, an, phase)
                    if r["h"] or r["ah_line"] != "":
                        rows.append(dict(base, phase=label, **r))
                if book == "pinnacle":
                    for lr in ladder_rows(fx.get("odds", []), hn, an, "clv"):
                        ladders.append(dict({k: base[k] for k in ("fixture_id", "date", "home", "away", "season")}, **lr))
        if rows:
            df = pd.DataFrame(rows); out[book] = df
            df.to_csv(os.path.join(OUT, f"lines_{book}{'' if league_tag == 'mls' else '_' + league_tag}.csv"), index=False)
    if ladders and league_tag == "mls":
        pd.DataFrame(ladders).to_csv(os.path.join(OUT, "ladders_pinnacle.csv"), index=False)
    if unknown:
        print(f"optic_flatten: unknown names: {sorted(unknown)}", file=sys.stderr)
    return out


def flatten_results():
    for lg in sorted(glob.glob(os.path.join(RAW, "results", "*"))):
        tag = os.path.basename(lg); rows = []
        for p in sorted(glob.glob(os.path.join(lg, "*.json.gz"))):
            try:
                j = load_gz(p)
            except Exception:
                continue
            for r in j.get("data", []):
                fx = r.get("fixture") or {}; sc = r.get("scores") or {}
                row = {"fixture_id": fx.get("id"), "start_date": fx.get("start_date"), "home": fx.get("home_team_display"), "away": fx.get("away_team_display"),
                       "home_score": (sc.get("home") or {}).get("total"), "away_score": (sc.get("away") or {}).get("total"), "season_year": fx.get("season_year"), "season_week": fx.get("season_week")}
                stats = r.get("stats") or {}
                for side in ("home", "away"):
                    for per in (stats.get(side) or []):
                        if per.get("period") in ("all", "full_time", "match", "total") or len(stats.get(side) or []) == 1:
                            for k, v in (per.get("stats") or {}).items():
                                row[f"{side}_{k}"] = v
                rows.append(row)
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(OUT, f"results_{tag}.csv"), index=False)
            print(f"optic_flatten: results_{tag}.csv {len(rows)} rows")


def feed_model(lines: dict[str, pd.DataFrame], season: int):
    pin = lines.get("pinnacle")
    if pin is None:
        print("optic_flatten: no Pinnacle lines"); return
    close = pin[pin["phase"] == "close"].copy()
    cols = ["date", "kickoff_utc", "home", "away", "book", "h", "d", "a", "ah_line", "ah_home", "ah_away", "total_line", "over", "under", "fetched_at", "fixture_id"]
    close["book"] = "pinnacle_close"; close["fetched_at"] = close["kickoff_utc"]
    cur = close[close["season"].astype(str) == str(season)][cols]
    cl = data.load("closing_lines")
    key = ["date", "home", "away"]
    keep = cl[~cl.set_index(key).index.isin(cur.set_index(key).index)] if len(cl) else cl
    merged = pd.concat([keep, cur], ignore_index=True).sort_values(["kickoff_utc", "home"])
    data.save("closing_lines", merged)
    print(f"optic_flatten: closing_lines.csv {len(cur)} Pinnacle closes for {season} ({len(merged)} rows total)")
    # past seasons -> history files with scores from fixtures_mls.csv
    fx = pd.read_csv(os.path.join(OUT, "fixtures_mls.csv"), dtype=str, keep_default_na=False) if os.path.exists(os.path.join(OUT, "fixtures_mls.csv")) else pd.DataFrame()
    scores = {r["fixture_id"]: (r["home_score"], r["away_score"]) for r in fx.to_dict("records")} if len(fx) else {}
    for s, g in close.groupby("season"):
        if str(s) == str(season):
            continue
        g = g.copy(); g["hg"] = g["fixture_id"].map(lambda i: scores.get(i, ("", ""))[0]); g["ag"] = g["fixture_id"].map(lambda i: scores.get(i, ("", ""))[1])
        g = g[(g["hg"] != "") & (g["ag"] != "")]
        g[["season", "date", "home", "away", "hg", "ag", "h", "d", "a", "book", "ah_line", "ah_home", "ah_away", "total_line", "over", "under"]].to_csv(os.path.join(data.HISTORY, f"OPTIC_{s}.csv"), index=False)
        print(f"optic_flatten: history OPTIC_{s}.csv {len(g)} matches with Pinnacle AH/total closes")


def main():
    cfg = load_config()
    lines = flatten_lines("mls")
    for tag in ("leagues_cup", "concacaf_champions_cup", "us_open_cup", "canadian_championship"):
        if os.path.isdir(os.path.join(RAW, "odds_historical", tag)):
            flatten_lines(tag)
    for b, df in lines.items():
        print(f"optic_flatten: lines_{b}.csv {len(df)} rows ({(df['phase']=='close').sum()} closes)")
    flatten_results()
    feed_model(lines, cfg["season"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
