# scripts/: what each one is for (2026-10-19)

**Live pipeline** (run by the scheduled tasks; CLAUDE.md 9)
- `weekly.py`: the 8:52 ET task's entry point: fetches, then on a completed match-day `apply_site_settings`, `fetch_xg`,
  `fetch_public opta`, `run_sim`, `risk`, `site_data`, `build_site`.
- `run_sim.py`: ratings (`refresh_ratings.build_ratings`), every remaining fixture, 200k seasons, markets; archives the run
  in `outputs/runs/<stamp>/`. `refresh_ratings.py`: the ratings (Kalman filter + posted lines + xG + hand). `what_if.py`:
  futures under other knobs, writes nothing (its `xg_w` drops hand adjustments: CLAUDE.md 4).
- `risk.py`: the Risk tab (`outputs/latest/risk.json`) and `data/ratings/ratings_history.csv`.
- `site_data.py` -> `build_site.py` -> `check_site.py`: the page and its headless check.
- `apply_site_settings.py`: the page's saved edits (hand log, xG share) into the model.
- Fetchers: `fetch_results.py` (ESPN, also refreshes the schedule), `fetch_pinnacle.py` (posted lines; `--close` ten minutes
  before kickoff), `fetch_optic.py` (OpticOdds daily pull, needs the key), `fetch_xg.py` (ASA), `fetch_injuries.py`
  (sportsgambler), `fetch_public.py opta` (sanity anchor), `news_scan.py` (7:40 task), `close_schedule.py` (capture slots),
  `clv_log.py` (opener v close log, called by run_sim), `disc_points.py` (discipline tiebreak; by hand, needs Optic data).
- Helpers: `common.py`, `optic_client.py`, `optic_lines.py`, `check_secrets.py` (before every push), `add_result.py`
  (a manual result), `price_market.py` (any market from a run's archive).

**Yardsticks and research** (run by hand)
- `close_track.py`: the ratings yardstick (tracking the close a week out). `backtest_season.py`: the rest-of-season
  backtest (variance, dock, shade). `replay.py`: loaders shared by both.
- `congestion.py` (rest and cup congestion v the close), `public_sources.py` (Opta / g+ / footballdatabase loaders),
  `calib_team_totals.py` (per-team totals), `calib_club_home.py` (club home edges; season-end re-fit with `--write`).
- One-off setup: `fetch_schedule.py`, `fetch_history.py`, `harvest_optic.py` + `optic_flatten.py`.

**Historical** (the 2026-10-12 calibration programme on the retired least-squares ratings; each says so in its docstring;
kept so the frozen knobs' evidence can be reproduced, not to be re-run as a procedure): `calib_half_life.py`,
`calib_home_total.py`, `calib_shared_goals.py`, `calib_rating_sd.py`, `calib_drift.py`, `calib_shade.py`,
`calib_replay.py`, `calib_clv.py`, `rating_scorecard.py`, `dead_teams.py`, `match_checks.py` (re-run 2026-10-19 at the live
rho), `playoff_strength.py`.
