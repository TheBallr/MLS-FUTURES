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

## 4. Blockers (current)
- **2026-10-12: every data host is denied by the environment's network policy.** `api.opticodds.com`, `site.api.espn.com`,
  `www.football-data.co.uk`, `guest.api.arcadia.pinnacle.com`, `app.americansocceranalysis.com`, `www.sportsgambler.com`,
  `www.mlssoccer.com`, `fbref.com`, `developer.opticodds.com` all return 403 from the egress proxy; only pypi, npm and GitHub
  pass. Fix: in the environment settings, Network access -> Limited (or Custom) and add those hosts under Allowed domains, or
  choose the broader level. Until then nothing in `data/` can be filled; every script is written and smoke-tested on
  synthetic data (`tests/synth.py`). The OpticOdds harvest (`scripts/harvest_optic.py`) runs first the moment the host opens.

## 5. Decisions log (date, decision, evidence)
- 2026-10-12 Repo laid out to mirror Prem-Futures; engine, standings chain, 2026 bracket, markets, layers, devig, ratings
  fit written and tested (`tests/run_tests.py`: all pass). Starting knobs are the EPL values, marked UNCALIBRATED in
  `config.json`; the frozen-knob rule applies only after the calibration programme runs on MLS history.
- 2026-10-12 Scenario draws use their own RNG stream (seed + 1,000,003) so a points scenario leaves the football-only
  seasons identical (needed for the Scenarios tab's re-ranking and for clean deltas).
- 2026-10-12 Home edge is a knob in the live fit (not re-fitted daily): `market_fit(..., fit_home_edge=False)`. The
  calibration script fits it from the closes and freezes it. Reason: a daily re-fit on a 14-day window is noisy.
- 2026-10-12 Best-of-three with no draws is simulated as the majority of three games (identical to first-to-two).

## 6. Calibration (status: NOT RUN — needs history on file)
Knobs and their provenance live in `config.json` notes. Reports go to `outputs/calibration/`. Order: home edge and total;
half-life; shared goals; rating_sd; drift; shade; longshot rule; season replay; CLV. Then freeze with a date here.

## 7. Scorecard (status: not run)
`scripts/rating_scorecard.py` — numbers to be recorded here before any weight changes.

## 8. Measurements of the layers (status: not run)
Injuries, call-ups: gap to Pinnacle on lined fixtures before/after; on only if the gap falls.

## 9. Automations (status: not created; Phase 4 waits on the network)
Morning news 7:40 ET; Pinnacle lines 8:52 ET (+ capture Routines ten minutes before each kickoff slot in the next eight
days); closes ten minutes before each kickoff; CLV log and forecast check inside every run.

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
