# outputs/calibration: which reports describe the live model

Live configuration (2026-10-19): Kalman-filter ratings on Pinnacle closes with this round's posted lines, xG 15%, club home
edges, rating_sd 0.10, drift 0.01, dc_rho -0.05, dead-club dock 0.5, shade off, team totals on, head-to-head and discipline
tiebreaks on. Anything produced before 2026-10-15 20:14Z ran on the retired half-life least-squares ratings (xG 25%) and most
of it at rating_sd 0.30, drift 0, dc_rho 0 and no dock. "live" inside a CSV from that period means that retired recipe.

Yardsticks today: `scripts/close_track.py` (ratings: the close a week out, CLAUDE.md 1 and 13) and the sim stage of
`scripts/backtest_season.py` (rating_sd, drift, dock, shade). The calib_* scripts are the 2026-10-12 programme (scripts/README.md).

| Report | Describes the live model? | Note |
|---|---|---|
| `match_checks.md` | yes (regenerated 2026-10-19 at dc_rho -0.05) | engine draw rate at the close's own margin and total 23.7% v devigged close 24.9% v realised 25.2% |
| `congestion.md` | yes (regenerated 2026-10-19 from `close_track/kf_var1.csv` recipe `kf`) | the previous file used the retired least-squares residuals and contradicted CLAUDE.md 13 |
| `shared_goals.md` | yes | fitted at rho 0; re-checked 2026-10-19 at -0.05: 0.05 v 0.10 tie (0.01468 v 0.01473), 0.10 stands |
| `team_totals.md` | yes | live hl 30 / ridge 0.25; offsets are a 2026-10-14 snapshot |
| `playoff_strength.md` / `.csv` | yes (method-independent) | season-only least-squares fits on purpose; saved console output |
| `home_total.md` / `.json` | partly | the 2026 row (+0.440 / 3.213) is what config uses; the closing "Recommendation 0.51 / 3.01" is NOT the frozen value (0.44 / 3.2) |
| `club_home.md` / `.json` | partly | the deltas are the live `data/ratings/home_edges.csv`; the held-out test was least squares, never re-tested inside the filter |
| `layers_log.csv` | partly | rows after 2026-10-15 20:14Z score ratings that already contain the posted lines (in sample) |
| `dead_teams.md`, `dead_teams_rows.csv` | historical | "vs ratings" (-0.36) is the least-squares market fit with a fixed 0.5 home edge; the dock was later checked at the filter's ratings in `backtest/kf_final_sim.csv` |
| `rating_sd.md/.json`, `drift.md`, `drift_k_grid.md/.json` | historical | 2026-10-12 replay on least-squares ratings; the grid answer moved 0.25 -> 0.30 between two runs minutes apart (noise); live values come from 11c/11d |
| `shade.md/.json` | historical | `{"conf": 1.5}` is NOT a live setting: the shade is off since 2026-10-15; the longshot rule it supported is retired (CLAUDE.md 6) |
| `replay.md` | historical | 68 of 105 checkpoints, at rating_sd 0.30 / drift 0 on least-squares ratings |
| `half_life.md/.json`, `scorecard.md/.json` | historical | least-squares fit and the next-ten-closes yardstick; under the filter there is no half-life and the blend is 85/15 |
| `clv.md` | historical | recommends posted-line shrink 0.55; live is 1.0 |
| `whatif_kalman_totals_2026-10-15.json` | historical | baseline = the afternoon of 2026-10-15 (least squares, xG 25%, sd 0.20, shade 1.5) |
| `backtest/*.csv` | historical except `kf_final_sim.csv` (partly: sd 0.10/0.01, rho -0.05, dock 0.5 but xG 25%, no club edges, totals or tiebreaks) | `backtest/README.md` indexes the files |
| `close_track/*.csv` | historical | no run includes the club home edges the live build uses; the closest to live is `xgmix1.csv` recipe `kfpx_w15`; `close_track/README.md` indexes the files |
