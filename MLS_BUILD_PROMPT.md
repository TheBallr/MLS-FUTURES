# Build prompt: MLS Futures (the Prem-Futures method, applied to Major League Soccer)

Paste everything below this line into a fresh Claude Code session with an empty repository. It is the complete
instruction set: who you work for, the goal, the maths, the data, the website, the automations, the rules, and the order
to build in. Where it says VERIFY, check the fact against the league's own site before building on it.

---

## 0. Who you are working for and how to work

You are building and then running a Monte Carlo futures model for Major League Soccer for Zac, who runs a professional
sports betting operation (Sierra Advisory LLC). Zac does not code. Every interaction is through chat; the model runs in
these sessions; the outputs live on a private website you publish. He is fluent in probability, EV, devigging, CLV, hold
and vig. Never explain those words, never add gambling or bankroll caveats, never lecture on risk. Lead with the answer.
Keep replies short. When uncertain, flag it first, then proceed.

Zac makes the calls. You propose changes in the model's own terms ("Messi MIA star, out from Jun 3 to Jun 20") numbered so
he can reply "do 1, 3". You never change a player's tier, a team rating, a scenario or a calibrated knob on your own.
Routine maintenance (new injury names at a default tier, dates from a dated source, data fetches, runs, publishing) you do
yourself and say so.

Keep one living document, `CLAUDE.md`, at the repo root: the operating rules, every decision with its date and the
evidence, every measurement. Future sessions start from it. Write it as you go, not at the end.

Git: commit with clear messages after every piece of work; push to the branch you are given. Every run is archived.

## 1. The goal and the yardstick

**The model exists to reproduce Pinnacle's closing MLS match lines from team ratings, so that when news or results move
the ratings, Zac holds a Pinnacle-grade view of every MLS futures market before the soft books have moved theirs.** Match
games are not bet. The futures edges are taken against soft books by Zac, by hand, from the website's numbers.

Every ratings decision is judged by one number: distance from Pinnacle's next closing line (goals of expected margin, in
handicap units, out of sample). Pinnacle is the only match-line source and the only futures book you compare against.
Kalshi, Polymarket and soft-book prices never enter the model.

The futures markets to price, all from one archive of simulated seasons so they are consistent with each other:

- Supporters' Shield (most regular-season points, league-wide)
- Eastern Conference and Western Conference regular-season winners
- MLS Cup winner (needs a playoff simulation on top of the season)
- MLS Cup finalist by conference (conference playoff champion)
- Make the playoffs, per team; finish top N of conference; exact seed ranges
- Regular-season points totals per team (Pinnacle posts these preseason; the win-totals equivalent)
- Wooden Spoon (fewest points league-wide) and bottom of conference
- Head to head (team A finishes above team B), top team of a group (best Canadian side, best expansion side)

Conference markets are the attack: soft books price conferences lazily, and the unbalanced schedule makes conference
strength a thing the sim knows and the books approximate.

## 2. MLS structure you must encode (VERIFY each item for the current season on mlssoccer.com before building)

- 30 clubs, two conferences (East and West, 15 each). 34 regular-season matches per club, UNBALANCED: more games against
  conference opponents than the other conference. Use the actual fixture list, never a round-robin assumption.
- Standings tiebreakers, in order (VERIFY the current chain): points, total wins, goal difference, goals for, fewest
  disciplinary points, away goal difference, away goals for, home goal difference, home goals for, coin toss. Implement
  the chain exactly; conference tables and the Shield table use it.
- Playoffs (VERIFY the format for the season you are modelling; it has changed often): top 9 per conference qualify;
  seeds 1-7 direct, seeds 8 and 9 play a single Wild Card match hosted by 8; Round One is a best-of-three series with
  the higher seed hosting games 1 and 3 and no draws (a drawn match goes to penalties, counted as a win for the series);
  conference semi-finals, conference finals and MLS Cup are single matches hosted by the higher seed; MLS Cup is hosted
  by the finalist with the better regular-season record. Model penalties as a coin flip in a drawn knockout match.
- MLS does NOT stop for FIFA international windows. Clubs lose called-up players to national teams during windows. This
  is a scheduled, predictable absence that the EPL version never needed; build it (section 9).
- Competing competitions that cause rotation and congestion: Leagues Cup (July-August, league pauses or thins), CONCACAF
  Champions Cup (spring midweeks), U.S. Open Cup and Canadian Championship. Measure whether the market prices a
  congestion effect before adding one (the EPL answer was 0.02-0.03 goals, not worth a knob).
- 2026: the FIFA World Cup is in North America; MLS pauses (VERIFY dates). The fixture list on file must carry the real
  dates so the sim's "remaining games" are right. VERIFY whether the league has announced a calendar change (a fall to
  spring season) for the following year; if so, note it in `CLAUDE.md` as the season-end re-plan.
- Decision Day: the final round kicks off simultaneously; late-season resting by sides whose seed is settled is a
  possible effect. Measure before modelling (the EPL evidence for dead rubbers was nil).
- Home advantage is larger and more varied than in Europe (travel distance, altitude in Colorado and Salt Lake, turf in
  a few stadiums, time zones). Fit the league-wide home edge from Pinnacle's closes; test a per-club home edge only if
  the residuals demand it, and only with several seasons of closes.
- Expansion sides and promoted sides do not exist in the EPL sense; an expansion club's first-season prior is "the mean
  expansion side", fitted from the league's history of expansion first seasons, until it has ten closes of its own.
- Roster changes land in two windows (primary, Feb-Apr; secondary, Jul-Aug) plus Designated Player signings; the closes
  carry them within two weeks, as in the EPL.

## 3. Repository layout (mirror the Prem-Futures layout exactly)

```
CLAUDE.md                     the living rules and decisions
config.json                   knobs with provenance notes; calibrated knobs frozen after calibration
PLAN.md                       the method summary (section 5-8 of this prompt, kept current)
data/
  teams.csv                   canonical names, conference, expansion flag, stadium notes (altitude, turf)
  schedule.csv                date, kickoff (UTC), round, home, away, competition
  results.csv                 date, home, away, goals, source (football-data, espn, manual)
  market/current_round_odds.csv   every captured posted line: date, home, away, book, h, d, a, ah_line, ah prices,
                                  total_line, over, under, fetched_at (UTC)
  market/closing_lines.csv    one close per match: pinnacle_close > pinnacle_last > avg_close
  market/futures_odds.csv     Pinnacle futures captures (Shield, Cup, conferences, points totals), with fetched_at
  ratings/sources.csv         every source's rating per team, side by side; blend.csv is generated, never edited
  ratings/source_config.csv   enabled y/n and weight per source
  ratings/injuries.csv        team, player, value_goals, out_from, expected_return, prob_out, tier, note, source, updated
  ratings/callups.csv         team, player, window_start, window_end, prob_out, note (the international layer)
  ratings/scenarios.csv       generic points or availability scenarios (section 9); the EPL's sanctions.csv generalised
  ratings/adjustments.csv     permanent and temporary hand adjustments in goals (used only on Zac's word)
  history/                    seasons of results and closes for calibration
sim/                          engine, ratings fit, blend, injuries, callups, totals, markets, playoffs, devig, knobs
scripts/                      fetch_*, refresh_ratings, run_sim, price_market, weekly, site_data, build_site, news_scan,
                              close_schedule, clv_log, backtests and calibration scripts
site/index.html               the website template; outputs/latest/site.html is the built page
outputs/latest/               the last run; outputs/runs/<stamp>/ the archive; outputs/calibration/ the reports
tests/run_tests.py            determinism, devig, tiebreakers, playoff bracket, injury absorption, totals
```

## 4. Data foundation

Build and verify each source before the model. Every fetch script prints what it did in one line and never writes a
secret into the repo.

1. **Canonical team names** (`sim/teams.py`): one spelling per club; map every source's spelling to it (football-data,
   ESPN, Pinnacle, the xG source, the injury site, news outlets). Nothing downstream ever sees a second spelling.
2. **Schedule**: ESPN's public scoreboard feed (`site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard?dates=YYYYMMDD`,
   loop the season's dates) gives every fixture with kickoff in UTC and status; cross-check the count against the league
   (30 clubs x 34 = 510 matches). Keep competition tags so Leagues Cup and cup ties never enter the league table.
3. **Results**: football-data.co.uk's USA file (the "extra leagues" download: Date, Home, Away, HG, AG plus closing
   odds) is the historical backbone; ESPN's feed fills the same-day lag (completed status, final score). A manual
   `add_result.py` exists for the rare miss.
4. **Closing lines**: football-data's USA file carries Pinnacle's close (PH, PD, PA columns; VERIFY they are populated
   for the current season; if not, the average close is the fallback). From day one, capture Pinnacle's own line ten
   minutes before every kickoff (step 6 below) so the fit target is Pinnacle's number, not an average. Priority per
   match: pinnacle_close > pinnacle_last (your capture) > avg_close.
5. **Pinnacle lines by API**: pinnacle.com's own front end reads a public guest API
   (`https://guest.api.arcadia.pinnacle.com/0.1/...`, header `X-API-Key` with the fixed public key found in the site's
   JavaScript; it is not an account credential). Find the MLS league id with `/0.1/sports/29/leagues` (soccer is sport
   29), then `/0.1/leagues/<id>/matchups` and `/0.1/leagues/<id>/markets/straight`. Take period 0 only: the three-way
   moneyline, and the handicap and total whose two sides are priced closest to even (the main line). Convert American to
   decimal. Append every fixture to `current_round_odds.csv` with a UTC timestamp; `--close` writes fixtures kicking off
   within 25 minutes to `closing_lines.csv` as pinnacle_last. Drop any fixture marked live. The feed serves current
   prices only; there is no history.
6. **Capture schedule**: one Routine ten minutes before every distinct kickoff time in the next eight days (MLS has many
   slots: 7:30, 8:30, 9:30, 10:30 ET and Pacific late kicks), created by a daily Routine from a script that lists them.
7. **Strength source (the Statz equivalent)**: American Soccer Analysis publishes team xG for and against per game via a
   free public API (`app.americansocceranalysis.com/api/v1/mls/teams/xgoals`, by season and date range; VERIFY). Build a
   daily team rating from it: xG difference per game, recency-weighted, ridge-shrunk, rescaled to the market's spread.
   FBref's MLS xG (Opta) is the fallback. Keep a daily history file so the source can be backtested walk-forward.
8. **Injuries**: sportsgambler.com's MLS injury page (`/injuries/football/usa-mls/`, dated with expected returns) and the
   league's official availability report on mlssoccer.com (VERIFY it exists and is reachable). Merge rules in section 9.
9. **Call-ups**: FIFA window dates for the season (VERIFY) and each club's likely call-ups (national-team regulars). The
   morning news scan maintains the list from squad announcements; Zac sets the tiers.
10. **News feeds**: ESPN soccer RSS, mlssoccer.com's news feed, The Athletic's MLS feed if reachable, plus club-specific
    searches when a headline is thin. Test reachability from the container first; keep only feeds that answer.
11. **Pinnacle futures**: Zac supplies Pinnacle's futures prices by screenshot into `futures_odds.csv` (Shield, Cup,
    conference winners, points totals) when he wants a comparison; the page shows "Pinnacle implies" from them. Soft-book
    prices are never stored; Zac compares on his phone.

### 4a. The OpticOdds key: harvest everything first

Zac holds an OpticOdds API key and will give it to you in chat. It lives only in the environment variable
`OPTIC_API_KEY` for the session; it is never written into a repo file, a commit, a note or the website (check with
`git grep` before every push). It is a trial key and can stop working any day, so the FIRST thing you do with it is a
one-off harvest of everything it can reach for MLS into `data/optic/` with a README, exactly as the EPL build did:

- the reference catalogues (sports, leagues, teams, players, sportsbooks, markets);
- every MLS fixture with scores for as many seasons as the feed holds, plus Leagues Cup, CONCACAF Champions Cup and
  U.S. Open Cup fixtures for the congestion study;
- Pinnacle's opening and closing lines (the historical odds endpoint with its clv field) for every past match it
  covers: three-way, Asian handicap and totals, with the full alternate ladders where available. This is the
  calibration set for the shared-goals knob, the posted-line shrink, the CLV test and the half-life grid, and it is
  worth more than anything else the key gives;
- the same for four or five other books (PS3838, Betfair, bet365, DraftKings, FanDuel) for the book comparison;
- every book's current MLS futures (Shield, Cup, conferences, points totals, playoffs) as a snapshot;
- the injury feed (team, player, status, type, position) and the team and player catalogues;
- Opta match stats (shots, shots on target, big chances, box entries) for the form-source study;
- the raw JSON of everything, so nothing has to be fetched twice.

While the key lives, the daily routine also uses it: `fetch_optic.py` pulls the coming three weeks' lines from every
book into `current_round_odds.csv` with the book id (Pinnacle by API, the rest for the Books view), backfills completed
fixtures' scores and Pinnacle's closes (book pinnacle_close from the clv field, which fills some hours after the final
whistle; until then your own ten-minutes-before capture stands in as pinnacle_last), and refreshes the injury list from
the feed (the merge rules of section 9). Every one of those steps is optional: without the key it prints one line and
the routine runs on the guest API, ESPN and the injury site. Design every script so the key is a bonus, never a
dependency. When the key goes dark, say so once in chat and carry on.

## 5. Ratings

A rating is a team's strength in goals of expected margin against a league-average side on a neutral pitch, centred at
zero across the 30 clubs. Several ratings sit side by side in `sources.csv`; the blend is regenerated every run from the
enabled sources and their weights; the scorecard decides the weights.

1. **market_recent** (the backbone). Fit team ratings and a league-wide home edge to Pinnacle's closing lines by weighted
   least squares, weight = 0.5^(age_days / half_life), half-life 14 days to start (the EPL grid chose 14 over 7 and 28;
   re-grid on MLS data). The target per match is the handicap-implied expected goal difference at the match's own
   total (`gd_fit`): devig the three-way with the power method, convert to an expected margin at the posted total, and
   use the main Asian handicap where it exists. Fit on closes only; posted (opening) lines do NOT enter the fit (the EPL
   backtest: openers in the fit at any weight were worse than closes-only plus a shrink).
2. **xg** (the ASA source). Daily rating from xG difference per game, half-life about 21 days, ridge toward zero, rescaled
   so its spread matches the market's. Score it walk-forward against the next closes before it gets weight.
3. **Blend**: start at market 1.0 / xg 1.0 (50/50). Run the three-way backtest (market only, xg only, blend, grid of
   weights) on every close since the xG history begins, leave-one-date-out. Keep 50/50 unless the grid separates cleanly
   out of sample. Re-test monthly.
4. **Posted-line shrink**: a fixture with a fresh Pinnacle line is priced at (1 - s) x the ratings' line + s x Pinnacle's
   line, in the predictions file and in the engine, s = 0.35 to start (the EPL value from 353 opener/close pairs). Once
   150 MLS opener/close pairs exist, grid s, the half-life and openers-in-the-fit, scored on the closes, and set s from
   MLS data. Manual overrides mix at 1.0.
5. **Expansion prior**: for a club with fewer than ten closes, rating = the mean first-season rating of expansion sides
   from history (fit it), blended toward the market fit as closes arrive.
6. **Hand adjustments** go in `adjustments.csv`, in goals, only on Zac's word; weekly moves above 0.15 goals need a
   reason. A team's price looking wrong is a ratings question, never a variance question.
7. **The scorecard** (`rating_scorecard.py`): every source scored on predicting the next ten closes over every season of
   history on file; the live sources scored on this season's closes. Run it before changing any weight and record the
   numbers in `CLAUDE.md`.

## 6. Match engine

For a fixture between home h and away a with ratings R_h, R_a:

- expected margin g = R_h - R_a + home_edge + injury and call-up adjustments (section 9); if a fresh Pinnacle line
  exists, g = (1 - s) g + s g_pinnacle.
- total T = avg_total_goals + both sides' total tendencies (fitted from the market's totals; `team_totals_enabled`), or
  the posted total when the fixture has one.
- home mean = max(T/2 + g/2, floor), away mean = max(T/2 - g/2, floor).
- shared-goals component: a Poisson common term c (mean `shared_goals_mean`, capped so neither mean goes below the
  floor) added to both sides, with the independent parts reduced by c. Goals = Poisson(home - c) + x3, Poisson(away - c)
  + x3, x3 ~ Poisson(c). Calibrate c from Pinnacle's alternate lines (handicap and totals ladders): the EPL value is
  0.15; MLS may differ.
- H/D/A probabilities from the score grid (analytic, 0-10 goals each side) for the website and the forecast check; the
  season engine samples.
- Knockout matches (playoffs): same goal model; a draw is resolved by a coin flip (penalties). Best-of-three: first to two
  wins, higher seed hosts games 1 and 3.

## 7. Season engine

- 200,000 seasons, fixed seed, same inputs give identical output (a test asserts it).
- Per season: draw each team's season rating R ~ Normal(rating, rating_sd) (one draw per team per season); play every
  unplayed fixture in date order; real results are locked in; after each simulated match shift both ratings by
  drift_k x surprise (surprise = actual margin - expected), capped at drift_cap; real results never feed drift.
- Standings: points, then the MLS tiebreaker chain (section 2), for the league table (Shield, Spoon) and each conference
  table (seeds). Record every team's points, conference position, league position, and playoff outcome (made playoffs,
  wild card, round one, conference semi, conference final, MLS Cup final, MLS Cup winner).
- Playoffs: seed from the conference tables, run the bracket with the match engine's knockout rules, home field to the
  higher seed, MLS Cup hosted by the better regular-season record; team ratings are the end-of-season drifted ratings.
- Scenarios (section 9): drawn per season and applied before standings (a points deduction) or as an availability
  overlay (a star absence window).
- Archive every season's table and playoff result (`seasons.npz`, 200k x 30 positions, points, conference seed, playoff
  stage) so any market is priced after the fact by `price_market.py`: `--above A B`, `--best-of "A,B,C"`,
  `--points-over Team line`, `--position Team lo hi`, `--conference East top 1`, `--playoffs Team`, `--cup-without Team`.
- Published pools carry an output shade (section 8) in the markets module only; ratings, the engine, the match prices
  and the solver see the raw sim; the markets file keeps `prob_raw`.

## 8. Calibration programme (do this from MLS history before anything is published; then freeze)

Load every season of football-data's USA file with closes (VERIFY how many seasons carry Pinnacle or average closes; eight
or more is the aim). Then, in this order, each with a script in `scripts/` and a report in `outputs/calibration/`:

1. **Home edge and average total** from the closes (league-wide; per-club only if residuals demand it).
2. **Half-life** for the market fit: grid 7 / 14 / 21 / 28 days on predicting the next ten closes.
3. **Shared goals and the goal model** from Pinnacle's alternate lines (handicap and totals ladders, captured from the
   guest API over several rounds) and from realised goal-difference and total variance around the closes.
4. **rating_sd** from the points backtest (the ridge): replay each season from matchweek 5 with the live recipe, score the
   team points distributions; then check the position markets (Shield, conference winner, playoffs, Spoon) at the same
   spread. If the two disagree (the EPL did: points wanted 0.35, positions wanted 0.20-0.25), keep the points answer and
   carry the difference as the shade below.
5. **drift_k_sim and drift_cap** from the market (Kalman fit of each team's closing-line rating as a random walk):
   measure the market's drift per team-match and its re-rating per goal of surprise; decide the sim's k (the EPL kept k
   0.01, cap 0.10, and the composition could not be told apart by the points backtest).
6. **The shade** per published market: replay the seasons, bucket predicted probabilities against outcomes, fit
   logit(p') = b logit(p) + c (c solved per pool so the pool keeps its size), b chosen leave-one-season-out; apply it only
   to the markets where it wins held out (the EPL: title, relegation, bottom at b 1.2; top four and six left raw).
   Scenario-driven teams are exempt from the shade.
7. **The longshot rule**: measure how often events the sim prices at 5-10% happen; write the hand rule (the EPL: a
   sub-5% price is a third to a half too high; not an edge unless the model's price is 1.5 times the book's fair).
8. **Season replay** against an equal-ratings benchmark at seven checkpoints per season: the sim must beat it at every
   checkpoint on log-loss and expected points.
9. **CLV test** on opener/close pairs once 150 exist: where the model disagrees with the opener by 0.15 goals or more,
   how often and how far does the close move the model's way. This is the proof the ratings are Pinnacle-grade.

Then the **frozen-knob rule**: `rating_sd`, `drift_k_sim`, `drift_cap`, `shared_goals_mean`, `home_edge_goals`,
`avg_total_goals` are frozen for the season. A re-set needs Zac's word, the evidence in the config note, and a date.
Re-size at season end with one more season of data.

## 9. Layers on top of the ratings

- **Injuries** (`sim/injuries.py`): each absence is a value in goals per match (star 0.20, key 0.10, starter 0.05,
  squad 0.02; a doubt counts half), dates out_from and expected_return, and a penalty per fixture net of what the
  market rating has already absorbed: s = share of the rating's half-life weight from closes dated inside the absence;
  penalty = value x ((1 - prob_out if absent else 1) - (1 - prob_out x s)). A fresh absence costs full value, an old one
  fades, the first fixtures after a return get a bonus. Team ratings never change. New names from the injury site enter
  at squad tier with the site's return date; a name the site already listed on first import is dated 28 days back (an
  old absence the closes have mostly absorbed); Zac sets the tiers. Measure the layer on the lined fixtures before and
  after switching it on; keep it on only if the gap to Pinnacle falls.
- **Call-ups** (`sim/callups.py`, MLS-specific): the same penalty mechanics, driven by `callups.csv` with window dates
  instead of injury dates; prob_out 1.0 once the squad is announced, 0.7 for a regular before the announcement. Because
  the market knows the windows in advance, the absorption share should be computed against the windows the closes
  covered; measure whether the layer helps before trusting it. Messi-class absences are the case that matters.
- **Scenarios** (`scenarios.csv`, the generalised sanctions file): rows of {team, type, prob, mean, sd, min, from, to,
  note}; type `points` (a deduction drawn per season and subtracted before standings) or `availability` (a star-tier
  absence over a date window with the given probability). Zac sets them; the website's Scenarios tab lets him edit and
  save them. A scenario team is exempt from the shade in the markets it dominates.
- **Congestion, rest, Decision Day**: measure in the closes' residuals before building anything; the default is no knob.

## 10. The website

One private artifact page, dark matte theme, centred tabs, no explanatory text on any grid (a group row, a header row,
then data; explanations only as hover notes on headers and team names), Eastern time everywhere, American odds, real club
crests on grey discs. Built by `scripts/site_data.py` (one JSON of everything the page needs) and `scripts/build_site.py`
(embeds the JSON into `site/index.html` to make `outputs/latest/site.html`); republished to the same URL after every run.
Check every change headlessly (Playwright with the bundled Chromium: open the page, click every tab, report console
errors, screenshot) before publishing. Tabs, in this order:

1. **Ratings**: the 30 clubs in two side-by-side tables (East, West), rating in goals, and Shield / Conference /
   Playoffs / MLS Cup probabilities beside it so the Settings sliders have something to move. Nothing editable.
2. **Games**: last week, this week, next week (weeks Tuesday to Monday, ET), arrows to move the window; each game:
   kickoff ET, Pinnacle fair H/D/A (power-devigged, raw on hover), the model's H/D/A, a Gap column (model minus
   Pinnacle fair on the home win, points), the score once played. For a played game the model columns are what the model
   said before kickoff (a walk-forward fit on closes strictly before the date), never today's ratings. Tables must fit
   their cards without a horizontal scrollbar at every width from 1100 to 1920 pixels.
3. **Conferences**: East and West tables as the sim sees them: expected points, make playoffs, top seed, conference
   winner, MLS Cup, plus the Shield and Spoon columns; sorted by expected points; a toggle for raw vs shaded where a
   shade applies.
4. **Injuries**: one row per club (Out, Listed, Next fixture, Penalty applied, Raw), click a club to expand the player
   rows; call-ups shown the same way under a second group row during a window.
5. **Scenarios**: the EPL Sanctions tab generalised. The scenario editable in the page (team, type, chance, size, spread,
   minimum or date window); a deduction ladder (each size as certain) for a points scenario; the league under the
   scenario with deltas against the run; "Pinnacle implies" (the chance that makes the team's Shield or Cup price equal
   Pinnacle's devigged price at this size) when a Pinnacle futures capture is on file. Priced in the page by re-ranking
   a 20k-season sample of the football-only run embedded in the page (no resim), with the shade applied as the engine
   does. Save writes `settings/pending.scenario` to the artifact's database.
6. **Settings**: sliders for Drift, Randomness and the xG share of team strength, showing the run's values; Run resims in
   a web worker (a 20k-season port of the engine including the playoff bracket); the Ratings and Games tabs show the
   preview with deltas; Reset restores the run; Save writes `settings/pending` {knobs, sources} to the artifact's
   database. Before every run, read that document and apply it (`apply_site_settings.py`), then mark it applied.

A top-right line shows when odds were last captured, results through which date, and the run time, in ET. Nothing else
in the header.

## 11. Automations (Routines bound to the working session; all times Eastern)

- **Morning news, 7:40**: `fetch_results.py` (ESPN, same-day scores), `news_scan.py` (feeds and the injury site, tagged by
  club and category: scenario / manager / injury / suspension / call-up / fixture / team news / congestion / transfer,
  deduped), one web search per thin headline that matters, injury-list and call-up maintenance at default tiers, then a
  report in chat under 250 words: Results / Act (numbered proposals) / Watch / Scenarios / Injury list. One-line push
  notification. Report saved under `outputs/news/` and committed.
- **Pinnacle lines, 8:52**: fetch every posted fixture; create the ten-minutes-before-kickoff capture Routines for the
  next eight days that do not exist yet; if a round has finished since the last run, apply pending website settings, run
  the full model, publish the site, post what moved. MLS plays midweek often; "a round finished" means every fixture of a
  calendar match-day has a result on file.
- **Closes, ten minutes before each kickoff slot**: `fetch_pinnacle.py --close`, commit, push, one line per fixture in
  chat.
- **CLV log**, inside every run: for every fixture, the earliest run that saw a posted line is the opener view; once the
  close lands, record whether the close moved the model's way and by how much; attack threshold 0.15 goals.
- **Forecast check**, inside every run: the ratings built from closes only, scored on the current posted lines (out of
  sample), goals rmse and bias; printed in chat with every run summary.

## 12. Rules that must not be broken

- Frozen knobs (section 8). A price looking wrong is a ratings question.
- The blend is regenerated, never edited. Human judgment goes in `adjustments.csv`, the injury tiers, the call-up list
  and the scenarios, on Zac's word.
- Real results never feed drift. Posted lines never enter the ratings fit; they shrink the fixture's line only.
- Full rerun every time; every run archived; same seed and inputs give identical output; `tests/run_tests.py` after any
  engine change; say in plain words when a change moves probabilities and by how much.
- Only complete pools are devigged (power method). One-sided prices are compared raw.
- Pinnacle is the only match line and the only futures comparison. Nothing from exchanges or prediction markets.
- Never write an API key into a repo file. The Pinnacle guest key is the site's public one and may live in the script.
- No standing requests at the end of replies. Mention prices or inputs only when the run at hand needs them.

## 13. Build order and acceptance checks

**Phase 1, data and ratings (first).** The OpticOdds harvest the moment the key arrives (section 4a), then teams,
schedule, results, history, closes, the Pinnacle fetch, the xG source.
Acceptance: 510 fixtures on file with UTC kickoffs; every history season loads with closes; `fetch_pinnacle.py` prints
every posted MLS fixture with three-way, handicap and total; the market fit reproduces this season's closes with a
residual sd under 0.15 goals; the scorecard runs and its numbers are in `CLAUDE.md`.

**Phase 2, engine and calibration.** Match engine, season engine with MLS tiebreakers and the playoff bracket, the
calibration programme in full, the shade, `price_market.py`, tests. Acceptance: all tests pass; a 200k run completes
and archives; the Shield, conference, playoff and Cup pools each sum to the right size; the season replay beats the
benchmark at every checkpoint; the knobs are frozen with provenance notes.

**Phase 3, the website.** Tabs 1-6, the worker, Save and apply. Acceptance: no console errors on any tab headless; the
Scenarios tab's run row reproduces the 200k markets within half a point; the Games tables fit without scrollbars.

**Phase 4, automations.** The four Routines, the results feed, the news scan, the CLV log. Acceptance: each Routine has
fired once successfully and its output is in chat and in git.

**Phase 5, layers.** Injuries, call-ups, scenarios, each measured on the lined fixtures before and after, kept only if
the gap to Pinnacle falls. Acceptance: the measurement and the decision are in `CLAUDE.md`.

Report at the end of each phase in chat: what was built, the acceptance numbers, what moved, what needs Zac's call.

## 14. Differences from the EPL build to keep in mind

- Playoffs decide the Cup; the regular season decides the Shield and the conferences. Two archives of outcomes per
  season, one engine.
- The unbalanced schedule means a club's remaining-strength-of-schedule is a real driver of conference prices; the sim
  has it because it plays the real fixture list.
- International windows are in-season absences, not pauses.
- No relegation, so the bottom market is the Spoon and the bottom-of-conference pools.
- Home edge bigger; verify per-club effects before adding any.
- The summer window and DP signings land mid-season; the closes carry them, the xG source lags them, so expect the
  blend to trail the market for two weeks after a big signing and do not chase it by hand.
- The season calendar may change after this season; everything is dated so a re-plan is a schedule change, not a
  rebuild.
