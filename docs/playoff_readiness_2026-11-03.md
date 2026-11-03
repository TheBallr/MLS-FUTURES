# Playoff readiness review, 2026-11-03 (Zac: "refresh and prepare ... anything missing before the playoffs"; nothing changed)

Branch claude/sharp-cerf-oxjusp, from the live branch at 3e8ee34 (run 20261103T153447Z). Read-only audit of what the pipeline does from
Nov 8 (the day after Decision Day) to Dec 18 (MLS Cup), with the state of the data and the model on the day. Section 7 of
docs/model_review_2026-10-27.md has the earlier proposals 13-20, still open.

## 1. State on Nov 3
- Results through Nov 1 (495 of 510); 15 fixtures left, all on Decision Day Nov 7; every one lined by Pinnacle (30 posted rows); captures armed
  (3:50 PM and 6:50 PM ET slots, all 15 games). Closes: one miss all season since Oct 14 (RSL v STL Oct 24, last line before kickoff used).
- East settled: nine clinched (Nashville 1 seed and Shield, Miami, New England, Chicago, Charlotte, Philadelphia, Cincinnati, Columbus, Orlando);
  seeds 2-9 still move on Decision Day (Philadelphia 6 seed 84%, Cincinnati 7 57%, Columbus 8 47%, Orlando 9 60%).
- West: Vancouver 1 seed (100%), Dallas, St. Louis, San Jose, Houston, LAFC in; three places among Portland 77%, RSL 56%, Seattle 55%, Galaxy 46%,
  Colorado 47%, Minnesota 18%.
- Track record (match-morning price v Pinnacle, no lines): last 7 days log-loss ours 0.970 v Pinnacle 0.974 (29 games, we were ahead); 30 days
  1.004 v 0.995; season 1.037 v 1.020 (492 games, 62% of Pinnacle's edge over no-skill). Miss v the close rmse 0.206 / 0.215 / 0.222.
- Decision Day lines v our prices: 6 of 15 are 0.27-0.42 goals apart (PHI v TOR +0.42, CIN v NSH -0.33, ATX v POR +0.29, CHI v CLB +0.28,
  SD v SKC -0.28, ORL v NE -0.27): rotation and motivation that the ratings cannot see; the sim prices all 15 off Pinnacle, so the futures carry
  Pinnacle's view. Forecast check rmse 0.225 (normal 0.11-0.14) is this.
- Hands in force: SEA +0.14, MIA +0.08, RSL +0.06, LAG +0.04, COL -0.05, MTL -0.06; Nashville's +0.11 removed Nov 3. Review: MIA keep, COL keep,
  LAG raise (last 4 +0.32 v us), SEA / RSL / MTL too early. Nashville and Vancouver still on the watchlist (Pinnacle 0.26 above us on NSH in 6 of 8,
  0.16 below us on VAN in 7 of 8).
- Health: tracking 0.264 ok, spread 1.09 (ratings a little flat on 2026, the flatness study of Oct 28 found no global fix), draws ok, one
  input warning (the 34 games with only a market-average close).
- Injury list 240 rows (184 from the MLS report; last report Matchday 34, Oct 30). No bracket absence term today.
- ESPN lists no 2026 playoff events yet (checked Nov 18, 21, Dec 18); Pinnacle lists only the Decision Day matchups. Both are expected: the
  pairings are set on Nov 7.

## 2. The end of the season as simulated (run 20261103T153447Z, 200k seasons)
- Win MLS Cup: Nashville 24.8, Vancouver 19.8, Miami 16.9, Philadelphia 6.9, Chicago 6.5, LAFC 5.1, St. Louis 4.9, Dallas 3.7.
- Reach MLS Cup: Vancouver 37.8, Nashville 35.2, Miami 26.4, LAFC 14.5, St. Louis 13.7, Philadelphia 13.0, Chicago 12.2, Dallas 12.0.
- East bracket, most likely: Wild Card Columbus v Orlando (Columbus 47, Orlando 34, Cincinnati 18 to win it); Round One Nashville (76) over the
  Wild Card winner, Miami (63) over the 7, Philadelphia (54) v New England (30) in 3 v 6, Chicago (70) v Charlotte (30) in 4 v 5; semis Nashville
  55 / Chicago 28 and Miami 48 / Philadelphia 29; conference final Nashville 35, Miami 26, Philadelphia 13, Chicago 12.
- West bracket: Wild Card winner Seattle 26, RSL 24, Portland 18; Round One Vancouver 70, Dallas 50 (Portland 21), LAFC 58 (St. Louis 21),
  St. Louis 37 / San Jose 34 / Houston 28 in 4 v 5; semis Vancouver 53 / St. Louis 15, LAFC 34 / Dallas 29; conference final Vancouver 38,
  LAFC 15, St. Louis 14, Dallas 12.

## 3. What breaks or misleads in the playoffs (verified in code; file:line)
1. **No playoff game is priced off Pinnacle's line.** run_sim.py:161 keeps only `competition == "MLS"` schedule rows, so the posted lines and
   shrink reach league fixtures only; sim/playoffs.py:157 prices every knockout off the ratings (plus the rating draw and drift) and
   pair_totals. The current-round rule (CLAUDE.md 2, posted_line_shrink 1.0) does not hold for the Wild Card, Round One, semis, finals or
   the Cup. A posted playoff line reaches the ratings only as a Kalman measurement (s_posted 0.40). The page worker's `ko` is the same.
2. **Bracket absences are valued as of the Wild Card date only.** run_sim.py:35-37 passes `wild_card` to `LF.playoff_mv` every run; a player
   hurt Nov 25 never counts, one back on Nov 22 costs his club through the Cup; site_data.py:426 (`pf`) the same.
3. **A cancelled Round One game 3 stays "scheduled".** fetch_schedule.py:43 maps every non-final, non-live status to scheduled (ESPN marks the
   unneeded game 3 STATUS_CANCELED days ahead, verified on the 2025 feed); close_schedule.py:16 arms a capture for it, fetch_pinnacle's
   `due` reports it MISSING and exits 1, and it lingers as a club's "next game" (site_data.py:359).
4. **One failed ESPN day blocks every new playoff fixture.** weekly.py:80 runs the full-season fetch_schedule (about 308 requests, no retries)
   every morning from Nov 8 and fetch_schedule.py:73 refuses to save on any failure; fetch_results never adds fixtures. Lost pairings mean
   no captures and no fallback closes for that round.
5. **A hand-added playoff result is filed as a league match.** add_result.py:12 hard-codes competition "MLS" and no winner; merge_results ranks
   manual above ESPN. It would enter the league table (points, wins, gd, h2h) and not the bracket lock.
6. **A level playoff score with no winner shifts the Round One slots.** sim/playoffs.py:131-133 skips the row before `locked_tables` counts
   meetings, so a skipped game 1 locks game 2's winner into slot 0.
7. **The data checks ignore playoff games.** freshness.py:24 and risk.py:384 filter to "MLS": after Decision Day "results", "closes", "lines in
   the next 3 days" and xG report ok whatever is missing.
8. **Absence rows are never cleared by playoff appearances.** absences.py:74 skips knockout games, so absence_values' "has played since" test
   cannot clear a player who returns in the Wild Card or Round One; the 28-day rule (factors.py:118-122) then makes an undated October knock a
   whole-bracket absence from late November.
9. **The Games tab, the morning report and the drawer's next game show no playoff fixtures** (site_data.py:238 skips non-MLS rows; morning.py reads
   those games); the track record and "Results: N new" do include them, scored at the 90-minute price against ESPN's final score.
10. Smaller: fetch_schedule drops the round name (week is None for playoffs; only the date tells the rounds apart); the Bracket tab's round
    dates are hard-coded (site/index.html:625-631), as is risk.py's Nov 18 call-up note and its "coin flip (no extra time)" text (stale since
    Oct 25); run_summary's results_through is MLS-only (the header will say "through Nov 7" all playoffs); fetch_psr names MLS Cup only on an
    exact date match; no test covers real_playoff_results from a results frame, a cancelled game, the skip shift or playoff_mv after Nov 18;
    rest and short week are not applied in knockouts (a Wild Card winner playing game 1 two or three days later: about 0.06 goals).
Works as intended: playoff rows enter the schedule tagged "MLS Cup Playoffs" (ESPN slug without "regular"); results arrive with ESPN's winner
(penalties included); the league table excludes playoff rows everywhere; `real_playoff_results` locks played games symmetrically; captures and
close_fallback cover every competition; Pinnacle's kickoff join tolerates Round One games 1 and 3; playoff closes enter the filter as
measurements (consistent with the backtests and 11j); the FIFA window has no fixtures and the call-up layer is off.

## 4. Proposals (Zac: "do 1, 2, 3" the same day; 1-3 DONE, 4 open, 5 not proposed)
1. Price every lined playoff game off Pinnacle (the current-round rule in the bracket): a `playoff_lines` input keyed on (home, away, meeting)
   from the posted lines of "MLS Cup Playoffs" rows, used in `knockout` in place of the ratings' margin and total, no rating draw; the page
   worker's `ko` the same; the Games tab, the morning report and the drawer get a playoff branch so the lines, our price and the gap are visible.
2. Bracket absences valued from each club's next playoff date (`max(asof, wild_card)` at least), and knockout games counted for "has played
   since" so a returning player clears his row.
3. Schedule and results plumbing: ESPN status mapping (cancelled / postponed), skipped by the capture arming and the MISSING alarm; a
   post-Decision-Day fetch of the playoff window only, with retries, that replaces playoff rows alone; add_result takes a competition and a
   winner; the skipped-level-score placeholder so the slots stay in step; data checks over every competition; results_through over every game.
4. The small stale text and the hard-coded dates (Bracket headers from config, risk.py notes), fetch_psr's MLS Cup date match, tests for the
   locks and the playoff absence date.
5. Not proposed now: rest and short week in the knockouts (0.06 goals at most, Wild Card winner only); call-ups (no fixtures in the window).
