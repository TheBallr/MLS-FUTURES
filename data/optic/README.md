# data/optic — the OpticOdds harvest

One-off harvest of everything the trial key reaches for MLS (build prompt section 4a), written by
`scripts/harvest_optic.py`; the daily `scripts/fetch_optic.py` adds to `raw/daily/`, `raw/odds_historical/` and `raw/injuries/`.
The key is never stored here or anywhere in the repo; it lives in the environment variable `OPTIC_API_KEY` for a session.

Status: **not yet run**. The container's egress policy denies `api.opticodds.com` (see CLAUDE.md, Blockers). The script is
resumable: re-run it after the host is allowed and it skips every raw file already on disk.

Layout once run:

```
manifest.json                      leagues found, books, seasons, call count, whether the key went dark
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
