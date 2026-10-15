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
Every ratings decision is judged by one number: distance from Pinnacle's next closing line (goals of expected margin, in
handicap units, out of sample). Pinnacle is the only match-line source and the only futures comparison. Kalshi, Polymarket
and soft-book prices never enter the model. Match games are not bet; futures edges are Zac's, by hand, from the site.

## 2. Rules that must not be broken
- Frozen knobs (section 6 below) once calibrated: `rating_sd`, `drift_k_sim`, `drift_cap`, `shared_goals_mean`,
  `home_edge_goals`, `avg_total_goals`. A price looking wrong is a ratings question, never a variance question.
- The blend is regenerated, never edited. Judgment goes in `adjustments.csv`, injury tiers, call-ups, scenarios, on Zac's word.
- Real results never feed drift. Posted lines never enter the ratings fit; they shrink the fixture's line only (s = 0.35).
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
| Bracket | 1 v WC, 2 v 7, 3 v 6, 4 v 5; semis (1/WC) v (4/5), (2/7) v (3/6) | standard MLS bracket; VERIFY on the playoff page when reachable |
| Tiebreakers | points, wins, gd, gf, fewest disciplinary points, away gd, away gf, home gd, home gf, coin toss | Wikipedia 2026 club-season pages quoting the Competition Guidelines; one secondary site claims an intra-conference head-to-head step — UNRESOLVED, re-check the 2026 Competition Guidelines PDF; chain implemented exactly as listed, disciplinary points default to 0 (no feed) |
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
| rating_sd | 0.30 | points backtest log-pmf best at 0.30 (-2.5830; 0.20-0.35 within 0.008); positions wanted 0.0 (shade carries it). First pass said 0.25 before the replay was corrected to fit on all seasons' closes |
| drift_k_sim / drift_cap | 0.0 / 0.10 | market re-rating +0.001 per goal of surprise; backtest flat-to-worse with drift |
| shade | east/west b 1.5; everything else raw | leave-one-season-out: conference winner 0.1205 vs 0.1213 raw; shield, playoffs, top-4, spoon, bottom lost held out |
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
| MLS Pinnacle lines 8:52 ET | trig_01SYLkPVCqP65bbbc5XdvEdB | daily 08:52 America/New_York | weekly.py (fetch, run + publish if a match-day finished), apply pending site settings first, create the capture Routines for the next eight days |
| MLS close capture Wed Oct 14 7:20 PM ET | trig_01AWKP5ZxVw52K2sB28tVoYx | once 2026-10-14 23:20Z | fetch_pinnacle.py --close, commit, push |
Capture Routines are one-shot, named "MLS close capture <date> <time ET>", created by the 8:52 routine from
`scripts/close_schedule.py --json` (ten minutes before each distinct kickoff). CLV log and forecast check run inside every run.
Status: none has fired yet (Phase 4 acceptance pending). The 8:52 routine republishes to the URL in section 10.

## 10. Website
`site/index.html` template (six tabs, dark matte, centred tabs, American odds, ET, crests on grey discs; a web-worker port of
the engine for the Settings resim; the Scenarios tab re-ranks a 20k-season football-only sample embedded in the page);
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
1. **Ridge toward zero in the market fit (`ridge_lambda` 0.5)** — the PDF is plain least squares with a sum-to-zero row. Flattens the
   live market ratings 7% (sd 0.389 -> 0.360 at hl 28 on 2026-10-15). Under test in section 11.
2. **Half-life 28 days picked on next-close accuracy**, not the season backtest. Under test.
3. **Blend spread never compared with the market's** (PDF: compare every time the blend changes). Live: blend sd 0.342 vs market
   0.389 at ridge 0, 12% flatter in total (ridge 7%, blending two sources correlated 0.74 another 5%). Under test (`blend_rescale`).
4. **xG source**: raw spread 1.3x the market's at the same checkpoints (correlation 0.63 early to 0.75 late in the season), so the
   PDF's rescale-to-the-market step is right for it; the blend weight was set on next-close rmse over three seasons. Under test on 13.
5. **Posted-line shrink 0.55 on fixtures with a fresh Pinnacle line** — the PDF prices the whole current round off the market
   (median devigged three-way across books, s = 1) and every later round off ratings. Ours mixes 45/55 and only for Pinnacle.
6. **Shade on the conference pool (logit stretch b 1.5)** — not in the PDF; the PDF's answer to "every top team's price is off at
   once" is the variance pair, and to one team's price a ratings fix. The shade papers over whichever of the two is wrong.
7. **Drift surprise vs the dice** (`sim/season.py`): with a posted line the dice roll around g = (1-s) g_model + s g_pinn but the
   surprise uses g_model. Inert while drift_k_sim is 0; the PDF's trap if drift is ever switched on (fix: surprise against g).
8. **No Dixon-Coles**: the engine gives 22.7% draws vs 25.1% realised and 24.9% in the devigged close (0-0 6.3% vs 4.6%). The PDF
   says add it once the draw rate is checked and misses; it misses by 2.4 points.
9. **Shared-goals component (c 0.10)** instead of independent Poissons — an addition, calibrated from Pinnacle's ladders; keeps
   margin noise right where totals are known (section 11).
10. **No eliminated-team / clinched / dead-rubber docks**, no congestion penalty, no per-team volatility ladder (PDF: after v1;
    congestion and dead rubbers to be measured in the residuals first).
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
| ClubElo | club pages exist for 4 MLS clubs only; API host resets the connection | per match from Oct 2022, 4 clubs | not usable |
| 538 SPI | dead | 2017-18 only reachable (datahub mirror); Wayback blocked here | not usable |
| Massey | Cloudflare challenge blocks every fetch from this container | unknown | not usable from here |
| Sagarin (through Dec 2024), ESPN SPI (not published for MLS), Global Football Rankings (MLS from Oct 2025), Kickoff.ai, Dunkel, Power Rank, Sonny Moore (no archive), forzapitch (book-blended) | - | - | not usable |
Reading: no public model beats market-only on its own; every blend at 15-35% adds 0.0004-0.0013 of match log-loss and wins 8-9
of 14-15 seasons, the same order as season noise. xG helps early in the season (thin market data), footballdatabase mid and late.
Recommendation (Zac decides): keep xG at 25%; take Opta as the live sanity anchor (daily, model-based, independent of our inputs),
displayed next to the blend and never weighted; no further source on the evidence. Loaders: `scripts/public_sources.py`;
fetchers: `scripts/fetch_public.py` (Opta needs the weekly `--dates` list; `--latest` for today).
