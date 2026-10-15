# CLAUDE.md — MLS Futures: operating rules, decisions, measurements

The living document. Future sessions start here. Written as the work happens, never at the end.
Build prompt: `MLS_BUILD_PROMPT.md` (the Prem-Futures method applied to Major League Soccer). Method summary: `PLAN.md`.

## 0. How to work (from the build prompt; non-negotiable)
- Zac (Sierra Advisory LLC) does not code. Everything through chat; outputs on the private website. No gambling caveats,
  no definitions of devig/EV/CLV/hold/vig, no risk lectures. Lead with the answer; short replies; flag uncertainty first.
- Zac makes the calls. Propose changes in the model's own terms, numbered ("1. Messi MIA star, out Jun 3 to Jun 20") so he
  can reply "do 1, 3". Never change a tier, a team rating, a scenario or a calibrated knob unprompted. Routine maintenance
  (new injury names at squad tier, dates from a dated source, fetches, runs, publishing) is done and said.
- Git: commit after every piece of work; push to the branch given; every run archived under `outputs/runs/<stamp>/`.
- Secrets: `OPTIC_API_KEY` lives only in the environment (this session keeps it at `/root/.config/optic/key`, mode 600,
  outside the repo). `python3 scripts/check_secrets.py` before every push. The Pinnacle guest key is the site's public one.

## 1. The yardstick
Since 2026-10-15 (Zac, later the same day, superseding the morning's rule): **the ratings are judged on how closely they track
Pinnacle's close** (`scripts/close_track.py`, section 13): walk-forward over every match date of 15 seasons, each close scored
from the ratings a week out (lag 7, what the futures sim uses once the current round is priced off the posted line) and on
the morning of the match (lag 0); rmse of expected margin, bias, slope of the close on the model (1.0 = right spread), and the
cross-conference gap. The rest-of-season backtest (section 11) stays the yardstick for the variance pair (rating_sd, drift),
the dock and the shade, and is reported alongside for any ratings change. Pinnacle is the only match-line source and the only futures comparison. Kalshi, Polymarket
and soft-book prices never enter the model. Match games are not bet; futures edges are Zac's, by hand, from the site.

## 2. Rules that must not be broken
- Frozen knobs (section 6 below) once calibrated: `rating_sd`, `drift_k_sim`, `drift_cap`, `shared_goals_mean`,
  `home_edge_goals`, `avg_total_goals`. A price looking wrong is a ratings question, never a variance question. A re-set needs
  the rest-of-season backtest (section 11) and Zac's word; last re-set 2026-10-15 (rating_sd 0.20, drift_k_sim 0.01).
- The blend is regenerated, never edited. Judgment goes in `adjustments.csv`, injury tiers, call-ups, scenarios, on Zac's word.
- Real results never feed drift. Posted lines never enter the ratings fit; a fixture with a fresh Pinnacle line is priced off
  Pinnacle (posted_line_shrink 1.0 since 2026-10-15, the PDF's current-round rule); every later fixture off the ratings.
- Full rerun every time; same seed and inputs give identical output; `python3 tests/run_tests.py` after any engine change;
  say in plain words when a change moves probabilities and by how much.
- Only complete pools are devigged (power method). One-sided prices are compared raw.
- No standing requests at the end of replies.

## 3. MLS 2026 structure as encoded (verified 2026-10-12 by web search; mlssoccer.com itself is unreachable from this container)
| Item | Value | Source / status |
|---|---|---|
| Clubs | 30, East 15 / West 15 (San Diego FC in the West; no 2026 expansion side) | mlssoccer.com preseason predictions article; `data/teams.csv` |
| Regular season | 34 matches per club, 510 total, Feb 21 to Decision Day Nov 7 | mlssoccer.com "2026 schedule: most important dates" |
| World Cup pause | May 25 to Jul 16 (play resumes Jul 16-17) | same |
| Playoffs | 9 per conference; Wild Card 8 v 9 (Nov 18, PKs if drawn, no extra time); Round One best-of-three Nov 20 - Dec 2 (higher seed hosts 1 and 3, every game has a winner); Conf semis Dec 5-6 and finals Dec 11-12 single matches; MLS Cup Dec 18 hosted by the better regular-season record | mlssoccer.com "Audi 2026 MLS Cup Playoffs format" |
| Bracket | 1 v WC, 2 v 7, 3 v 6, 4 v 5; semis (1/WC) v (4/5), (2/7) v (3/6); Wild Card hosted by the 8 seed, PKs if level (no extra time); Round One best-of-three, higher seed hosts 1 and 3, PKs if level; semis and finals single matches hosted by the higher seed, extra time then PKs; MLS Cup hosted by the finalist higher in the Shield standings | VERIFIED 2026-10-15 night on https://www.mlssoccer.com/news/2026-mls-competition-guidelines (Playoffs section); `sim/playoffs.py` matches pairing for pairing. Only simplification: a level semi/final/Cup is a coin flip (the page gives extra time before PKs) |
| Tiebreakers (ON since 2026-10-15 night, proposal 3) | points, wins, gd, gf, **head-to-head (intraconference only: points, then gd in the matches between the tied clubs; after the top club is settled the rest go through the chain again)**, fewest disciplinary points, away gd, away gf, home gd, home gf, coin toss (two clubs) or drawing of lots (three or more) | VERIFIED 2026-10-15 on the official page https://www.mlssoccer.com/news/2026-mls-competition-guidelines (section "Tie-Breaking Procedures"). Disciplinary points on the same page: foul 1, technical-staff warning 2, yellow 3, second yellow 7 for the incident in total, straight red 7, at most 7 per incident. Engine: head-to-head and disciplinary points implemented 2026-10-15 (`sim/standings.py` h2h key, `scripts/disc_points.py` from the OpticOdds team stats: fouls = `fouls` column, yellows include both of a sent-off player so a second yellow adds 1, straight reds = reds minus second yellows), both OFF behind `tiebreak_h2h` / `disc_points_enabled` until Zac's word |
| FIFA windows | Mar 23-31; Sep 21 - Oct 6 (merged window); Nov 9-17 (after Decision Day, before the Wild Card) | FIFA calendar reports; MLS plays through them |
| Leagues Cup 2026 | Aug 4 - Sep 6, 18 MLS clubs | leaguescup.com |
| Calendar change | Board approved a fall-to-spring calendar: a 14-match transition season Feb-May 2027, then 2027-28 from mid/late July 2027. SEASON-END RE-PLAN: the schedule file is dated, so this is a schedule change, not a rebuild; playoff format for 2027 is still to be announced | ESPN / sixonefivesoccer.com reports; VERIFY the official release |
| Home edge | larger and more varied than Europe (altitude COL/RSL, turf ATL/CLT/NE/POR/SEA/VAN) | encoded as stadium notes in `teams.csv`; per-club edge only if residuals demand it |

## 3a. Feeds as verified on the live services (2026-10-12)
| Feed | Verified shape | Notes |
|---|---|---|
| OpticOdds v3 | base `https://api.opticodds.com/api/v3`, header `X-Api-Key`; `/fixtures?league=usa_-_major_league_soccer&season_year=YYYY&page=N` (100 per page, `has_more`); seasons on the feed: 2024, 2025, 2026 only (2023 and earlier return nothing); statuses `completed`, `unplayed`, `cancelled`; `/fixtures/odds/historical?fixture_id=&sportsbook=` returns every market's `olv` (opening) and `clv` (closing) `{price (American), points}` per odd, ~90 KB per fixture for Pinnacle; `/fixtures/odds` (decimal with `odds_format=DECIMAL`, up to 5 fixtures and 5 books per call); markets: `Moneyline` is the three-way (Draw selection), `Asian Handicap` (points per selection), `Total Goals` (`selection_line` over/under); `/futures` MLS: Championship Winner, Eastern/Western Conference Winner, To Make The Finals, Top Goalscorer; `/injuries?league=` (player, team, status, type) | leagues: `usa_-_major_league_soccer`, `north_america_-_leagues_cup`, `concacaf_-_champions_cup`, `usa_-_open_cup`; books: pinnacle, ps3838, betfair, bet365, draftkings, fanduel; historical limit 10 req/15 s; team spellings "Club Internacional de Fútbol Miami", "Club de Foot Montréal", "New York City Football Club", "DC United" (aliases added) |
| ESPN scoreboard | `?dates=YYYYMMDD` one day per request (ranges give 400); 510 MLS fixtures for 2026, kickoffs in UTC, `season.slug` regular-season; logos at a.espncdn.com (saved to `data/logos.csv`) | spells the Red Bulls "Red Bull New York"; "MLS All-Stars" is skipped |
| football-data.co.uk | `https://football-data.co.uk/new/USA.csv` (www redirects); columns `PSCH/PSCD/PSCA` = Pinnacle closing three-way, `AvgC*`, `MaxC*`, `BFEC*`, `B365C*`; seasons 2012-2025 fully Pinnacle (5800 closes), 2026 average closes only (405 rows) | dates are UK local, converted to ET dates with the Time column; "Chivas USA" kept as a historical club |
| Pinnacle guest API | `/0.1/sports/29/leagues` -> MLS id 2663; matchups and `markets/straight` as expected; key `CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R` works | 15 fixtures posted on 2026-10-12; `--ladders` captured 259 alternate prices |
| ASA | `/api/v1/mls/teams`, `/games?season_name=`, `/teams/xgoals?season_name=&split_by_games=true` (xgoals_for/against per team-game) | 420 games for 2026 on first fetch |
| sportsgambler.com | `injury-block` / `inj-row` markup; type class `injury-questionmark` = doubt (prob_out 0.5), card classes = suspension | 25 rows on first import, dated 28 days back at squad tier |

## 4. Blockers (current)
- 2026-10-12 (resolved the same day): Zac set the environment's network access to allow all. The entry below is kept for the record.
- **2026-10-12: every data host is denied by the environment's network policy.** `api.opticodds.com`, `site.api.espn.com`,
  `www.football-data.co.uk`, `guest.api.arcadia.pinnacle.com`, `app.americansocceranalysis.com`, `www.sportsgambler.com`,
  `www.mlssoccer.com`, `fbref.com`, `developer.opticodds.com` all return 403 from the egress proxy; only pypi, npm and GitHub
  pass. Fix: in the environment settings, Network access -> Limited (or Custom) and add those hosts under Allowed domains, or
  choose the broader level. Until then nothing in `data/` can be filled; every script is written and smoke-tested on
  synthetic data (`tests/synth.py`). The OpticOdds harvest (`scripts/harvest_optic.py`) runs first the moment the host opens.

## 5. Decisions log (date, decision, evidence)
- 2026-10-15 (night) **tiebreak_h2h on, disc_points_enabled on, dc_rho -0.05, dead_dock_goals 0.5 (min odds 0.02), rating_sd 0.20 ->
  0.10, shade off** (Zac: "do 1,2,3,4" = proposals 3, 4, 5, 6 of section 11d; 6's dock 0.5 supersedes 5's 0.35). Evidence: 11e, 11f,
  11g, 11h, 11i (at the least-squares ratings; the sim-stage backtest at the Kalman ratings with this configuration is
  `backtest/kf_final_sim.csv`, run after the change). Effect on the 200k run (asof 2026-10-15, run 20261015T212438Z vs
  20261015T201200Z): **West Vancouver 81.8 -> 70.0, St. Louis 14.0 -> 19.9, Dallas 4.2 -> 9.0** (the shade coming off: the raw
  pool was already about 70, section 11d item 8); Cup Vancouver 21.4 -> 21.6, Nashville 20.2 -> 20.9, Miami 14.3 -> 14.7, St. Louis
  9.7 -> 9.8, Philadelphia 9.2 -> 8.9; playoffs Galaxy 64.3 -> 67.2, Red Bulls 49.8 -> 52.5, Columbus 23.6 -> 22.3, San Diego 13.1
  -> 11.9 (the dock); top-4 San Jose 44.4 -> 46.2, Chicago 65.0 -> 66.1; Cup finalist Nashville 31.3 -> 32.1. East and Shield
  unchanged (Nashville 100). Page republished (version 10). The rating_sd re-set is on Zac's word under the frozen-knob rule.
- 2026-10-15 (evening) **rating_method wls -> kalman, posted_in_fit on, team_totals_enabled on** (Zac: "Ok do it all" on proposals
  9 and 10 of section 13a). Evidence: section 13 (close a week out 0.2437 vs 0.2677, 15 of 15 seasons; season backtest points
  log-pmf better in 10 of 15, playoffs and conference a wash, tails honest at 0.20/0.01; team totals 0.216 vs 0.332 goals of total).
  Effect on the 200k run (asof 2026-10-15, 75 fixtures left): blend spread 0.341 -> 0.380; Cup Nashville 19.1 -> 20.2, St. Louis
  8.2 -> 9.7, Vancouver 21.4 -> 21.4, Miami 14.7 -> 14.3, Philadelphia 8.7 -> 9.2; West St. Louis 12.5 -> 14.0, Vancouver 82.7 ->
  81.8; playoffs NYCFC 33.0 -> 34.6, Red Bulls 51.4 -> 49.8, Galaxy 63.0 -> 64.3; top-4 Houston 43.7 -> 40.1. Opta rank agreement
  0.849 -> 0.886. Page republished (version 8). Caveat: the run line's "forecast check" against the posted lines is no longer out of
  sample (the posted lines are in the ratings); the honest live number is close_track's lag-7 rmse. The run line prints "resid sd nan"
  under the filter (no least-squares residual). The Games tab's walk-forward "model before kickoff" now comes from the filter's state
  before each date (`site_data.py`). half_life_days and ridge_lambda stay in config for `rating_method wls` comparisons only.
- 2026-10-15 posted_line_shrink 0.55 -> 1.0 (Zac's word; PDF current-round rule). Evidence from the other session on 902 games
  2025-26: result log-loss 1.0320 at s 0.55 vs 1.0326 at s 1.0 on true openers (tie, se 0.0013), the close alone 1.0190; live
  lines are fresher than openers. Effect on the 200k run (10 fixtures carry a fresh line): Cup and conference pools moved under
  0.3 points (Vancouver Cup 21.6 -> 21.4, St. Louis 8.0 -> 8.2); playoffs Seattle 96.3 -> 96.8, Red Bulls 51.8 -> 51.4; top-4
  Chicago 65.1 -> 65.5, Philadelphia 47.6 -> 47.2. Page republished.
- 2026-10-15 rating_sd 0.30 -> 0.20 and drift_k_sim 0 -> 0.01 (Zac: "do 1, 2"), with the drift surprise now measured against
  the expected margin the dice used (`sim/season.py`, page worker too; new test `test_drift_surprise`). Evidence: section 11c.
  Effect on the 200k run (asof 2026-10-15, results through Oct 14, 75 fixtures left): Vancouver Cup 20.5 -> 21.6, Nashville
  18.6 -> 19.1, Inter Miami 14.6 -> 14.7, Philadelphia 8.7 -> 8.6; West Vancouver 82.5 -> 82.9; playoffs within a point.
  Opta Power Rankings wired in as the public sanity anchor (Zac: do 2): `fetch_public.py opta --latest` runs in `weekly.py`
  before each run, `site_data.py` rescales the latest snapshot to the blend's spread, the Ratings tab shows it as an "Opta"
  column (hover: the gap) and the stamp shows the rank agreement (0.849 today). Never weighted. Page republished.
- 2026-10-12 Per-club home edge ON (Zac: "do 2"). `scripts/calib_club_home.py`: residual-mean deltas per club over 14
  seasons, shrunk with k=50 pseudo-games, centred; held out they beat no-club-edge in all five test seasons 2022-2026
  (pooled next-ten rmse 0.2606 vs 0.2622; k 50 > 100 > 200 > 400). Deltas in `data/ratings/home_edges.csv` (RSL +0.05,
  LAFC +0.05, Seattle +0.04, Colorado +0.03 ... NYCFC -0.03, Cincinnati -0.05, D.C. United -0.05). Wired into the fit
  target (`market_fit(club_deltas=)`), the fixture adjustment in `run_sim.py` and the Games walk-forward lines; playoff
  knockouts still use the league edge. Effect on the 200k markets: nothing moved by a point (largest: Cincinnati playoffs
  84.5 -> 83.8, Vancouver West 82.4 -> 83.1). Forecast check on the 15 posted lines 0.164 -> 0.172 (tiny sample; the
  held-out test is the evidence). Re-fit the deltas at season end; a stadium move (Inter Miami 2026, NYCFC 2027) resets
  that club's delta to 0 until it has 50 home closes.
- 2026-10-12 rating_sd 0.35 -> 0.25 (points backtest, 15 seasons x 7 checkpoints: log-pmf -2.582 at 0.25 vs -2.588 at 0 and
  0.35; positions wanted 0.0, as in the EPL the shade carries the difference). drift_k_sim 0.01 -> 0.0 (market re-rating per
  goal of surprise +0.001/week; backtest flat-to-worse with drift). drift_cap stays 0.10 (inert).
- 2026-10-12 half_life_days 14 -> 28: `calib_half_life.py` on 14 seasons, pooled next-ten rmse 0.3203 (14) vs 0.3125 (28),
  0.3137 (21); 21-28 beat 14 in 13 of 15 seasons.
- 2026-10-12 home_edge_goals placeholder 0.35 -> 0.45 provisional: Pinnacle three-way closes imply +0.449 (2025), +0.536
  (2024), +0.514 pooled since 2012 (0.6+ in 2017-19); 2026 average closes +0.432. Frozen once the 2026 Pinnacle
  handicap closes confirm it. avg_total_goals cannot be measured from three-way closes; waits for the Pinnacle totals.
- 2026-10-12 First real fit (14-day half-life, home edge placeholder 0.35): 6119 closes, weighted residual sd 0.202 goals
  against football-data's AVERAGE closes for 2026 (Pinnacle three-way only through 2025; no totals, so T = 3.0 for every
  match). The 0.15 acceptance is judged again once the OpticOdds Pinnacle closes with handicaps and totals land.
- 2026-10-12 History priority for one match: OpticOdds Pinnacle close with AH/total (`data/history/OPTIC_<season>.csv`)
  over football-data's three-way Pinnacle close over the average close; `scripts/optic_flatten.py` writes the OPTIC files.
- 2026-10-12 Repo laid out to mirror Prem-Futures; engine, standings chain, 2026 bracket, markets, layers, devig, ratings
  fit written and tested (`tests/run_tests.py`: all pass). Starting knobs are the EPL values, marked UNCALIBRATED in
  `config.json`; the frozen-knob rule applies only after the calibration programme runs on MLS history.
- 2026-10-12 Scenario draws use their own RNG stream (seed + 1,000,003) so a points scenario leaves the football-only
  seasons identical (needed for the Scenarios tab's re-ranking and for clean deltas).
- 2026-10-12 Home edge is a knob in the live fit (not re-fitted daily): `market_fit(..., fit_home_edge=False)`. The
  calibration script fits it from the closes and freezes it. Reason: a daily re-fit on a 14-day window is noisy.
- 2026-10-12 Best-of-three with no draws is simulated as the majority of three games (identical to first-to-two).

## 6. Calibration (run 2026-10-12 on 14 seasons of Pinnacle closes plus the 2026 OpticOdds closes; knobs FROZEN 2026-10-12)
| Knob | Value | Evidence |
|---|---|---|
| half_life_days | 28 | next-ten rmse 0.3125 vs 0.3203 at 14 (15 seasons) |
| home_edge_goals | 0.44 | Pinnacle 2026 handicap-implied closes +0.440 (n 367); 2025 +0.449; 2024 +0.536; pooled since 2012 +0.51 |
| avg_total_goals | 3.2 | Pinnacle 2026 totals average 3.21; realised 3.26 |
| shared_goals_mean | 0.10 | 6049 closing-ladder prices: rmse 0.0150 at 0.10 (0.05 0.0152, 0.15 0.0154); realised margin variance agrees |
| rating_sd | 0.10 (RE-SET 2026-10-15 night, Zac, proposal 6; was 0.20 from the morning, 0.30 before) | rest-of-season backtest, section 11c: with drift 0.01 the pair keeps the points log-pmf of 0.30/0, puts 20.3% of real points totals in the 20% tails (0.30/0: 18.6%, too wide) and wins playoff qualification in 13 of 15 seasons |
| drift_k_sim / drift_cap | 0.01 / 0.10 (RE-SET 2026-10-15; was 0 / 0.10) | same backtest; surprise taken against the dice's own expected margin (shrink included) since 2026-10-15; cap never binds at k 0.01 |
| rating_method / posted_in_fit | kalman (q_day 0.03, s 0.25, q_off 0.1, off_shrink 0.75, p0 0.4) / on (SET 2026-10-15, Zac) | close-tracking yardstick, section 13: 0.2437 vs 0.2677 a week out, 15 of 15 seasons |
| dc_rho / dead_dock_goals / tiebreakers | -0.05 / 0.5 (min odds 0.02) / h2h + disciplinary points on (SET 2026-10-15 night, Zac, proposals 3-5) | 11f, 11g, 11e |
| team_totals_enabled | on, hl 30, ridge 0.25 (SET 2026-10-15, Zac) | walk-forward vs Pinnacle's totals 0.216 vs 0.332 (`outputs/calibration/team_totals.md`) |
| shade | OFF everywhere (SET 2026-10-15 night, Zac, proposal 6; was east/west b 1.5) | leave-one-season-out: conference winner 0.1205 vs 0.1213 raw; shield, playoffs, top-4, spoon, bottom lost held out |
Phase 1 acceptance: the live fit's weighted residual sd on this season's Pinnacle closes is 0.214 goals (target under
0.15) — NOT MET; the forecast check (closes-only ratings against the 15 posted lines of Oct 14) is rmse 0.164, bias -0.03.
Per-club home residuals over 14 seasons (full-season fits): RSL +0.06 (4 se), Seattle +0.05 (3.5 se), LAFC +0.06 (3 se),
D.C. United -0.06 (3.5 se), Cincinnati -0.07 (2.6 se), Colorado +0.035 (2.3 se); a per-club edge is a proposal for Zac.
Longshot rule (replay, raw prices): events priced 2-5% happen 0.64x as often as priced; 5-10% 0.83x; 10-20% 0.79x;
20-40% 1.04x. Hand rule: a sub-5% price is a third to a half too high, a 5-20% price a fifth too high; not an edge
unless the model's price is 1.5x the book's fair.
Season replay vs the equal-ratings benchmark (15 seasons x 7 checkpoints, 5000 seasons each): the model wins at 68 of
105 checkpoints on both position log-loss and points rmse, and at nearly every checkpoint on points rmse alone. The
losses are the playoff and conference pools in high-parity seasons (2012-2014, 2020-2021) where the market's
favourites missed (LAFC +0.66 top-rated in July 2021 and missed the playoffs): the probabilities are informative
(correlation of ratings with final points 0.50-0.69 at mid-season) but MLS outcomes are noisier than the EPL's. The
"beats at every checkpoint" acceptance is NOT met and is recorded as a property of the league, not a defect.
Knobs and their provenance live in `config.json` notes. Reports go to `outputs/calibration/`. Order: home edge and total
(`calib_home_total.py`); half-life (`calib_half_life.py`); shared goals (`calib_shared_goals.py`, needs
`fetch_pinnacle.py --ladders` over several rounds for the ladder half); rating_sd (`calib_rating_sd.py`); drift
(`calib_drift.py`); shade and longshot rule (`calib_shade.py`); season replay (`calib_replay.py`); CLV and shrink
(`calib_clv.py`, at 150 opener/close pairs). Then freeze with a date here.
2026-10-12: every script executed end to end on the synthetic scratch repo (numbers meaningless there; the synthetic ratings
barely drift, so the half-life grid picked 45 days and drift 0 — that is the synthetic world, not MLS).

## 6a. Once the network opens: order of operations (next session)
1. `OPTIC_API_KEY=$(cat /root/.config/optic/key) python3 scripts/harvest_optic.py` (resumable; Pinnacle history first).
2. `fetch_schedule.py` (expect 510), `fetch_results.py`, `fetch_history.py` (count seasons with Pinnacle closes),
   `fetch_pinnacle.py --ladders`, `fetch_xg.py`, `fetch_injuries.py --first-import`. Fix any unknown team spellings in
   `sim/teams.py` as the fetchers report them. Save ESPN logo URLs to `data/logos.csv`.
3. `refresh_ratings.py`; Phase 1 acceptance: residual sd under 0.15 goals on this season's closes; `rating_scorecard.py`
   numbers into section 7.
4. The calibration programme in order (section 6), set and freeze the six knobs with notes and a date, then `run_sim.py`,
   `tests/run_tests.py`, `site_data.py`, `build_site.py`, `check_site.py`, publish with `capabilities: {db: {}, user: {}}`.
5. Create the four Routines (section 9) from `close_schedule.py --json` for the capture slots.
6. Layers (section 8): measure injuries and call-ups on the lined fixtures before switching either on.

## 6b. CLV test and the shrink (run 2026-10-12 on 903 Pinnacle opener/close pairs from the OpticOdds harvest, 2025-2026)
- Where the closes-only ratings disagreed with Pinnacle's opener by 0.15 goals or more (267 of 903 fixtures), the close
  moved the model's way 67.4% of the time, mean signed move +0.11 goals; at 0.30 or more (65 fixtures) 73.8%. The closes
  move further on attacks (0.22) than elsewhere (0.19). This is the Pinnacle-grade proof the build prompt asks for.
- Shrink grid on the close: ratings only 0.261, s 0.35 0.248, s 0.50 0.246, s 0.70 0.247, opener only 0.257; fine grid
  s = 0.55. posted_line_shrink 0.35 -> 0.55 (floor: the live posted line is fresher than the true opener).
- Openers-in-the-fit grid: not yet run (the EPL answer was "never"); half-life re-grid on the 2025-26 handicap closes: pending.
- OpticOdds coverage facts: Pinnacle history exists for 2025 and 2026 only (the 2024 files are empty), 34 completed 2026
  fixtures carry an opener but no close (suspended markets) and fall back to football-data's average close.
- Harvest complete 2026-10-13 (`data/optic/README.md`): six books x 960 MLS fixtures 2025-2026, the four cups' Pinnacle
  history (438 fixtures) for the congestion study, results with team stats for the form-source study. Not yet used:
  the book comparison (`lines_<book>.csv`), the congestion study, the form-source study.

## 7. Scorecard (run 2026-10-12 on 14 seasons of Pinnacle three-way closes; xG for 2024-2026)
rmse in goals predicting the next ten closes, walk-forward (`outputs/calibration/scorecard.md`), market half-life 28:

| season | market | 75/25 (xg hl 45) | 50/50 (xg hl 21) | xg alone (hl 45) | benchmark (home edge only) |
|---|---|---|---|---|---|
| 2024 | 0.3150 | 0.3151 | 0.3361 | 0.4109 | 0.4968 |
| 2025 | 0.2606 | 0.2512 | 0.2742 | 0.3484 | 0.5027 |
| 2026 | 0.2451 | 0.2377 | 0.2867 | 0.3938 | 0.5740 |

Decision 2026-10-12 (the recipe's own rule: keep 50/50 unless the grid separates cleanly, and it does): weights market 3.0 /
xg 1.0 (75/25), xG half-life 45 days. 50/50 loses to market-only in every season; 75/25 wins by 0.007-0.009 goals in 2025
and 2026 and ties 2024. Earlier seasons have no xG on file. Re-test monthly. Zac can set the weights back in one line.
Market-only by season (2012-2023): 0.247, 0.272, 0.259, 0.289, 0.345, 0.367, 0.411, 0.388, 0.321, 0.297, 0.278, 0.302.

## 8. Measurements of the layers
- 2026-10-12 Injuries (25 site rows, all squad tier 0.02, first import dated 28 days back so mostly absorbed): on the 15 lined
  fixtures of Oct 14 the gap to Pinnacle is rmse 0.1723 with the layer off and 0.1703 on; mean |adjustment| 0.010 goals,
  max 0.023. Within noise: the layer stays OFF until Zac sets tiers and three or more rounds of lines are logged.
  `run_sim.py` now measures off vs on every run (`outputs/calibration/layers_log.csv`, also printed in the run line).
- Call-ups: the next FIFA window is Nov 9-17, after Decision Day; no regular-season fixture is affected, so `callups.csv`
  stays empty and the layer OFF. The Wild Card on Nov 18 follows the window: a call-up list matters for the bracket only.

## 9. Automations (Routines bound to this session, created 2026-10-12)
| Routine | id | schedule | does |
|---|---|---|---|
| MLS morning news 7:40 ET | trig_01S17cqCUZRuu9NoJAs4XA9m | daily 07:40 America/New_York | fetch_results, fetch_injuries, news_scan, web search per thin headline, injury/call-up maintenance at default tiers, commit, report under 250 words, push notification |
| MLS Pinnacle lines 8:52 ET | trig_01SYLkPVCqP65bbbc5XdvEdB | daily 08:52 America/New_York | weekly.py (fetch incl. Opta anchor, run + publish if a match-day finished), apply pending site settings first, create the capture Routines for the next eight days |
| MLS close capture Wed Oct 14 7:20 PM ET | trig_01AWKP5ZxVw52K2sB28tVoYx | once 2026-10-14 23:20Z | fetch_pinnacle.py --close, commit, push |
Capture Routines are one-shot, named "MLS close capture <date> <time ET>", created by the 8:52 routine from
`scripts/close_schedule.py --json` (ten minutes before each distinct kickoff). CLV log and forecast check run inside every run.
Status: none has fired yet (Phase 4 acceptance pending). The 8:52 routine republishes to the URL in section 10.

## 10. Website
`site/index.html` template (since 2026-10-15 night the Prem Futures design from the other session's branch claude/awesome-edison-nr0r68, commit 5231f94, taken on Zac's word "use the updated website": same tabs, data and ids; six tabs, American odds, ET, crests; a web-worker port of
the engine for the Settings resim; the Scenarios tab re-ranks a 20k-season football-only sample embedded in the page);
Page changes 2026-10-15 night (Zac): **Scenarios tab removed** (and the embedded 20k-season sample with it: the page fell from
4 MB to 570 KB; `apply_site_settings.py` still reads `settings/pending.scenario` if one is ever saved, but nothing writes it);
**crests embedded** as 96 px data URIs from `data/logos/<code>.png` (fetched once from the ESPN URLs in `data/logos.csv`; the
published page cannot rely on external images, which is why letters showed); the Games detail row shows **EV% at Pinnacle's
price** per outcome (model probability x Pinnacle decimal price - 1); the Ratings header line (run date, Opta anchor) removed;
the Shaded/Raw toggle is hidden while no shade is applied; the Ratings tab shows Conf 1st (top seed), Playoffs, Semi (reaches the conference semifinals, pool `conf_semi`), Final (reaches the conference final, `conf_final`), Win conf (conference champion, the Cup finalist pool) and Cup; the Shield column was dropped (decided). The two stage pools were added to `sim/markets.py` (sizes 8 and 4, raw) and are in every run's markets.json from 20261015T221200Z on. `check_site.py` no longer checks a Scenarios tab.
`scripts/site_data.py` -> `outputs/latest/site_data.json`; `scripts/build_site.py` -> `outputs/latest/site.html`;
`scripts/check_site.py` (Playwright, bundled Chromium: every tab, console errors, Games-table fit at 1100-1920 px, a worker
run, the Scenarios run-row check) before publishing. Save buttons write `settings/pending` and `settings/pending.scenario`
through the artifact `db` capability (`claude.use("db")`, `db.doc(path).set(doc)`); the page is published with
`capabilities: {db: {}, user: {}}`; `scripts/apply_site_settings.py` reads them (the session exports the two documents to
`outputs/latest/pending_settings.json` with ArtifactData first). Logos: `data/logos.csv` (team, logo URL) once ESPN is
reachable; the page falls back to the three-letter code on the disc.
Smoke-tested 2026-10-12 on synthetic data (`tests/synth.py` builds a scratch repo; never the real `data/`): 0 console errors,
worker resim 20k seasons in 0.5 s, Scenarios run row within 0.6 points of the 20k run's markets (the deduction draws use a
different RNG in the page; at 200k seasons the gap shrinks). URL: not yet published (no real run to publish).
Cup prices under a scenario are a no-resim approximation: seasons where the team's seed is unchanged keep the run's result;
where it changed, the team gets its seed-conditional cup rate from the archive and the rest is spread pro rata.
**URL: https://claude.ai/artifact/PYXHJ1tuZhpRqgoub1Nfao** (published 2026-10-12 from the first real 200k run, capabilities
db + user, private to Zac). Republish the same file path (`outputs/latest/site.html`) after every run; from another session
pass the URL as `url`. The template is a fragment (title + style first, no doctype/html/body): the publish tool wraps it;
`build_site.py` also writes `site_local.html` with the same wrapper for the headless check.

## 11. Ratings session 2026-10-15 (north star: `docs/futures_sim_method_nfl.pdf` on branch claude/awesome-edison-nr0r68; no hand ratings, no book futures)
Yardstick change (Zac, 2026-10-15): ratings are judged on the rest-of-season backtest (`scripts/backtest_season.py`), not on the
next close. From six checkpoints per season (matchweeks 4, 9, 14, 19, 24, 29; 15 seasons 2012-2026) ratings are built from data
strictly before the checkpoint, results before it are locked, the remainder is simulated, and the scores are: final points
(log-pmf, rmse, PIT tails: 20% combined is honest), remaining-match H/D/A log-loss of the actual results from the static ratings,
rmse against the remaining closes, and playoff / conference / Shield / Spoon log-loss. Home edge and total per season as known at
the checkpoint. Paired seeds. Rows under `outputs/calibration/backtest/`; `summary` prints pooled means and seasons won vs a baseline.
A deviation from the PDF stays only if it wins clearly and consistently across most seasons there, and Zac approves it.
Plumbing fixed 2026-10-15 (data, not model): (1) `scripts/replay.py` double-counted 2025 (football-data and OpticOdds history files
both carry it; the replay joined both, so every 2025 match was simulated twice: 1056 matches, points rmse 16). Every earlier
calibration that used the replay (rating_sd, drift grid, shade, season replay) saw a doubled 2025; the other 14 seasons were fine.
(2) ASA xG now on file for 2013-2026 (`fetch_xg.py`, defunct clubs admitted via canon(historical=True); Chivas USA included), so
the xG blend can be backtested on 13 seasons instead of three.
Match-level checks (`scripts/match_checks.py`, `outputs/calibration/match_checks.md`, 6236 lined matches): favourite win rate by
closing bucket matches the devigged close (no NFL-style win-curve mismatch); the engine at the close's own margin and total gives
22.7% draws against 25.1% realised and 24.9% in the devigged close (0-0 realised 6.3% vs engine 4.6%: the Dixon-Coles signature);
margin noise matches where totals are known (2025 sd 1.68 realised vs 1.70 engine; 2026 1.66 vs 1.74), the pooled gap (1.60 vs
1.73) is the 3.2 default total applied to 2012-2024 three-way-only closes whose seasons averaged 2.6-2.9 goals.

## 12. Where the model deviates from the method PDF (audit 2026-10-15; for later, none changed without Zac's word)
Excluded on Zac's instruction: hand ratings; market-implied ratings from futures / win totals; book futures as a comparison.
1. ~~Ridge toward zero in the market fit~~ SUPERSEDED 2026-10-15: the market fit is now the Kalman filter (section 13); its prior (p0, off-season reversion) plays the ridge's role and was set on the close-tracking yardstick. Original note: the PDF is plain least squares with a sum-to-zero row. Flattens the
   live market ratings 7% (sd 0.389 -> 0.360 at hl 28 on 2026-10-15). Under test in section 11.
2. ~~Half-life 28 days~~ SUPERSEDED 2026-10-15: no half-life in the filter (q_day/s = 0.12 is the equivalent memory, set on the close).
3. **Blend spread** (PDF: compare every time the blend changes) — now measured on every close-tracking run as the slope of the close on the model: 1.04 with the filter + xG (was 1.20). Live: blend sd 0.342 vs market
   0.389 at ridge 0, 12% flatter in total (ridge 7%, blending two sources correlated 0.74 another 5%). Under test (`blend_rescale`).
4. **xG source**: raw spread 1.3x the market's at the same checkpoints (correlation 0.63 early to 0.75 late in the season), so the
   PDF's rescale-to-the-market step is right for it; the blend weight was set on next-close rmse over three seasons. Under test on 13.
5. ~~Posted-line shrink 0.55~~ SET TO 1.0 on 2026-10-15 (Zac): a fixture with a fresh Pinnacle line is priced 100% off Pinnacle,
   as the PDF does for the current round. Still Pinnacle only, not a median across books (Pinnacle is the only line source here).
6. ~~Shade on the conference pool~~ OFF since 2026-10-15 night (proposal 6: replaced by rating_sd 0.10 and the dock). Was: logit stretch b 1.5, not in the PDF; the PDF's answer to "every top team's price is off at
   once" is the variance pair, and to one team's price a ratings fix. The shade papers over whichever of the two is wrong.
7. ~~Drift surprise vs the dice~~ FIXED 2026-10-15 with proposal 1: the surprise is measured against g, the margin the dice used
   (`test_drift_surprise` keeps it: a shrunk fixture drifts its sides by 0.0000 on average).
8. **Dixon-Coles** ON at -0.05 since 2026-10-15 night (proposal 4): with true totals the base engine misses the draw rate by 1.2 points, rho -0.05 closes it;
   backtest a wash (11f). Proposal 4.
9. **Shared-goals component (c 0.10)** instead of independent Poissons — an addition, calibrated from Pinnacle's ladders; keeps
   margin noise right where totals are known (section 11).
10. **Eliminated-team dock** ON at 0.5 since 2026-10-15 night (proposals 5/6; measured -0.36 goals vs the ratings, 11g, proposal 5); clinched
    clubs show nothing, locked seeds unmeasurable (n 26). No congestion penalty, no per-team volatility ladder (PDF: after v1).
11. **Expansion prior** (-0.25, not in the PDF): the market's matchweek-4 rating of 13 expansion sides 2012-2025 averaged -0.32
    (range -0.78 to -0.09), -0.21 by matchweek 9. Only matters before a club has ten closes.
12. **Per-club home edge** on (PDF: per-team tiers scaled back to the league average — ours are centred deltas, consistent).
13. **Playoff knockouts use the league home edge** (not the club delta) and a drawn knockout is a coin flip (PDF silent).
14. **Fit target for 2012-2024 three-way-only closes** uses the 3.2 default total where those seasons averaged 2.6-3.1 goals;
    second-order on gd_fit, first-order on the engine's draw rate and margin noise when those lines are replayed at 3.2.
15. **Rating history**: the PDF keeps one row per team per week of the blend; ours is per-run `outputs/runs/<stamp>/ratings.csv`
    (`xg_ratings_history.csv` is empty). Plumbing.
16. **Uncertainty and drift were calibrated on market-only ratings** at ridge 0.5 (the replay never blended xG), while the live
    sim runs on the 75/25 blend, and with 2025 doubled (section 11). Re-done in step three of this session.

### 11a. Ratings grid on the rest-of-season backtest (2026-10-15, `outputs/calibration/backtest/ratings_grid1.csv`, 146 recipes x 90 season-checkpoints)
Static ratings scored on the remaining matches (H/D/A log-loss of the actual results; rmse of analytic expected final points).
- **Ridge**: the PDF's plain least squares (ridge 0) LOSES to ridge 0.5 at every half-life: hl 28 match log-loss 1.0141 vs 1.0133,
  expected-points rmse 6.116 vs 6.066; ridge 0 wins 5 of 15 seasons on log-loss and 4 of 15 on points. Ridge 1.0 ties ridge 0.5
  (1.0133 / 6.058; 7 and 10 of 15). The ridge is James-Stein shrinkage for a fit that sees about three closes per club in a
  half-life: it helps most early (matchweeks 4-9: 1.0270 vs 1.0296) and costs a hair late (1.0012 vs 1.0008).
- **Spread**: multiplying the ridge-0.5 market ratings by 0.9 / 1.0 / 1.1 gives log-loss 1.0134 / 1.0133 / 1.0136 and points rmse
  6.061 / 6.066 / 6.088: their spread is right for predicting results. The ridge-0 ratings want 0.85x (6.077 vs 6.116). The closes
  themselves want 1.1x (close rmse 0.3354 vs 0.3368): the market's lines are about 10% wider than what best predicts results, so
  "8% flatter than Pinnacle implies" is the right amount of flattening for this yardstick, not a defect.
- **Half-life**: 21-28 days is best on both scores at every ridge (28/0.5: 1.0133, 6.066); 45 within 0.0003; 60 and longer lose
  monotonically (90: 1.0154, 6.183; 180: 1.0181, 6.293). The next-close answer and the season answer agree.
- **xG blend** (14 seasons 2013-2026): every market+xG blend at ridge 0.5 beats market-only (pooled 1.0145 / 6.126). Live 75/25 at
  xG half-life 45: 1.0141 / 6.082, wins 8 of 14 seasons on log-loss and 10 of 14 on points. Best: 25-35% xG at half-life 90:
  1.0138 / 6.080 (8 and 8 of 14). The blend helps early (1.0269 vs 1.0286) and costs late (1.0013 vs 1.0007). Rescaling the blend
  back to the market's spread makes it slightly worse (1.0148 vs 1.0144 at 35%/90): the blend's 5% lower spread is not a defect.
  Blends on ridge-0 market ratings are all worse than the same blends on ridge 0.5.
Reading: the current market recipe (hl 28, ridge 0.5, 75/25 xG) is on the flat top of the surface; nothing in the grid beats it
clearly and consistently across seasons. The PDF deviation (ridge) stays on evidence. Public sources are tested next (11b).

### 11b. Public predictive models for MLS (survey verified live 2026-10-15; backtest `outputs/calibration/backtest/public_*.csv`)
| Source | Live | History for backtesting | Verdict on the rest-of-season backtest |
|---|---|---|---|
| ASA xG (match level) | API, by game | 2013-2026 complete (`data/ratings/xg_history.csv`) | alone loses to market-only (1.0189 vs 1.0145); 25% blend wins by 0.0004 (8 of 14 seasons) |
| ASA goals added (g+) | API, player rows summed to team-game (team by-game endpoint 500s) | 2013-2026 (`data/public/asa_gplus/team_games.csv`) | alone 1.0190; 25% blend at 90-day half-life 1.0129 vs 1.0140 market (8 of 14) |
| Opta Power Rankings | performfeeds JSON daily (needs a theanalyst.com Referer), 0-100 | daily snapshots by `rankDt` from June 2022 (`data/public/opta/snapshots.csv`, 2022 has 3 checkpoints) | alone 1.0424 vs 1.0396 market over 26 checkpoints; 25% blend 1.0389 (3 of 5 seasons) |
| footballdatabase.com Elo-style points | weekly page | monthly club histories 2010-2026 (`data/public/footballdatabase/history.csv`; Toronto page bot-gated, retry) | alone 1.0184 vs 1.0133; 25% blend 1.0120 (8 of 15); market+xG+15% fdb 1.0116 vs live 1.0125 (8 of 15 vs live) |
| soccerpowerrankings.substack.com "MLS Power Ranking Averages" (Zac asked 2026-10-15) | weekly post, public Google Sheet: truncated mean of ordinal ranks from ~15 editorial sites plus an Elo group (Massey, Opta, ASA xPts, Concacaf, Adam King) and a 9-book betting-odds group | 2026 only (first post 2026-02-24; `data/public/spr/avg_rank_long_2026.csv`, 25 weekly columns) | ordinal, lagged, book-derived component; week 24 Spearman 0.78 with the blend, 0.92 with Opta; 2026 backtest (5 checkpoints) alone 1.0890 vs market 1.0764 (worst of all sources), 25% blend 1.0771, on top of live 1.0755 vs 1.0740: not a rating source |
| ClubElo | club pages exist for 4 MLS clubs only; API host resets the connection | per match from Oct 2022, 4 clubs | not usable |
| 538 SPI | dead | 2017-18 only reachable (datahub mirror); Wayback blocked here | not usable |
| Massey | Cloudflare challenge blocks every fetch from this container | unknown | not usable from here |
| Sagarin (through Dec 2024), ESPN SPI (not published for MLS), Global Football Rankings (MLS from Oct 2025), Kickoff.ai, Dunkel, Power Rank, Sonny Moore (no archive), forzapitch (book-blended) | - | - | not usable |
Reading: no public model beats market-only on its own; every blend at 15-35% adds 0.0004-0.0013 of match log-loss and wins 8-9
of 14-15 seasons, the same order as season noise. xG helps early in the season (thin market data), footballdatabase mid and late.
Recommendation (Zac decides): keep xG at 25%; take Opta as the live sanity anchor (daily, model-based, independent of our inputs),
displayed next to the blend and never weighted; no further source on the evidence. Loaders: `scripts/public_sources.py`;
fetchers: `scripts/fetch_public.py` (Opta needs the weekly `--dates` list; `--latest` for today).

### 11c. Uncertainty and drift on the rest-of-season backtest (2026-10-15, live blend ratings, `sim_grid1-3.csv`, 4000 seasons, paired seeds)
The log-pmf surface is the PDF's ridge: sd 0.3 / drift 0 (-3.1532), 0.2 / 0.01 (-3.1535), 0.1 / 0.02 (-3.1536), 0 / 0.02
(-3.1511) are within noise of each other. The tails and the position markets separate them:
| pair (sd, k) | points log-pmf | tails (20% honest) early/mid/late | playoffs ll | conf ll | seasons better than 0.3/0 (lpmf, tails, playoffs, conf) |
|---|---|---|---|---|---|
| 0.30 / 0 (frozen) | -3.1532 | 0.186 (0.193 / 0.182 / 0.178) too wide | 0.3069 | 0.1454 | - |
| 0.20 / 0.01 | -3.1535 | 0.203 (0.215 / 0.203 / 0.184) | 0.3035 | 0.1443 | 9, 8, 13, 11 of 15 |
| 0.15 / 0.015 | -3.1533 | 0.205 (0.220 / 0.205 / 0.187) | 0.3030 | 0.1444 | 10, 8, 13, 11 |
| 0.10 / 0.02 | -3.1536 | 0.202 (0.217 / 0.201 / 0.187) | 0.3034 | 0.1443 | 7, 8, 13, 11 |
| 0 / 0.02 | -3.1511 | 0.211 (0.228 / 0.210 / 0.193) | 0.3017 | 0.1443 | 9, 8, 13, 12 |
| 0 / 0 (static, no uncertainty) | -3.1844 | 0.267 too confident | 0.2953 | 0.1404 | - |
Readings: (1) the frozen pair is too wide: 18.6% of real points totals land in its 20% tails, 17.8% late in the season, and it
is the worst of the ridge on playoff qualification and conference winner in 13 and 11 of 15 seasons. (2) Position markets want
less variance than the points totals (static 0/0 is best on playoffs but puts 26.7% in the tails); the honest pairs sit between.
(3) Per-season tails range from 0.09 (2012, 2015) to 0.31 (2014, 2026) at any setting: MLS seasons differ a lot in how
surprising they are. (4) The PDF's claim that a static sim prices favourites too short does not hold here with sd 0.3: moving to
the honest pair makes today's favourites slightly shorter (Vancouver Cup 20.5 -> 21.4) because total variance falls.
The drift-surprise fix (section 12 item 7) must land with any non-zero drift. Market ratings alone (no xG) give the same picture.
Knobs unchanged pending Zac's word.

### 11c2. Shade re-tested at the new pair (Zac asked 2026-10-15; `outputs/calibration/backtest/shade_sd020_k001.csv`)
Conference-winner log-loss from the live blend at rating_sd 0.20 / drift 0.01, 15 seasons x 6 checkpoints, 4000 seasons each:
off (b 1.0) 0.1434, b 1.2 0.1400, b 1.3 0.1391, **b 1.5 0.1386** (current), b 1.8 0.1403. The shade beats off in 12 of 15
seasons; it loses in the parity seasons 2014, 2020 and 2021 (where the favourite missed) and wins everywhere else, by phase
early 0.1775 -> 0.1732, mid 0.1389 -> 0.1308, late 0.1106 -> 0.1087. Off is not equal or better, so the shade STAYS at 1.5 on
the two conference pools (every other pool was already raw). Nothing rerun.

### 11e. Tiebreakers (Zac's item 1, 2026-10-15)
How often the chain matters, 100k seasons from today's state (`gf` now in the archive): adjacent conference seeds level on
points in 2.2 (East) / 2.4 (West) pairs per season; still level after wins 0.69 / 1.17; after gd 0.027 / 0.053; after gf,
where head-to-head would decide, 0.0012 / 0.0017 per season (disciplinary points sit behind that). Vancouver v St. Louis
(52 pts 15 w +31 v 51 pts 14 w +16, no meetings left: Sep 5 STL 3-1 at VAN, Oct 14 0-0): level on points in 7.0% of
seasons, still level after wins 2.5%, never after gd; Vancouver wins every tiebreak. The nine-ten line is level on points
in 26% (East) / 22% (West) of seasons, settled by wins or gd. What-if (100k, same seed): head-to-head on, disciplinary
points on, or both: West Vancouver 82.5 -> 82.5, St. Louis 12.7 -> 12.7, every seed market within 0.1, Cup within noise
(0.2-0.4 on the favourites at 100k seasons). 2026 disciplinary totals: Portland fewest (414), Inter Miami most (655); the
scale is dominated by fouls (about 300 per club) with cards adding 130-250.

### 11f. Dixon-Coles (Zac's item 2, 2026-10-15; engine knob `dc_rho`, off)
Fit on 6251 lined matches 2012-2026 with the 2012-2024 three-way lines replayed at their seasons' realised totals (not the 3.2
default): the base engine gives 23.9% draws vs 25.1% real (0-0 6.1% vs 6.3%, 1-1 10.8% vs 10.7%), so most of the 2.4-point gap in
section 11 was the default total, not the Poisson shape. Scoreline likelihood is best at rho -0.05 (draw 25.2%, 0-0 6.8%, 1-1
11.4%, 1-0 and 0-1 down 0.5 each), the devigged closes' draw rate (24.9%) is matched at -0.04; on 2025-26 alone (975 matches,
real totals) the likelihood is flat between 0 and -0.05 (23.2% engine vs 24.6% real, 24.1% close). E[margin] moves 0.0004.
Engine: `score_grid(rho)` multiplies the four cells and renormalises; `sample_goals` imposes it by rejection (tests: sampler
matches its grid within 0.001); rho runs through the playoffs, the fit targets (gd_fit cache keyed on rho), run_sim, what_if and
the backtest (`BT_KNOBS` env). Rest-of-season backtest at 0.20/0.01 (`dc_rho*.csv`): rho -0.05 vs 0: match log-loss 1.0131 vs
1.0125 (6 of 15 seasons better), points log-pmf -3.1555 vs -3.1571 (8 of 15), tails 0.206 vs 0.202, playoffs 0.3028 vs 0.3028,
conference 0.1435 vs 0.1434: a wash. Shade with rho -0.05: off 0.1435, b 1.5 0.1388, 12 of 15 seasons (unchanged: the shade is
not patching the draw rate). Today's futures at -0.05 (200k): nothing moves by 0.3 (Vancouver Cup 21.4 -> 21.4, West 82.7 ->
82.9, St. Louis 12.5 -> 12.3, Chicago Cup 4.9 -> 5.1). Section 12 item 14 (the 3.2 default total on old lines) is the larger
of the two draw-rate issues and only touches calibration replays, not the live sim, which has real totals.

### 11g. Dead-team docks (Zac's item 3, 2026-10-15; `scripts/dead_teams.py`, `outputs/calibration/dead_teams.md`; knobs off)
Measured on the last ten rounds of 2012-2025 (lined matches; status from the table before each date, conservative tests):
| status | team-matches | vs the close | vs the ratings (what the sim uses) |
|---|---|---|---|
| open | 2288 | +0.01 | +0.03 |
| clinched, seed open | 789 | +0.03 | +0.06 |
| locked seed | 26 | -0.33 (se 0.29) | -0.40 (se 0.30) |
| top seed locked | 43 | -0.12 (se 0.19) | -0.03 |
| eliminated | 300 | -0.15 (se 0.10) | **-0.36 (se 0.10)** |
Eliminated clubs play 0.36 goals a match below their ratings (negative in 11 of 14 seasons; their opponents +0.47 vs the
ratings); the close prices 0.2 of it, the ratings none, so the sim's future rounds miss it. Clinched clubs with a seed to play
for show nothing; locked seeds are too few to measure (no dock proposed). Engine (`dead_dock_goals`, `dead_dock_min_odds`): the
match-day a club's reachable points fall below the last playoff place in a simulated season its rating drops by the dock for
the rest of that season (in R, so the dice and the drift surprise both see it); clubs already out at the run date or under 2%
playoff odds in a 20k pre-pass without the dock are exempt (the market has priced them: without the exemption Montréal was
docked in 100% of seasons on top of its price). Rest-of-season backtest at 0.20/0.01 (`dockx*.csv`), dock 0.35 vs none:
points log-pmf -3.1512 vs -3.1571 (10 of 15 seasons), points rmse 6.018 vs 6.040 (12 of 15), playoffs 0.3018 vs 0.3028 (10),
conference 0.1427 vs 0.1434 (10), tails 0.192 vs 0.202 (slightly wide); 0.5: -3.1480, 6.010, 0.3015, 0.1425 (13 of 15), tails
0.188. Today (200k, exempt Montréal and Sporting KC; Austin docked in 85% of seasons, Atlanta 78%, Minnesota 77%, San Diego
63%, RSL 52%, Portland 50%, Toronto 46%, D.C. 44%, Columbus 40%, NYCFC 26%, Red Bulls 14%): at 0.35 West Vancouver 82.7 ->
82.5, St. Louis 12.5 -> 12.7, Cup unchanged; playoffs LA Galaxy 63.0 -> 64.7, Red Bulls 51.4 -> 53.0, Cincinnati 73.9 -> 72.8,
Colorado 75.1 -> 74.2; top-4 San Jose 43.5 -> 44.9, Dallas 88.4 -> 87.9.

### 11h. What the conference shade covers (Zac asked 2026-10-15; `shade_diag*.csv`, scripts in the session scratchpad)
Raw conference-winner probabilities are under-confident at every phase: favourites priced 30-70% win 1.2x their price
(early 0.43 -> won 0.55; mid 0.53 -> 0.62; late 0.66 -> 0.76), 5-20% shots win 0.3-0.8x. Tested causes at 0.20/0.01:
- Ratings compression: NO. The closes rate our rank-1 club 0.07 goals higher and ranks 11-15 0.04-0.10 lower than we do (the
  ridge), but ridge 0, market-only, or a 1.15-1.3x stretch all make the raw score worse (0.1416-0.1453 vs 0.1434) and the shade
  still helps; the rank-1 club's results match our rating (+0.02 goals a match) and its expected points (+0.07).
- Variance size: PART. The shade's gain scales with the pair (0.0049 at 0.20/0.01, 0.0016 at 0.10/0.005, none static), but a
  static sim is still under-confident (favourite 0.50 -> 0.55 early, 0.68 -> 0.76 late) and over-confident on points (tails 0.27).
- Variance shape: NO. A smaller draw for the top 3-5 of each conference, or a league-wide spread draw that never reorders
  teams, score 0.1412-0.1422 raw: no better than simply lowering sd.
- Dead teams: PART. Eliminated clubs collapse (11g); the dock plus a lower draw (sd 0.10, drift 0.01, dock 0.5) is the best
  structural point: raw 0.1412 (13 of 15 seasons better than 0.20/0.01 raw), playoffs 0.2981 (12), log-pmf -3.1519 (9),
  tails 0.214; the shade's remaining gain there is 0.0029 (favourite 0.55 -> 0.64 pooled).
- Dixon-Coles: NO (0.1434 -> 0.1435).
What is left is a persistent 20% favourite over-performance that no engine lever reproduces. Caveat on the evidence: the
conference-winner pool has 2 outcomes per season, 30 independent races in 15 years; the favourites' 0.64 realised vs 0.53 raw
is a 1.2-standard-error difference on 30 races, and a quarter of it is two dynasties (LAFC 2019/2022, Miami 2024). The points
and playoff pools, with 15-30 outcomes a season, are the reliable yardsticks, and they prefer the structural point above.
Reading: the shade is a 30-race fit standing in for (a) too much static variance and (b) the missing dead-team collapse; the
rest may be noise. Proposal 6 replaces it with mechanisms.

### 11i. Flat and lagging ratings (Zac's three tests, 2026-10-15; `zac3_ratings.csv`, `zac3_sim.csv`; knobs `ridge_fade_mw`, `posted_in_fit`, off)
Zac's symptom reproduced walk-forward on the 217 post-World Cup closes: miss 0.252, slope of the close on our rating 1.20,
cross-conference 0.349 vs within 0.224; last six weeks Pinnacle rates Nashville +0.46, Philadelphia +0.22, Miami +0.21, St. Louis
+0.19 above us. Scored honestly on closes 4-10 days ahead (474): live 0.276 / slope 1.19 / cross 0.370; posted lines in the fit
0.268 / 1.17 / 0.366; fading ridge 0.269 / 1.04 / 0.352; both 0.263 / 1.05 / 0.353. Results barely move (rmse result-rating
1.660 / 1.658 / 1.661 / 1.661): the slope is a market-tracking symptom, not a results one.
Season yardstick, static ratings (match log-loss on the rounds after the current one; expected-points rmse; close rmse), 15 seasons:
| recipe | later-round match ll | seasons | points rmse | seasons | close rmse | seasons |
|---|---|---|---|---|---|---|
| live | 1.0126 | - | 6.046 | - | 0.3329 | - |
| (1) ridge fading to 0 at mw 15 | 1.0125 | 7 | 6.047 | 6 | 0.3288 | 13 |
| (2) current round's lines in the fit | 1.0120 | 12 | 6.009 | 12 | 0.3263 | 15 |
| (3) both | 1.0119 | 8-10 | 6.008 | 10-13 | 0.3224 | 15 |
| conference offset from a 180-day window | 1.0125 | 6 | 6.050 | 6 | 0.3331 | 6 |
Sim stage with the current round priced off its line as live does (`BT_CURRENT=3`), vs live at 0.20/0.01 (points log-pmf
-3.1584, tails 0.205, playoffs 0.3018, conf raw 0.1434 / shaded 0.1387):
| recipe, variance | log-pmf (seasons) | tails | playoffs (seasons) | conf raw (seasons) | conf shaded |
|---|---|---|---|---|---|
| posted, 0.20/0.01 | -3.1514 (7) | 0.203 | 0.3003 (11) | 0.1435 (6) | 0.1394 |
| posted, 0.15/0.01 + dock 0.5 | -3.1454 (12) | 0.201 | 0.2965 (13) | 0.1422 (13) | 0.1394 |
| posted, 0.10/0.01 + dock 0.5 | -3.1453 (12) | 0.211 | 0.2950 (13) | 0.1416 (12) | 0.1395 |
| fade15, 0.20/0.01 | -3.1574 (7) | 0.205 | 0.3034 (7) | 0.1437 (9) | 0.1404 |
| both15, 0.15/0.01 + dock 0.5 | -3.1458 (9) | 0.203 | 0.2977 (10) | 0.1423 (11) | 0.1404 |
| live, 0.15/0.01 + dock 0.5 | -3.1453 (10) | 0.203 | 0.2982 (12) | 0.1420 (13) | 0.1386 |
Readings: (2) is a real, consistent gain on every score (the PDF's "every posted spread is one equation" holds here); (1) fixes
the slope against Pinnacle and nothing else, stretches the ratings 8% (the spread test in 11a said no) and loses on the sim at
the current pair; (3) adds nothing to (2). The right variance pair moves down once the ratings carry the current lines and
the dock: 0.15/0.01 with dock 0.5 keeps the tails honest (0.201). The shade still adds about 0.003 on the conference pool at
every point (the 30-race caveat in 11h stands); it is a separate decision.

### 11d. Proposals put to Zac 2026-10-15 (1 and 2 APPLIED on "do 1, 2"; 3, 4, 5, 6 APPLIED the same night on "do 1,2,3,4"; 7 made redundant by the Kalman change (13a); 8 is an alternative to 6, not taken; section 5 has the effects)
1. rating_sd 0.30 -> 0.20 and drift_k_sim 0 -> 0.01 (cap 0.10 unchanged), with the surprise-vs-dice fix in `sim/season.py`.
   Backtest: tails 0.186 -> 0.203, playoffs log-loss better in 13 of 15 seasons, log-pmf tied (9 of 15). Today's futures (asof
   2026-10-15, 100k seasons): Vancouver Cup 20.5 -> 21.4, Nashville 18.6 -> 19.0, Inter Miami 14.6 -> 15.1, Philadelphia 8.7 ->
   8.4; West Vancouver 82.5 -> 82.9; Cup finalist Vancouver 37.1 -> 38.2. Alternative 0.15 / 0.015: Vancouver Cup 21.6.
2. Opta Power Rankings as the sanity anchor: fetched daily, shown next to the blend (rescaled), never weighted. Today: rank
   correlation 0.85 with the blend; Opta likes Seattle, Dallas, Austin, San Jose more (0.3 goals), the blend likes Vancouver and
   Montréal more. Moves no probability.
3. Tiebreakers exactly per the 2026 guidelines: `tiebreak_h2h` on (head-to-head step) and `disc_points_enabled` on (2026
   disciplinary totals from `scripts/disc_points.py`, refreshed by the morning routine). Decides a seed in 0.1-0.2% of seasons;
   today every market within 0.1 (West Vancouver 82.5 -> 82.5, St. Louis 12.7 -> 12.7). Correctness, not prices.
4. Dixon-Coles `dc_rho` -0.05: draw rate 23.9% -> 25.2% (real 25.1%); season backtest a wash (log-pmf +0.0016 in 8 of 15, match
   log-loss -0.0006 in 6 of 15); today nothing moves by 0.3 (Vancouver Cup 21.4 -> 21.4, West 82.7 -> 82.9, St. Louis 12.5 -> 12.3).
5. Eliminated-team dock `dead_dock_goals` 0.35 with `dead_dock_min_odds` 0.02: backtest points log-pmf better in 10 of 15 seasons,
   points rmse in 12, playoffs 10, conference 10; today West Vancouver 82.7 -> 82.5, St. Louis 12.5 -> 12.7, Cup unchanged,
   playoffs LA Galaxy 63.0 -> 64.7, Red Bulls 51.4 -> 53.0, Cincinnati 73.9 -> 72.8, Colorado 75.1 -> 74.2. Alternative 0.5:
   conference better in 13 of 15, Galaxy 65.2, Red Bulls 53.5, Colorado 73.8.
6. Replace the shade with mechanisms: rating_sd 0.20 -> 0.10 (drift 0.01 unchanged), dead_dock_goals 0.5 (with proposal 5's
   exemption), shade east/west 1.5 -> off. Backtest vs today's setup (0.20/0.01 + shade 1.5): conference-winner log-loss raw
   0.1412 vs shaded 0.1386 (the shade's 30-race edge), playoffs 0.2981 vs 0.3028 (12 of 15 seasons), points log-pmf -3.1519 vs
   -3.1571 (9 of 15), tails 0.214 vs 0.202. Today's futures: measured on request (what_if supports every knob).
7. Current round's posted Pinnacle lines in the fit (`posted_in_fit` on). Today (200k): Cup Vancouver 21.4 -> 21.5, Philadelphia
   8.7 -> 8.4, St. Louis 8.2 -> 8.4; West Vancouver 82.7 -> 82.5, St. Louis 12.5 -> 12.8; top-4 St. Louis 95.4 -> 95.6.
8. With 7: rating_sd 0.20 -> 0.15 and dead_dock_goals 0.5 (exemption 2%). Today: Cup Vancouver 21.4 -> 21.8, Nashville 19.1 ->
   19.2, St. Louis 8.2 -> 8.5; West Vancouver 82.7 -> 82.6 (raw 70.1 -> 70.0), St. Louis 12.5 -> 12.9, Dallas 4.6 -> 4.3; playoffs
   Galaxy 63.0 -> 65.8, Red Bulls 51.4 -> 53.6, Portland 20.1 -> 21.5, San Diego 13.5 -> 12.2; top-4 San Jose 43.5 -> 45.8,
   Chicago 65.5 -> 66.6, Houston 43.7 -> 42.6. At 0.10 instead: Cup Vancouver 22.1, Galaxy 66.0.
Not proposed (evidence against): the fading ridge (slope 1.20 -> 1.05 against Pinnacle but results flat, points rmse worse, sim
playoffs worse in 8 of 15 seasons; it would move Vancouver Cup 21.4 -> 22.6 and West 82.7 -> 84.2); the conference offset; ridge 0 (loses 11 of 15 seasons on points; Vancouver Cup 20.5 -> 21.9); any half-life change; a
footballdatabase or g+ weight (gains 0.001 of log-loss, 8 of 15 seasons; fdb 15% would move Vancouver Cup 20.5 -> 15.6 on a
monthly-lagged source); xG half-life 45 -> 90 (1.0138 vs 1.0141, 8 of 14; Vancouver Cup 20.5 -> 22.8, Nashville 18.6 -> 17.5).

## 13. Close-tracking session 2026-10-15 (Zac: "attack everything", yardstick = track Pinnacle's close; section 1)
Tooling: `scripts/close_track.py` (walk-forward, every match date of 15 seasons, each close scored from the ratings a week out,
lag 7, and on the morning, lag 0; league home edge as known month by month from a 90-day fit, so the bias is ~0); `sim/kalman.py`
(Kalman-filter ratings: one random-walk strength per club, every close a noisy difference measurement, full covariance across
clubs so a club with few recent closes moves further on its next line); the filter runs in the backtest (`"kalman": {...}` recipe),
in `what_if.py` (`rating_method=kalman,kalman_q_day=...`) and in the live build behind `rating_method` (wls, OFF).
Data fact: the OpticOdds Pinnacle history carries only the opener and the close per market (`entries` empty), so "the full price
path" reduces to openers as a second, noisier measurement (2025-2026 only); the openers are dated kickoff minus 5 days.
- **Kalman grid** (`kf_grid1-2.csv`, 67 pairs): rmse a week out is flat along q_day/s = 0.12 (0.03/0.25, 0.04/0.35, 0.06/0.5:
  0.2674-0.2677), q_off 0.05-0.15 indifferent; slope 0.93 (a shade wide), bias 0.003. Chosen 0.03 / 0.25 / 0.1 (config, provisional,
  method OFF). Lag 0: 0.249.
- **Team totals** (`scripts/calib_team_totals.py`, build prompt section 6, never built before today): the sim's constant 3.2
  misses Pinnacle's total by 0.332 goals rmse on 670 walk-forward totals 2025-2026; `totals_fit` (base + both clubs' offsets,
  hl 30, ridge 0.25) 0.216 (lag 7: 0.227); longer half-lives lose monotonically. Today: base 3.37, Inter Miami +0.55,
  Cincinnati +0.30, Orlando +0.26 ... NYCFC -0.29, Colorado -0.30, Houston -0.40. Wired into run_sim/what_if behind
  `team_totals_enabled` (OFF). 5000-season what-if: Cup Nashville 18.8 -> 19.8, Miami 15.2 -> 13.8; West St. Louis 11.8 -> 13.1.
- **Kalman variants** (`kf_var1.csv`, a week out, 15 seasons, wins vs the plain filter 0.2676): current round's posted lines
  applied to the state 0.2537 (15/15 seasons); xG blended 25% at hl 45 (rescaled to the filter's spread) 0.2555 (13/15), xG fused
  inside the filter as a measurement (sd 0.8) 0.2576 (14/15), weaker; posted + xG fused 0.2491; openers as a second measurement
  no gain (0.2673, 2/15); spread x0.95 0.2658 (12/15; unnecessary once xG is in: slope 0.996); p0 and the expansion prior do not move it.
- **Rest and congestion** (`scripts/congestion.py`, `outputs/calibration/congestion.md`, residual = close minus the plain filter on the
  morning of the match): with the cups counted (2025-2026, 975 matches) the close moves +0.018 goals per day of rest difference
  (se 0.004), -0.055 per extra match in the previous 7 days (se 0.013), a short week (3 days or fewer) costs -0.054 (se 0.023);
  MLS-only over 15 seasons: short week -0.044 (se 0.010), +0.008 per rest day (se 0.002). Real but small: removes about 0.004 of
  rmse overall, 0.05-0.1 goals on a cup week. No cup matches remain for the 2026 run-in (Open Cup and Canadian finals aside), so it
  does not move today's futures; it belongs in the fixture adjustment and in the fit's measurements for next season.
- **Least squares vs the filter on the same 6251 closes, a week out** (`wls1.csv` + `kf_var1.csv`; rmse, slope, seasons better than live):
  live 0.2677 / 1.20; market-only hl 28 0.2731 / 1.12; ridge 0 0.2699 / 0.95; hl 14 0.2883; hl 21 ridge 1 0.2919; xG hl 90 0.2674;
  live + posted lines 0.2553 / 1.18 (15/15); posted + fading ridge (mw 15) 0.2505 / 1.10 (15/15); plain filter 0.2676 / 0.93 (10/15);
  filter + xG 25% 0.2555 / 1.00 (15/15); filter + posted 0.2537 / 0.95 (15/15); filter + posted + xG fused 0.2491 (15/15).
  On the morning of the match (lag 0, the posted recipes see the close itself): live 0.2510, filter + xG 0.2358.
  By phase (lag 7): the filter is too wide early (slope 0.82 before matchweek 10: it carries last season's spread, which the market
  discounts) and right from mid-season; live is too flat in every phase (1.13-1.25). Off-season reversion (`off_shrink`) under test.
- **Posted + xG combinations** (`kf_var2.csv`, a week out, vs filter + posted 0.2537): + xG blended 25% hl 45 **0.2458** (13/15 seasons,
  slope 1.006, cross-conference 0.2515 vs live 0.2700); xG fused at sd 0.6 0.2450 (13/15); fused 0.8 + blend 15% 0.2445; xG 35% 0.2503;
  xG hl 90 0.2467; q/s 0.02/0.18 or 0.04/0.35 identical (0.2459). By season the filter recipe beats live in 2013-2017, 2019-2026 and
  ties 2012; 2026: 0.2510 vs 0.2657 live. Candidate recipe: `rating_method kalman` (0.03 / 0.25 / q_off 0.1) + `posted_in_fit` +
  the existing 75/25 xG blend. First season-backtest look (2026 only, six checkpoints): close rmse 0.336 vs 0.345 live but match
  log-loss 1.0782 vs 1.0740 and expected-points rmse 6.41 vs 6.28: tracking the close and predicting results pull apart; the
  15-season ratings and sim stages are running (`kf_ratings1`, `kf_sim1`).
- **Season backtest, ratings stage, 15 seasons** (`backtest/kf_ratings1.csv`; live / live + posted lines / filter + posted + xG):
  match log-loss 1.0125 / 1.0117 / 1.0120 (filter better than live in 8 of 15), close rmse over the rest of the season 0.3329 /
  0.3263 / **0.3209** (15/15), expected-points rmse 6.046 / 6.009 / 6.032 (6/15). The filter's gain is late in the season (match
  log-loss 1.0001 vs 1.0015, close 0.288 vs 0.311); early it ties. The single-season look above was 2026 noise.
- **Off-season reversion and rest** (`kf_var3.csv`, on top of filter + posted + xG 0.2458): strengths reverting 25% toward the mean
  across the off-season (`off_shrink` 0.75) **0.2437** (14/15; early season 0.2607 -> 0.2547, early slope 0.93 -> 1.02); 0.9 0.2445,
  0.6 0.2444. The rest adjustment in the measurements (0.01 or 0.018 goals per day of rest difference) does not help the filter
  track (0.2453 / 0.2462, 8/15): Pinnacle prices rest, but netting it out of the closes does not sharpen the strengths; dropped
  from the ratings. Final candidate: Kalman 0.03 / 0.25 / q_off 0.1 / off_shrink 0.75, posted lines in, xG 25%: **0.2437 vs live 0.2677**.
- **Season backtest, sim stage** (`backtest/kf_sim1.csv`, 4000 seasons, current round priced off its line, pairs 0.20/0.01 and
  0.15/0.01; filter + posted + xG vs live at 0.20/0.01): points log-pmf -3.1518 vs -3.1584 (better in 10 of 15), points rmse 6.028
  vs 6.034, tails 0.204 vs 0.205 (both honest: the 0.20/0.01 pair needs no re-set for the filter), playoffs 0.3027 vs 0.3018
  (8/15), conference 0.1445 vs 0.1434 (6/15), Shield 0.0893 vs 0.0879. A wash on the position pools, better on points, best on the
  close: the filter changes how close we sit to Pinnacle week to week, not how the season resolves.

### 13a. Proposals from the close-tracking session (put to Zac 2026-10-15; 9 and 10 APPLIED the same evening on "Ok do it all"; section 5 has the effect; 11 stays a 2027 item)
9. **Kalman-filter ratings with the current round's lines** (`rating_method` kalman: q_day 0.03, s 0.25, q_off 0.1, off_shrink 0.75;
   `posted_in_fit` on; xG stays 25% through the source config). Close a week out: 0.2437 vs 0.2677 live (better in 15 of 15 seasons;
   2026: 0.249 vs 0.283); slope 1.04 vs 1.20 (the ratings stop being too flat); cross-conference gap 0.249 vs 0.270. Season backtest:
   points log-pmf better in 10 of 15, playoffs and conference a wash, tails honest at the frozen 0.20/0.01 pair. Today (200k):
   blend spread 0.341 -> 0.380; Cup Nashville 19.1 -> 20.3, St. Louis 8.2 -> 9.6, Vancouver 21.4 -> 21.3, Miami 14.7 -> 14.4,
   Philadelphia 8.7 -> 9.0; West St. Louis 12.5 -> 13.9, Vancouver 82.7 -> 82.0, Dallas 4.6 -> 4.0; playoffs NYCFC 33.0 -> 35.1,
   Red Bulls 51.4 -> 49.4, Columbus 22.6 -> 24.1, Galaxy 63.0 -> 64.2; top-4 Houston 43.7 -> 40.5, St. Louis 95.4 -> 96.3;
   Cup finalist St. Louis 18.2 -> 20.8, Nashville 29.6 -> 31.2. Ratings today: St. Louis +0.27 -> +0.41, Nashville +0.61 -> +0.69,
   Vancouver +0.71 -> +0.76, Philadelphia +0.63 -> +0.72, Montréal -0.36 -> -0.48 (rank correlation with live 0.993).
10. **Per-team totals** (`team_totals_enabled` on, hl 30, ridge 0.25): an unlined fixture's total tracks Pinnacle's (rmse 0.216 vs
    0.332 goals for the constant 3.2). Today (200k) it moves nothing by 0.3 points (Cup within 0.1, West Vancouver 82.7 -> 82.5,
    Red Bulls playoffs 51.4 -> 52.1): a correctness item for match-level prices and the draw rate, not a futures mover now.
11. **Rest in the fixture adjustment**: measured (Pinnacle prices +0.018 goals per day of rest difference with the cups counted,
    a short week -0.05), but it neither sharpens the strengths nor touches the 2026 run-in (no cup weeks left), so NOT proposed
    for this season; it goes into the 2027 build with the schedule's cup dates (`scripts/congestion.py` has the measurement).
Both 9 and 10 together (200k): Cup Nashville 19.1 -> 20.2, St. Louis 8.2 -> 9.7, Vancouver 21.4 -> 21.4, Miami 14.7 -> 14.3; West
St. Louis 12.5 -> 14.0, Vancouver 82.7 -> 81.8; playoffs NYCFC 33.0 -> 34.6, Red Bulls 51.4 -> 49.8, Galaxy 63.0 -> 64.3; top-4
Houston 43.7 -> 40.1. What-if archive: `outputs/calibration/whatif_kalman_totals_2026-10-15.json`.
Not proposed: openers as extra measurements (no gain); xG fused inside the filter (ties the blend, more plumbing); a spread
multiplier (unnecessary once xG is in); the fading ridge on the least-squares fit (0.2505 with posted lines: good, but the filter
is better still and does the same job by construction). Key-player absences cannot be measured here: no historical injury feed
exists before 2026-10-12 (the OpticOdds injuries endpoint is current-state only), so the injury layer stays a tier question for Zac.
- **Verification of the applied configuration at the Kalman ratings** (`backtest/kf_final_sim.csv` vs `kf_sim1.csv`, 4000 seasons, 87
  season-checkpoints; dc -0.05, dock 0.5, shade off, sd 0.10 / drift 0.01 vs the morning's dc 0, no dock, shade 1.5, sd 0.20 / 0.01):
  playoffs log-loss 0.2984 vs 0.3027 (better at 63 of 87 checkpoints), conference 0.1434 raw vs 0.1445 shaded (57 of 87), points
  rmse 6.009 vs 6.028 (52), points log-pmf -3.1539 vs -3.1518 (tie, 48), tails 0.220 vs 0.204 (a shade too narrow now: 22% of real
  points totals in the 20% tails; at sd 0.20 with the same mechanisms the tails are 0.194 and playoffs 0.3007). The evidence the
  decision was made on (11h/11i, least-squares ratings) holds at the filter's ratings; the shade is not missed on its own pool.
