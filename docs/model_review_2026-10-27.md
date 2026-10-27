# Full model review, 2026-10-27 (Zac: "full analysis and report of everything ... we are about to start using this model to bet real money")

Read-only. Nothing in the model, the data or the page was changed. Five parallel reviewers (engine and markets; ratings pipeline;
data feeds and routine; yardsticks and reports; page and docs) plus independent checks in this session. Every finding below was
verified against the code and the files on disk (run 20261027T124533Z, results through Oct 25, 44 fixtures left). Line numbers
are in the committed files on the live branch. Section 7 is the numbered list for "do N".

## 0. Verdict

**The engine and the ratings pipeline are sound.** The published 200k run reproduces exactly from its inputs; every pool sums and
chains correctly; the goal model, Dixon-Coles, drift, dock, tiebreakers, bracket, extra time and locked results all do what the
notes say; today's blend reproduces to four decimals; the filter's update equations, signs, home edges and posted-line handling
are right; no close is used twice; nothing from after the as-of date leaks into the live ratings. Tests pass. Every input is current.

**Three things stand between this and real money:**

1. **The playoffs are not wired** (section 3). No playoff fixture can ever enter the schedule file, so from Nov 8 there are no close
   captures, no fallback closes, no Games rows and no rest dates for any playoff game; the MLS injury report fetcher cannot find the
   Decision Day or any playoff report; the close capture keys on Pinnacle's own start time and already lost a close when Europe's
   clocks changed on Oct 25 (the US changes this Sunday, Nov 1).
2. **The evidence behind the variance knobs is contaminated** (section 4). Every rest-of-season backtest season includes that
   season's playoff games as league fixtures (2025: 540 matches, 30 of them playoffs; 2024: 29; 2019: 13), so the "20% tails
   honest", "playoffs log-loss 0.298" and conference figures that set rating_sd 0.10, drift 0.01 and the 0.5 dock scored a
   corrupted target. The directions probably survive (paired comparisons share the corruption); the calibration claims do not.
3. **The current round's line is over-trusted** (section 4). The yardstick's "posted lines" are the closes of the next three days,
   not the line as fetched days out; the live line 1-3 days out sits 0.21 goals from its close, so a posted-line sd of 0.22
   weights it about twice as precisely as the evidence supports.

Nothing found changes a futures price by more than about a point today. The items that matter for accuracy are the hands
(section 5), the dock's 2% cliff, and the home-edge zero point.

## 1. Verified correct (what the reviewers checked and found right)

- **Engine** (`sim/engine.py`): home mean T/2 + g/2, away T/2 - g/2, shared component c = min(0.10, min mean - 0.15); E[margin] = g
  exactly (2M draws); Var(margin) = T - 2c; the Dixon-Coles rejection reproduces the corrected grid (draw rate within 0.0004);
  the 40-pass cap leaves nothing unresolved at live totals; the goal floor never binds.
- **Season** (`sim/season.py`): one N(0, 0.10) draw per club per season; drift 0.01 x (actual minus the margin the dice used), cap
  never binds; the dock fires on a valid sufficient condition at the first fixture of each date; already-out and pre-pass-exempt
  clubs never docked; the dock lives in the rating so the dice, the drift and the playoffs all see it.
- **Standings** (`sim/standings.py`): the 2026 chain in order (points, wins, gd, gf, head-to-head inside the conference with the
  re-run after the top club, fewest disciplinary points, away gd, away gf, home gd, home gf, coin); 3- and 4-way ties checked by hand.
- **Playoffs** (`sim/playoffs.py`): top 9; 8 hosts 9, straight to penalties; Round One 1 v WC, 2 v 7, 3 v 6, 4 v 5, best of three,
  higher seed hosts games 1 and 3; fixed bracket (no reseeding); semis, finals and Cup play extra time (30 minutes at a third of
  the means, no Dixon-Coles) then a coin; Cup hosted by the better record; team totals clipped 2.0-4.5; locked results in meeting order.
- **Markets** (`sim/markets.py`): every pool sums exactly; East + West Cup shares = 100%; cup <= finalist <= conf final <= semi <=
  playoffs for every club; power devig right both ways and refuses one-sided pools; the published markets.json reproduced to 0.0.
- **Ratings** (`sim/kalman.py`, `scripts/refresh_ratings.py`): h = e_home - e_away, full covariance, gain and update right; y =
  gd_fit - league edge - club delta - factors (home minus away), the same vector and sign in the add-back; closes 0.25, posted
  0.22; off-season >= 45 days adds q_off and shrinks 0.75; dedup on (date, home, away) by book priority (6282 unique); posted rows
  skipped once a close exists; each posted line enters the state once and prices its fixture once; the ratings "without this
  round's lines", the forecast check and the CLV log are out of sample; the xG fit is walk-forward, rescaled to the market sd, centred;
  today's blend reproduces to 4 dp; blend_raw + hand = rating; hand week 2026-10-27 carries week 2026-10-20 (MIA +0.08, NSH +0.06,
  SEA +0.05, HOU +0.05, COL -0.05, LAG +0.04); adjustments.csv empty.
- **Data**: 510 schedule rows, 34 per club, 466 final + 44 scheduled; the 44 match ESPN today on date, kickoff, home side and id;
  every score equals ASA's; 416 OpticOdds closes + 14 captures (all 8-9 minutes before kickoff) + 2 fallbacks; exactly 34 games
  with no Pinnacle close; all 14 Oct 28 lines carry moneyline, handicap and total; Pinnacle's guest key and league id work;
  Opta, discipline, xG, absence dataset and injury list all current; time zones keyed on ET via zoneinfo.
- **Yardstick**: `close_track.py` is walk-forward in every input (closes before asof, xG before asof, trailing-ten absences before
  asof, eliminated status as of asof, monthly home edge fitted on closes before the month, replacement rates from the previous
  season). The live recipe reproduced today: **rmse 0.2383 a week out** (bias +0.003, slope 1.02, 6282 closes, 15 seasons;
  `outputs/calibration/close_track/review_live.csv`).
- **Page**: all 7 futures pools x 30 clubs equal markets.json to 1e-5; xPts, Top 4, Bottom, ratings, hands, 95% band, deltas v the
  previous run, Pinnacle fair (power devig), Model and Gap all equal their sources; American odds conversion right; the header
  stamp is right; the bracket with no picks equals markets.json; ✓ marks today are real clinches; an unedited Run moves nothing;
  no console errors at 1400 or 400 px.
- **what_if** reproduces run_sim at the same inputs (paired 5000: identical).

## 2. Findings that move or misstate a number today

2.1 **The absence dataset and the live add-back use different "regular" thresholds** (`scripts/weekly.py:88` runs `absences.py build`
    with the CLI default share-min 0.5; `scripts/absences.py:280`; the live `absence_values.py` ramps 0.3 -> 0.6). So the closes
    were netted, and factor_abs -0.48 fitted, on a dataset where a player at 0.45-0.55 of his club's minutes is worth about nothing,
    while the same player is worth 0.4-0.7 of his value when a fixture is priced. Today: Red Bulls add-back 0.075 goals of missing
    value on the live ramp v 0.003 on the dataset's (Che at share 0.503), Cincinnati 0.050 v 0.000; x -0.48 = up to 0.034 goals on
    every remaining Red Bulls margin (about 1 point of a home-win price; futures under half a point). Fix: one basis (pass
    `--share-min 0.3` and make it the default, rebuild every season, re-read the beta), then rerun.

2.2 **The hand review never reaches a verdict.** `scripts/morning.py:333-336` dates a hand from the newest hand_log row, and the
    weekly carry-over writes rows with the edit's timestamp ("carried from week 2026-10-13", saved 10-24). Every hand has read "too
    early" for a week; Miami's +0.08 has four closes since Oct 16 and the page says "0 closes since set 10/24". The keep / raise /
    trim / drop verdicts Zac was told to act on have not fired once. Fix: date a hand from the first week its value appeared.

2.3 **The track record is priced with the day's actual lineups.** `scripts/site_data.py:323-324` adds each played game's factors from
    the lineups as they were; the morning's 7d / 30d / season rmse and the "edge share" come from those rows. Recomputed on 466
    games: 0.221 with the lineups, 0.230 with the honest trailing-ten forecast, 0.228 with no absence term. The 30-day figure
    0.231 is 0.238 honestly. The "miss v close 0.22 (normal 0.24)" line overstates what the morning's model could know by about
    0.008 goals. Also the eight track rows of Oct 14-17 carry hands that were sized on those very games (rmse 0.282 with them,
    0.308 without). Fix: price played games with the injury list as it stood that morning; apply a hand to a track row only after
    its saved_at.

2.4 **Three sign conventions for one quantity.** Forecast check: model minus Pinnacle (-0.070 today); Morning track: ours minus close
    (30d -0.017); Risk tile: close minus model ("bias +0.03"). The Risk tile and the Morning track show the same direction with
    opposite signs. Fix: one convention (ours minus Pinnacle), one label.

2.5 **Page: the club drawer's record shows 0 losses for every club** (`site/index.html:846` counts only the page's 9-week window:
    Nashville "21-7-0", true 21-7-3). **A 100% market prints "-Infinity"** in the drawer's futures line (`:820`, Nashville Playoffs,
    Conf 1st; Vancouver and Dallas Playoffs). **Three names for one pool**: the drawer calls Reach MLS Cup "MLS CUP" and Win MLS Cup
    "WIN CUP"; Movers says "MLS Cup" / "Win Cup"; the Table says Reach / Win MLS Cup. A tile reading "MLS CUP +151" under Nashville
    reads as the Cup-winner price (+248). **A 4,000-season bracket preview is labelled "20,000 seasons" on the Table** (`:517`), and
    a seed pin reaches the Table as "Conf 1st –-79.6" with xPts unchanged. **The Morning "Why" column is clipped at 1400 px** (the
    card scrolls sideways with no visible bar).

2.6 **The confidence range the docs tell a bettor to check is not on the page.** CLAUDE.md 6 and 17, docs/edge_finding.md and
    docs/forecasting_principles.md say the Risk tab's futures range decides whether an edge is noise; the tab went 2026-10-23 and
    nothing shows the range (risk.json is still embedded in the page payload). The range itself is a sensitivity band (four recipe
    alternatives at 20k) whose cells sit at the Monte Carlo noise floor (0.3 points per alternative at 20%), not a posterior.

2.7 **Same-seed comparisons in the Python engine are not paired.** The Poisson sampler and the Dixon-Coles redraw consume a
    data-dependent number of random values, so the first fixture that differs shifts every later draw: a +0.001 nudge to Nashville
    gives 0% identical seasons and the same Cup winner in 17% (independent runs). Published prices are unaffected (identical inputs
    reproduce exactly), but every "same seed, so not noise" delta in the decision log, what_if, risk.py's ranges and the hand sizing
    carries full Monte Carlo noise: se of a difference 0.45 points at 20k and 0.14 at 200k on a 28% price. Moves under 0.5 points at
    20k or 0.2 at 200k are noise. The page worker is paired (one uniform per draw); the Python engine is not. Fix: inverse-CDF
    sampling on one uniform per draw, or a substream per fixture.

2.8 **edges.py writes our fair to 5 decimals** where the 200k SE at 29% is 0.001; `bracket_slots` 4 dp. Cosmetic but it reads as
    precision the sim does not have.

## 3. Operational risks, in date order

3.1 **This weekend (Oct 31 / Nov 1, US clocks go back Nov 1 06:00Z).** `scripts/fetch_pinnacle.py:70-71, 175` drops `isLive`
    matchups and takes as "soon" only matchups whose Pinnacle start time is 0-26 minutes ahead. On Oct 24-25 Pinnacle's start time
    for Colorado v Vancouver and RSL v St. Louis read 00:30Z, 02:30Z, 01:30Z, then 02:30Z and 00:30Z within a minute of each other
    (Europe's clocks went back at 01:00Z); the Colorado capture 9 minutes before kickoff was filed as a fallback and RSL v St. Louis
    was off the board at both fetches, so its "close" is 69 minutes stale. The Oct 31 night and Nov 1 kickoffs are exposed to the
    same wobble. Fix: pick fixtures by the schedule's kickoff joined on (date, home, away), keep an `isLive` matchup whose scheduled
    kickoff is still ahead, and rank a line fetched within 15 minutes of the scheduled kickoff as a capture. Until then: arm a second
    capture 25 minutes before each Oct 31 / Nov 1 kickoff.

3.2 **Decision Day (Nov 7).** `scripts/fetch_psr.py:185-224` builds only matchday-N slugs. Last season the Decision Day report was
    under a non-matchday slug and the playoff reports were "wild-card-games-<weekday>-<month>-<day>", "round-one-best-of-3-series-
    game-1/2/3", "...-conference-semifinal". Effect: the Nov 7 round runs on the Nov 1 report silently (the freshness check accepts a
    report up to 8 days old), then fetch_psr fails from about Nov 9 and the list stops following the league. Fix: add the slug forms
    and a "paste a slug" path in the routine. Matchday 33 (Oct 28) and 34 (Oct 31 / Nov 1) are covered.

3.3 **From Nov 8: no playoff fixture will ever enter `data/schedule.csv`.** `weekly.py` never runs `fetch_schedule.py`, and
    `fetch_results.py:32-37` refreshes only espn_ids already on file. Consequences: `close_schedule.py` arms no capture task for any
    playoff game; `close_fallback.py` and fetch_pinnacle's "missing" alarm are MLS-schedule-only (`close_fallback.py:248`,
    `fetch_pinnacle.py:159`); the Games tab and Morning lists show no playoff games; `sim/factors.py` rest dates lack the playoff
    dates. The results side works: ESPN's playoff events are tagged "MLS Cup Playoffs" with the shootout winner, and
    `real_playoff_results` locks them. Fix: run `fetch_schedule.py` in the routine from Nov 8 (it overwrites the whole file; its
    guard protects the MLS count), extend the fallback and the alarm to every competition, verify the playoff rows' kickoffs before
    arming slots.

3.4 **Pinnacle may list the playoffs under another league name** (today one MLS league, id 2663; `find_mls_league_id` takes the exact
    name first). If so, nothing is fetched and every playoff game is priced off the ratings. Check the league list on Nov 16.

3.5 **Absences freeze at Decision Day.** `scripts/absences.py:74` skips knockout games, so the stale-by-play rule and the trailing-ten
    regulars stop at Nov 7: a player who returns in the Wild Card is still counted out, and one hurt in it is unvalued until the PSR
    lists him (3.2). `fetch_xg.py` does import ASA's playoff games and `sim/ratings.py:171-174` would feed them to the xG source;
    decide whether playoff xG should enter (the closes do not enter the state as playoff games either: they carry the league home
    edge and no absence data).

3.6 **Playoff games get no factors** (`sim/season.py:148-149` -> `knockout`: ratings plus the league edge only). A long, dated
    absence is priced for the remaining league games and vanishes in the bracket: Philadelphia's Sullivan (0.107 goals a game, no
    return date) = 0.052 goals per playoff game the bracket does not see. Fix: carry live absence rows with a blank or post-Nov-18
    return into the knockouts, or state the omission.

3.7 **A playoff result with no winner fails silently** (`sim/playoffs.py:46` prints to stderr; weekly.py shows run_sim's stderr only on
    a non-zero exit). Make it a freshness check.

3.8 **FIFA window Nov 9-17**: call-ups off by design; injuries picked up on duty reach the list only through the Wild Card PSR (3.2)
    or the news scan. The Risk blind spot says this correctly.

3.9 **A Pinnacle failure still publishes** (soft step): a rotated guest key gives a 403, fetch_pinnacle exits 1, the run prices the
    round off any line fetched within 3 days and the page publishes with day-old Pinnacle columns; freshness flags it. Acceptable if
    the routine's report leads with it (it does).

3.10 **Injury list hygiene**: Petković listed at Charlotte (he is Seattle's); Ebobisse, Tillman and Cabral Carter filed under LA
     Galaxy by the PSR parser when the league wrote "Los Angeles Football Club" on Oct 16 (`sim/teams.canon` returns None,
     `fetch_psr.py:150-152` inherits the previous club; the 10-23 report used "LAFC" and parsed); duplicate rows for Franco, Abou
     Ali, Steffen, Ku-DiPietro, Farnós, Borges, Puig (Ricard / Riqui); 27 open "optic" rows with no fetcher since Oct 19; 140 of 180
     rows have no return date; 44 rows have played since. None carries cost today (every duplicate or wrong-club row is 0), but a
     valued regular listed by two sources would be double-counted (`sim/factors.py:138-139` sums every costed row), and an LAFC
     absence is lost whenever the long name is used. Also 19 Optic "gtd" rows carry prob_out 1.0 instead of 0.5. Clean before the
     bracket is priced.

3.11 **Freshness checks that cannot fire**: nothing compares Pinnacle's kickoff with the schedule's (3.1 was invisible except as a
     "closes warn"); the PSR check accepts an 8-day-old report (3.2). Add both.

3.12 Minor: a fixed UTC-4 offset in `absences.py:79` and `fetch_psr.py:207` (wrong by an hour from Nov 1; no MLS kickoff sits in the
     04:00-05:00Z hour, so no date flips); reschedules reach the schedule only when the old or new date enters the 10-day results
     window (loud, not silent: the results check turns bad); `latest_posted` has no upper bound on fetched_at (`run_sim.py:81-87`),
     harmless live, look-ahead for any back-dated run; a straight red after a yellow is scored as a second yellow (7, should be 10).

## 4. Evidence and yardstick problems

4.1 **Playoff games inside every backtest season.** `scripts/replay.py:19-38` merges every close with football-data's results and
    never cuts at Decision Day; `backtest_season.py:259-283` simulates everything from the checkpoint and scores the final table on
    the same frame. In the history files 2024 has 18 clubs with more than 34 games (max 39), 2019 has 14 (max 38), 2025 is 540 =
    510 + 30. So at matchweek 29 up to a quarter of the "remaining season" is playoff games simulated as league fixtures (3 points,
    draws allowed, league home edge), and the "actual final points" include playoff results. Every sim-stage figure in CLAUDE.md
    11c, 11d, 11f-11i, 13 (kf_sim1, kf_final_sim), 14e (fh_sim) and 14l (gd_sim) scores that target: points log-pmf, points rmse,
    the 20% tails, playoffs, conference and Shield log-loss. rating_sd, drift and the dock were chosen partly on the tails and the
    playoff log-loss. close_track also scores about 240 playoff closes (4% of 6282) with the league home edge. The match-level checks
    that use "the last ten rounds" (dead_teams, locked_seed) read the same seasons. Fix: cut each season at the date every club
    reached its quota (or carry a stage column), re-run fh_sim at the frozen pair, re-verify tails and playoff log-loss before the
    next knob decision; re-measure the dock (11g) on league games only.

4.2 **The yardstick's "posted lines" are the closes of the next three days** (`close_track.py:206-212`; also `backtest_season.py`,
    `risk.py:199-207`, `site_detail.py:222-230`). Live feeds the line as fetched on the morning. Measured on this season's captures
    (46 games): rms(close minus the morning's line) 0.175 on match day, 0.209 one day out, 0.213 two days out, 0.23 at first fetch;
    mean move +0.03 to +0.05 toward the home side. So (a) the measured gain of posted_in_fit (0.2676 -> 0.2537, 15/15) is a ceiling
    the live line cannot deliver in full, and the live 0.2383, the Risk tile's 0.248 v 0.240 and the lag-0 0.1325 inherit it;
    (b) kalman_s_posted 0.22 treats a line fetched 1-3 days out as sharper than a close (0.25) when its noise about the latent
    strength is about sqrt(0.25^2 + 0.19^2) = 0.31, so the filter weights the current round's early line about twice as precisely
    as the evidence supports. Fix: build the posted set from the harvested 2025-26 openers or the capture history and grid s_posted
    on it (expect 0.30-0.35); at minimum widen it on the 2026 evidence.

4.3 **Two home edges.** The filter nets a monthly 90-day fit (0.481 May, 0.468 Jun-Jul, 0.451 Aug, 0.447 Sep, 0.439 Oct) while every
    price adds back the frozen 0.44 (`run_sim.py:172`, `site_data.py:322`, the implied windows). A 0.00-0.04 home-side inconsistency
    that moves month to month; the filter has no intercept, so a wrong edge is not absorbed, it shows as bias in the forecast check.
    Today's forecast check is -0.070 on 14 lines (2.3 se); the last week ran -0.01 to -0.03 every day but one; the season bias is
    -0.009. Measured here: the closing home edge in the last 15% of each season is 0.023 goals above the rest (se 0.011, 11 of 14
    seasons), so a small late-season home bump is real. Fix: price with the same monthly edge the state was netted with (or net
    with the knob); then the forecast check reads cleanly.

4.4 **Selection without a holdout.** Every grid (67 Kalman pairs, 146 ratings recipes, 25 full-health recipes, three sim grids) was
    scored on the same 15 seasons and the best taken. Recomputed paired margins a week out: xG 15% v 25% -0.0008 +- 0.0007 (not a
    result); club deltas -0.0018 +- 0.0003 but in sample; full-health -0.0029 +- 0.0007 (4 se, real); the filter and the posted lines
    are the only large gains and the posted-line one is leaky (4.2). 0.001-level winners sit inside selection noise.

4.5 **Hand sizing.** 0.3 x the last-4 miss comes from a 2026-only carry-over (0.30, se 0.06) against 0.05 (se 0.02) over 15 seasons
    (14j). The review's "suggest" at 2-4 closes has noise 0.036-0.05 goals against a 0.03 keep threshold, so once 2.2 is fixed the
    verdicts will churn on noise. Measured today (60k paired, se about 0.25 points): the six hands move Miami's conference final
    47.0 -> 49.5, its Cup 13.8 -> 15.4, Reach MLS Cup 23.4 -> 25.2; Nashville Cup 27.2 -> 28.5; Houston semi 40.4 -> 42.5; Seattle
    semi 29.4 -> 31.4; Galaxy playoffs 47.6 -> 49.3; Colorado semi 21.1 -> 19.6; Philadelphia conference final 29.9 -> 28.8. More
    than any range on the Risk card.

4.6 **The dock's 2% cliff.** Minnesota (3.1% playoffs) is docked 0.5 goals in 77% of seasons, Portland (12.6%) 50%, Toronto (3.8%)
    40%, while Austin (1.0%), San Diego (1.1%) and D.C. (0.5%) are exempt and, not yet "eliminated" by the crude test, carry no
    -0.19 factor either, so their opponents get nothing. Today the whole live dock effect is the Minnesota, Portland and Toronto
    games: exempting them (or switching the dock off) moves San Jose top-4 57.4 -> 54.9, Houston 29.6 -> 30.6, LAFC 14.6 -> 15.2.
    The three clubs' states already carry Pinnacle's recent closes on a near-dead side, which is the double count the exemption
    exists to prevent, just above the threshold. Options: scale the dock by (1 - P(playoffs)) instead of a step at 2%; or dock in-sim
    eliminations at -0.19 (what the close prices) rather than 0.5 (what results show). Either needs 4.1 re-run first.

4.7 **Blend flatness on 2026 is the xG share, not the filter.** Slope of this season's closes on the match-morning ratings: Kalman
    state alone 1.03, 85/15 blend 1.08, with hands 1.08 (rmse 0.239 v 0.223: the blend is closer but flatter, because two sources
    correlated 0.70 averaged at 0.85/0.15 lose 4% of spread). The Risk tile's "ratings too flat" means the blend step. A rescale of
    the blend to the market sd is the knob; the 2026-10-21 stretch test found no 15-season gain, 2026 alone likes x1.10.

4.8 **Unset knobs**: kalman_s 0.25 and s_posted 0.22 (4.2); the 95% band's coverage unchecked (it is the filter's posterior with
    this round's lines, no xG or hand width); no posterior predictive checks on season outcomes (CLAUDE.md 18).

4.9 **Stale calibration text**: `backtest_season.py` reads dc_rho, dock, tiebreaks and totals from config at run time and records
    none; `backtest/README.md` does not index fh_sim, fh_sim2, gd_sim; `close_track/README.md` says no run carries club deltas
    (base9.csv does, 0.2383); `calibration/README.md` says layers_log rows after 10-15 are in sample (since 10-21 they score the
    no-lines ratings, out of sample); the 2026-10-12 reports are correctly marked historical.

4.10 **Edges (dormant, no key)**: the pooling weight is a constant 0.5, not measured; "cautious" is a minimum over four 20k
     alternatives, not a 0.2 quantile; no fees; futures CLV written and never read; a book's field counts as complete when our
     probabilities for its clubs sum to 0.97 (a favourites-only field devigs as complete). The arithmetic is right.

## 5. What could improve prediction power (in order of expected value)

5.1 Fix the evidence first (4.1, 4.2), then re-decide the variance pair and the dock on a clean backtest. Until then the frozen
    knobs stay; nothing here says they are wrong, only that the proof is.
5.2 Widen kalman_s_posted to what the capture history measures (4.2). Expected: the current round's early line pulls each club
    about half as far; today's ratings move under 0.03 on the clubs with Oct 28 lines.
5.3 One home edge for the state and the price (4.3): removes a 0.00-0.04 home-side drift and makes the forecast check readable.
5.4 One regular threshold for the absence dataset and the live list, beta re-read (2.1).
5.5 Hands: size on the 15-season carry-over (0.05 x the last-4 miss) rather than 0.3, or drop them and let the posted lines carry
    the week; keep the review honest (2.2, 2.3). Today's hands are worth 1-2.5 points on Miami, Nashville, Houston and Seattle.
5.6 Dock: continuous in P(playoffs), or at the netted -0.19 (4.6). Today it is three clubs' games.
5.7 Pairing in the engine (2.7): every what-if, range and hand delta becomes readable at 20k; nothing in the prices changes.
5.8 Playoff factors (3.6) and club deltas in the knockouts (LAFC +0.047, Seattle +0.043: about 1 point on a Round One they host).
5.9 A late-season home edge (+0.02 in the last 15% of a season, 4.3) is real but small (0.5 point on a home-win price): a 2027 item.
5.10 Not worth doing on the evidence: faster filter (14j), goal-difference source (14l), xG share change (4.4), spread stretch.

## 6. Stale text (the page and the docs say things the model no longer does)

Page: "Hand edits on the Ratings tab" (`index.html:346`), "the line's path" (`:345`, chart removed 10-24), "ET ET" in the header hover
(`:476-477`), the With-lines button hover carries the No-lines summary (`:554-556`), "settled" ✓ at 99.95% rather than a true clinch
(`:466, :615`; today's marks happen to be clinches), the Morning futures rows rounded from one decimal (`:926`, "+529" v the Table's
"+527"), a fallback close labelled plain "Close" (`:678-681`).
risk.py: "Level knockout game after 90 = coin flip (no extra time)" (`:478`) and the Draws tile note (`:367`): extra time is on since
10-25; the chat report reads these.
README.md: Risk tab, 7:40 and 8:52 tasks, "on a completed match-day", OPTIC_API_KEY as the secret (ODDS_API_KEY is the live one and
is absent, so edges.json has 0 prices every day). PLAN.md: "as of 2026-10-19", close precedence omits the fallback, "the Risk tab
shows", "8:52 ET task", OpticOdds, "if a match-day finished", the 7:40 task. scripts/README.md the same. config.json
`disc_points_enabled` note "no task refreshes them" (refreshed daily). docs/morning_routine_prompt.md:22 "Risk tab".
CLAUDE.md: the branches block (7:40 / 8:52), Known gaps (Risk tab Inputs tile; missing: ODDS_API_KEY absent, the two missed
captures, the items above), section 6 "the Risk tab's ranges are the current guide", section 10 (v45; the Morning, Table, Games,
Injuries and Risk paragraphs describe the page before 10-23/10-24), 11c2 "the shade STAYS at 1.5" with no SUPERSEDED mark, 14f
"not wired", 14i "the 7:40 routine's feed", 16 "Edges tab BUILT" with no removal note, 19 summarises the 10-21 review as open
(Edges tab, coin flip, tab dots, today screen are all done), section 9's weekly order omits fetch_headshots; sections 6, 6b, 7, 8,
11, 13, 14c-14h, 15-18 are dated records without a header saying so.
check_site.py would pass a page of dashes, a stale morning report, "Infinity" text (live today), the wrong drawer record, or a
Games tab with no rows.

## 7. Proposals (numbered for "do N"; nothing applied)

**Before this weekend (Oct 31 / Nov 1):**
1. Close capture keyed on the schedule's kickoff, `isLive` kept while the scheduled kickoff is ahead, a line within 15 minutes of
   kickoff ranked as a capture (3.1). Until merged: a second capture task 25 minutes before each Oct 31 / Nov 1 kickoff.
2. Hand review dated from the first week a value appeared (2.2); track rows carry a hand only after its saved_at (2.3); one sign
   convention, ours minus Pinnacle, on the forecast check, the Morning track and the Risk tile (2.4).
3. Page fixes: drawer record from games played, no "-Infinity", one label set (Reach MLS Cup / Win MLS Cup / Reach conf final)
   everywhere, the preview's season count printed from the run that made it, a pinned seed shown as "pin" with xPts greyed, the
   Morning Why column allowed to wrap, "last line before kickoff" on a fallback close, the stale hovers (2.5, 6).

**Before Decision Day (Nov 7):**
4. fetch_psr slug forms for Decision Day, Wild Card, Round One games 1-3, conference semifinal, conference finals, MLS Cup, plus a
   paste-a-slug path; freshness check on the report's date v the next round (3.2, 3.11).
5. `fetch_schedule.py` in the routine from Nov 8; close_fallback and the missing-close alarm for every competition; a freshness
   check comparing Pinnacle's kickoff with the schedule's (3.3, 3.11).
6. Injury list clean: Petković to Seattle, the LAFC alias ("Los Angeles Football Club") with the parser refusing an unknown bold
   line, duplicates merged, gtd rows at 0.5, optic rows closed when the newest PSR covers the club and omits the player,
   absence_values deduped by (club, ASA player) (3.10).
7. Playoff factors in the knockouts (live absence rows with a blank or post-Nov-18 return) and the club home delta in the
   knockouts; a playoff result with no winner as a freshness check (3.6, 3.7).
8. Absence dataset rebuilt at share-min 0.3 (one basis with the live list), beta re-read, rerun (2.1).

**Model evidence (no knob moves until these are done):**
9. Cut every backtest season at Decision Day, re-run fh_sim at the frozen pair, re-verify tails and playoff log-loss; re-measure
   the dock on league games only; close_track on league closes only (4.1). Then re-decide rating_sd / drift / dock if the clean
   numbers say so.
10. Posted-line yardstick from the capture history and the harvested openers; grid kalman_s_posted on it and set it on Zac's word
    (4.2; expect 0.30-0.35).
11. One home edge: price with the monthly edge the state was netted with (4.3).
12. Paired sampling in the Python engine (inverse-CDF, one uniform per draw) so what-ifs and ranges are readable at 20k (2.7);
    se printed next to every delta; `ours` to 3 decimals (2.8).

**Ratings and sim (Zac's calls; each needs 9 first where it touches the backtest):**
13. Hands: re-size to 0.05 x the last-4 miss (the 15-season carry-over) or drop them and let the posted lines carry the week (4.5).
    Today's six hands are worth 1-2.5 points on Miami, Nashville, Houston and Seattle.
14. Dock continuous in P(playoffs) at the pre-pass, or in-sim eliminations at -0.19 (4.6). Today: San Jose top-4 57.4 -> 54.9,
    Houston 29.6 -> 30.6, LAFC 14.6 -> 15.2 with the three near-dead clubs exempt.
15. Blend rescaled to the market sd (slope 1.08 -> about 1.03 on 2026; 4.7). Only if 9's clean backtest does not lose.
16. Playoff xG and playoff closes: decide whether they enter the state during the bracket (3.5).

**Evidence hygiene and docs:**
17. backtest_season records every knob per row; backtest and close_track READMEs indexed; calibration README corrected (4.9).
18. check_site asserts: Table equals markets.json, the morning report is today's, no Infinity/NaN/undefined text, 20+ odds cells,
    a game row this week (6).
19. Docs brought to the live model: README, PLAN (date, pipeline, fallback, no Risk tab, 8:30 routine), scripts/README, config
    note, the routine prompt; CLAUDE.md: branches block, Known gaps, section 10 marked by date, 11c2 SUPERSEDED, 14f, 14i, 16, 19,
    headers on the dated sections (6).
20. Risk ranges either back on the page (a hover on each futures cell) or the docs changed to say chat-only (2.6).

**For 2027 (recorded, not proposed now):** the expansion prior's variance (a new club's first close carries weight 0.86, not 0.72),
the late-season home edge, a keeper coefficient, uncertainty-shrunk match prices, the regular threshold in the dataset (8 covers
it), the fixed UTC-4 offsets.
