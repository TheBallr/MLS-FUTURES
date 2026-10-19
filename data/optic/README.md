# data/optic — the OpticOdds harvest

One-off harvest of everything the trial key reaches for MLS (build prompt section 4a), written by
`scripts/harvest_optic.py`; the daily `scripts/fetch_optic.py` adds to `raw/daily/`, `raw/odds_historical/` and `raw/injuries/`.
The key is never stored here or anywhere in the repo; it lives in the environment variable `OPTIC_API_KEY` for a session.

Status: **harvested 2026-10-12/13.** MLS fixtures 2024-2026 (1575), results and team stats for every completed fixture, Pinnacle
historical odds (olv/clv) for 1482 MLS fixtures (2024's 522 files are empty: the feed's Pinnacle history starts in 2025), the
other five books for the 960 completed 2025-2026 fixtures, Pinnacle history for Leagues Cup (124), CONCACAF Champions Cup (102),
U.S. Open Cup (173) and Canadian Championship (39), one futures snapshot (Pinnacle had no MLS futures posted), one current-odds
snapshot, the injury feed, teams and players. 114 MB of gzipped raw JSON. Re-running any stage skips files on disk.

Layout once run:

```
manifest_<stage>.json              one per harvest stage (catalogue, cups, current, futures, pinnacle, books, results): leagues found, books, seasons, call count, whether the key went dark
fixtures_<league>.csv              flattened fixtures per competition (mls, leagues_cup, concacaf_champions_cup, us_open_cup, canadian_championship)
raw/catalogues/                    sports, leagues (soccer), sportsbooks, markets (soccer), teams_mls, players_mls
raw/fixtures/<league>_<season>.json   every page of /fixtures per season (status, scores where carried, venue, season_week)
raw/results/<league>/<id>.json     /fixtures/results, five fixtures per file: scores and team stats (shots, SoT, etc.) for the form-source study
raw/odds_historical/<league>/<book>/<fixture>.json   /fixtures/odds/historical: every price change, opener and close (clv field) per book
raw/odds_current/<league>/<stamp>_*.json   current lines for upcoming fixtures, all books, at harvest time
raw/futures/                       futures list and every book's current MLS futures (Shield, Cup, conferences, points totals, playoffs)
raw/injuries/<date>.json           the injury feed (team, player, status, type)
raw/daily/                         fetch_optic.py's daily fixture pulls
```

Order of value: Pinnacle's historical odds (the calibration set for shared goals, the posted-line shrink, the CLV test and the
half-life grid) first, then the other books, then results and stats.

Used by the model today (2026-10-19): `lines_pinnacle.csv` (openers for close_track and calib_clv), `results_mls.csv` (team stats
for disc_points.py), `fixtures_*.csv` and the raw Pinnacle / results / fixtures files (optic_flatten rebuilds from them).
Not read by anything: `lines_{bet365,betfair,draftkings,fanduel,ps3838}.csv`, the cups' `lines_pinnacle_*` and `results_*`, and
raw/odds_current, raw/futures, raw/daily (kept as the record of a trial key that may lapse). The live closes are in
data/market/closing_lines.csv (precedence: OpticOdds Pinnacle close > the 10-minute capture > football-data's average close).
