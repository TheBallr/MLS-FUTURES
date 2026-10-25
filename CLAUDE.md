# CLAUDE.md — MLS Futures: operating rules, decisions, measurements

The living document. Future sessions start here. Written as the work happens, never at the end.
Method as it runs today: `PLAN.md` (rewritten 2026-10-19). Every knob, value and provenance: `config.json`. Applied model
changes with times: `data/ratings/method_log.csv`. Original spec: `MLS_BUILD_PROMPT.md` (superseded wherever this file or
PLAN.md differ).
**Goal since 2026-10-20 (Zac): move from building the model to finding edges in the market.** The framework is
`docs/edge_finding.md` (Miller & Davidow, *The Logic of Sports Betting*, read in full and mapped to this model, section 16).
Its companion `docs/forecasting_principles.md` (Silver, *The Signal and the Noise*, section 17) says when our number
deserves to be bet. `docs/bayesian_methods.md` (Reich & Ghosh, *Bayesian Statistical Methods*, section 18)
is the technical layer under both. Read all three before any edge, futures-comparison or betting-workflow work. Sections 6-8 and 11-13 are dated working records: numbers there describe the configuration of their day.

**Branches (2026-10-19).** `claude/gallant-heisenberg-o7xbg9` is the live branch: the 7:40 and 8:52 ET tasks and every close
capture check it out, pull, commit, push and publish from it, so work only reaches the page once it is merged there (before
a task fires, or the task republishes without it). Merged into gallant 2026-10-19 afternoon: `claude/elegant-carson-p0svfm` (the
Risk tab, the overnight code review, playoff totals and locks), `claude/full-health-ratings-0b33j4` (full-health ratings, ON on
Zac's word the same day, section 14) and `claude/determined-cray-ckr043`; all three are spent: new work branches from gallant.
gallant is GitHub's default branch since 2026-10-19 (Zac); `main` holds only the initial commit. Deleted by Zac on GitHub
2026-10-19: `claude/awesome-edison-nr0r68` (its one unique file, the method PDF, is `docs/futures_sim_method_nfl.pdf`) and
`claude/tender-knuth-7t40rv` (the old routines branch). This container can push branches but not delete them. `claude/loving-noether-4oekoj` (2026-10-19 night, cut from gallant 7b0cd37): the two
PDFs' review (section 15), the absence-dataset fix, the Ratings tab's 95% band and the History tab's futures chart; merged into gallant
2026-10-19 night on Zac's "Merge" (fast-forward to dcae7a4), so it is spent too.

## 0. How to work (from the build prompt; non-negotiable)
- Zac (Sierra Advisory LLC) does not code. Everything through chat; outputs on the private website. No gambling caveats,
  no definitions of devig/EV/CLV/hold/vig, no risk lectures. Lead with the answer; short replies; flag uncertainty first.
- Zac makes the calls. Propose changes in the model's own terms, numbered ("1. Messi MIA star, out Jun 3 to Jun 20") so he
  can reply "do 1, 3". Never change a tier, a team rating, a scenario or a calibrated knob unprompted. Routine maintenance
  (new injury names at squad tier, dates from a dated source, fetches, runs, publishing) is done and said.
- Git: commit after every piece of work; push to the branch given; every run archived under `outputs/runs/<stamp>/`.
- Merging (Zac 2026-10-19 night, standing rule): each session works on its own branch, cut from the live branch
  (`claude/gallant-heisenberg-o7xbg9`). When a piece of work Zac has approved is finished, merge it into the live branch as the last
  step, without waiting for him to say "merge": fetch the live branch, merge it into the session branch first (other sessions and
  the 8:30 routine push there), rerun tests / run / page check if anything came in, then push to the live branch and the session
  branch. Stop and ask instead when another session changed the same files at the same time and both sides changed the same logic,
  or when the work is an unfinished test or something Zac has not approved. Work left unmerged is wiped from the page at the next
  8:30 refresh.
- Secrets: `OPTIC_API_KEY` lives only in the environment. The scheduled tasks' container keeps it at
  `/root/.config/optic/key` (mode 600, outside the repo); other sessions usually do not have it, so `fetch_optic.py` and
  `disc_points.py` skip there and the guest API carries the lines. `python3 scripts/check_secrets.py` before every push.
  The Pinnacle guest key in section 3a is the public one from pinnacle.com's own front end.

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
  the rest-of-season backtest (section 11) and Zac's word; last re-set 2026-10-15 night (rating_sd 0.10, drift_k_sim 0.01).
- The blend is regenerated, never edited. Judgment goes in `adjustments.csv`, injury tiers, call-ups, scenarios, on Zac's word.
- Real results never feed drift. Posted lines never enter the ratings fit; a fixture with a fresh Pinnacle line is priced off
  Pinnacle (posted_line_shrink 1.0 since 2026-10-15, the PDF's current-round rule); every later fixture off the ratings.
- Full rerun every time; same seed and inputs give identical output; `python3 tests/run_tests.py` after any engine change;
  say in plain words when a change moves probabilities and by how much.
- Only complete pools are devigged (power method). One-sided prices are compared raw.
- No standing requests at the end of replies.
- Page wording (Zac 2026-10-23, modelled on his betting sheet): numbers in grids, short column labels (Pin, Ours, Gap, Miss, LL),
  windows as rows (7d / 30d / season), status as a word (OK / Watch / Act). No sentence-long card subtitles, no paragraph footers,
  no "how to read" text on the page: an explanation goes in a hover (the card title's "?" or the column header). A "why" is a
  phrase ("Pin last 4 on LAG +0.08 v us"), never a sentence. Secondary lists fold (`details`) and open only when something is not
  ok. Every new card or column follows this before it goes on the page.

## 3. MLS 2026 structure as encoded (verified 2026-10-12 by web search; the official competition guidelines on mlssoccer.com were read 2026-10-15)
| Item | Value | Source / status |
|---|---|---|
| Clubs | 30, East 15 / West 15 (San Diego FC in the West; no 2026 expansion side) | mlssoccer.com preseason predictions article; `data/teams.csv` |
| Regular season | 34 matches per club, 510 total, Feb 21 to Decision Day Nov 7 | mlssoccer.com "2026 schedule: most important dates" |
| World Cup pause | May 25 to Jul 16 (play resumes Jul 16-17) | same |
| Playoffs | 9 per conference; Wild Card 8 v 9 (Nov 18, PKs if drawn, no extra time); Round One best-of-three Nov 20 - Dec 2 (higher seed hosts 1 and 3, every game has a winner); Conf semis Dec 5-6 and finals Dec 11-12 single matches; MLS Cup Dec 18 hosted by the better regular-season record | mlssoccer.com "Audi 2026 MLS Cup Playoffs format" |
| Bracket | 1 v WC, 2 v 7, 3 v 6, 4 v 5; semis (1/WC) v (4/5), (2/7) v (3/6); Wild Card hosted by the 8 seed, PKs if level (no extra time); Round One best-of-three, higher seed hosts 1 and 3, PKs if level; semis and finals single matches hosted by the higher seed, extra time then PKs; MLS Cup hosted by the finalist higher in the Shield standings | VERIFIED 2026-10-15 night on https://www.mlssoccer.com/news/2026-mls-competition-guidelines (Playoffs section); `sim/playoffs.py` matches pairing for pairing. Only simplification: a level semi/final/Cup is a coin flip (the page gives extra time before PKs) |
| Tiebreakers (ON since 2026-10-15 night, proposal 3) | points, wins, gd, gf, **head-to-head (intraconference only: points, then gd in the matches between the tied clubs; after the top club is settled the rest go through the chain again)**, fewest disciplinary points, away gd, away gf, home gd, home gf, coin toss (two clubs) or drawing of lots (three or more) | VERIFIED 2026-10-15 on the official page https://www.mlssoccer.com/news/2026-mls-competition-guidelines (section "Tie-Breaking Procedures"). Disciplinary points on the same page: foul 1, technical-staff warning 2, yellow 3, second yellow 7 for the incident in total, straight red 7, at most 7 per incident. Engine: head-to-head and disciplinary points implemented 2026-10-15 (`sim/standings.py` h2h key, `scripts/disc_points.py` from the OpticOdds team stats: fouls = `fouls` column, yellows include both of a sent-off player so a second yellow adds 1, straight reds = reds minus second yellows), both ON since 2026-10-15 night (`tiebreak_h2h`, `disc_points_enabled`; disciplinary totals as of 2026-10-15, section 4) |
| FIFA windows | Mar 23-31; Sep 21 - Oct 6 (merged window); Nov 9-17 (after Decision Day, before the Wild Card) | FIFA calendar reports; MLS plays through them |
| Leagues Cup 2026 | Aug 4 - Sep 6, 18 MLS clubs | leaguescup.com |
| Calendar change | Board approved a fall-to-spring calendar: a 14-match transition season Feb-May 2027, then 2027-28 from mid/late July 2027. SEASON-END RE-PLAN: the schedule file is dated, so this is a schedule change, not a rebuild; playoff format for 2027 is still to be announced | ESPN / sixonefivesoccer.com reports; VERIFY the official release |
| Home edge | larger and more varied than Europe (altitude COL/RSL, turf ATL/CLT/NE/POR/SEA/VAN) | stadium notes in `teams.csv`; per-club deltas ON since 2026-10-12 (`data/ratings/home_edges.csv`, section 5) |

## 3a. Feeds as verified on the live services (2026-10-12)
| Feed | Verified shape | Notes |
|---|---|---|
| OpticOdds v3 | base `https://api.opticodds.com/api/v3`, header `X-Api-Key`; `/fixtures?league=usa_-_major_league_soccer&season_year=YYYY&page=N` (100 per page, `has_more`); seasons on the feed: 2024, 2025, 2026 only (2023 and earlier return nothing); statuses `completed`, `unplayed`, `cancelled`; `/fixtures/odds/historical?fixture_id=&sportsbook=` returns every market's `olv` (opening) and `clv` (closing) `{price (American), points}` per odd, ~90 KB per fixture for Pinnacle; `/fixtures/odds` (decimal with `odds_format=DECIMAL`, up to 5 fixtures and 5 books per call); markets: `Moneyline` is the three-way (Draw selection), `Asian Handicap` (points per selection), `Total Goals` (`selection_line` over/under); `/futures` MLS: Championship Winner, Eastern/Western Conference Winner, To Make The Finals, Top Goalscorer; `/injuries?league=` (player, team, status, type) | leagues: `usa_-_major_league_soccer`, `north_america_-_leagues_cup`, `concacaf_-_champions_cup`, `usa_-_open_cup`; books: pinnacle, ps3838, betfair, bet365, draftkings, fanduel; historical limit 10 req/15 s; team spellings "Club Internacional de Fútbol Miami", "Club de Foot Montréal", "New York City Football Club", "DC United" (aliases added) |
| ESPN scoreboard | `?dates=YYYYMMDD` one day per request (ranges give 400); 510 MLS fixtures for 2026, kickoffs in UTC, `season.slug` regular-season; logos at a.espncdn.com (saved to `data/logos.csv`) | spells the Red Bulls "Red Bull New York"; "MLS All-Stars" is skipped |
| football-data.co.uk | `https://football-data.co.uk/new/USA.csv` (www redirects); columns `PSCH/PSCD/PSCA` = Pinnacle closing three-way, `AvgC*`, `MaxC*`, `BFEC*`, `B365C*`; seasons 2012-2025 fully Pinnacle (5800 closes), 2026 average closes only (405 rows) | dates are UK local, converted to ET dates with the Time column; "Chivas USA" kept as a historical club |
| Pinnacle guest API | `/0.1/sports/29/leagues` -> MLS id 2663; matchups and `markets/straight` as expected; key `CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R` works | 15 fixtures posted on 2026-10-12; `--ladders` captured 259 alternate prices |
| ASA | `/api/v1/mls/teams`, `/games?season_name=`, `/teams/xgoals?season_name=&split_by_games=true` (xgoals_for/against per team-game) | 420 games for 2026 on first fetch |
| sportsgambler.com | `injury-block` / `inj-row` markup; type class `injury-questionmark` = doubt (prob_out 0.5), card classes = suspension | 25 rows on first import, dated 28 days back at squad tier |

## 4. Known gaps (current, 2026-10-19)
- **OpticOdds is not used** (Zac 2026-10-19: the key is gone, do not rely on it). `weekly.py` no longer calls `fetch_optic.py`;
  `absence_values.py` ignores an Optic injury file more than two days old (the last one is 2026-10-18); discipline comes from ESPN
  (`disc_points_espn.py`). Closes are the 10-minute captures (`pinnacle_last`); a missed capture is filled every morning by
  `close_fallback.py` with the last Pinnacle line fetched before kickoff (`pinnacle_lastposted`, ranked between the two; the data
  checks name each one). The Optic scripts and harvested files stay in the repo for history and backtests.
- 34 games of 2026 (Aug 16 to Oct 1) have no Pinnacle close on file and are rated off football-data's market-average close
  (OpticOdds shows an opener but no close for them: suspended markets). The Risk tab's Inputs tile counts them.
- `data/ratings/injuries.csv` feeds the full-health add-back (absence_values.csv), so open rows cost goals. Each source closes
  its own dropped rows: sportsgambler's when the site drops them (`fetch_injuries.py`), the MLS report's when the newest report
  covers the club and no longer lists the player, and a reported suspension after one match (`fetch_psr.py`, 2026-10-19).
  Rows Zac or the news scan added stay until dated; absence_values.py zeroes any row whose player has played since.
- Playoff results are locked into the bracket since 2026-10-19 (`real_playoff_results`, `locked_tables` in `sim/playoffs.py`):
  ESPN's winner (penalties included) is in results.csv's `winner` column. A level playoff score that only OpticOdds has filed
  (no winner) is skipped with a warning until ESPN's row lands: check the run line after the Wild Card (Nov 18).
- Review items of 2026-10-19 still open (the rest were fixed 2026-10-21, section 5): `backtest_season.py`'s sim stage reads dc_rho
  and the dock from config at run time without recording them; 13b's "goals-tempered xG is worse" was measured when `_mix_xg` joined
  on UTC dates and needs a re-run; `run_sim.latest_posted` has no upper bound on `fetched_at`; run_sim's fixture builder duplicates
  `what_if.build_fixtures`.
- Club home deltas in the yardsticks are in sample for past seasons (fitted on 2012-2025; +-0.05 goals).
- (Resolved 2026-10-12: the network policy that blocked every data host.)

## 5. Decisions log (date, decision, evidence)
- 2026-10-25 **Hands: St. Louis -0.05 and LAFC -0.04 removed, Houston +0.05, Colorado -0.05** (Zac: "do them all"; week 2026-10-20 of hand_log.csv; Miami +0.08, Nashville +0.06, Seattle +0.05, Galaxy +0.04 kept). Each rating sat outside every Pinnacle-implied window (last 4 / 8 / 12): STL +0.16 v +0.35 / +0.33 / +0.21, LAFC +0.40 v +0.42 / +0.55 / +0.51, HOU -0.10 v 0.00 / +0.02 / +0.05, COL 0.00 v -0.06 / -0.11 / -0.07. Ratings now STL +0.21, LAFC +0.44, HOU -0.05, COL -0.04. Full rerun v the morning run: Cup St. Louis 4.7 -> 5.1; Reach MLS Cup St. Louis 12.9 -> 13.6, LAFC 14.4 -> 14.9, Houston 5.5 -> 5.9, Colorado 2.9 -> 2.4, Vancouver 39.0 -> 38.5; conf final LAFC 29.3 -> 30.3, St. Louis 28.8 -> 29.8, Colorado 8.3 -> 7.4; semis San Jose 38.3 -> 36.7, Colorado 21.4 -> 20.1; playoffs unmoved.
- 2026-10-24 **Hands St. Louis -0.05, Galaxy +0.04** (Zac: "do 1 and 2" of the morning report): week 2026-10-20 of hand_log.csv (Miami +0.08, Nashville +0.06, Seattle +0.05, LAFC -0.04 carried into it). Ratings St. Louis +0.25, Galaxy -0.29. Full rerun v the morning run: Cup St. Louis 6.8 -> 6.0, Nashville 23.7 -> 24.1; Reach MLS Cup St. Louis 17.0 -> 15.8; conf final St. Louis 36.2 -> 34.4; semis St. Louis 63.2 -> 61.4, Galaxy 6.4 -> 6.9; playoffs Galaxy 58.1 -> 58.6; nothing else 0.5 points. RSL v STL gap 0.29 -> 0.27.
- 2026-10-24 **Bracket drawn as one bracket, the Cup in the middle** (Zac: "some % are falling out of form ... turn the western
  conference side around so it looks like a normal bracket ... make it more intuitive"). One nine-column grid: East Seeds → Round One →
  Semis → Final → MLS Cup ← Final ← Semis ← Round One ← West Seeds, headers in a row above, each column's slots spread down its height.
  Slots are fixed to the column (the runner-up moved into the hover, smaller crest and label) so nothing overflows; every pickable slot
  carries a ▾ caret, pinned slots are copper with PIN, settled ones ✓. Until something is picked the status line says how it works ("click
  a seed to pin a club into it, or a winner's slot to pick who wins; the bracket reruns on each pick"), the title counts the picks, and the
  menu heading says "pin a club" or "pick the winner" with CLEAR to undo. Under 1250 px the grid folds to East, West, then the Cup. The
  changes table sits under the bracket. Display only. Same day (Zac: "add dates for when each game will be played"): every column
  header carries its dates on a second line (Seeds: Decision Day Nov 7; Wild Card Nov 18; Round One Nov 20 – Dec 2; Semis Dec 5 – 6;
  Final Dec 11 – 12; MLS Cup Final Dec 18).
- 2026-10-24 **Light theme removed; the odds toggle covers every tab** (Zac: "take the light mode out ... the Odds / % button only works
  for table tab"). The Light/Dark button, the light palette and the theme code are gone (dark only). The header's Odds: US / Odds: %
  button now re-renders the Games tab (the Pinnacle fair and Model columns and the detail's fair / Model / Full health rows), the Morning
  tab (futures moves) and the Bracket's changes table as well as the Table and the club drawer. Bracket slot shares stay in percent (shares
  of seasons, not prices). Display only.
- 2026-10-24 **Game detail cut to three small tables** (Zac: "we dont need the graph ... just the summary ... how many injuries / factors,
  how much all of it equals and what the impact on the game is to team ratings ... when the last time pinnacles close for that game was
  collected, and the line since posted"). A game's drop-down is now: prices (Pinnacle fair, raw, gap, Model, Full health) with, under it, the
  Pinnacle line (Posted line and time ET, Close or Last fetch line and time, Since posted with the number of moves, Ours v the line), and beside
  them the match-day factors as one table (Absences as "2 out −0.022" with the players, costs, status and return in the hover, Rest, Short
  week, Eliminated, On rating = each side's goals, On margin = the net; a played game adds Close net). The line chart, the per-player
  absence tables and the listed-not-counted tables are gone (the hover carries the names and why a listed player is not counted); the notes
  are one phrase line. 1,080 px drop-down -> about 250 px. Display only.
- 2026-10-24 **Bracket tab rebuilt as a what-if bracket** (Zac: "see the future bracket with all the locked in knowledge we have, and be able
  to add teams in and see what happens when teams win ... a couple thousand sims"). One card in the Table tab's shape: East and West side by
  side, each as Seeds (1-7, the Wild Card box with 8, 9 and the WC winner) → Round One → Semis (A = 1/WC v 4/5, B = 2/7 v 3/6) → Final, then
  MLS Cup (East v West → Cup) and a "Changes v the run" table; the seed heatmaps fold under it. Every slot shows the club most likely to fill it
  and its share, ✓ when settled (a clinch or a locked result). Click a seed to pin a club into it (menu: the conference's clubs by their chance of
  that seed), click any winner's slot to pick who wins it (menu: who can reach it, by share); the page engine reruns 4,000 seasons by itself
  0.4 s after each pick, paired on one seed with and without the picks, and every slot, the seeds, the Table and Games previews and the
  futures show the run plus the difference (0.5 s a run). Engine: `d.br` in the worker; a pinned seed takes its place and the rest keep the
  simulated order; a forced winner wins when it is in the pairing (a real locked result still comes first); Run One / semi / final / Cup
  picks, hand edits and Games what-ifs all ride the same edit run. Data: `run_sim.bracket_slots` gains `wc` (the Wild Card winner's share);
  today's run (20261023T181453Z) recomputed from its saved seasons so the slot is filled without a rerun (every other number identical).
  check_site drives a pin and Clear. No probability in the run moves.
- 2026-10-23 (night, latest) **Games tab in the Table tab's shape** (Zac: "I want the games tab to look closer to the table tab ... the
  table tab looks right"). One card: a Games title row, a control bar (‹ Oct 20–26 › on the left, the No lines / With lines buttons on
  the right, the same buttons as the Table's By rating / By points; the Model header is just "Model"), then the table at the Table's row
  height, 22 px crests and short club names ("Sporting KC", "D.C. United"), day rows styled like the conference header rows, the favourite
  marked in copper text instead of a tan block, odds columns 58 px, Gap / FT / If packed on the right, card 1080 px. The What if card sits
  under it. Display only.
- 2026-10-23 (night, last) **One type scale; Morning as four tables; no stamps on the tabs** (Zac: "more unison ... off centered and not
  that neat ... get rid of all the random changes made dates"; "UNISON around the whole site"). Site-wide: every table 12.5 px rows with
  10.5 px uppercase headers, card titles, buttons, selects and the Games week title 12 px (the week title and arrows were 15). Morning:
  the stamp line (made / results through / lines) and the "since the 10/22 report" and "since Oct 16" subtitles are gone (the header's
  Refreshed / Last close stamp is the one date); Moved is a table (kind chip 64 px, club, item, was → now, move, note), Games v Pinnacle has
  Kick, Flag and Verdict columns (verdict as a word: Pin right / Maybe us / Flip, basis and action in the hover) with Why last, Uncertain is
  one table (hand rows, data issues and the least-sure ratings with the same chip column), Movers 7d is a table with the bar in a cell;
  the Table tab's subtitle no longer names the previous run's time. Display only.
- 2026-10-23 (night, later) **Table tab on one screen** (Zac: "I dont want to have to scroll at all though on the tables tab"). East and
  West side by side down to 1100 px wide (they stacked under 1800 before), rows 3 px padding at 12.5 px with 22 px crests, short club
  names in the rows ("Sporting KC", "NYCFC", "Red Bulls"; full name in the hover and the drawer), the hand box 50 px, card 1560 px wide,
  and six columns by default (Rating, Hand, xPts, Playoffs, Reach MLS Cup, Win MLS Cup; 95% band, Conf 1st, Top 4, Reach semis, Reach
  conf final and Bottom start hidden; the Columns menu remembers under `mls.rtcols4`, the old key is ignored). Panel bottom at 671 px
  from the top of the window at 1280, 1440 and 1920 wide, no sideways scroll. Display only.
- 2026-10-23 (night) **Games and Table cards capped (960 / 1180 px, centred); Morning's Race card removed; week selector dates
  only** (Zac: "feels stretched"; "take the race part out"). `morning.race` is still written (the review's clinch and elimination
  lines and the headline field use it); the Bracket tab's seed heatmap carries the race.
- 2026-10-23 (night) **Games tab: one week at a time, full width, no Adj column** (Zac). The ‹ › arrows step the week; the week's
  title sits between them. The match-day factors stay in each game's detail (the factor table), only the column went.
- 2026-10-23 (night, last) **Morning tab: two columns of specifics, no summaries** (Zac: "take out all the slop ... split the screen in
  half ... no more just summaries with numbers. I want specific things that moved or uncertainties"). Gone: the headline sentence,
  the four tiles, the Today list, the Data card (its all-ok list) and the folded What's new. Left column: **Moved** (every specific
  change since the previous report as one line each with a kind chip: a Pinnacle line moved 0.05+ since the last report with the
  direction v us, a futures price moved a point (then → now), a rating moved 0.02 with its Pinnacle / xG / hand split, a player on
  or off the injury list, a model change), **Games v Pinnacle** (only games 0.10+ goals from the line, with why and verdict; the
  rest counted in one line), **Review** after a round. Right column: **Uncertain** (data inputs not current, each hand with the
  closes' verdict, the least sure ratings with their "could be" range and why), **Movers 7d**, **Race**. The report selector and
  stamp sit in a thin bar above. `morning.py` unchanged: the page reads the same fields.
- 2026-10-23 (late) **Line ticker removed; Games model switch moved into the table header, Stats only dropped** (Zac: "take out the
  Lines ... we dont need"; "take out stats only ... move the options to where we have our model prices"). The two options (No
  lines / With lines) are buttons in the Model header cell of each week's table, beside Pinnacle fair; the typical-gap summary
  is the header's hover. `g.path` stays in site_data for the line chart in each game's detail. The stats-only variant is still
  computed (`g.alt.stats`) but not shown.
- 2026-10-23 (late night) **Morning tab rebuilt around a written headline; verdicts, race strip, movers, review; Conferences
  merged into Table** (Zac: "13, 15, 16, 17, 18, 19 ... find neat ways to combine on that tab"). Four tabs: Morning, Table, Games,
  Bracket. Morning, top to bottom: (18) the headline sentence written by `morning.headline` ("Busy morning: 2 games to watch; data 1
  issue; hands unchanged; 2 futures prices moved a point."; Quiet/Busy by big flags, hand actions and bad data; leads with the
  result count after a round; names clinches and eliminations since the previous report), the four tiles, the Today list (flagged
  games now carry their verdict); (16) Race card per conference: In (clinched by the run, "1 seed" when that is too), Race (the
  points that clinch a top-nine place against the best possible finish outside it, or points behind the line), Out
  (`morning.race` from the run's playoff shares and the engine's remaining fixtures); (17) Movers card: each club's biggest 7-day
  futures move from the archived runs as a bar in club colour, six largest; (15) Review card (shown only when results arrived since
  the previous report; "Weekend review" Mon/Tue, "Midweek review" otherwise): miss v close, log-loss ours v Pinnacle, the biggest
  surprise (lowest probability we gave an actual result), clinches and eliminations, and the results sorted by surprise
  (`morning.review`; What's new no longer lists results); Data folded (quiet hands fold with the ok checks); (13) Games v Pinnacle
  with a Verdict column on flagged games (`morning.game_verdict`: the line's move since posted decides first, 0.05+ toward us = "we
  may be right · watch the close", away = "Pinnacle right · nothing"; else Pinnacle's last four closes on the club we lean on,
  0.05+ above our rating = "we may be right · consider a hand" (or nothing when a hand is already on), below = "Pinnacle right",
  else "coin flip · watch the close"); Least sure ratings; What's new folded. (19) The Conferences tab is gone: Table (the old
  Ratings tab) carries xPts, Top 4 and Bottom beside the futures columns (Top 4 and Bottom start hidden in the Columns menu), with
  a By rating / By points sort remembered per browser. Display and report fields only: no probability moves.
- 2026-10-23 (night) **Ticker, line charts, Bracket tab, club drawer, what-if results, auto-run hands** (Zac: "now 6-12" of the UI
  proposals). Five tabs: Morning, Ratings, Games, Conferences, Bracket. (6) A line strip under the header: every lined game in the
  next 3 days with Pinnacle's home margin and its move since the first fetch today (or since posted); rebuilt by the close captures
  too, so it changes through the day; click a game to open its week. Data: `path` per game in site_data (`current_round_odds`,
  one point per fetch where the line moved). (7) Each game's detail has the line's path since posted against our price (dashed).
  (8) Bracket tab: the East and West brackets (seeds 1-7, the Wild Card 8 v 9, Round One winners by pairing, semi winners by
  branch, conference champion) and MLS Cup, each slot filled by the club most likely to fill it with its share of seasons (hover
  for the top four, click for the club); results lock in as the markets lock. Data: `run_sim.bracket_slots` -> `markets.json`
  `bracket` (P(seed k) per club and P(reach round AND seed in the slot's pairing), from the sim's `conf_seed` and `stage`
  arrays). (9) Seed heatmaps per conference under the brackets (club x seed 1-9 and Out, copper by probability). (10) Club drawer:
  click any club name or crest anywhere (or a Ratings row) and a side panel shows record and seed now, rating with band and Opta,
  the five futures prices with the 7-day change, the rating chart (published / each morning / Pinnacle closes, same series as the
  old History tab), the futures price chart, the sources and Pinnacle-implied windows, the next 4 games from the club's side,
  the Pinnacle closes (last 10, button for the season), the absences list with headshots, and What changed (folded). The History
  and Injuries tabs and the Ratings detail rows are gone into it; the model change log and all-clubs trend table were dropped
  (method_log.csv keeps the log). (11) What if: H / D / A buttons on every upcoming game (Games tab); a What if bar runs the page
  engine with those results forced (the fixture gets `f`; the dice still roll so the paired stream stays in step) and lists the
  futures moves of half a point or more; the Ratings and Conferences deltas show the same preview; hand edits are included. (12)
  A hand edit (arrows or typed) previews itself 0.9 s after the last change; Run stays. Full rerun 20261023T19xxxxZ for the
  bracket data (same inputs as the midday run: no futures moved). Page check covers the five tabs and the drawer.
- 2026-10-23 (evening) **Matte palette, club colours, headshots, light theme, American odds by default** (Zac: "do 1,2,3,4,5" of the
  UI proposals). (1) Palette: warm charcoal page, slate cards, no pure white text, four muted status colours (sage OK, sand Watch,
  clay Act, dust Note), copper accent; zebra rows and horizontal rules only (the `.sep` column breaks stay as a thin line). (2) One
  matte colour per club from its crest (`scripts/club_colours.py` -> `data/club_colours.csv`; eight set by hand where the crest's
  dominant hue is the wrong one: POR green, CHI red, LAFC gold, SKC light blue, RSL claret, DAL red, COL claret, LAG navy; a `hand`
  row is never overwritten) as a 3 px bar on every club cell, the Ratings sparkline and the futures-history line; Ratings crests
  32 px. (3) Player headshots from ESPN's CDN (`scripts/fetch_headshots.py`: rosters by the club ids in logos.csv, 36 px palette
  PNGs under `data/headshots/`, `roster.csv`; ESPN has photos for 325 of 963 rostered players, the rest show initials); matched by
  name in `site_data.headshots` and embedded as `heads` (132 today, about 200 KB); shown on the Games detail absences and the
  Injuries players. weekly.py runs the fetcher daily (soft step). (4) `data-theme=light` palette (off-white page like the sheet),
  Light/Dark button in the header, remembered per browser; chart series colours redefined for the light surface. (5) Futures
  prices default to American odds (the toggle stays). Display only: no probability moves.
- 2026-10-23 (later) **Edges, Risk and Settings tabs removed; Morning's Track record card removed** (Zac: "just get rid of the
  settings tab, risk tab, and edges tab ... the morning report does enough"). Six tabs remain: Morning, Ratings, Games, Conferences,
  History, Injuries. The page engine's Run stays on the Ratings tab at the run's xG share (the slider is gone; the xG share changes on
  Zac's word in chat). risk.py, edges.py and freshness.py still run every morning: risk.json feeds the rating history, the Morning
  tiles and the chat report; edges.json feeds the chat report's Edges line; the Risk and Edges cards simply have no tab. Morning keeps
  the Miss 30d tile (one number); the 7d / 30d / season / month grid is gone (morning.json still carries `track` for the chat report
  and the headline line). check_site.py checks the six tabs and the Morning tab at phone width instead of Risk / Edges / Settings.
- 2026-10-23 **Page cut to the sheet's style** (Zac: "cut and shorten and make neater the whole thing", using his betting sheet as the
  guide: a top block of a few numbers, flat tables with short headers, windows as rows, status words; branch
  claude/optimistic-franklin-m9ptc3). Display and wording only: no probability moves. Morning tab 3,494 -> 1,908 px at 1400 wide:
  five tiles on top (Data / Games / Miss 30d / Edges / Hands), one Today list (the old headline list and Today card merged), Data
  checks folded and listing only what is not ok, the games table with Pin / Ours / Gap / HW pts / Move / Why in phrases, the track
  record as one grid (7d / 30d / season rows, months under them), What's new folded with a count line. History 5,020 -> 3,307
  (footer paragraphs gone, the change log folded, runs that moved a club under 0.005 dropped), Risk 1,884 -> 1,458 (tile notes to
  hover, blind spots folded), Games 3,510 -> 3,082 (one detail table of prices incl. full health, the factor table, absent players
  only where there are any, the three note paragraphs gone), Edges (the flag-rule prose moved to the title hover, Books folded).
  Ratings detail: one row of sources and Pinnacle-implied windows, the band and next game on one line. Text sources shortened too:
  morning.py reasons / headline / least-sure strings and risk.py tile subs, watchlist flags and blind spots. Reports before this date
  keep their long strings. The routine's chat report (step 9 of docs/morning_routine_prompt.md) reads the same fields, unchanged.
- 2026-10-23 **Open Cup final added to the match list** (Zac: "do 1"). The final (Wed Oct 21, Columbus 0-0 St. Louis, St. Louis on
  penalties; ESPN) was missing: results.csv carries MLS only, and the cup fixture file had it as unplayed since OpticOdds went. Both
  clubs were on 7 days' rest for Saturday instead of 3. Fixed: a results.csv row with competition "US Open Cup" (every model path
  filters to MLS; LiveFactors and the rest table read every competition) and the cup fixture marked completed. Run v the midday run:
  St. Louis +0.317 -> +0.328, Columbus +0.129 -> +0.138, RSL -0.147 -> -0.157, Toronto -0.413 -> -0.422; RSL v STL gap to Pinnacle
  0.25 -> 0.20, CLB v TOR 0.04 -> 0.00; futures: only St. Louis semi 63.2 -> 63.6 moved 0.3. Cup games from now on are not fetched by
  anything (no OpticOdds): a midweek cup match must be added by hand the same way.
- 2026-10-21 **Review of proposals 4-21 carried out** (Zac: "do it in your order"; branch claude/youthful-einstein-kb6gq7). No knob,
  rating, hand or tier changed; no futures probability moves except through the day's data. (14) Tab dots obey `hidden`. (9) The
  yardsticks' "live" baseline is the live recipe read from config (`scripts/recipes.py`: Kalman, posted lines, 15% xG, club home
  deltas, full-health factors); the retired least-squares recipes keep their names with `_retired`. Live close a week out **0.2383**
  (15 seasons, `close_track/base9.csv`; 0.2402 without the club deltas = 14l's figure). (8) One ratings-without-this-round's-lines
  function (`refresh_ratings.ratings_without_lines`) and one implied-rating function (`implied_pair`) for site_data, site_detail,
  risk and morning; every Pinnacle-implied window is now net of home edge, club delta and the game's factors. (6/7) run_sim's
  forecast check and the CLV opener use the ratings without this round's lines (honest rmse 0.126 that day); `--quick`/`--no-write`
  leave layers_log and clv_log alone; `fit_resid_sd` null under the filter; what_if `xg_w` keeps the hands (xg_w 0.15 = live
  exactly). (19/17/21/16/18) Page: pool names unified ("Reach MLS Cup · East" on Edges), a %/US odds toggle in the header, gap
  units labelled, settled cells greyed, zero-move runs dropped from History, Risk dot red only for a red tile, the hand-week note
  says whose hands the run used, the Drift and Randomness sliders removed (frozen knobs; Settings keeps the xG share), the
  Injuries tab's tier column replaced by games missed. (10) Data checks that can fire: injury-report rows carry the report's
  date, a dated absence row goes stale once the player plays after it, missed-capture closes count in the Risk tile, new checks
  for the absence dataset's seasons and the injury report's age, freshness runs again at the end. (11) risk.py's dock-exemption
  pre-pass once per run (85 s -> 52 s, every range cell identical). (12) Seven inert knobs marked INERT in config.json (values
  kept for the backtests). (15/20) Morning is the first tab with a Today card (edges, data verdict, hands, flagged games, futures
  moves, widest ranges); data checks fold when all ok; on a phone the refresh stamp and odds toggle sit under the tabs, the tab bar
  fades where more tabs scroll, and the Ratings club column stays pinned. Tests, reported only: (4) a spread stretch does not help
  over 15 seasons: fixed x1.10 0.2406 (3/15 seasons), x1.05 0.2385, a walk-forward rule from the trailing slope (75/180/365 days,
  half or full) 0.2382-0.2393 v live 0.2383; 2026 alone likes x1.10 (0.2430 v 0.2453), the Risk tile's 1.10 is a 2026 reading. (5)
  Measurement noise (`close_track/noise1.csv`): posted-line sd 0.18 0.2382 (9/15), 0.22 live 0.2383, 0.25 0.2386, 0.30 0.2394;
  market-average closes at sd 0.35 or 0.50 change nothing (35 games). Nothing proposed from either. Still open: the futures price
  source for the Edges tab (The Odds API carries no MLS futures).
- 2026-10-20 **Edges tab and book futures prices** (Zac: "lets make the edge tab"; markets Cup + conference champions; Kalshi and
  Polymarket dropped, "they don't have volume"). Source: The Odds API (official documented feed, key in `ODDS_API_KEY`, which Zac adds as an
  environment secret). The playbook Zac linked was used for its schema, team matching and devig only; its sportsbook-endpoint methods
  (bot-protection workarounds, keys taken from site traffic) were not used. New: `scripts/odds_math.py`, `scripts/fetch_odds.py` ->
  `data/market/futures_odds.csv` (+ `futures_odds_history.csv` for CLV), `scripts/edges.py` -> `outputs/latest/edges.json`, the Edges tab, weekly.py
  steps, check_site coverage. Book "conference winner" = conference playoff champion = our `cup_finalist` pool within the conference (our
  `east`/`west` are regular-season first place). Flag rule: our fair pooled with the books' devigged median in log odds (weight 0.5 on ours,
  provisional), at the low end of the Risk tab's range, still +EV at the best price. Tested on a synthetic two-book sample (holds 23-39%: no
  flag; an injected Nashville +700 against our ~+336 flagged alone). UNVERIFIED until the key is in: whether the feed lists MLS outrights
  (conference markets especially) and which US books it carries; `fetch_odds.py --list` shows the MLS sport keys. Display only: moves no
  probability.
- 2026-10-19 (night) **Both method PDFs reviewed (Corey's NFL lessons, Glickman's Glicko); 95% band and futures history on the page;
  absence dataset fixed; no locked-seed dock** (Zac: "do 1 if it makes sense when the test is done, and 2, 3"; section 15). (1) The
  locked-seed dock was tested on regular-season games only and does not make sense: clubs with nothing to play for ran +0.22 goals above
  their ratings (n 34, se 0.24; top seed locked alone -0.13, se 0.27, n 25) and benched about 0.04 goals of missing value a game (x the
  ~0.7 price = 0.03 goals), which each round's Pinnacle line already carries; not built. (2) Ratings tab: a "95% band" column (rating
  plus or minus 1.96 x the Kalman filter's posterior sd, Glicko's RD) and a line in each club's detail naming any Pinnacle-implied window
  outside it. (3) History tab: a "Futures price history" card (our published price of Conf 1st / Playoffs / Semi / Final / Win conf /
  Cup at every archived run). (4) Bug found on the way: the morning routine's container holds only this season's ASA raw files, so its
  `absences.py build` cut `absences.csv` to 2026 since the go-live (no close before 2026 netted; 870 of 900 2026 team-games off by 0.03
  goals on average, up to 0.26, for want of last season's minutes) and `absence_values.py` valued players without 2025. Fixed:
  `absences.py` keeps any season it cannot rebuild faithfully (own and previous season's raw files) from the file on disk; `weekly.py`
  fetches last season's raw files once per container. Full dataset restored (2013-2026, 11,344 team-games; 2013-2025 identical to the
  committed 13e1d86 within 0.0003). Run 20261019T211304Z v 20261019T202950Z (same inputs otherwise): ratings Dallas -0.02, San Jose
  -0.02, Galaxy +0.01, every other club under 0.01; Cup Nashville 23.1 -> 22.8, Vancouver 21.4 -> 21.7; semi Dallas 55.0 -> 54.1, Houston
  41.9 -> 42.7; nothing else more than 0.6 points. Display items move no probability. Page v54 (published from this branch).
- 2026-10-19 (evening) **Goal-difference source tested and left off; Seattle +0.09 -> +0.05; LAFC -0.04** (Zac: "do all" on the
  four proposals after 14l: adopt 75/15/10 only if the futures backtest does not lose; Nashville +0.06 -> +0.03 only if adopted, LAFC
  -0.04 only if not). The backtest lost on the futures pools (14l), so Nashville stays +0.06 and LAFC gets -0.04 (week 2026-10-13 of
  hand_log.csv). Ratings LAFC +0.45 -> +0.41, Seattle +0.12 -> +0.08 (Nashville +0.81, Miami +0.81 kept). Run 20261019T202950Z v
  20261019T185853Z: Cup LAFC 5.2 -> 4.9; Cup finalist LAFC 13.6 -> 12.9, Seattle 5.0 -> 4.6, St. Louis 17.4 -> 17.9; conf final LAFC 28.6 ->
  27.6, Seattle 13.7 -> 13.0, St. Louis 36.7 -> 37.4; semi LAFC 60.7 -> 59.5, Seattle 34.0 -> 32.9, Dallas 54.3 -> 55.0; top-7 Seattle 68.5 ->
  67.7; nothing else 0.3 points. Page v52.
- 2026-10-19 (evening) **One morning routine at 8:30 ET** (Zac: centralise every task, refresh everything daily, check for red flags,
  keep the history current). Section 9 has the routine; new scripts freshness.py and disc_points_espn.py; weekly.py runs the injury
  site, ESPN discipline and the page check too; the Morning tab gains Data checks and the hand review. Tested end to end here
  (weekly.py, 17 steps, exit 0, every check ok, page check clean). Discipline now through 29-31 matches (was 28, Oct 15). No knob,
  rating or hand changed.
- 2026-10-19 (evening) **Hand adjustments Nashville +0.06, Seattle +0.09** (Zac: "just do 1", after 14j): week 2026-10-13 of
  hand_log.csv (carried into the following weeks until edited; Miami +0.08 kept). Sized at 0.3 x each club's average miss v Pinnacle
  over its last 4 lines (Seattle +0.29, 7 of 8 the same way; Nashville +0.20, 6 of 8); 14j says the carry-over is a 2026 pattern
  (0.05 historically), so re-size or drop them as the closes come in. Ratings Nashville +0.75 -> +0.81, Seattle +0.04 -> +0.13. Run
  20261019T175724Z v 20261019T164703Z: Cup Nashville 21.4 -> 23.1, Vancouver 21.7 -> 20.9; Win conf Nashville 32.4 -> 34.2, Seattle
  4.2 -> 5.0, Philadelphia 16.2 -> 15.8; conf final Nashville 51.1 -> 52.9, Seattle 12.0 -> 13.6; semi Seattle 31.2 -> 34.0; playoffs
  and seeds unmoved. The Games tab's played games of that week (Oct 14-18) are repriced with the week's hand, as every week's are.
- 2026-10-19 (late) **Hand adjustments: Philadelphia -0.05 and St. Louis +0.03 removed, Miami +0.08 kept** (Zac: "do 2"; week
  2026-10-13 rows deleted from hand_log.csv, so the next weeks carry Miami alone). Evidence put to him: without hands Miami +0.71 v
  Pinnacle-implied +0.79 (last 4) / +0.84 (8) / +0.85 (12) / +0.80 (posted line), market source +0.75, xG +0.44 at 15% pulls it down;
  full-health ratings do not lift Miami (market source +0.752 with factors v +0.755 without: Miami's absences are small and offset
  by opponents'). Ratings: Philadelphia +0.71 -> +0.76, St. Louis +0.35 -> +0.32, Miami +0.79. Run 20261019T162741Z v page v41: Cup
  Philadelphia 8.1 -> 8.8, St. Louis 7.7 -> 7.2, Nashville 21.6 -> 21.3; Win East Philadelphia 15.5 -> 16.5, Nashville 32.5 -> 32.0;
  Win West St. Louis 18.3 -> 17.4; conf final Philadelphia 31.1 -> 32.4, St. Louis 37.8 -> 36.6. Page v43 (on top of the History tab, v42).
- 2026-10-19 (evening) **Risk and Games tabs on the full-health recipe; injury-report rows close** (Zac: "do 1 and 3"). (1) The Risk
  tab's Ratings v Pinnacle tile, spread tile and watchlist misses now score the live recipe (closes and the posted round net of
  their factors; each close priced a week out with rest, short week and eliminated status from then and absences as the club's
  last-ten average, close_track's honest recipe; normal 0.240): tile 0.250 -> 0.246, spread 1.10 -> 1.09. The Games tab's played
  games add back their own factors (absences as the lineups were): margin gap to the close rmse 0.235 either way, single games move
  up to 0.2 goals (an eliminated club's -0.19). Display only. (3) `fetch_psr.py`: a reported suspension is one match (5 rows
  dated, incl. Bartlett D.C. 0.07 goals a game, Elliott Chicago 0.02, Kuscevic Toronto 0.01, which had been counted out for every
  remaining fixture); rows the newest report drops close; re-listed players get a new row. Run 20261019T154929Z v page v40: playoffs
  D.C. 11.3 -> 11.8, Columbus 48.4 -> 47.9, NYCFC 34.8 -> 34.5; conf semi Chicago 52.3 -> 52.8, Dallas 54.9 -> 55.3; nothing else
  0.3 points. Page v41.
- 2026-10-19 (late afternoon) **Morning report, daily rerun, eliminated-status fix** (Zac: monitor every upcoming game against
  Pinnacle each morning like the SKC v ATX note, rerun everything every morning, a tab with each morning's report; and "why were we so
  off last weekend"). (1) `scripts/morning.py` after `site_data.py` in `weekly.py` (section 10, Morning tab). (2) `weekly.py` runs the
  full model EVERY morning (was: only after a finished match-day); `--force` kept and inert. (3) Bug: `absence_price.eliminated_table`
  built 2026's eliminated flags from played games only, so a club with games left but not yet scheduled-in looked mathematically out:
  Columbus, Atlanta, Montréal flagged from Oct 11; Austin, Minnesota, Portland, RSL, San Diego from Oct 17 (truth: only Sporting KC,
  from Oct 17). Their closes were netted 0.19 too much and their played-game prices docked. Fixed: the current season is rebuilt on
  every call from the full schedule (past seasons stay cached). Run 20261019T164703Z v the live 20261019T162741Z (same inputs): ratings
  SKC -0.04, Austin -0.03, Atlanta -0.03, Montréal -0.03, RSL -0.03, Columbus -0.02; Colorado +0.04, Vancouver +0.04, Galaxy +0.03,
  Seattle +0.03, St. Louis +0.03, Miami +0.03; Cup Vancouver 21.0 -> 21.7; Win conf Vancouver 39.4 -> 40.0; playoffs RSL 41.7 -> 40.2,
  Galaxy 57.9 -> 59.3, NYCFC 34.7 -> 35.4, Columbus 48.0 -> 47.4. Audit of last weekend's 30 games (match-morning ratings, no lines):
  margin miss v the close rmse 0.234 (normal 0.24), home-win probability off 3.8 points on average (max 12); the "40%" Zac saw is the
  detail row's "gap v close" ratio (model prob x Pinnacle decimal - 1), which balloons on longshots. Season (447 games): rmse 0.224,
  results log-loss ours 1.041 v Pinnacle 1.022 v no-skill 1.067 (our ratings alone get 58% of Pinnacle's edge).
- 2026-10-19 (afternoon) **Go live, playoff totals, playoff locks, played-game pricing, branch tidy-up** (Zac: "make all of the
  changes that you proposed"). (1) Playoff matches at the two clubs' team totals (base + both offsets, clipped 2.0-4.5) instead of
  the flat 3.2. Paired 100k at today's inputs: Cup Miami 18.0 -> 16.9, Vancouver 22.2 -> 21.7, Nashville 21.7 -> 21.9,
  Philadelphia 7.7 -> 8.0; Win East Miami 29.4 -> 27.9; conf final Miami 54.6 -> 51.9 (Miami's +0.55 total offset makes its ties
  more random). (2) Real playoff results locked into the bracket (ESPN winner, penalties included; results.csv `winner` column;
  OpticOdds results after Decision Day filed as playoff games); no effect until the Wild Card. (3) Games tab: a played game's Model
  is the match-morning ratings WITHOUT that round's lines (same basis as upcoming games): 78 played games in the window, margin
  gap to the close rmse 0.235 (was near zero by construction). (4) Go live: claude/elegant-carson-p0svfm (Risk tab, overnight
  review, these changes) AND the full-health session's branch (factors ON on Zac's word that morning, entry below; its page v39
  went up from its own branch at 14:35Z, so the 8:52 routine would have dropped it) merged and pushed to the live branch
  (merge fix: weekly.py called dt.date.today() without the import). Run 20261019T145409Z (fresh lines, xG re-dated to ET,
  factors on, playoff totals) v the live page v39 (20261019T143459Z): Cup Miami 18.5 -> 17.2, Vancouver 21.4 -> 20.9,
  Philadelphia 7.5 -> 8.1, Nashville 21.6 -> 21.5; conf final Miami 54.5 -> 51.8, Dallas 24.7 -> 26.1; playoffs Galaxy 56.8 -> 58.2,
  Columbus 49.6 -> 48.4, Colorado 72.2 -> 71.2. Page v40 published from gallant. (5) `docs/futures_sim_method_nfl.pdf` copied in from
  claude/awesome-edison-nr0r68; that branch and claude/tender-knuth-7t40rv retired (see the branches block).
- 2026-10-19 **Full-health ratings ON** (Zac: "lets get this working live if its helping us ... do what you proposed", proposals 1, 4, 5 of
  section 14h): `factors_enabled` true at `factor_abs` -0.48, rest +0.005, short week -0.031, eliminated -0.19; the official MLS Player
  Status Report and Transfermarkt wired in (`scripts/fetch_psr.py`, 14i); the daily absence refresh in `weekly.py`; the Injuries tab in
  goals. Run 20261019T143459Z vs the routine's 20261019T125515Z (same results through Oct 18, same 12 posted lines; the branch was merged
  from the live branch first): ratings Sporting KC +0.09, Minnesota +0.03, LAFC +0.03, Montréal +0.02, Cincinnati +0.02; Colorado -0.07,
  Seattle -0.03, Vancouver -0.03, Charlotte -0.03, St. Louis -0.02. Cup Vancouver 22.1 -> 21.4, Nashville 22.0 -> 21.6, Miami 18.1 -> 18.5,
  LAFC 5.3 -> 5.7; West Vancouver 88.9 -> 88.4, Dallas 5.3 -> 5.7; playoffs Colorado 73.2 -> 72.2, RSL 41.2 -> 42.0, Galaxy 57.5 -> 56.8,
  Minnesota 10.7 -> 11.4, San Diego 7.3 -> 7.9, Columbus 49.0 -> 49.6; top-4 San Jose 49.6 -> 47.7, Houston 34.1 -> 35.1, LAFC 25.3 -> 26.2;
  Cup finalist Vancouver 40.7 -> 39.7, LAFC 13.4 -> 14.3; conference final LAFC 28.2 -> 29.8, Vancouver 57.6 -> 56.7. Forecast check on the
  12 posted lines: rmse 0.077 vs 0.067 before (bias +0.010 vs +0.007): one round, 12 lines, within the noise of a 0.25-goal residual, and
  the posted lines are in the ratings either way; the honest read of the change is section 14d-14e. Page v39 republished from
  this branch; merged into the live branch the same afternoon with the go-live (entry above), so the routines carry it.
- 2026-10-19 (night) **Full code review while Zac slept** (his ask: "full code review of everything ... nothing stale ... fix bugs";
  branch claude/elegant-carson-p0svfm, commits "Review 1/n" to "Review 5/n"; seven read-only reviewers, every fix made and checked
  here; the full-health session's files were not touched, section 4 lists what waits for them). Futures are unchanged by every
  commit (a 20k-season run gives identical output before and after; tests ALL PASS) except the xG dating fix (ET, not UTC),
  which only changes which day a late game's xG lands on. Highlights: weekly.py stops on a failed step instead of publishing
  stale markets and no longer skips a morning after an evening rerun; fetchers fail loudly (Pinnacle, ESPN), track
  rescheduled games and keep playoff results; the injury list closes rows its source drops; the page's Run is paired against
  its own baseline (an unedited Run moved ~40 cells, now none) and the Games Model shows our ratings' own price; Settings Save
  no longer wipes hand edits; head-to-head tiebreak fixed for ties spanning conferences; docs, config notes, PLAN.md, README,
  scripts and calibration indexes rewritten to the live model; dead code, dead knobs, ClubElo, smoke files, tracked raw files
  and per-run screenshots removed. Not live until merged into gallant-heisenberg (Zac's "go live").
- 2026-10-19 **Run 20261019T041521Z on Zac's "fully update and rerun"** (this session, branch claude/determined-cray-ckr043, cut from
  claude/gallant-heisenberg-o7xbg9 at 26599a2; the routines still push to gallant-heisenberg, so the 8:52 ET routine's own run supersedes this one
  there). Inputs: Oct 18 final (Cincinnati 0-2 Columbus; xG 2.74 v 0.23), its Pinnacle close (AH -0.25 from 0 at the posting), 15 posted lines
  for Oct 21-25 (D.C. v Cincinnati Oct 24 not yet posted), ASA xG through Oct 18, Opta Oct 19 (rank agreement 0.868), injuries 0 new, no
  pending site edits (hand week 2026-10-13 unchanged: Miami +0.08, Philadelphia -0.05, St. Louis +0.03). Ratings: Cincinnati +0.01 -> +0.08 and
  Columbus +0.20 -> +0.14 (the xG source and the close both sided with Cincinnati despite the score), Philadelphia +0.67 -> +0.71, Chicago
  +0.30 -> +0.33, Dallas 0.00 -> +0.04, New England +0.08 -> +0.05, Houston -0.03 -> -0.06. Markets (v run 20261018T125442Z): playoffs
  Columbus 29.3 -> 48.3, Cincinnati 73.2 -> 60.4, Red Bulls 32.1 -> 28.5, Toronto 20.7 -> 19.1; Cup Nashville 22.4 -> 21.7, Vancouver 22.3 ->
  22.1, Miami 18.2 -> 18.1, Philadelphia 7.1 -> 7.8; West Vancouver 89.1 -> 88.6, Dallas 5.0 -> 5.5; conf semi Dallas 52.4 -> 54.3, New
  England 50.9 -> 49.1. Forecast check on the 15 posted lines rmse 0.052 (layer on 0.077). Page v38. Optic key absent from this container
  (fetch_optic skipped; the guest API carried the lines). Website items put to Zac the same day: stale injury rows (125 on file, 123 counted
  out, the source site lists 26), uncapped American odds on the Conferences tab (-28553, +77721), the dead Shield column, the Penalty column
  of zeros while the layer is off, the page worker's missing Semi/Final pools (open since 2026-10-16).
- 2026-10-16 **St. Louis hand -0.07 -> +0.03, rating +0.40** (Zac: "I want their rating to be .4"; his "add .03" meant a +0.03 hand on
  the +0.37 blend, not +0.03 on the +0.27). Run 20261016T180604Z vs 20261016T180352Z: St. Louis Cup 7.2 -> 8.7, Win conf 17.3 -> 19.8, conf
  final 36.7 -> 40.1, semi 64.2 -> 67.2, West 16.8 -> 18.6, top-2 57.6 -> 60.5, top-4 95.7 -> 96.4; Vancouver West 72.1 -> 70.8, Win conf
  41.2 -> 40.3; Dallas top-2 39.9 -> 38.3. Page v35. Net of the day's three St. Louis edits the hand is +0.03 (was none this morning).
- 2026-10-16 **St. Louis hand -0.10 -> -0.07** (Zac: "move st. louis to add .03"): rating +0.27 -> +0.30 (blend +0.37), week 2026-10-13
  row edited in place. Run 20261016T180352Z vs 20261016T173204Z: St. Louis Cup 6.7 -> 7.2, Win conf 16.5 -> 17.3, conf final 35.5 -> 36.7,
  semi 63.2 -> 64.2, West 16.4 -> 16.8, top-2 56.9 -> 57.6; nothing else moved half a point. Page v34.
- 2026-10-16 **St. Louis hand adjustment -0.10 goals** (Zac in chat: "Move saint louis down to .27 and rerun"): week 2026-10-13 of
  `hand_log.csv`; blend +0.37 -> rating +0.27 (the hand stays -0.10 in goals as the blend moves). Run 20261016T173204Z vs 20261016T155624Z
  (the earlier rerun the same day on the 11:54 AM ET lines and the Oct 14 xG): St. Louis Cup 8.2 -> 6.7, Win conf 19.2 -> 16.5, conf final
  39.1 -> 35.5, semi 66.4 -> 63.2, West 18.0 -> 16.4, top-2 59.7 -> 56.9, top-4 96.2 -> 95.6; Vancouver West 71.1 -> 72.4, Win conf 40.5 -> 41.2;
  Dallas top-2 38.8 -> 40.4. Page v33. Same day: the page's Run worker does not count the Semi and Final pools (they keep the run's
  values on Run) — proposed to Zac as a fix, not yet applied.
- 2026-10-16 **Weekly hand-adjustment log** (Zac: each week keeps its own set; a new week carries the previous week's values until he
  edits it; past weeks stay as they were). `data/ratings/hand_log.csv` (week, team, goals, saved_at, source, note), weeks Tuesday-Monday
  ET keyed by the Tuesday (the Games tab's weeks). `sim.layers.rating_adjustments` takes the run date's week (`week_of`), falling back to
  the latest earlier week (`hand_week_values`); the open-ended rows of `adjustments.csv` moved into the log (dated fixture-window rows
  would stay there). Ratings tab: a week selector (every week on file plus the current and next), each week's boxes, a note line (used by
  the run / carried over from / saved at / changes v previous week), past weeks read-only; Save writes the selected week's full set
  (`adjustments_week` in settings/pending); `apply_site_settings.py` replaces that week's rows only. Zac's site save of 2026-10-16 00:11Z
  (Inter Miami +0.08, Philadelphia -0.05) confirmed and written to week 2026-10-13; pending doc marked applied. Run 20261016T00xxxx:
  Miami +0.70 -> +0.78; Cup Miami 14.8 -> 16.4, Nashville 21.9 -> 21.6, Vancouver 22.6 -> 22.4, Philadelphia 8.2 -> 7.9. Page v26.
- 2026-10-15 (late) Rerun 20261015T234549Z on the 15 Pinnacle closes of Oct 14 that the Optic pull brought in (no knob change): ratings
  Nashville +0.70 -> +0.74, Miami +0.72 -> +0.70, Philadelphia +0.65 -> +0.69 (hand -0.05 included), St. Louis +0.41 -> +0.39; Cup Nashville
  21.2 -> 21.9, Miami 15.4 -> 14.8, Philadelphia 7.6 -> 8.2, St. Louis 9.3 -> 8.7; West St. Louis 18.8 -> 18.0; playoffs Orlando 83.6 -> 86.0,
  Galaxy 67.5 -> 69.3, D.C. 19.8 -> 17.7, San Diego 12.6 -> 10.7. Forecast check on the 15 posted lines of Oct 17-18: rmse 0.088 (layer on
  would be 0.123). Page republished (v24); the implied grid drops a posted row once its close is on file.
- 2026-10-15 (night) **Philadelphia hand adjustment -0.05 goals** (Zac: bring them down to between the last-4 and last-12 Pinnacle-implied
  ratings; another source ranks them 12th on a season-long rating). Mechanism built the same night: an open-ended row in
  `data/ratings/adjustments.csv` (no `to` date) is **rating-level**: added to the club's blend in `build_ratings`, so the regular season,
  the playoffs and the Ratings tab (hover shows "hand adjustment") all see it; `blend.csv` now carries `blend_raw` and `hand_adj`.
  Dated rows (with a `to`) stay fixture-level as before (`hand_adjustment`; its from/to read was fixed, the keyword column was being
  ignored). Philadelphia +0.70 -> +0.65 (blend +0.70 kept). Effect (200k): Cup Philadelphia 8.4 -> 7.6, Miami 15.2 -> 15.4; top-4
  Philadelphia 48.8 -> 47.4; Cup finalist 16.5 -> 15.4; conf semi 66.3 -> 64.6; East and playoffs unchanged. Page republished (v20).
  SUPERSEDED 2026-10-16: rating-level hand adjustments live in the weekly `data/ratings/hand_log.csv` (Ratings tab week boxes);
  `adjustments.csv` is only for dated fixture-window rows. An open-ended row there would be ADDED on top of the log.
- 2026-10-15 (night) **xG weight 25% -> 15%** (source_config market 0.85 / xg 0.15; Zac: "do 12", section 13b). Evidence: close-tracking
  15 seasons 0.2430 vs 0.2437 (10 of 15 seasons), goals-tempered xG worse, Pinnacle's recent closes side with the trusted reader on
  Philadelphia and Miami. Effect on the 200k run: ratings Vancouver +0.76 -> +0.81, Miami +0.69 -> +0.72, Nashville +0.69 -> +0.70,
  Philadelphia +0.72 -> +0.70, St. Louis +0.42 -> +0.41; Cup Vancouver 21.6 -> 22.6, Miami 14.7 -> 15.2, Philadelphia 8.9 -> 8.4,
  St. Louis 9.8 -> 9.3; West Vancouver 70.0 -> 70.8, St. Louis 19.9 -> 18.8; Cup finalist Vancouver 39.2 -> 40.4, Miami 25.1 -> 26.2;
  playoffs within a point. Page republished (version 19). Section 7's 75/25 scorecard decision is superseded.
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
  before each date (`site_data.py`). half_life_days still sets the injury/call-up absorption weights and ridge_lambda is the xG fit's ridge (both live); neither shapes the market source under the filter.
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
HISTORICAL PROCEDURE (review 2026-10-19): the table below is kept current, but the text after it records the 2026-10-12
programme, which ran on the retired least-squares ratings at rating_sd 0.30, drift 0, dc_rho 0 and no dock. Those reports
(`rating_sd`, `drift`, `drift_k_grid`, `shade`, `replay`, `half_life`, `scorecard`, `clv`, `match_checks`, `dead_teams`) are
historical; `outputs/calibration/README.md` says which reports still describe the live model. Today's procedure:
`close_track.py` for anything that changes the ratings, `backtest_season.py` (sim stage) for rating_sd, drift, dock and shade.
| Knob | Value | Evidence |
|---|---|---|
| half_life_days | 28 | next-ten rmse 0.3125 vs 0.3203 at 14 (15 seasons) |
| home_edge_goals | 0.44 | Pinnacle 2026 handicap-implied closes +0.440 (n 367); 2025 +0.449; 2024 +0.536; pooled since 2012 +0.51 |
| avg_total_goals | 3.2 | Pinnacle 2026 totals average 3.21; realised 3.26 |
| shared_goals_mean | 0.10 | 6049 closing-ladder prices: rmse 0.0150 at 0.10 (0.05 0.0152, 0.15 0.0154); realised margin variance agrees |
| rating_sd | 0.10 (RE-SET 2026-10-15 night, Zac, proposal 6; was 0.20 from the morning, 0.30 before) | rest-of-season backtest, section 11c: with drift 0.01 the pair keeps the points log-pmf of 0.30/0, puts 20.3% of real points totals in the 20% tails (0.30/0: 18.6%, too wide) and wins playoff qualification in 13 of 15 seasons; the 0.10 re-set came with the dock and the shade's removal (11d proposal 6), and at 0.10 the filter-rating backtest (`kf_final_sim`) puts 22.0% in the tails |
| drift_k_sim / drift_cap | 0.01 / 0.10 (RE-SET 2026-10-15; was 0 / 0.10) | same backtest; surprise taken against the dice's own expected margin (shrink included) since 2026-10-15; cap never binds at k 0.01 |
| rating_method / posted_in_fit | kalman (q_day 0.03, s 0.25, q_off 0.1, off_shrink 0.75, p0 0.4) / on (SET 2026-10-15, Zac) | close-tracking yardstick, section 13: 0.2437 vs 0.2677 a week out, 15 of 15 seasons |
| dc_rho / dead_dock_goals / tiebreakers | -0.05 / 0.5 (min odds 0.02) / h2h + disciplinary points on (SET 2026-10-15 night, Zac, proposals 3-5) | 11f, 11g, 11e |
| team_totals_enabled | on, hl 30, ridge 0.25 (SET 2026-10-15, Zac) | walk-forward vs Pinnacle's totals 0.216 vs 0.332 (`outputs/calibration/team_totals.md`) |
| shade | OFF everywhere (SET 2026-10-15 night, Zac, proposal 6; was east/west b 1.5) | leave-one-season-out: conference winner 0.1205 vs 0.1213 raw; shield, playoffs, top-4, spoon, bottom lost held out |
Phase 1 acceptance (least-squares era; the filter has no residual sd): the live fit's weighted residual sd on this season's Pinnacle closes is 0.214 goals (target under
0.15) — NOT MET; the forecast check (closes-only ratings against the 15 posted lines of Oct 14) is rmse 0.164, bias -0.03.
Per-club home residuals over 14 seasons (full-season fits): RSL +0.06 (4 se), Seattle +0.05 (3.5 se), LAFC +0.06 (3 se),
D.C. United -0.06 (3.5 se), Cincinnati -0.07 (2.6 se), Colorado +0.035 (2.3 se); a per-club edge is a proposal for Zac.
Longshot rule (replay, raw prices, measured at rating_sd 0.30): events priced 2-5% happen 0.64x as often as priced; 5-10%
0.83x; 10-20% 0.79x; 20-40% 1.04x. RETIRED 2026-10-19: rating_sd is now 0.10 with the dock (at 0.10 the conference-pool 2-5%
ratio is 0.81x, `shade_diag.csv`), so the old haircut ("a sub-5% price is a third to a half too high") would double-count;
do not apply it to today's prices. The Risk tab's futures-confidence ranges are the current guide.
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

## 6a. First-run order of operations (DONE 2026-10-12/13)
Harvest, fetches, first fit, calibration programme, first 200k run and publish, scheduled tasks, layer measurements: all done
(sections 6, 6b, 8, 9, 10). For a fresh season or a fresh container: `harvest_optic.py` (resumable; needs the Optic key),
`fetch_schedule.py`, `fetch_results.py`, `fetch_history.py`, `fetch_xg.py`, then `weekly.py --force`.

## 6b. CLV test and the shrink (run 2026-10-12 on 903 Pinnacle opener/close pairs from the OpticOdds harvest, 2025-2026)
- Where the closes-only ratings disagreed with Pinnacle's opener by 0.15 goals or more (267 of 903 fixtures), the close
  moved the model's way 67.4% of the time, mean signed move +0.11 goals; at 0.30 or more (65 fixtures) 73.8%. The closes
  move further on attacks (0.22) than elsewhere (0.19). This is the Pinnacle-grade proof the build prompt asks for.
- Shrink grid on the close: ratings only 0.261, s 0.35 0.248, s 0.50 0.246, s 0.70 0.247, opener only 0.257; fine grid
  s = 0.55. posted_line_shrink 0.35 -> 0.55 (floor: the live posted line is fresher than the true opener). SUPERSEDED:
  1.0 since 2026-10-15 (section 5).
- Openers as measurements: run in section 13 (no gain, 2 of 15 seasons). Half-life re-grid: moot under the Kalman filter.
- OpticOdds coverage facts: Pinnacle history exists for 2025 and 2026 only (the 2024 files are empty), 34 completed 2026
  fixtures carry an opener but no close (suspended markets) and fall back to football-data's average close.
- Harvest complete 2026-10-13 (`data/optic/README.md`): six books x 960 MLS fixtures 2025-2026, the four cups' Pinnacle
  history (438 fixtures) for the congestion study, results with team stats for the form-source study. The congestion
  study is done (section 13, `congestion.md`); the book comparison (`lines_<book>.csv`) and the form-source study are unused.

## 7. Scorecard (run 2026-10-12 on 14 seasons of Pinnacle three-way closes; xG for 2024-2026)
rmse in goals predicting the next ten closes, walk-forward (`outputs/calibration/scorecard.md`), market half-life 28:

| season | market | 75/25 (xg hl 45) | 50/50 (xg hl 21) | xg alone (hl 45) | benchmark (home edge only) |
|---|---|---|---|---|---|
| 2024 | 0.3150 | 0.3151 | 0.3361 | 0.4109 | 0.4968 |
| 2025 | 0.2606 | 0.2512 | 0.2742 | 0.3484 | 0.5027 |
| 2026 | 0.2451 | 0.2377 | 0.2867 | 0.3938 | 0.5740 |

SUPERSEDED: the weights are 85/15 since 2026-10-15 night (13b) and the yardstick is close-tracking (section 1), not this scorecard.
Decision 2026-10-12 (the recipe's own rule: keep 50/50 unless the grid separates cleanly, and it does): weights market 3.0 /
xg 1.0 (75/25), xG half-life 45 days. 50/50 loses to market-only in every season; 75/25 wins by 0.007-0.009 goals in 2025
and 2026 and ties 2024. Earlier seasons have no xG on file.
Market-only by season (2012-2023): 0.247, 0.272, 0.259, 0.289, 0.345, 0.367, 0.411, 0.388, 0.321, 0.297, 0.278, 0.302.

## 8. Measurements of the layers
- 2026-10-15 night: **injury layer ON** (Zac: "turn on injuries, get the latest updates, and adjust accordingly"). Optic key absent from
  this container (re-add as an environment secret for the daily Optic pull; the sportsgambler feed needs none). Tiers set: Müller
  star (hamstring Oct 6, return assumed Nov 1), Lozano, Harrison, Lod, Steffen, Luna (key; Luna out for the season since Sep 9, absorbed),
  Allende, Silvetti, Bright, Robinson starter, Blackmon and Pasalic one-match suspensions Oct 17; the duplicate "Riqui Puig" row removed
  (Ricard Puig out for 2026, key, absorbed). The absorption now counts the current round's posted lines (they are in the ratings). MEASURED
  on the 10 lined fixtures of Oct 17-18: gap to Pinnacle rmse 0.125 without the layer, 0.150 with it; the layer moved the model away from
  Pinnacle on 8 of 10 (e.g. Atlanta v Miami +0.086 for Miami's absences where Pinnacle already had Miami stronger than us): with the round's
  lines inside the ratings, the absences are already priced and the layer double-counts them. Effect on the 200k run (vs the layer-off run
  20261015T225014Z): West Vancouver 70.0 -> 68.1, St. Louis 19.9 -> 21.2; playoffs NYCFC 34.9 -> 32.8, San Diego 11.9 -> 13.7, Galaxy 67.2 ->
  65.7, Red Bulls 52.5 -> 54.0; top-4 Philadelphia 48.9 -> 51.8, Chicago 66.1 -> 63.7; Cup within 0.1. Kept ON on Zac's word; the
  measurement says it should be off or re-based on the filter's own absorption. **Turned OFF again the same night (Zac: "Ok turn it off")**;
  rerun 20261015T225xxx restores the layer-off markets; tiers stay in `injuries.csv` for the record and the every-run off-vs-on measurement.
- 2026-10-12 Injuries (25 site rows, all squad tier 0.02, first import dated 28 days back so mostly absorbed): on the 15 lined
  fixtures of Oct 14 the gap to Pinnacle is rmse 0.1723 with the layer off and 0.1703 on; mean |adjustment| 0.010 goals,
  max 0.023. Within noise: the layer stays OFF until Zac sets tiers and three or more rounds of lines are logged.
  `run_sim.py` now measures off vs on every run (`outputs/calibration/layers_log.csv`, also printed in the run line).
- Call-ups: the next FIFA window is Nov 9-17, after Decision Day; no regular-season fixture is affected, so `callups.csv`
  stays empty and the layer OFF. The Wild Card on Nov 18 follows the window: a call-up list matters for the bracket only.

## 9. Automations (scheduled tasks; centralised 2026-10-19 evening, Zac: "one routine every morning at 8:30 ... everything refreshed")
**One routine: "MLS morning 8:30 ET"** (trig_01QLveWYB68apnJwRMi7Mbmn; daily 08:30 America/New_York, the server fires it a few
minutes after; it fires into the dedicated session **session_011MVmd8CrBrBc6Mcjc9vGJc** "MLS morning routine (scheduled)", which has
the repo attached with push access to the live branch). Its prompt is `docs/morning_routine_prompt.md` (kept in step with the stored
prompt; the stored prompt can only be edited from session_01CwMyfvastsNUFFP5iAd7hE, which created it, or from the session it fires
into). A first version that started a fresh session per firing was tested and dropped the same evening: a fresh session has no
repository access (its push got 403) and no Python packages (hence `requirements.txt`). Steps: git onto the live branch and
install requirements; export the page's
settings/pending; news (fetch_results, fetch_injuries, news_scan, a web search per thin item, injury maintenance at squad tier);
`weekly.py` (every input, the full run, Risk, history, data checks, morning report, page, page check); write back the applied
stamps; publish the page; commit and push; arm the close captures for the next eight days as one-shot tasks into the same
session; report in chat there (Data / Games to look at / Moved / Hands / Act / Injury list) and a one-line push notification.
Rehearsed 2026-10-19 19:00Z by a one-off task into the same session: all 9 steps, weekly.py exit 0, page v49 published, pushed
(f61eb95), settings/pending stamped, no capture slots missing (the Oct 21-25 captures armed by the old 8:52 task, bound to
session_01Lyt4NSGCEM6d6K5u8BMXg7, are left to fire), TEST push notification sent. A manual "fire now" of the bound task opened a
separate session without the repo instead of using the bound one; rehearse with a one-off task bound to the session instead.
`weekly.py` order: fetch_results -> fetch_pinnacle -> fetch_odds -> close_fallback -> fetch_injuries -> close_schedule -> fetch_asa_players
-> absences build -> fetch_psr -> absence_values -> disc_points_espn -> apply_site_settings -> fetch_xg -> opta -> run_sim -> risk
(Risk tab + ratings_history row) -> edges -> site_data -> freshness -> morning -> build_site -> check_site -> freshness_final (the ASA fetch logs as fetch_asa_players_last_season / _this_season); each step's exit code and last
line in `outputs/latest/weekly_steps.json`. New the same evening: `scripts/freshness.py` (data checks: steps ran today, every past
game scored, Pinnacle closes since Oct 14, lines for the next 3 days fetched within 24 h, xG and ASA minutes for every played game,
injury list valued today, discipline current, Opta age, the run/risk/history built today on today's data, site edits applied, hands
in force) and `scripts/disc_points_espn.py` (disciplinary points from ESPN's match summaries, no key: fouls and card events per game
cached in `data/discipline/espn_games_<season>.csv`; agrees with the OpticOdds totals to a club ranking of 0.98 over the 28
matches both cover, fouls almost identical, ESPN 0-12 yellows more per club); `apply_site_settings.py` now writes a method_log row
for every applied site edit (hand changes club by club), so the History and Risk tabs mark them. The morning report's hand review
judges each hand only on closes played after it was set (verdict too early / keep / raise / trim / drop, from 0.3 x the average miss).
OpticOdds is not used (section 4). Close captures (Zac 2026-10-19 "do 2"): each capture task runs `scripts/close_capture.py`
(fetch_pinnacle --close, then site_data + build_site, about 15 s, no model rerun) and republishes the page, so the top-corner "Last
close" is current the same evening. Every regular-season capture slot through Decision Day (22 tasks, Oct 21 to Nov 7) was
created from this session (session_01CwMyfvastsNUFFP5iAd7hE) into the dedicated session with that prompt, and the old Oct 21-25 ones
(bound to session_01Lyt4NSGCEM6d6K5u8BMXg7) disabled. Stored prompt replaced with docs/morning_routine_prompt.md on 2026-10-20 from the dedicated session (Zac: "update").
**Retired 2026-10-19 evening (disabled, not deleted, so their history stays):** "MLS morning news 7:40 ET" (trig_01S17cqCUZRuu9NoJAs4XA9m)
and "MLS Pinnacle lines 8:52 ET" (trig_01SYLkPVCqP65bbbc5XdvEdB), both bound to session_01Lyt4NSGCEM6d6K5u8BMXg7. The close captures
that 8:52 task armed for Oct 21-25 were disabled and re-created (above); the new routine only adds slots that are not covered.
The account's Premier League tasks (Prem-Futures repo, session_01EC9w3X9LTm7utEs871wzfr) are separate: leave them alone.

## 10. Website (current page, rewritten 2026-10-19)
**URL: https://claude.ai/artifact/PYXHJ1tuZhpRqgoub1Nfao** (v45, 2026-10-19: Morning tab) (private to Zac; capabilities `db` + `user`). Build:
`site_data.py` -> `outputs/latest/site_data.json` -> `build_site.py` embeds it into `site/index.html` ->
`outputs/latest/site.html` (published) and `site_local.html` (the headless copy) -> `check_site.py` (every tab, console errors,
no sideways scroll, the Bracket slots, the club drawer opening and closing, a Ratings Run with no edit moves nothing). Republish the same file path after every
run with capabilities omitted so db + user carry forward; from another session pass the URL as `url`. The template is a
fragment (title + style first; the publish tool wraps it). Design (since 2026-10-23 evening, section 5): matte charcoal (dark only since 2026-10-24), club colour bars (`data/club_colours.csv`),
American odds by default, ET, crests and player headshots embedded as data URIs (`data/logos/<code>.png`, `data/headshots/`).
Top-corner stamp (Zac 2026-10-19 evening): "Refreshed <time> · Last close <time> ET" = the last full morning refresh
(weekly_steps.json) and the last Pinnacle close on file (a 10-minute capture stamped when taken; Pinnacle's official close via
OpticOdds stamped at kickoff); hover gives the games, the source, results-through, lines and run times. The page is built only by
the refresh, so a close captured in the evening shows the next morning. Closes: the 10-minute captures write `pinnacle_last`;
the morning OpticOdds pull used to upgrade them to `pinnacle_close` (needs the key, absent since 2026-10-19), so without the key the
captured line 10 minutes before kickoff is the close. The morning refresh fetches posted lines for upcoming games only.
Tabs (four since 2026-10-23 late night: Morning, Table, Games, Bracket (the what-if bracket since 2026-10-24, section 5); the club drawer holds History and Injuries; the
line ticker of proposal 6 was removed the same night; section 5 has the night's entries):
- **Morning** (shape since 2026-10-23, section 5: tiles Data / Games / Miss 30d / Edges / Hands, one Today list, Data folded and
  showing only what is not ok, Games v Pinnacle, Track record grid, Least sure ratings, What's new folded; the first tab since
  2026-10-21; its Today list gathers edge flags, the data verdict, hands, flagged games, futures moves of a point and the widest
  Risk ranges) (2026-10-19, `scripts/morning.py` -> `outputs/reports/morning_<date ET>.json` and `outputs/latest/morning.json`; the last
  14 embedded by `build_site.py` as `window.MORNING`, a selector picks the day): headline lines; every lined game of the next 8 days,
  our ratings' own price (without this round's lines, factors added back) v Pinnacle's line, the gap in goals (watch 0.15, big 0.25),
  home-win points, the line's move since first posted / since the previous report, and the reasons in plain words (a factor we add:
  eliminated, absences, rest; Pinnacle's last 4 closes v our rating; the xG share; a hand adjustment; the line moving toward or away
  from us); track record over 7 / 30 days / season (match-morning price v the close and v the results, log-loss ours v Pinnacle v
  no-skill, by month); what's new since the previous report (results and our miss, rating moves split Pinnacle / xG / hand, futures
  moves of a point, injury-list changes, model changes). A same-day rerun overwrites that day's report and still compares with the day
  before. Since the evening of 2026-10-19 the first card is Data checks (`freshness.py`) plus the hand review (each hand in force,
  judged on the closes since it was set), and the first headline line is the data verdict. weekly.py prints the headline lines.
  Since 2026-10-19 night (Zac: "add that") a "Least confident ratings" card and headline line (`morning.confidence`): for each club
  with a live futures price, our rating v Pinnacle's implied windows (last 4 / 8 / 12, this round's line; raw), flagged when outside
  every window by 0.04+, 0.12+ from the 8-12 windows with the xG share pulling the same way by 0.05+, Pinnacle's windows 0.25+ apart,
  last 4 v season 0.40+ apart, or a hand of 0.05+; "could be" = the window range plus ours; biggest doubt first, at most 8.
- **Edges** (TAB REMOVED 2026-10-23, Zac; edges.py still writes edges.json for the chat report) (2026-10-20, `scripts/edges.py` -> `outputs/latest/edges.json`): per market (MLS Cup / East champion / West champion) and club:
  our fair (200k run) with the Risk tab's range, the books' devigged median (complete fields only, power method), the best price and its
  break-even, edge in points, EV, and the cautious EV (pooled with the market at weight 0.5, at the low end of our range). A green EDGE chip
  and a tab dot when the cautious EV is positive. A Books card per market: clubs listed, hold, coverage, devigged or raw. Without book
  prices (no `ODDS_API_KEY`) the tab shows our fair prices and says what is missing.
- **Table** (the Ratings tab until 2026-10-23 late night; data-tab still `ratings`) (column names 2026-10-20, Zac: "Final" read as the MLS Cup final; now Reach semis / Reach conf final / Reach MLS Cup
  (was Win conf) / Win MLS Cup (was Cup), the same on the Conferences, History, Risk and Morning tabs; data keys unchanged): a "95% band" column after Rating (2026-10-19 night, Zac "do 2"; Glicko's interval: rating plus or minus 1.96 x the filter's
  posterior sd, `sd` in site_data teams, moves with hand edits; the club detail names Pinnacle-implied windows outside it; the sim's own
  season draw is narrower, plus or minus 0.20, drift adds the rest). A "Columns" menu (2026-10-19, Zac) hides any of Rating, 95% band, Hand, Conf 1st, Playoffs, Semi, Final, Win conf, Cup
  (remembered per browser). Both conferences ranked by rating; columns Rating, Hand (one box per club = the week's hand adjustment in goals,
  `hand_log.csv`), Conf 1st, Playoffs, Semi (wins its Round One series), Final (reaches the conference final), Win conf, Cup;
  ▲/▼ arrows beside each Hand box step it 0.01 goals (2026-10-19, Zac); every cell shows its change v the previous run (Deltas on/off button, remembered per browser). A week selector (Tue-Mon
  weeks), Run (the page engine, 20k seasons, run twice on one seed: the run's ratings and the edited ones; the preview is the
  run's price plus the difference, so the engine's missing dock and tiebreak steps cancel and an unedited Run moves nothing)
  and Save (merges the week's hand values into `settings/pending`; applied by the 8:52 task or on Zac's word in chat).
  Clicking a club shows its sources (blend before hand, market, xG, Opta anchor, closes, club home edge) and the
  Pinnacle-implied rating grid (this weekend's line, last 4 / 8 / 12 closes, season, ours).
- **Games**: a "Model price from" switch (2026-10-19, Zac; remembered per browser) picks the Model columns: **without this round's
  lines** (default, as below), **with this round's lines** (the live ratings with the round's Pinnacle lines fed in; played games from
  the match-morning filter with that round's closes applied as posted measurements: close to Pinnacle by construction), or **stats
  only** (the xG source alone, never fed a Pinnacle line, rescaled to the filter's spread, same home edge and match-day factors, no
  hand). A line under it gives each version's typical gap to Pinnacle on the page's games (2026-10-19: played v the close 0.23 / 0.13 /
  0.44 goals; upcoming v the line 0.09 / 0.05 / 0.38): how much of our price the recent lines carry. Data: `site_detail.replay_fits
  (variants=True)`, `g.alt` in site_data.json.
  Tue-Mon weeks (labels follow the week shown). Per game: Pinnacle fair (power-devigged three-way; the 34 games
  with only the market-average close are labelled so), Model = our ratings' price, Gap = model minus Pinnacle on the home
  win. Model always uses the ratings built WITHOUT that round's Pinnacle lines: an upcoming game today's (the sim itself
  prices a lined game off the line), a played game the ratings on match morning (Zac, 2026-10-19; from 2026-10-15 to then a
  played game used the morning ratings with the round's lines in, so its gap to the close was small by construction), so a
  played game's gap is the ratings' own miss against the close. With full-health ratings on, the played game's price adds back
  that game's factors (rest, short week, eliminated status, and the absences as the lineups were, which the close knew). Detail row: raw prices, Gap v line / v close per
  outcome, expected margins. Other books' lines show dimmed where Pinnacle has none (display only).
- **Conferences** (TAB REMOVED 2026-10-23 late night: xPts, Top 4 and Bottom are columns of the Table tab): expected points
  (p10-p90 on hover), Playoffs, Top 4, Seed 1, Win conf, Cup, Bottom (Spoon on hover); odds shown between 1% and 99% (outside
  that a dash or a dot with the exact percent on hover).
- **Risk** (TAB REMOVED 2026-10-23, Zac; risk.py still runs: rating history, Morning tiles, chat report): health tiles (ratings v
  Pinnacle a week out, spread, draws, inputs), watchlist, futures confidence ranges, rating changes split into Pinnacle / xG / hand,
  blind spots (paragraph below).
- **History** (TAB REMOVED 2026-10-23 night: the charts, closes and What changed live in the club drawer; the change log and the
  all-clubs table were dropped) (2026-10-19, Zac: "more vision ... what the rating was, when it was changed, and what changed it"): a club picker and
  range (season / 60 / 30 days / since the first run) over one chart with three series (validated for the dark surface): the rating
  each published run used (blue, `ratings_history.csv`), today's method replayed on every match morning of the season (aqua: the
  full-health Kalman ratings without that round's lines, xG blend, that week's hand, the same walk-forward the Games tab prices
  played games with), and what each Pinnacle close implied for the club at full health (orange: close net of home edge, club delta
  and the game's factors, opponent at its match-morning rating); dashed numbered lines are `method_log.csv` entries; the crosshair
  lists every series at the nearest date. Below: "What changed it" (each run where the club moved or the model changed: rating,
  change split into Pinnacle / xG / hand, the games since the run before with close and implied rating, model changes, hand edits),
  the club's Pinnacle closes table (close, factors, implied, v ours), the model change log, and all 30 clubs with changes since the
  last run / 7 days / the first run and a trend sparkline (click to chart). Data: `scripts/site_detail.py` (`history`).
  Under the chart (2026-10-19 night, Zac "do 3", the method PDF's weekly fair-odds history): "Futures price history", the club's published
  price of one market (Conf 1st / Playoffs / Semi / Final / Win conf / Cup, remembered per browser) at every archived run as a step line,
  same range buttons, model changes dashed, hover for the run, fair American odds, the change v the run before and any model change
  between. Data: `history.runs[].m` from `outputs/runs/<stamp>/markets.json` (published prices: the two conference pools carried the shade
  before 2026-10-15 night; Semi and Final only from 2026-10-19).
- Page v42 (2026-10-19 ~16:20Z) is the first with the History tab and the breakdowns; it was published from branch
  claude/full-health-ratings-0b33j4 (gallant 0f85fa4 + this work) and merged into gallant the same afternoon on Zac's "Yes merge"
  (fast-forward), so the scheduled tasks carry it.
- **Full-health breakdowns** (same day): every Games row has an Adj column (the match-day factors on the home margin) and its detail
  shows, per side, absences (player by player: value per 96 x share or prob out x regular weight), rest (v a normal 7-day week),
  short week and eliminated status, the price at full health, with the factors and Pinnacle's; a played game adds the close net of
  factors (what the ratings absorbed); an upcoming game lists the listed players NOT counted and why (stale, no MLS minutes, not a
  regular, at replacement), the dock share and that the sim prices a lined game off Pinnacle. Each Ratings club detail shows full
  health v strength as fielded in the next game, a trend sparkline and a "Rating history" button. Data: `site_detail.py`.
- **Injuries** (TAB REMOVED 2026-10-23 night: the club drawer's Absences card): per club out / listed / next fixture, the layer's would-be penalty (a Penalty column only while a layer is on).
- **Settings** (TAB REMOVED 2026-10-23, Zac; the xG share changes on his word in chat) (Drift and Randomness sliders removed 2026-10-21: frozen knobs): the xG share slider, Run (page engine) and Save (merges into `settings/pending`; the
  frozen knobs are reported, not applied, by `apply_site_settings.py`; only the xG share goes through).
The page engine (`worker-src`) has the goal model with Dixon-Coles (by rejection on a second random stream), drift, posted
lines, team totals (playoff matches too), club home edges and the locked playoff results; not the dock, the head-to-head / discipline tiebreak steps or scenarios, which is why
Run is differenced against its own baseline.
History (details in section 5): first published 2026-10-12; Prem Futures design taken 2026-10-15 night; Scenarios tab and the
embedded season sample removed 2026-10-15 (page 4 MB -> 570 KB); hand column 2026-10-15; weekly hand log, Run/Save bar and
deltas 2026-10-16; Risk tab 2026-10-19; Shield column, shade toggle and unused payload removed and the Games Model switched
to the ratings' own price 2026-10-19 (review).
**Risk tab (2026-10-19, Zac: "a risk tab that shows all the red flags ... concise and neat and helpful"; branch claude/elegant-carson-p0svfm,
cut from claude/determined-cray-ckr043; built beside the full-health session without touching its files).** `scripts/risk.py` runs in
`weekly.py` after `run_sim.py` (about 80 s) and writes `outputs/latest/risk.json`, which `site_data.py` embeds (marked stale when built
for an earlier run). Five cards: (1) health tiles: ratings v Pinnacle's close priced a week out over the last 30 days (live recipe, hand
from the week's log; normal 0.243; with full-health ratings on, closes and the posted round net of their factors and each priced
close given its factors back as known a week out, absences as the last-ten average: close_track's honest recipe, normal 0.240), spread (slope of close on ratings, last 75 days; 1.10 on 2026-10-19 = ratings too flat), draws
(engine at the close's own margin/total v devigged close v actual), inputs (missing results, games with no Pinnacle close, unlined games
in the next 2 days, xG gaps matched within a day since ASA dates late kickoffs in UTC, Opta age, stale injury rows); (2) watchlist: only
clubs with a live futures price and either a persistent miss (|mean| >= 0.15 over the last 8 closes, >= 6 of 8 one sign) or a big
source split (xG v market >= 0.50, Opta v rating >= 0.40) where +0.10 goals moves a price >= 2 points; (3) futures confidence: each
live price (2-98%) under no recent lines / xG 0% / xG 30% / spread x1.06 and +0.10 goals per club, 20k seasons each on the same seed,
fixtures built once (`risk.Sim`); wide = >= 3 points or >= 1 point and >= 30% of the price; (4) rating changes since the last run / 7
days / the first run, split exactly into Pinnacle part + xG part + hand (weights x centred source; reconstructs every archived run to
0.0001), with results played and the Cup/playoff moves, plus the dated model changes inside the window from
`data/ratings/method_log.csv` (append a row whenever a ratings, pricing or sim change is applied); (5) blind spots. History:
`data/ratings/ratings_history.csv` (one row per club per run, backfilled from git with `risk.py --backfill`, appended every run).
Found while building it: `what_if.py`'s `xg_w` rebuilds the ratings from the sources and DROPS the hand adjustments (risk.py keeps
them; fix what_if when the full-health session is done with that file); `match_checks.md` was regenerated at dc_rho -0.05 on
2026-10-19; 34 games of 2026 (Aug 16 to Oct 1) have only the market-average close and cannot be recovered (OpticOdds has an
opener but no close for them; the 10-minute capture began on Oct 14).

## 11. Ratings session 2026-10-15 (north star: `docs/futures_sim_method_nfl.pdf`; no hand ratings, no book futures)
Yardstick change (Zac, 2026-10-15): ratings are judged on the rest-of-season backtest (`scripts/backtest_season.py`), not on the
next close. From six checkpoints per season (matchweeks 4, 9, 14, 19, 24, 29; 15 seasons 2012-2026) ratings are built from data
strictly before the checkpoint, results before it are locked, the remainder is simulated, and the scores are: final points
(log-pmf, rmse, PIT tails: 20% combined is honest), remaining-match H/D/A log-loss of the actual results from the static ratings,
rmse against the remaining closes, and playoff / conference / Shield / Spoon log-loss. Home edge and total per season as known at
the checkpoint. Paired seeds. Rows under `outputs/calibration/backtest/`; `summary` prints pooled means and seasons won vs a baseline.
A deviation from the PDF stays only if it wins clearly and consistently across most seasons there, and Zac approves it.
Plumbing fixed 2026-10-15 (data, not model): (1) `scripts/replay.py` double-counted 2025 (football-data and OpticOdds history files
both carry it; the replay joined both, so every 2025 match was simulated twice: 1056 matches, points rmse 16). Every earlier
calibration run after `OPTIC_2025.csv` landed (19:44Z on 2026-10-12) would have seen a doubled 2025; the committed rating_sd, drift,
shade and replay reports (19:04-19:23Z) predate it and saw a single 2025 (review 2026-10-19: replay.md's 2025 checkpoints match 540 matches).
(2) ASA xG now on file for 2013-2026 (`fetch_xg.py`, defunct clubs admitted via canon(historical=True); Chivas USA included), so
the xG blend can be backtested on 13 seasons instead of three.
Match-level checks (`scripts/match_checks.py`, `outputs/calibration/match_checks.md`, 6236 lined matches): favourite win rate by
closing bucket matches the devigged close (no NFL-style win-curve mismatch); the engine at the close's own margin and total gives
22.7% draws against 25.1% realised and 24.9% in the devigged close (0-0 realised 6.3% vs engine 4.6%: the Dixon-Coles signature;
at the live dc_rho -0.05 the engine gives 23.7%, recomputed 2026-10-19);
margin noise matches where totals are known (2025 sd 1.68 realised vs 1.70 engine; 2026 1.66 vs 1.74), the pooled gap (1.60 vs
1.73) is the 3.2 default total applied to 2012-2024 three-way-only closes whose seasons averaged 2.6-2.9 goals.

## 12. Where the model deviates from the method PDF (audit 2026-10-15; for later, none changed without Zac's word)
Excluded on Zac's instruction: hand ratings; market-implied ratings from futures / win totals; book futures as a comparison.
1. ~~Ridge toward zero in the market fit~~ SUPERSEDED 2026-10-15: the market fit is now the Kalman filter (section 13); its prior (p0, off-season reversion) plays the ridge's role and was set on the close-tracking yardstick. Original note: the PDF is plain least squares with a sum-to-zero row. Flattens the
   live market ratings 7% (sd 0.389 -> 0.360 at hl 28 on 2026-10-15). Under test in section 11.
2. ~~Half-life 28 days~~ SUPERSEDED 2026-10-15: no half-life in the filter (q_day/s = 0.12 is the equivalent memory, set on the close).
3. **Blend spread** (PDF: compare every time the blend changes) — now measured on every close-tracking run as the slope of the close on the model: 1.04 with the filter + xG (was 1.20). Live: blend sd 0.342 vs market
   0.389 at ridge 0, 12% flatter in total (ridge 7%, blending two sources correlated 0.74 another 5%). `blend_rescale` was not adopted.
4. **xG source**: raw spread 1.3x the market's at the same checkpoints (correlation 0.63 early to 0.75 late in the season), so the
   PDF's rescale-to-the-market step is right for it; the weight is 15% since 13b (close-tracking, 15 seasons).
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
13. **Playoff knockouts use the league home edge** (not the club delta) and a drawn knockout is a coin flip (PDF silent). Their
    totals are the clubs' team totals since 2026-10-19 (were the flat 3.2), and a played playoff match is locked to its winner.
14. **Fit target for 2012-2024 three-way-only closes** uses the 3.2 default total where those seasons averaged 2.6-3.1 goals;
    second-order on gd_fit, first-order on the engine's draw rate and margin noise when those lines are replayed at 3.2.
15. **Rating history**: done 2026-10-19: `data/ratings/ratings_history.csv` keeps every run's rating and its Pinnacle / xG / hand
    parts (Risk tab, `risk.py`).
16. **Uncertainty and drift were calibrated on market-only ratings** at ridge 0.5 (the replay never blended xG), while the live
    sim runs on the 75/25 blend (section 11). Re-done in step three of this session; the live blend is 85/15 since 13b.

### 11j. Playoff strength v regular season (Zac asked 2026-10-16: is MLS like the NBA, where playoff strength differs?; `scripts/playoff_strength.py`)
239 playoff matches 2012-2025 (2020 excluded; the 35th+ match of both clubs; football-data's Pinnacle closes) v a control of 520 last-3-week
regular-season matches, each predicted from that season's regular-season closes only (hl 28, ridge 0.5, home edge fitted). Pinnacle prices
playoff games exactly as the regular-season ratings imply: slope of the close on the rating gap 1.24 (se 0.045) v 1.25 control, fitted
home edge 0.54 v 0.56. Results: playoff favourites beat the close by +0.06 goals (se 0.10), win 55.6% at 90 minutes v 51.0% priced
(1.4 se; the control is -0.06): noise. Reading: no playoff strength shift to model; the engine's same-ratings knockouts match the market.
Schedule (2026 file): 14 conference rivals twice + 6 of the 15 other-conference clubs once = 34; the sim plays the real schedule.

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
| footballdatabase.com Elo-style points (RETIRED as a sanity source 2026-10-19, Zac: newest point Sep 1 and Vancouver at -0.75 goals when every other source has them top-3; data and loaders kept for the backtest only) | weekly page | monthly club histories 2010-2026 (`data/public/footballdatabase/history.csv`; Toronto page bot-gated, retry) | alone 1.0184 vs 1.0133; 25% blend 1.0120 (8 of 15); market+xG+15% fdb 1.0116 vs live 1.0125 (8 of 15 vs live) |
| soccerpowerrankings.substack.com "MLS Power Ranking Averages" (Zac asked 2026-10-15) | weekly post, public Google Sheet: truncated mean of ordinal ranks from ~15 editorial sites plus an Elo group (Massey, Opta, ASA xPts, Concacaf, Adam King) and a 9-book betting-odds group | 2026 only (first post 2026-02-24; `data/public/spr/avg_rank_long_2026.csv`, 25 weekly columns) | ordinal, lagged, book-derived component; week 24 Spearman 0.78 with the blend, 0.92 with Opta; 2026 backtest (5 checkpoints) alone 1.0890 vs market 1.0764 (worst of all sources), 25% blend 1.0771, on top of live 1.0755 vs 1.0740: not a rating source |
| ClubElo | club pages exist for 4 MLS clubs only; API host resets the connection | per match from Oct 2022, 4 clubs | not usable |
| 538 SPI | dead | 2017-18 only reachable (datahub mirror); Wayback blocked here | not usable |
| Massey | Cloudflare challenge blocks every fetch from this container | unknown | not usable from here |
| Sagarin (through Dec 2024), ESPN SPI (not published for MLS), Global Football Rankings (MLS from Oct 2025), Kickoff.ai, Dunkel, Power Rank, Sonny Moore (no archive), forzapitch (book-blended) | - | - | not usable |
Reading: no public model beats market-only on its own; every blend at 15-35% adds 0.0004-0.0013 of match log-loss and wins 8-9
of 14-15 seasons, the same order as season noise. xG helps early in the season (thin market data), footballdatabase mid and late.
Recommendation (Zac decides; xG later set to 15%, 13b): keep xG at 25%; take Opta as the live sanity anchor (daily, model-based, independent of our inputs),
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
Knobs unchanged pending Zac's word (rating_sd 0.10 / drift 0.01 applied the same night, section 5).

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

### 11f. Dixon-Coles (Zac's item 2, 2026-10-15; engine knob `dc_rho`; APPLIED -0.05 the same night)
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

### 11g. Dead-team docks (Zac's item 3, 2026-10-15; `scripts/dead_teams.py`, `outputs/calibration/dead_teams.md`; dock 0.5 APPLIED the same night)
CORRECTION 2026-10-19 night: the "last ten rounds" below include playoff games, so the locked-seed and top-seed-locked rows are mostly
playoff matches (Nov 23, Dec 7...). Regular season only (`scripts/locked_seed.py`, `outputs/calibration/locked_seed.md`): locked + top seed
locked n 34, +0.22 v the ratings (se 0.24); eliminated -0.36 (se 0.10, n 268), unchanged; clinched +0.04 (n 377). Section 15.
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

### 11i. Flat and lagging ratings (Zac's three tests, 2026-10-15; `zac3_ratings.csv`, `zac3_sim.csv`; knobs `ridge_fade_mw` (rejected), `posted_in_fit` (APPLIED with the filter, 13a))
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
in `what_if.py` (`rating_method=kalman,kalman_q_day=...`) and in the live build behind `rating_method` (kalman since the same evening, 13a).
Data fact: the OpticOdds Pinnacle history carries only the opener and the close per market (`entries` empty), so "the full price
path" reduces to openers as a second, noisier measurement (2025-2026 only); the openers are dated kickoff minus 5 days.
- **Kalman grid** (`kf_grid1-2.csv`, 67 pairs): rmse a week out is flat along q_day/s = 0.12 (0.03/0.25, 0.04/0.35, 0.06/0.5:
  0.2674-0.2677), q_off 0.05-0.15 indifferent; slope 0.93 (a shade wide), bias 0.003. Chosen 0.03 / 0.25 / 0.1 (config, provisional,
  method APPLIED the same evening). Lag 0: 0.249.
- **Team totals** (`scripts/calib_team_totals.py`, build prompt section 6, never built before today): the sim's constant 3.2
  misses Pinnacle's total by 0.332 goals rmse on 670 walk-forward totals 2025-2026; `totals_fit` (base + both clubs' offsets,
  hl 30, ridge 0.25) 0.216 (lag 7: 0.227); longer half-lives lose monotonically. Today: base 3.37, Inter Miami +0.55,
  Cincinnati +0.30, Orlando +0.26 ... NYCFC -0.29, Colorado -0.30, Houston -0.40. Wired into run_sim/what_if behind
  `team_totals_enabled` (ON since the same evening). 5000-season what-if: Cup Nashville 18.8 -> 19.8, Miami 15.2 -> 13.8; West St. Louis 11.8 -> 13.1.
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

### 13b. The trusted reader's feedback (2026-10-15 night: Philadelphia not 1st in the East, about +0.60; Miami a little higher)
Pinnacle agrees with him: the last eight closes price Philadelphia 0.07 below our rating and Miami 0.13 above it. The pull is the xG
source: Philadelphia market +0.67 / xG +0.90 (blend +0.72); Miami market +0.76 / xG +0.48 (blend +0.69). The market-minus-xG gap per
club persists (correlation 0.64 one month on, 0.47 two months; Miami's positive all season, finishing above xG; Philadelphia's negative
since August), while the market still drifts a quarter of the way toward xG over 60 days (corr -0.24), so xG keeps its place.
Tests on the close-tracking yardstick (`close_track/xgmix1.csv`, a week out, 15 seasons, vs the live recipe 0.2437): xG weight 15%
**0.2430** (better in 10 of 15 seasons; 2026 0.2481 vs 0.2492); no xG 0.2497; xG tempered with actual goals (a finishing-aware source)
worse at every mix (25% goals 0.2533, 50% 0.2543, 100% 0.2599). Today's ratings at xG 15%: Philadelphia +0.70, Miami +0.72, Nashville
+0.70, Vancouver +0.81 (market-only: +0.67, +0.76, +0.72, +0.88).
12. **APPLIED the same night (do 12): xG weight 25% -> 15%** (source_config market 3.0 / xg 1.0 -> 85/15). Today (100k): Cup Vancouver 22.0 -> 22.5, Nashville
    20.6 -> 21.2, Miami 14.5 -> 15.1, St. Louis 9.8 -> 9.2, Philadelphia 9.1 -> 8.5; West Vancouver 69.9 -> 70.7, St. Louis 20.0 -> 18.9;
    Cup finalist Miami 25.0 -> 26.0, Philadelphia 17.4 -> 16.7. A small, consistent gain, not a decisive one.

## 14. Full-health ratings session 2026-10-19 (Zac: strengths with the pricable match-day factors netted out of every close; branch claude/full-health-ratings-0b33j4, cut from the live model; proposals 1, 4, 5 ON since 2026-10-19 afternoon, section 5)
Goal: the Kalman state should be what Pinnacle's closes imply each club's strength is once the known, pricable factors of each match
day (absences, rest, eliminated status) are removed from the line; the rest of the season is priced from that full-health strength
with each future fixture's own factors added back. Yardsticks unchanged: close a week out (lag 7, `scripts/close_track.py`, live
recipe 0.2431 reproduced today on 6265 closes, slope 1.02) and the rest-of-season backtest (section 11). Pinnacle only; no hand
ratings; frozen knobs, dock, Dixon-Coles, tiebreakers and team totals untouched.

### 14a. Step 1: the absence dataset (`scripts/absences.py`, `outputs/calibration/absences.md`; raw ASA rows by `scripts/fetch_asa_players.py`)
- Source: ASA goals added by player and game with minutes played, 2013-2026 (every season has minutes; 2012 has no ASA data), plus the
  keepers file; the ASA games list (regular season only) joined to our closes by ET date and club: 90% of all closes matched, 95% of
  2013-2025 (the rest are playoff games, which carry no absence data and enter as zero) and 100% of 2026.
- Definitions (walk-forward, nothing peeks): a **regular** is a player with at least half of the club's minutes over its trailing ten
  league games (10.4 regulars per team-game); for the first five games of a season a trailing regular counts only once he has appeared
  for the club that season within the next five games (off-season departures are not absences; a mid-season departure fades out of the
  window within five games). **Absent** is judged pre-match: 0 minutes = fully absent, under 60 minutes = partly (a late sub was not fit
  to start), 60 or more = present. **Value** = goals added (raw) per 96 minutes over the trailing 365 days, shrunk toward the club's
  minutes-weighted rate with 900 pseudo-minutes, minus the league replacement rate (the previous season's non-regulars, minutes-weighted);
  keepers shrunk toward the league keeper mean with 3000 pseudo-minutes (ASA shot-stopping is noisy: regular keepers spread 0.15 goals
  per 96 within a season) against a backup-keeper rate itself shrunk with 5000 pseudo-minutes. **Missing value** of a team-game = sum of
  value x absent fraction over its absent regulars, in goals.
- Distribution (11,344 team-games): mean 0.037 goals, median 0.019, p90 0.16, p99 0.35, max 0.72; 2.4 regulars fully absent per
  team-game; the home-minus-away difference has sd 0.13 goals (the closes' residual sd against the morning state is 0.25).
- Sanity: the largest single absences are Messi (+0.50 per 96 in 2026, +0.38 in 2025; Miami v Chicago Jul 22 and v Montréal Jul 25
  2026, v Charlotte Mar 14), then Petrović, Vela (+0.36, 2019), Keane (2014), Bürki, Blake, Zlatan (+0.30, 2019); the most-valuable list
  by season reads Turner, Blake, Buksa, Bürki, Cucho, Benteke, Messi, Surridge, Pec; the regulars absent most often are the
  internationals (Osorio, Zimmerman, Godoy, Chará): FIFA windows and suspensions are in the data, not just injuries.
- Caveat: a long absence fades out of the trailing-10 window after five games, so a player out for the season (Puig, Luna) carries no
  missing value by now and his absence sits in the state, as it should; "full health" means the club's regulars of the last ten games.

### 14b. Step 2: does Pinnacle price it? (`scripts/absence_price.py`, `outputs/calibration/absence_price.md`)
Residual = close minus the plain filter's morning-of state (recipe `kf_plain`, lag 0, both net of the home edge), on 5602 matched
closes with an absence window, regressed on the home-minus-away missing value with rest, short week and eliminated status alongside:

| factor | coefficient (goals per unit, home minus away) | se |
|---|---|---|
| absences (per goal of missing value) | **-0.393** | 0.024 |
| rest (per day of rest difference, capped 10; MLS-only rest for 2012-2024, cups counted 2025-2026) | +0.005 | 0.002 |
| short week (3 days or fewer, flag) | -0.032 | 0.011 |
| eliminated (flag) | -0.193 | 0.016 |

- Stable: negative in 14 of 14 seasons (season coefficients -0.05 in 2013 to -0.63 in 2016, mean -0.38, sd across seasons 0.15 against a
  mean se 0.09, i.e. the spread is mostly noise); walk-forward (fitted on the seasons before each one) -0.17 (2015), -0.33 (2018), -0.39
  (2020), and between -0.38 and -0.39 every season since 2021. Same in every phase (early -0.40, mid -0.37, late -0.38). Symmetric
  (home -0.34, away +0.43). Field players -0.42, keepers -0.29. The residual by bucket is monotone: dmv below -0.3 goals +0.21,
  above +0.3 goals -0.18 (n 129 and 66). The close on model + factors gives model slope 0.99 and the same coefficients.
- Reading: Pinnacle prices absences, at 0.39 goals of closing margin per goal of our missing value, over and above what the
  morning-of state has already absorbed through earlier closes (so the full price of an absence is higher; step 3 reads it off the
  netting grid). The eliminated coefficient -0.19 is the 11g number (close 0.2 below the ratings for an eliminated club). Rest is the
  MLS-only figure of 13 (+0.005 to +0.008 per day; +0.018 needs the cups, which are on file for 2025-2026 only). Nothing here is
  "news": every factor is known before kickoff, so the idea has an edge to extract and the work continues to step 3.

### 14f. Step 5: today's absences in goals (`scripts/absence_values.py` -> `data/ratings/absence_values.csv`, `outputs/calibration/absence_values.md`)
Every listed player (injuries.csv plus the latest Optic feed, 2026-10-18) matched to his ASA name within the club's roster (106 of
125 matched; the 19 unmatched have no league minutes in the last 365 days, e.g. Puig, de la Vega, and carry nothing), valued at
his goals-added per 96 above replacement (same method as the dataset, as of 2026-10-19), weighted by his regular ramp (share of the
club's trailing-10 minutes) and prob_out (Optic "gtd" and sportsgambler doubts 0.5), with return date and league games missed.
Stale rows (a player who has appeared since his `out_from` and is not on the Optic feed; sportsgambler keeps old rows: Denkey,
Musa, Ramiro, Pereyra, Donkor, Osorio and 15 more) carry nothing and are flagged. Reading today: the list is thin. Largest
absence values now: D.C. United 0.07 goals a game (Bartlett, Munteanu), Cincinnati 0.05 (Miles Robinson), Portland 0.035 (Surman,
doubt), Dallas 0.03 (Farrington); every other club under 0.02. Müller (Vancouver) values at -0.01 per 96 on the position-adjusted
basis (his g+ above average is at replacement level over the last 365 days) at a regular weight 0.6: no cost in this model, where
the star tier priced him at 0.20; Lozano +0.01 (key tier 0.10); Harrison +0.02 at weight 0.21 (key tier 0.10); Allende and
Silvetti are not regulars by minutes. At factor_abs -0.48 the largest live fixture effect today is 0.035 goals (D.C. home).
So the edge in this work is in the state (full-health strength), not in today's fixture add-backs. The Injuries tab can show this
file's `value_per96`, `regular`, `cost_per_game` and `games_missed` instead of tiers once Zac wants it (not wired).

### 14c. Step 3, first grid: netting the factors out of every close (`close_track/fh_grid1.csv`; 17 recipes x 15 seasons, lags 0 and 7; absence dataset on the raw basis with a hard 0.5 regular threshold, the one in place when the grid started; the final grid on the position-adjusted basis is 14d)
Every close enters the filter as close minus (absences x beta_abs) minus rest minus short week minus eliminated status; the posted
lines likewise; each scored fixture gets its factors added back a week out: absences either as the actual lineups (`actual`, the
ceiling: known only on the day) or as the club's mean missing value over its last ten games before asof (`trail10`, the honest
persistence forecast), rest and short week from the schedule, eliminated status as of asof. Live recipe 0.2431 (slope 1.02).

| recipe (a week out, lag 7) | rmse | slope | seasons better than live |
|---|---|---|---|
| all four factors, absences added back from the actual lineups (ceiling) | **0.2327** | 1.03 | 15/15 |
| absences only (beta -0.39 or -0.60), actual lineups | 0.2360 | 1.03 | 13/15 |
| all four, no xG, actual lineups | 0.2398 | 0.99 | 10/15 |
| all four, netted out and NOT added back | 0.2402 | 0.99 | 12/15 |
| all four, absences forecast from the trailing ten games (honest) | 0.2404 | 1.02 | 13/15 |
| eliminated status only | 0.2407 | 1.02 | 13/15 |
| rest and short week only | 0.2422 | 1.02 | 12/15 |
| live | 0.2431 | 1.02 | - |
| absences only, trailing-ten forecast (-0.25 / -0.39 / -0.60) | 0.2432 / 0.2437 / 0.2448 | 1.02 | 5 / 4 / 3 of 15 |
| live without xG | 0.2498 | 0.98 | 1/15 |

Readings: (1) with the lineups known the gain is large and universal (0.2431 -> 0.2327, 15 of 15 seasons): Pinnacle's close
really is full-health strength plus the day's absences, and the filter tracks it better when the two are kept apart. (2) The
honest part of that gain is small: netting alone (not adding back) 0.2402 and the trailing-ten forecast 0.2404, i.e. 0.003 of rmse,
12-13 of 15 seasons, most of it from the eliminated-status and rest terms; absences forecast by persistence add nothing on their
own (a club's absences a week out are not well predicted by its last ten games). (3) What the live model would use sits between
the two: the injury list with return dates is far closer to the lineups than a trailing average, so the live gain is between 0.003
and 0.010 of rmse, closer to the ceiling for clubs with long, dated absences. (4) The season backtest (14e) decides whether the
full-health state prices the rest of the season better; on the morning of the match (lag 0, posted lines in) the same ordering holds
(all four actual 0.1217 vs live 0.1282, 15/15; trailing-ten 0.1331, worse: at lag 0 the posted line already carries the day's
absences, so a persistence forecast only adds noise on top of it).

### 14d. Step 3, final grid on the position-adjusted dataset (`close_track/fh_grid2.csv`; 25 recipes x 15 seasons, lags 0 and 7; rest +0.005, short -0.031, eliminated -0.19 in every "all four" recipe)
| recipe (a week out, lag 7) | rmse | slope | seasons better than live |
|---|---|---|---|
| all four, beta_abs -0.60, absences added back from the actual lineups (ceiling) | **0.2317** | 1.03 | 15/15 |
| same at -0.48 / -0.75 / -0.30 | 0.2321 / 0.2322 / 0.2338 | 1.03 | 15/15 each |
| absences only at -0.48, actual lineups | 0.2353 | 1.03 | 14/15 |
| all four at -0.48, no xG, actual lineups | 0.2392 | 0.99 | 10/15 |
| **all four at -0.30, netted out and not added back (honest)** | **0.2395** | 1.00 | **15/15** |
| all four at -0.30, absences forecast from the trailing ten games (honest) | 0.2399 | 1.02 | 14/15 |
| all four at -0.48, not added back / trailing ten / last three games | 0.2403 / 0.2404 / 0.2408 | 0.99-1.02 | 12 / 13 / 13 |
| eliminated status only | 0.2407 | 1.02 | 13/15 |
| all four at -0.60, trailing ten / not added back | 0.2409 / 0.2411 | | 13 / 10 |
| rest and short week only | 0.2422 | 1.02 | 12/15 |
| live | 0.2431 | 1.02 | - |
| absences only at -0.48, trailing ten | 0.2437 | 1.02 | 5/15 |
| live without xG | 0.2498 | 0.98 | 1/15 |

- **The full price of an absence is about -0.7 goals per goal of missing value** (fixed point: after netting the plain filter at -0.48 the
  morning residual still loads -0.15 on absences, at -0.60 -0.07, at -0.80 +0.07; the crossing is at -0.69; the plain filter's
  morning rmse is lowest at -0.60: 0.2377 vs 0.2380 / 0.2387 / 0.2456 unnetted). The -0.48 of 14b is the part the morning state had
  not absorbed. Keepers are priced at half the field rate (14b), left as one coefficient for now.
- With the lineups known a week out (never true live) the gain is 0.011 of rmse in 15 of 15 seasons, flat between -0.48 and -0.75.
  Honest (no lineup knowledge), the best netting is lighter, -0.30, because an absence that is netted out of the state and not
  forecast back is a pure miss: 0.2395 (15/15 seasons; 0.2399 with the trailing-ten forecast, 14/15). Netting at the full price
  -0.60 without a forecast is 0.2411 (10/15): still better than live, but the add-back then matters.
- The live model sits between these two rows: it adds absences back from the injury list with return dates (data/ratings/absence_values.csv),
  which knows the long, dated absences (the ones that carry value) and misses the match-day surprises. No injury-list history exists
  before 2026-10-12, so the live gain cannot be backtested exactly; it is bounded by 0.2395 (list knows nothing) and 0.2317 (list
  knows everything) at the right beta, and the 2026 posted lines from here on are the running test (forecast check in every run).
- No-xG rows say the same as 13b: xG stays. Lag 0 (posted lines in) keeps the ordering: all four actual 0.1213 vs live 0.1282,
  15/15; the persistence forecasts are worse than live at lag 0 (the posted line already carries the day's absences).

### 14e. Step 4: the rest-of-season backtest at the frozen pair (`backtest/fh_sim.csv`, `fh_sim2.csv`; rating_sd 0.10 / drift 0.01, dock 0.5, dc -0.05, shade off, current round priced off its line, 87 season-checkpoints, 4000 seasons, paired seeds)
Ratings from the netted filter (posted lines netted with the round's actual absences, as the live posted lines will be with the injury
list); every remaining fixture gets its factors added back: rest and short week from the schedule, eliminated status for clubs
already out at the checkpoint (dock-exempt by the pre-pass, so no double count; in-sim eliminations keep the dock), absences by
`abs_mode` (trailing ten games = honest, actual lineups = ceiling, none).

| recipe (beta_abs) | points log-pmf (seasons better than live) | points rmse | tails (20% honest) | playoffs ll | conference ll | match ll | close rmse |
|---|---|---|---|---|---|---|---|
| live | -3.1486 | 6.007 | 0.219 | 0.2986 | 0.1425 | 1.0125 | 0.3202 |
| all four at -0.48, trailing-ten absences (honest) | **-3.1453 (11/15)** | **5.983 (13/15)** | 0.215 | **0.2980 (10/15)** | **0.1418 (10/15)** | 1.0122 (12/15) | 0.3176 (13/15) |
| all four at -0.48, actual lineups (ceiling, future lineups known) | -3.1518 (4/15) | 6.016 (5/15) | 0.218 | 0.2990 (8/15) | 0.1417 (9/15) | 1.0112 (12/15) | 0.3135 (13/15) |

### 14g. Live effect on today's 200k markets (`what_if.py` asof 2026-10-19, results through Oct 17, 61 fixtures left; archive `outputs/calibration/whatif_fullhealth_2026-10-19.json`; nothing switched on)
Full-health ratings today vs the current blend (goals): Sporting KC +0.09 (the eliminated price comes out of its closes), Minnesota
+0.03, LAFC +0.035, Cincinnati +0.02, New England +0.02, Montréal +0.02; Colorado -0.08 (rested or depleted opponents in its recent
closes), Vancouver -0.03, Seattle -0.03, Charlotte -0.03, St. Louis -0.02; sd of the moves 0.025 at beta -0.30 and 0.027 at -0.60.
Late in the season with a thin absence list (14f) the futures barely move; every pool moving 0.3 points at 200k seasons:
- beta_abs -0.30 (the honest close-tracking optimum): Cup Vancouver 21.9 -> 21.3; West Vancouver 88.8 -> 88.4, Dallas 5.3 -> 5.6;
  Cup finalist Vancouver 40.6 -> 39.9, LAFC 13.5 -> 14.0, Dallas 9.7 -> 10.1, St. Louis 18.4 -> 18.0, Houston 5.9 -> 6.2; playoffs
  Colorado 73.2 -> 72.1, RSL 40.7 -> 41.4, NYCFC 35.1 -> 34.5, San Diego 7.1 -> 7.6, Columbus 27.4 -> 27.9, Minnesota 10.6 -> 11.0,
  Galaxy 58.4 -> 57.9, D.C. 11.8 -> 11.5; top-4 Chicago 55.2 -> 55.7, LAFC 25.4 -> 25.9, San Jose 49.5 -> 49.0, Charlotte 18.7 -> 18.3;
  conference final Vancouver 57.6 -> 56.8, St. Louis 38.6 -> 37.9, LAFC 28.5 -> 29.2, Colorado 5.7 -> 5.2, Charlotte 9.6 -> 9.1;
  semis Colorado 14.8 -> 13.9, Charlotte 31.6 -> 30.6, LAFC 60.8 -> 61.4, Seattle 31.2 -> 30.6.
- beta_abs -0.48: the same list plus Cup Nashville 22.6 -> 22.2, LAFC 5.2 -> 5.6, Vancouver 21.1; Cup finalist Nashville 33.9 -> 33.5.
- beta_abs -0.60 (the full price): as -0.48 plus Cup Miami 18.3 -> 18.6, semis LAFC 62.2, Colorado 13.4, Cincinnati playoffs 74.8 -> 75.1.
- rest, short week and eliminated status only (no absence term): Cup Vancouver 21.9 -> 21.1, Nashville 22.6 -> 22.9, Miami 18.3 -> 17.9;
  playoffs Columbus 27.4 -> 28.5, Colorado 72.5, Galaxy 57.7; most of today's movement is these two terms, not absences.
No pool moves by a full point. The value of the change today is correctness of the state going into next season's build (the
2027 ratings start from the 2026 closes, netted) and the live tracking of each week's lines; its size will be larger whenever a
club carries a long, dated absence of a valuable regular (Messi: 0.45 goals of missing value x 0.6 = 0.27 goals of line).
| all four at -0.30, trailing ten (honest) | -3.1462 (9/15) | 5.990 (13/15) | 0.217 | 0.2984 (9/15) | 0.1426 (9/15) | 1.0123 (11/15) | 0.3176 (13/15) |
| all four at -0.30, not added back | -3.1509 (7/15) | 5.996 (8/15) | 0.217 | 0.2984 (8/15) | 0.1415 (10/15) | 1.0123 (9/15) | 0.3173 (13/15) |
| all four at -0.60, trailing ten | -3.1477 (9/15) | 5.982 (12/15) | 0.215 | 0.2983 (11/15) | 0.1427 (7/15) | 1.0121 (12/15) | 0.3177 (12/15) |
| rest, short week and eliminated only | -3.1464 (9/15) | 6.000 (9/15) | 0.218 | 0.2994 (6/15) | 0.1425 (8/15) | 1.0125 (7/15) | 0.3181 (13/15) |

Readings: no netted recipe loses the season backtest. The honest recipes beat live on expected points (rmse 5.98-5.99 vs 6.01,
12-13 of 15 seasons), on the closes over the rest of the season (13 of 15), and are a wash to slightly better on the position pools
(playoffs 0.2980-0.2984 vs 0.2986, conference tied); the tails move from 21.9% toward 20% (21.5-21.7%). The best season figure is
beta -0.48 with the trailing-ten absences (points log-pmf -3.1453, 11/15; points rmse 5.983, 13/15), -0.30 and -0.60 within noise
of it. The ceiling recipe (future lineups known) is better match by match and worse on points: knowing who plays next week is not
what the points markets need; the full-health state is. The eliminated and rest terms alone give half the points gain and nothing on
the playoffs: the absence netting is doing real work in the state.

### 14h. Proposals (2026-10-19; nothing applied; `what_if.py --alt "x:factors_enabled=true,factor_abs=-0.48"` reproduces any of them)
1. **Full-health ratings on at the regression's price**: `factors_enabled` true, `factor_abs` -0.48, rest +0.005, short week -0.031,
   eliminated -0.19; absences added back from the injury list (absence_values.csv), rest from the schedule, eliminated status for
   clubs already out. Evidence: close a week out 0.2404 honest / 0.2321 with lineups known (vs 0.2431; 13 and 15 of 15 seasons);
   season backtest points log-pmf -3.1453 vs -3.1486 (11/15), points rmse 5.983 vs 6.007 (13/15), playoffs 0.2980 vs 0.2986 (10/15),
   conference 0.1418 vs 0.1425 (10/15), tails 21.5% vs 21.9%. Today (200k): Cup Vancouver 21.9 -> 21.1, Nashville 22.6 -> 22.2, LAFC
   5.2 -> 5.6; West Vancouver 88.8 -> 88.4, Dallas 5.3 -> 5.7; playoffs Colorado 73.2 -> 71.9, RSL 40.7 -> 41.3, NYCFC 35.1 -> 34.6,
   San Diego 7.1 -> 7.7, Minnesota 10.6 -> 11.1; Cup finalist LAFC 13.5 -> 14.2, Vancouver 40.6 -> 39.9, St. Louis 18.4 -> 17.9.
   Recommended: the live list sits between the honest and the ceiling rows, and -0.48 is the best season figure.
2. **The same at -0.30** (the honest close-tracking optimum when nothing is known about next week's lineups: 0.2395, 15/15; season
   backtest -3.1462 / 5.990 / 0.2984, 9-13 of 15). The conservative version of 1; today it moves the same pools by a little less
   (Cup Vancouver 21.3, Nashville unchanged).
3. **The same at -0.60** (the full price of an absence, 14d; best when the lineups are known, 0.2317; honest 0.2411, 10/15; season
   -3.1477 / 5.982 / 0.2983). Only if the injury list is kept sharp (return dates, stale rows cleaned); today as 1 plus Cup Miami
   18.3 -> 18.6.
4. **Maintenance that goes with 1-3**: the 8:52 routine refreshes the ASA minutes and the absence files each morning
   (`fetch_asa_players.py --seasons 2026 --force`, `absences.py build`, `absence_values.py`), so the closes of the last round are
   netted with their actual lineups and the posted lines with today's list; without it the newest closes enter un-netted. Commit the
   two csvs with the run. About 30 seconds of work in the routine.
5. **Injuries tab in goals**: show `value_per96`, regular weight, prob_out, `cost_per_game` and games missed from absence_values.csv
   next to each listed player (the tiers stay as Zac's override; the layer itself stays off, it would double count the netting).
   Display only; moves nothing.
Not proposed: rest, short week and eliminated status alone (half the points gain, playoffs worse in 9 of 15); a separate keeper
coefficient (keepers priced at -0.29 vs field -0.56, 14b; a refinement to test on the yardstick later); absences without the other
three factors (tracking no better than live when forecast honestly). Caveats to know: values are ASA goals added above the position
average, so a famous name can carry little (Müller -0.01 per 96 over the last 365 days; Lozano +0.01) and a few listed regulars
carry a negative value (their absence reads as a small gain); the 2012 season has no ASA data and enters unnetted; playoff closes
carry no absence data.

### 14j. Faster-moving ratings (Zac 2026-10-19: "lets try 3"; `close_track/fast1.csv`, recipes `close_track/recipes/fast1.json`; NOT applied)
Prompted by a 2026 finding: on the season's 447 played games (match-morning ratings without that round's lines, `morning.py` track),
about 30% of a club's average miss over its last 4 closes carried into its next close (slope 0.30, se 0.06; 0.29 before July, 0.30
after; out of sample after July rmse 0.222 -> 0.216), i.e. the ratings looked slow. Tested on the yardstick (15 seasons, every close a
week out, live full-health recipe v the filter made faster):
| recipe | rmse lag 7 | slope | seasons better than live | carry-over of the last-4 miss (15 seasons / 2026) |
|---|---|---|---|---|
| live (q_day 0.03, s 0.25) | **0.2395** | 1.02 | - | +0.05 (se 0.02) / +0.16 |
| s 0.20 (s_posted 0.18) | 0.2399 | 1.00 | 4/15 | -0.01 / +0.10 |
| q_day 0.045 | 0.2409 | 0.99 | 3/15 | -0.06 / +0.05 |
| q_day 0.06 | 0.2436 | 0.97 | 1/15 | -0.13 / -0.02 |
| q_day 0.06, xG 10% | 0.2454 | 0.96 | 0/15 | -0.16 / -0.05 |
| q_day 0.09 / 0.12 | 0.2491 / 0.2533 | 0.95 / 0.93 | 0/15 | -0.21 / -0.24 |
2026 alone (450 closes): q_day 0.045 0.2479, s 0.20 0.2482, q_day 0.06 0.2484 v live 0.2492. Reading: today's speed is the best over
15 seasons; a faster filter overshoots in a normal season (negative carry-over). 2026 is the unusual season where a club's run of
closes kept going (carry-over 0.16 a week out v 0.05 historically): a slightly faster filter would gain 0.001 this season and cost
0.001-0.004 across the record. No change proposed. The same history says per-club hand tweaks at 0.3 x the last-4 miss would usually
overshoot; in 2026 the effect is real in both halves of the season, so a tweak is a judgment call on whether the pattern holds for the
last three weeks, not a measured correction.

### 14k. Sanity checks against outside sources (Zac 2026-10-19: "do 1, 2, 4"; scripts in the session scratchpad, nothing changed in the model)
Rank agreement of our no-hand ratings with: Pinnacle last 4 / 12 closes 0.96 / 0.97, the other books' lines this week (bet365,
DraftKings, FanDuel, ps3838) 0.96, Opta 0.88, season xG 0.85, goal difference 0.79. Polymarket MLS Cup (normalized) has the same top
three; ours is richer on the favourites (Nashville 23.1 v 17.4, Vancouver 20.9 v 17.9, Miami 17.1 v 15.1).
1. **Nashville's Cup price is the seeding, not the rating** (100k paired, `risk.Sim`): live 22.9; without its +0.06 hand 21.2;
   with a neutral home edge in every playoff game 14.4, level with Miami at the same rating (14.3). Nashville has the Shield and the
   East's 1 seed, so it hosts every playoff game including the Cup final: about 7 points of its price. Pinnacle prices playoff games
   with the regular-season home edge (11j: fitted 0.54), so the path value is backed by Pinnacle's own lines; the soft and exchange
   futures (16-18%) price Nashville about like Miami.
2. **Market v stats, 15 seasons** (2013-2025, checkpoints at 60% and 75% of each season's closes; the market = the plain Kalman state
   at the checkpoint; stats = xG rating and season goal difference per game, both rescaled to the market's spread; outcome = the
   rest-of-season results and closes against that market rating; b = the share of the gap that comes true, 0 = market right):
   | gap | later closes move | results move | results v the later close | seasons, results v close same sign |
   |---|---|---|---|---|
   | xG minus market | +0.19 (se 0.02) | +0.02 (se 0.09) | -0.18 (se 0.09) | 3 of 13 positive |
   | goal difference minus market | +0.22 (se 0.02) | +0.45 (se 0.09) | **+0.24 (se 0.09)** | 9 of 13 positive |
   Clubs whose xG sat 0.30+ above or below the market finished the season at their market rating (+0.02 / -0.02 goals a game); clubs
   whose goal difference sat 0.30+ above the market beat it by +0.27 a game, those below by -0.23. The goal-difference signal holds
   with eliminated clubs controlled (+0.23, se 0.09; +0.20 on games with no eliminated club). Reading: late in the season Pinnacle
   follows xG a fifth of the way and the results do not (xG gaps are noise, so Vancouver's xG gap, -0.56 today, is no warning);
   Pinnacle also follows goal difference a fifth of the way but the results follow it about half way, so the close underweights
   season goal difference by about a quarter of the gap. Today's goal-difference gaps (rating basis: plain market state): San Jose
   +0.58, Nashville +0.31, Charlotte +0.29, Dallas +0.13; Philadelphia -0.42, Miami -0.18, Vancouver -0.07. A goal-difference source in
   the blend is a candidate (proposal 1 of the reply that day); not tested on the yardsticks yet, nothing changed.

### 14l. Goal-difference source and xG share (Zac 2026-10-19: "do 1 and 2" of 14k; `close_track/gd1.csv`, recipes `close_track/recipes/gd1.json`; NOT applied)
Live full-health recipe v the same with a goal-difference source (ASA-matched actual goals fed through the xG fit, `xg_goal_mix`,
45-day half-life, rescaled to the market's spread) and other xG shares; 15 seasons, 6266 closes, a week out (lag 7); results =
the same week-out price v the actual score (margin rmse, three-way log-loss at T 3.0).
| recipe (market / xG / goal diff) | close rmse | slope | seasons better (close) | result log-loss | seasons better (result margin) |
|---|---|---|---|---|---|
| 75 / 15 / 10 | **0.2373** | 1.04 | 14/15 | 1.0223 | 10/15 |
| 80 / 15 / 5 | 0.2375 | 1.03 | 14/15 | 1.0221 | 10/15 |
| 80 / 10 / 10 | 0.2376 | 1.03 | 13/15 | 1.0223 | 8/15 |
| live 85 / 15 / 0 | 0.2402 | 1.02 | - | 1.0220 | - |
| 85 / 0 / 15 | 0.2408 | 1.03 | 5/15 | 1.0225 | 6/15 |
| 90 / 10 / 0 | 0.2414 | 1.01 | 3/15 | 1.0222 | 5/15 |
| 100 / 0 / 0 (no xG) | 0.2469 | 0.98 | 0/15 | 1.0226 | 4/15 |
Readings: goal difference added ON TOP of xG tracks the close better by 0.003 (14 of 15 seasons; four times the gain of the xG
25 -> 15 change), results a tie; replacing xG with goal difference, or cutting xG to 10% or 0%, is worse. xG stays at 15%. At lag 0
the extra sources cost a little (the posted line already knows). Today's effect of 75/15/10 on the no-hand ratings is at most 0.05
(Vancouver -0.05, Orlando +0.05, Toronto +0.05, LAFC -0.04, Cincinnati -0.04, Nashville +0.03, St. Louis +0.03; the source is recent,
45-day-weighted goal difference, so San Jose's strong SEASON goal difference of 14k barely shows: -0.10 v market -0.31). The
rest-of-season backtest has not been run on it yet.
Rest-of-season backtest (Zac 2026-10-19 "do all": adopt only if it does not lose; `backtest/gd_sim.csv`, recipes
`backtest/recipes/gd_sim.json`, live full-health recipe at the frozen pair, current round off its line, 87 season-checkpoints,
4000 seasons, paired; `xg_goal_mix` added to backtest_season.py): 75/15/10 v live: match log-loss 1.0120 v 1.0125 (8/15 seasons),
remaining closes 0.3152 v 0.3176 (11/15), points rmse 5.986 v 5.991 (6/15) but **points log-pmf -3.1511 v -3.1477 (5/15), conference
winner 0.1437 v 0.1421 (5/15, z -1.8)**, playoffs 0.2978 v 0.2983 (4/15), Shield tied; 80/15/5 the same picture (conference 0.1433,
5/15). Better match by match, worse on the futures pools: NOT adopted. The knob `xg_goal_mix` (0 = off) is wired into the live
build, risk.py and site_detail.py (`sim.ratings.xg_with_goals`) for a later look.

### 14i. Injury news sources (Zac 2026-10-19: "look for other places to find injury news"; survey of what this container can read)
| Source | What it gives | Status |
|---|---|---|
| **MLS Player Status Report** (mlssoccer.com press release per matchday, e.g. "MLS Player Status Report: Matchday 31 (Saturday, October 17 - Sunday, October 18)", published the day before the round; every club, each player Out or Questionable with the reason; Suspension listed as a reason) | the league's official availability list: 100 players for Matchday 31 (94 out, 6 questionable) | **WIRED** (`scripts/fetch_psr.py`): read through the site's content API `dapi.mlssoccer.com/v2/content/en-us/stories/<slug>` (the list endpoint hides these stories, so the slug is built from the schedule's round dates and the ASA matchday number and probed in the forms MLS uses, 90 candidates, 50 s); merged into injuries.csv (new names at squad tier with out_from = the match date, Questionable = prob_out 0.5; existing rows get the report's status; Zac's tiers and dates never overwritten; since 2026-10-19 evening a reported suspension closes the day after its match, an open
psr row of a covered club that the newest report no longer lists closes at that report's first match date, and a re-listed player
gets a new row); raw under data/optic/raw/psr/ |
| **Transfermarkt** MLS injured players (player, club, injury, "until") | expected return dates (39 rows today, most "until" blank) | WIRED in the same script: fills a blank expected_return only; the site answers 405/502 at times (three retries) |
| OpticOdds `/injuries` (out / gtd / suspended, no dates) | daily, already in the morning pull | kept (prob 0.5 for gtd) |
| sportsgambler.com | the 7:40 routine's feed, dated returns where the site has them | kept |
| ASA minutes (the lineups themselves) | who actually played: the stale-row check in `absence_values.py` | kept; refreshed daily by `weekly.py` |
| Club "Player Availability Report" pages (e.g. sportingkc.com), squawka tracker, ESPN injuries page, Rotowire | club pages repeat the league report; squawka 403 from here; ESPN returns an empty page; Rotowire has no MLS table | not used |
| X / Twitter (beat writers, Tom Bogert) | fastest for breaking news but unreadable from this container (no API access) and not a dated list | not used; Zac can paste a line in chat ("Messi out until Nov 15") and it goes into injuries.csv as a dated row |
Daily order in `weekly.py` (8:30 ET routine): fetch_asa_players (last season once per container, this season forced) -> absences.py build (keeps the
seasons it cannot rebuild, 2026-10-19 night) -> fetch_psr -> absence_values, then the lines and the run.

## 15. The two method PDFs reviewed (2026-10-19 night, Zac: "review the full model and see if adding anything from this pdf is useful", then the Glicko paper; branch claude/loving-noether-4oekoj)
Corey's `docs/futures_sim_method_nfl.pdf` item by item. IN: blend anchored and rescaled; market-implied ratings (as a Kalman filter, 13);
public sanity anchor (Opta); hands on top of the blend, weekly; per-club home edge centred on the league; rest and short week (factors);
eliminated dock with the priced-as-hopeless exemption; drift against the dice's own price, capped, k_real 0; one season-long rating draw
that does not shrink; current round off Pinnacle; locked results; full reruns, seeded, tests; rating history; power devig on complete
pools; match checks (no win-curve mismatch); Poisson + Dixon-Coles; team totals; exact tiebreakers; rounds by date; exact-seed,
finish-above and points-over markets (`price_market.py`). EXCLUDED by Zac: hand-rating sources, futures / win-total implied ratings, the
median across books. NOT IN: (a) a locked-seed dock: tested, no (section 5, `locked_seed.md`); (b) the weekly book comparison of futures:
Pinnacle's guest feed posts no MLS futures (checked 2026-10-19: outrights for the EPL, La Liga, Serie A, Bundesliga, Ligue 1, the UEFA
cups, Libertadores, Nations League, Euro 2028 only) and `futures_odds.csv` has been empty since OpticOdds went; (c) per-club volatility:
see Glicko below; (d) injuries drawn inside the sim: not useful (largest live absence 0.07 goals a game); (e) a history of our own futures
prices: built (section 10, History). Neutral-site edges do not arise in MLS.
Glickman's Glicko (rating + ratings deviation RD; RD grows with time inactive, shrinks with games, sets the update size; uncertainty-
shrunk expected scores; a floor on RD): our filter is the general form Glicko approximates. p0 0.4 = the unrated RD; q_day = c squared per
day (RD rose from about 0.15 to 0.21 over the World Cup break); s = the game noise; the expansion prior = the unrated 1500; the daily q
keeps a floor; the full covariance does what Glicko's opponent-RD weighting does, jointly. Measured: the filter's posterior sd per club is
0.129-0.135 on 2026-10-19 without this round's lines (0.115-0.123 with them), sd across clubs 0.002; at season starts 0.19-0.30 (Feb
2025, San Diego the widest as the expansion side; sd across clubs 0.016). So per-club uncertainty in the sim draw moves nothing this
season; it is a 2027-build candidate (expansion sides, the 14-match transition season), to be set on the rest-of-season backtest (frozen
knob rule). Uncertainty-shrunk match prices: 0.13 per club moves a home-win price about 0.1 point; not worth it. The interval is on the
Ratings tab (95% band).

## 16. Edge-finding framework (2026-10-20, Zac: "transition from hard building out the model to finding edges in the market")
`docs/edge_finding.md` holds the notes on *The Logic of Sports Betting* (copyrighted; the text is not committed). The short
version: the model is a derivative-pricing engine anchored to the strong market (Pinnacle match lines). The edges live in the
weak markets priced off it: MLS futures, which no market maker posts, at soft books and on Kalshi/Polymarket. Bet the
structural inconsistencies (path and seeding value, bracket format, eliminated collapse, stale prices after events), not
opinions, and only once the hold is chopped below zero. Expect one or two edges per market. Track CLV against later prices.
The section 1 rule stands: those prices never enter the model. Using them as the comparison target is proposal 1 there.
Proposals 1-6 were put to Zac 2026-10-20. Proposal 2 (Edges tab) and the book half of proposal 1 are BUILT 2026-10-20 (section 5);
Kalshi/Polymarket dropped on Zac's word (no volume). The rest are not applied.

## 17. Forecasting principles (2026-10-20, Zac: "same with this text")
`docs/forecasting_principles.md` holds notes on *The Signal and the Noise*. The upload was a Bookey summary with chapters cut
short, not the book; points from the full book are marked [book]. The short version: 100k seasons buy precision, not
accuracy. An edge smaller than our own confidence range (Risk tab) is noise. Calibration by market type is the test of
whether a price can be bet. Before betting a disagreement, shrink our fair toward the market by how often our
disagreements have proved right (measured for match lines in 6b, not yet for futures venues). The Kalman filter is the
Bayesian update and the hand review is the hands' update. Hands are the scouts: they stay only if they help against the
closes. Process over results: futures settle once a season, so judge on calibration and CLV. No model change may be sold
on a position. Proposals 7-11 there extend section 16's 1-6; none is applied.

## 18. Bayesian methods (2026-10-20, Zac: "Here")
`docs/bayesian_methods.md` holds notes on Reich & Ghosh, *Bayesian Statistical Methods* (2019). It was read in full by five
parallel readers, one per section, and synthesised; the text is not committed. In the book's terms:
- The filter is the normal-normal posterior, and the pseudo-counts are partial pooling with a fixed m.
- The yardsticks are the right kind: walk-forward log score plus coverage.
- The sim is plain Monte Carlo. SE is √(p(1-p)/S): 2% ±0.03 points at 200k, ±0.10 at 20k. So edges come from the 200k run,
  never from the page's 20k Run.
- "N of 15 seasons" is a sign count: 10/15 is p ≈ 0.15, 12/15 p ≈ 0.02, 15/15 p ≈ 0.00003.

Gaps it names:
- The season draw is independent 0.10 per club where the filter's posterior is correlated and 0.13.
- Every close enters at s = 0.25 whatever its source (checked in sim/kalman.py).
- The 95% band's coverage is unchecked, and there are no posterior predictive checks on season outcomes.
- The bet rule should be log-odds pooling with the venue at a measured weight, flagging only when a lower quantile (≈0.2)
  clears break-even plus fees.

Proposals 12-20 there; none is applied.
