# Rest-of-season backtest (2026-10-15)

`scripts/backtest_season.py`: six checkpoints per season (matchweeks 4, 9, 14, 19, 24, 29), 15 seasons 2012-2026, ratings
built strictly before the checkpoint, results before it locked, remainder simulated (4000 seasons, paired seeds).
Scores: remaining-match H/D/A log-loss of the actual results from the static ratings (`match_ll`), rmse vs the remaining
closes (`close_rmse`), analytic expected final points rmse (`pts_rmse_static`); sim: log-pmf of actual final points
(`points_logpmf`), PIT tail share (`tails`, 0.20 honest), playoffs / conference / shield / spoon log-loss.

| file | what |
|---|---|
| ratings_grid1.csv | market half-life x ridge, spread multipliers, xG blends (146 recipes) |
| public_opta_fdb.csv, public_gplus.csv, public_fdb3.csv | Opta, footballdatabase, ASA g+ alone and blended |
| sim_grid1.csv | market_live / live / xG-90 blend x rating_sd {0,.1,.2,.3,.4} x drift {0,.005,.01,.02} |
| sim_grid2.csv, sim_grid3.csv | live blend, finer ridge and pure-drift pairs |

Summaries and readings: CLAUDE.md sections 11a-11d. Summary CLI: `python3 scripts/backtest_season.py summary <csv> --baseline market_live --metric match_ll`.
