# PLAN.md — the method (kept current; CLAUDE.md holds the decisions and measurements)

## Ratings (section 5 of the build prompt)
A rating is a club's strength in goals of expected margin against a league-average side on a neutral pitch, centred at zero
across the 30 clubs. `data/ratings/sources.csv` holds every source side by side; `blend.csv` is regenerated every run from the
enabled sources and their weights in `source_config.csv`.

1. **market_recent** (backbone): weighted least squares on Pinnacle's closing lines, weight 0.5^(age/half_life), half-life 14
   days to start. Target per match `gd_fit`: the handicap-implied expected margin at the match's own total (three-way power
   devigged -> margin at the posted total; the main Asian handicap wins where it exists). Closes only; posted lines never
   enter the fit. Home edge is a frozen knob (fitted league-wide from the closes by the calibration programme), not re-fitted
   daily. Ridge toward zero (`ridge_lambda`) and a sum-to-zero constraint.
2. **xg** (ASA): WLS on match-level xG difference, half-life 45 days, ridge, rescaled to the market's spread; 25% of the blend.
   **Opta Power Rankings** is the public sanity anchor: fetched daily, shown next to the blend rescaled, never weighted.
3. **Blend**: market 1.0 / xg 1.0 to start; three-way backtest grid monthly; keep 50/50 unless the grid separates cleanly.
4. **Posted-line shrink**: a fixture with a fresh Pinnacle line (fetched within 3 days) is priced at (1-s) ratings + s Pinnacle,
   s = 0.35 to start; set from MLS data at 150 opener/close pairs. Manual overrides mix at 1.0.
5. **Expansion prior**: fewer than ten closes -> mean first-season expansion rating, blended toward the fit as closes arrive.
6. **Hand adjustments** in `adjustments.csv`, goals, on Zac's word only.
7. **Scorecard** (`scripts/rating_scorecard.py`): every source on the next ten closes over every history season; numbers in CLAUDE.md.

## Match engine (section 6)
g = R_h - R_a + home_edge + layers; with a fresh line g = (1-s) g + s g_pinnacle. T = avg_total (or the posted total).
home mean = max(T/2 + g/2, floor), away mean = max(T/2 - g/2, floor); shared Poisson c (mean `shared_goals_mean`, capped) added
to both sides, the independent parts reduced by c. E[margin] = g exactly. H/D/A from the analytic 0-10 grid; the season
engine samples. Knockouts: same model, a draw is a coin flip; best-of-three = majority of three games, higher seed hosts 1 and 3.

## Season engine (section 7)
200,000 seasons, fixed seed. Per season one rating draw per team ~ N(rating, rating_sd); every unplayed fixture in date order;
real results locked in; after each simulated match both ratings move by clip(drift_k x surprise, ±drift_cap), surprise = actual margin minus the
expected margin the dice used (shrink included); real results never feed drift. rating_sd 0.20 / drift_k 0.01 since 2026-10-15,
set on the rest-of-season backtest (`scripts/backtest_season.py`), which is the yardstick for ratings and variance. Standings by points then the MLS chain (wins, gd, gf, fewest disciplinary points, away gd, away gf, home gd, home gf,
coin toss) for the league table (Shield, Spoon) and each conference (seeds). Playoffs from the conference tables with the
2026 bracket (9 per conference; 8 v 9 Wild Card; Round One best-of-three 1vWC, 2v7, 3v6, 4v5; single-match semis and finals,
higher seed hosts; MLS Cup hosted by the better regular-season record). Scenarios drawn per season from their own RNG stream
(points deductions before standings; availability windows as a rating penalty). Archive `seasons.npz`: points, wins, gd,
league_pos, conf_seed, playoff stage. `scripts/price_market.py` prices any market after the fact. The shade lives in
`sim/markets.py` only; `prob_raw` is always kept.

## Calibration programme (section 8), in order, each a script and a report in outputs/calibration/
1. home edge and average total from the closes; 2. half-life grid 7/14/21/28; 3. shared goals from Pinnacle's alternate ladders
and realised variance; 4. rating_sd from the points backtest (keep the points answer; carry the position difference as the
shade); 5. drift from a Kalman fit of closing-line ratings; 6. the shade per pool, leave-one-season-out; 7. the longshot rule;
8. season replay against an equal-ratings benchmark at seven checkpoints; 9. the CLV test at 150 opener/close pairs.
Then the frozen-knob rule: rating_sd, drift_k_sim, drift_cap, shared_goals_mean, home_edge_goals, avg_total_goals are frozen for
the season; a re-set needs Zac's word, the evidence in the config note, and a date.

## Layers (section 9)
Injuries and call-ups: value in goals per match by tier (star 0.20, key 0.10, starter 0.05, squad 0.02; doubt half), penalty per
fixture net of what the closes have absorbed (s = share of the half-life weight from closes inside the absence);
penalty = value x ((1 - prob_out if absent else 1) - (1 - prob_out x s)). Off by default; on only if the gap to Pinnacle falls.
Scenarios (`scenarios.csv`): points or availability rows, Zac's; scenario teams exempt from the shade.
Congestion, rest, Decision Day: measure in the residuals first; default no knob.
