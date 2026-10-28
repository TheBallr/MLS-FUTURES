#!/usr/bin/env python3
"""Edges tab (Zac 2026-10-20; docs/edge_finding.md proposal 2, docs/bayesian_methods.md proposal 20). Writes
outputs/latest/edges.json, which site_data.py embeds. Display only: nothing here feeds the model.

For each market (MLS Cup; Eastern / Western Conference champion = our cup_finalist pool within the conference):
  ours       the run's fair probability (200k seasons; never the page's 20k Run)
  range      our futures-confidence range from risk.json (no recent lines / xG 0 or 30% / spread +6%), when it has one
  best       the best price across books, its break-even probability (the hold is inside it: it is what you pay)
  market     the median across books of each COMPLETE field, power-devigged (incomplete fields are compared raw only)
  pooled     our fair pooled with the market's in log odds at weight W on ours (provisional: no settled record yet)
  flag       the pooled price at the LOW end of our range still beats the best price's break-even: EV > 0 at the cautious
             end. Expect one or two per market; more is a reason to check the model before the market.
Usage: python3 scripts/edges.py"""
from __future__ import annotations
import csv, datetime as dt, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.teams import ROOT, conference_of
from scripts.odds_math import hold, power_devig, pool, prob_to_american

LATEST = os.path.join(ROOT, "outputs", "latest")
ODDS = os.path.join(ROOT, "data", "market", "futures_odds.csv")
W = 0.5            # weight on our fair in the pool; to be set from the bet log / CLV record (bayesian_methods.md 20)
STALE_H = 36       # prices older than this are marked stale
COMPLETE_MASS = 0.97
MARKETS = [("cup", "Win MLS Cup", "cup", "cup", None),   # labels = the page's pool names (Ratings tab, 2026-10-20)
           ("conf_east", "Reach MLS Cup · East", "cup_finalist", "cup_finalist", "East"),
           ("conf_west", "Reach MLS Cup · West", "cup_finalist", "cup_finalist", "West")]


def load_json(name):
    p = os.path.join(LATEST, name)
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    mk = load_json("markets.json")
    run = load_json("run_summary.json") or {}
    risk = load_json("risk.json") or {}
    if not mk:
        print("edges: no markets.json (run run_sim.py first)")
        return 1
    conf = conference_of()
    rng = {}
    for r in (risk.get("confidence") or {}).get("rows", []):
        for k, c in r["cells"].items():
            rng[(r["team"], k)] = c
    prices = []
    if os.path.exists(ODDS):
        with open(ODDS) as f:
            prices = [r for r in csv.DictReader(f) if r.get("price_decimal")]
    now = dt.datetime.now(dt.timezone.utc)
    fetched = max((r["fetched_at"] for r in prices), default=None)
    age_h = None
    if fetched:
        try:
            age_h = (now - dt.datetime.fromisoformat(fetched.replace("Z", "+00:00"))).total_seconds() / 3600
        except ValueError:
            pass
    out_m, notes = [], []
    for key, label, pool_key, rng_key, cf in MARKETS:
        ours = {t: float(v["prob"]) for t, v in mk[pool_key].items() if cf is None or conf.get(t) == cf}
        rows_m = [r for r in prices if r["market"] == key and r["team"] in ours]
        by_book = {}
        for r in rows_m:
            d = float(r["price_decimal"])
            b = by_book.setdefault(r["book"], {})
            b[r["team"]] = max(d, b.get(r["team"], 0))
        books, fair_by_book = [], {}
        for b, field in sorted(by_book.items()):
            mass = sum(ours[t] for t in field)
            imp = [1 / d for d in field.values()]
            complete = mass >= COMPLETE_MASS and sum(imp) >= 1
            books.append({"book": b, "n": len(field), "hold": round(hold(imp), 4), "complete": complete, "covers": round(mass, 3)})
            if complete:
                fair_by_book[b] = dict(zip(field.keys(), power_devig(imp)))
        rows = []
        for t, p in ours.items():
            quotes = {b: f[t] for b, f in by_book.items() if t in f}
            if p < 0.001 and not quotes:
                continue
            c = rng.get((t, rng_key))
            lo = max(1e-4, p - (c["live"] - c["lo"]) / 100) if c else None
            hi = min(0.9999, p + (c["hi"] - c["live"]) / 100) if c else None
            row = {"team": t, "ours": round(p, 3), "lo": round(lo, 5) if lo else None, "hi": round(hi, 5) if hi else None,
                   "quotes": {b: round(d, 3) for b, d in quotes.items()}, "n_books": len(quotes)}
            fairs = [fb[t] for fb in fair_by_book.values() if t in fb]
            mkt = statistics.median(fairs) if fairs else None
            row["market"] = round(mkt, 5) if mkt is not None else None
            if quotes:
                bb, bd = max(quotes.items(), key=lambda kv: kv[1])
                be = 1 / bd
                row["best"] = {"book": bb, "dec": round(bd, 3), "am": prob_to_american(be), "be": round(be, 5)}
                row["edge_pts"] = round((p - be) * 100, 2)
                row["ev"] = round(p * bd - 1, 4)
                if mkt is not None:
                    pp = pool(p, mkt, W)
                    pl = pool(lo if lo else p, mkt, W)
                    row["pooled"] = round(pp, 5)
                    row["pooled_ev"] = round(pp * bd - 1, 4)
                    row["cautious_ev"] = round(pl * bd - 1, 4)
                    row["flag"] = pl * bd - 1 > 0
            rows.append(row)
        rows.sort(key=lambda r: (-(r.get("cautious_ev") if r.get("cautious_ev") is not None else -9), -r["ours"]))
        nflag = sum(bool(r.get("flag")) for r in rows)
        if nflag > 3:
            notes.append(f"{label}: {nflag} flags. More than a market usually offers; check the model before the market.")
        if by_book and not fair_by_book:
            notes.append(f"{label}: no book posts a complete field, so there is no devigged market to pool with; raw prices only.")
        out_m.append({"key": key, "label": label, "books": books, "rows": rows, "flags": nflag})
    out = {"asof": run.get("asof"), "run_utc": run.get("run_utc"), "n_seasons": run.get("n_seasons"), "w": W,
           "fetched_at": fetched, "age_h": round(age_h, 1) if age_h is not None else None,
           "stale": bool(age_h is not None and age_h > STALE_H), "source": "The Odds API" if prices else None,
           "n_prices": len(prices), "markets": out_m, "notes": notes,
           "built_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    json.dump(out, open(os.path.join(LATEST, "edges.json"), "w"), indent=1)
    tot = sum(m["flags"] for m in out_m)
    print(f"edges: {len(prices)} book prices" + (f", {tot} flagged (" + ", ".join(f"{m['label']} {m['flags']}" for m in out_m) + ")" if prices else
          " (none on file: add ODDS_API_KEY for fetch_odds.py)") + (" · STALE prices" if out["stale"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
