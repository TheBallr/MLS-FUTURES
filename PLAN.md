# PLAN.md: the method as it runs today

Values below are the live configuration as of 2026-10-19. `config.json` is the source of truth for every knob (each has a
dated note), CLAUDE.md section 5 is the decisions log (why each value is what it is), and `data/ratings/method_log.csv` lists
every applied ratings, pricing or sim change with its time. `MLS_BUILD_PROMPT.md` is the original 2026-10-12 spec; where it
differs from this file, this file and config.json win.

## 1. Ratings (`scripts/refresh_ratings.py`, `sim/kalman.py`, `sim/ratings.py`)
A rating is a club's strength in goals of expected margin against a league-average side on a neutral pitch, centred at zero
over the 30 clubs.

- **Market source (85%)**: a Kalman filter over every Pinnacle close on file, 2012-2026 (`rating_method kalman`). Each close's
  target `gd_fit` is the expected margin implied by the devigged three-way price at the match's own total (the main Asian
  handicap wins where it exists), net of the league home edge as fitted month by month (90-day half-life) and the home club's
  delta (`data/ratings/home_edges.csv`, `club_home_edge_enabled`). One random-walk strength per club: process sd
  `kalman_q_day` 0.03 per day (gaps capped at 30 days), close sd `kalman_s` 0.25. Any league-wide gap of 45 days or more is
  treated as an off-season: strengths revert 25% toward the mean (`kalman_off_shrink` 0.75) and variance grows by
  `kalman_q_off` 0.10. The 2026 World Cup pause (53 days) triggered this on Jul 16; measured 2026-10-19, that tracks the
  close better afterwards than not shrinking (0.278 v 0.291 goals rmse a week out), so it stays.
- **Posted lines in the fit** (`posted_in_fit`): the current round's Pinnacle lines fetched within 3 days enter as
  measurements with sd 0.22 (`kalman_s_posted`). Closes for the same fixture replace them once captured.
- **xG source (15%)**: weighted least squares on ASA match xG difference (half-life 45 days, ridge `ridge_lambda` 0.5),
  rescaled to the market source's spread (`sim.ratings.xg_fit`).
- **Blend**: `data/ratings/source_config.csv` weights (0.85 / 0.15), re-centred. Regenerated every run, never edited.
- **Hand adjustments**: Zac's, in goals, on top of the blend, in `data/ratings/hand_log.csv` (weeks Tuesday to Monday ET,
  a week carries the previous week's values until saved). `adjustments.csv` is only for dated fixture-window rows; an
  open-ended row there would be added on top of the log.
- **Expansion prior**: a club with fewer than 10 closes is blended toward -0.25 (`expansion_prior_rating`), which is also
  the filter's prior mean for a new club.
- Order of precedence for one match's close: OpticOdds Pinnacle close > the 10-minute capture (`pinnacle_last`) >
  football-data's market-average close (`avg_close`). 34 games of 2026 (Aug 16 to Oct 1) have only the average close.

## 2. Match engine (`sim/engine.py`)
g = R_home - R_away + home_edge_goals (0.44) + club delta + fixture hand + layers. A fixture with a fresh posted Pinnacle line
is priced off the line (`posted_line_shrink` 1.0: g = g_pinnacle). Total T: the posted total, else the league base plus both
clubs' offsets (`team_totals_enabled`, half-life 30, ridge 0.25, clipped to 2.0-4.5). Home mean = max(T/2 + g/2, 0.15),
away mean = max(T/2 - g/2, 0.15); a shared Poisson component (mean 0.10) is added to both sides; Dixon-Coles rho -0.05 on the
four low scorelines (draws). Knockouts: a level game after 90 minutes is a coin flip; best-of-three = majority of three.

## 3. Season engine (`sim/season.py`, `sim/standings.py`, `sim/playoffs.py`, `sim/markets.py`)
200,000 seasons, seed 20260. Per season one rating draw per club ~ N(rating, `rating_sd` 0.10); every unplayed fixture in date
order with real results locked in; after each simulated match both ratings move by clip(0.01 x surprise, ±0.10)
(`drift_k_sim`, `drift_cap`), surprise = actual margin minus the margin the dice used; real results never feed drift.
**Dead-club dock**: once a club is mathematically out of the playoffs inside a simulated season its rating drops 0.5 goals
(`dead_dock_goals`), except clubs already under 2% playoff odds entering the run (`dead_dock_min_odds`, a quick pre-pass).
**Standings**: points, wins, goal difference, goals for, head-to-head inside the conference (`tiebreak_h2h`), fewest
disciplinary points (`disc_points_enabled`, `data/discipline/`), away gd, away gf, home gd, home gf, coin toss.
**Playoffs**: 9 per conference; 8 v 9 Wild Card hosted by the 8 seed; Round One best-of-three 1 v WC, 2 v 7, 3 v 6, 4 v 5
(higher seed hosts games 1 and 3); single-match semis and finals hosted by the higher seed; MLS Cup hosted by the better
regular-season record. Markets from the archive; the shade (`shade`, `sim/markets.py`) is 1.0, i.e. off, and `prob_raw` is
always kept. Settings that live only in code: `playoff_spots` 9, `rating_sd_top`, `spread_sd` (unused).

## 4. Layers (`sim/layers.py`), all off unless noted
Injuries and call-ups (`injury_layer_enabled`, `callup_layer_enabled`: off; measured every run as `layer_full`). Scenarios
(`scenarios.csv`, empty): points or availability rows on Zac's word. Rest and congestion: measured (CLAUDE.md 13), no knob.

## 5. Yardsticks and the frozen-knob rule
- **Ratings**: how closely they track Pinnacle's close a week out (`scripts/close_track.py`; the current recipe scores 0.243
  goals rmse over 15 seasons). The Risk tab shows the same number for the last 30 days.
- **Variance and sim knobs** (rating_sd, drift, dock, shade): the rest-of-season backtest (`scripts/backtest_season.py`).
- Frozen for the season: rating_sd, drift_k_sim, drift_cap, shared_goals_mean, home_edge_goals, avg_total_goals. A re-set
  needs the backtest, Zac's word, the evidence in the config note, a date, and a row in `method_log.csv`.
- What-ifs: `scripts/what_if.py` (futures under other knobs, writes nothing).

## 6. Pipeline (`scripts/weekly.py`, run by the 8:52 ET task)
fetch results -> Pinnacle lines -> OpticOdds (when the key is present) -> capture slots; if a match-day finished since the
last run: apply saved site settings -> xG -> Opta anchor -> `run_sim.py` (ratings, 200k seasons, archive in
`outputs/runs/<stamp>/`) -> `risk.py` (Risk tab) -> `site_data.py` -> `build_site.py`, then publish `outputs/latest/site.html`.
The 7:40 ET task fetches results and injuries and scans the news; one-shot tasks capture Pinnacle's line ten minutes before
each kickoff (`fetch_pinnacle.py --close`).
