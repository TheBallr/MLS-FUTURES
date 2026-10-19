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
| public_spr_2026.csv | the SPR average-rank source, 2026 only |
| shade_sd020_k001.csv, shade_dc005.csv, shade_diag.csv - shade_diag4.csv | the conference shade re-tested at 0.20/0.01 and what it covers (CLAUDE.md 11c2, 11h; the diag runs came from scratchpad scripts not in the repo) |
| dc_rho0.csv, dc_rho-0.05.csv, dc_rho-0.08.csv | Dixon-Coles rho (11f) |
| dock0.2.csv, dock0.35.csv, dock0.5.csv, dockx0.35.csv, dockx0.5.csv | dead-club dock size, with and without the hopeless-club exemption (11g) |
| zac3_ratings.csv, zac3_sim.csv | Zac's three tests: ridge fade, posted lines in the fit (11i) |
| kf_ratings1.csv, kf_sim1.csv | the Kalman candidate, ratings and sim stages (13) |
| kf_final_sim.csv | the configuration applied on 2026-10-15 night at the filter's ratings (closest to live, but xG 25%, no club edges, team totals or tiebreaks) |

"live" in these files is the recipe of its day: the half-life least-squares fit with xG 25% (retired 2026-10-15). The sim stage
reads dc_rho and the dock from config.json at run time and does not record them per row, so re-running an old recipe today
silently differs from the file (CLAUDE.md 4 lists the fix for the backtest script).

Summaries and readings: CLAUDE.md sections 11a-11d. Summary CLI: `python3 scripts/backtest_season.py summary <csv> --baseline market_live --metric match_ll`.
