# Close-tracking runs (`scripts/close_track.py`, CLAUDE.md 1 and 13)

One row per scored close: recipe, lag (0 = morning of the match, 7 = a week out), season, date, phase, home, away, cross
(cross-conference), y_close and y_model (expected home margin net of the league home edge). The recipe dictionaries were
passed on the command line and are not saved; CLAUDE.md 13 describes them. None of these runs passes the club home edges the
live build uses (`club_home_edge_enabled`), so each sits a little off the live recipe (up to 0.04 goals per club).

| file | recipes |
|---|---|
| kf_grid1.csv, kf_grid2.csv | the filter's q_day / s / q_off grid (67 pairs) |
| kf_var1.csv | filter variants: posted lines, xG blended v fused, openers, spread, priors; `kf` is the plain filter |
| kf_var2.csv | posted lines + xG combinations |
| kf_var3.csv | off-season reversion (`phi` = kalman_off_shrink), rest adjustment |
| wls1.csv | the half-life least-squares fit, including the retired "live" recipe of 2026-10-12 to 10-15 |
| xgmix1.csv | xG weight and xG tempered with goals; `kfpx_w15` (filter + posted + xG 15%) is the closest to today's live recipe |

Note: xG rows were dated by UTC until 2026-10-19 (about half of all games sat a day late), so the goals-tempered xG test in
xgmix1.csv joined only half the games; re-run it before relying on "goals-tempered xG is worse".
Summary: `python3 scripts/close_track.py summary <csv> --lag 7 --baseline <recipe>`.
