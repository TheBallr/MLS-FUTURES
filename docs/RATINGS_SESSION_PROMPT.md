# MLS Futures — Ratings session: get the ratings right for predicting the rest of the season

You are picking up the MLS Futures model for Zac (Sierra Advisory LLC). Zac does not code: everything goes through chat, results go into the repo and onto the private site. Lead with the answer, keep replies short, flag uncertainty first. No gambling caveats, no definitions of EV/CLV/devig/hold, no risk lectures.

## 0. Setup (do this first)
- Repo: `theballr/mls-futures`. **All existing work is on branch `claude/tender-knuth-7t40rv`.** Start from that branch's head, not `main` (`main` is an empty README). Push to whatever branch this session is given.
- Read in this order: `CLAUDE.md` (decisions, measurements, rules), `PLAN.md` (method), `config.json` (knobs), `sim/ratings.py`, `scripts/refresh_ratings.py`, `scripts/rating_scorecard.py`, `scripts/calib_replay.py`, `scripts/calib_rating_sd.py`.
- **The north star is the method PDF** `docs/futures_sim_method_nfl.pdf`, committed on branch `claude/awesome-edison-nr0r68`. Get it with `git fetch origin claude/awesome-edison-nr0r68 && git show origin/claude/awesome-edison-nr0r68:docs/futures_sim_method_nfl.pdf > docs/futures_sim_method_nfl.pdf`. Read the whole thing before changing anything. It was written for the NFL and the Premier League. Translate it to MLS: goals not points, Poisson match model, 34-game season, two conferences, playoffs.
- `OPTIC_API_KEY` must come from the environment and never be committed. Run `python3 scripts/check_secrets.py` before every push.

## 1. The goal (Zac's words, settled; do not re-argue)
"Follow the full PDF method. I don't want all these little adjustments that just make the model's stats better but taint our actual view of predicting in the long term. The goal is to accurately predict the rest of the season."

What that means in practice:
1. **New yardstick for ratings: predicting the rest of the season**, not the next match or the next close. Distance from Pinnacle's next close (the current yardstick in `CLAUDE.md` section 1) becomes a secondary diagnostic. Record this change in `CLAUDE.md` with today's date.
2. **The PDF method is the default. Every deviation from it must be removed or justified.** A deviation stays only if it wins clearly and consistently on the rest-of-season backtest (most seasons, not one), and Zac approves it. A small gain on next-ten-closes RMSE is not a justification.
3. **Out of scope by Zac's decision, never to be added:** hand ratings, and any futures prices (Pinnacle or any other book) as a rating source or calibration target. These are the only parts of the PDF not used: MLS futures markets are unreliable. Everything else in the PDF applies.

## 2. Ratings structure required (from the PDF)
- A rating is a club's expected goal margin against a league-average side on a neutral pitch, centred at zero.
- **Source A, backbone: market-implied ratings from Pinnacle closing lines.** One equation per match: implied margin = R_home − R_away + home edge. Stack them, add a sum-to-zero row, solve by least squares. This exists (`market_fit` in `sim/ratings.py`).
- **Source B: a public predictive model's ratings** as the sanity anchor and second blend source. Choosing it is task 3.
- **Blend per the PDF:** anchor each source to mean zero; rescale any off-scale source so its SD across teams matches the market's; take the weighted average; re-anchor to zero. **Compare the blend's spread to the market's spread every run.** A flatter blend quietly favours bad teams and fades good ones.
- Human-style overrides (not hand ratings): the existing `adjustments.csv` stays empty unless Zac says otherwise. The blend is never edited by hand.

## 3. Task A — find the right public model
Current state: the only second source is ASA match xG, which we fit into ratings ourselves (`xg_fit`, 25% weight, xG on file only 2024–2026). It is not a published model, and it disagrees sharply with the market on several clubs. As of Oct 12: Vancouver market +0.89 vs xG +0.36, LAFC +0.42 vs +0.02, SKC −0.71 vs −0.21, Columbus +0.03 vs +0.34, Austin −0.48 vs −0.97.

1. **Survey the candidates and verify each one live** (state plainly what you could and could not reach). Starting list:
   - ASA xG and ASA goals added (g+), with team-level history back to 2013 if the API serves it.
   - Opta / The Analyst Power Rankings.
   - Massey ratings (MLS).
   - Any public Elo or SPI-style MLS rating that still publishes. FiveThirtyEight SPI stopped in 2023; ClubElo does not cover MLS.
   - An Elo or goals-based rating computed from results, as a transparent public-method fallback.
2. **For each, record:** is it predictive (built to forecast) or descriptive (a power ranking); update cadence; all 30 clubs covered; **can past values be recovered as of past dates** (needed for backtesting; a source with no history can only be judged going forward, so say so); licence or access problems; how it maps to the goals scale.
3. **Backtest each available candidate** on the rest-of-season yardstick (section 5), alone and blended with the market at a few weights (e.g. 100/0, 75/25, 50/50). Use only data that existed at each checkpoint.
4. **Recommend one public model** (or say none beats market-only), with the numbers, in plain words.

## 4. Task B — make the market-derived ratings make sense for simulating the rest of the season
Audit every step of the market fit against the PDF. Measure each item on the rest-of-season backtest, not on next-close RMSE.

1. **Shrinkage toward zero (`ridge_lambda` 0.5), not in the PDF and never calibrated.** Measured Oct 12: market-rating SD is 0.349 with the ridge and 0.380 without (8% flatter); fit error is 0.211 vs 0.207. The blend with xG then drops to 0.331, about 13% flatter than what Pinnacle implies. PDF default is no ridge. Test 0 vs current. Use the smallest value that keeps the solve stable (expansion clubs with few closes are handled by the expansion prior, not the ridge).
2. **Half-life (28 days),** chosen on next-ten-closes RMSE. Re-test on the rest-of-season yardstick (e.g. 14 / 28 / 45 / 60 / 90). The PDF says the market source should "move freely", but a rating used for ten weeks ahead may want a longer memory than one used for next weekend. Let the data decide.
3. **Blend spread vs market spread.** Measure every run; if the blend is flatter, test rescaling the blend back to the market's spread.
4. **Fit target.** Check that the conversion from handicap + total (or three-way) to expected margin is unbiased: mean residual by line bucket, and favourites vs underdogs.
5. **Prior seasons and the offseason.** Check how much weight last season's closes carry early in a season, and whether start-of-season ratings are sensible (roster turnover, expansion sides).
6. **Per-club home edges** are in the PDF (per-team, scaled to the league average). Keep them; only confirm the league average still matches what the market prices.
7. **Posted-line shrink (55% Pinnacle for fixtures with a fresh line).** This is the PDF's "current round off the market" in a modified form; the PDF prices the current round fully off the market. Report the deviation; don't change it in this session unless Zac says so.

## 5. The yardstick: rest-of-season backtest (the PDF's season-level backtest)
- Seasons: every season with Pinnacle closes on file (2012–2026; `data/history/`). Checkpoints: the existing seven per season in `calib_replay.py`, or similar.
- At each checkpoint: build ratings using only closes (and public-model values) dated before the checkpoint, lock real results to date, simulate the rest of the season with the current engine and frozen knobs, and score:
  1. **Final points per club:** log-loss of the actual total under the simulated distribution, and RMSE of expected points.
  2. **Tail calibration:** the share of real final points landing in the sim's 10% tails on each side. About 20% combined is honest; more means overconfident, less means too wide.
  3. **Remaining-match results:** log-loss of H/D/A over all matches after the checkpoint.
  4. **Final positions:** conference seed and playoff qualification log-loss.
- Report by season and pooled. **A change wins only if it improves the pooled score and wins in most seasons.** Record the next-close RMSE beside it as a diagnostic only.
- Rating uncertainty and drift are calibrated as a pair on this same backtest (PDF). If the ratings change materially, especially their spread, `rating_sd` may no longer be right. Re-run `calib_rating_sd.py` on the new ratings and **propose** the re-set to Zac with the numbers. Never change a frozen knob without his word.

## 6. Deliverables
1. `outputs/calibration/ratings_review.md`: the public-model survey table, each backtest table, the audit of every market-fit step, and a **full list of every place the current model deviates from the PDF** (ratings, match model, uncertainty, drift, weekly routine, counting). Fix only ratings items in this session; list the rest for later.
2. A start of the PDF's **rating history**: one row per team per run (blended rating plus each source), so stale sources and moving teams are visible.
3. **Numbered proposals** in the model's own terms so Zac can reply "do 1, 3". Example: "1. ridge 0.5 → 0: rest-of-season points log-loss −2.583 → −2.571, wins 11 of 15 seasons; Nashville MLS Cup 17.0% → 17.6%, Vancouver 22.5% → 23.4%". Every proposal that moves probabilities says by how much, in plain words.
4. After Zac approves: implement, run `python3 tests/run_tests.py`, full rerun (`scripts/run_sim.py`), rebuild and check the site (`site_data.py`, `build_site.py`, `check_site.py`), republish to the existing site URL in `CLAUDE.md` section 10, and record the decision with its evidence and date in `CLAUDE.md`.

## 7. Rules carried over (from CLAUDE.md, still binding)
- Never change a team rating, a calibrated or frozen knob, or a source weight unprompted. Analysis, backtests and reports are free; switching anything on needs Zac's word.
- Real results never feed drift; posted lines never enter the ratings fit.
- Full rerun every time; same seed and inputs give identical output; tests after any engine change.
- Keep plumbing changes and model changes separate in commits and notes.
- Commit after every piece of work with a clear message; archive runs under `outputs/runs/<stamp>/`; update `CLAUDE.md` as you go, not at the end.
- No standing requests at the end of replies.
