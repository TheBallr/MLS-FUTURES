# Bayesian methods: "Bayesian Statistical Methods" applied to this model

Source: Brian J. Reich and Sujit K. Ghosh, *Bayesian Statistical Methods* (CRC, 2019), uploaded by Zac 2026-10-20. Read in full
(chapters 1-7 and appendices A.1-A.5, every line; bibliography and index skimmed) by five parallel readers, one per section,
each checking its section against the model; synthesised here. The book is copyrighted, so only these notes are committed.
Companion to `docs/edge_finding.md` (where the edges are) and `docs/forecasting_principles.md` (when our number deserves to
be bet). This book is the technical layer under both: how to measure uncertainty honestly, how to shrink, how to choose
between models, and how to turn a posterior into a decision.

## The book in one paragraph
Probability is a statement of belief. Prior x likelihood gives the posterior, and every prediction should come from the
**posterior predictive distribution**, which averages over parameter uncertainty and is always wider than the plug-in.
Conjugate priors act as **pseudo-observations**, and the posterior mean is a precision-weighted average ("shrinkage"):
ridge is a Gaussian prior, LASSO a Laplace prior. **Hierarchical models** pool units through a shared distribution and
estimate how much to pool from the data. Fusing several data sources means giving each its own measurement model (noise
and bias), not a fixed weight. Models are chosen by out-of-sample **log score** (cross-validation, WAIC, DIC), and fit is
checked separately by coverage, PIT and **posterior predictive checks** on statistics the model wasn't fitted to. Monte Carlo
error is sd/√ESS. Decisions minimise posterior expected loss: squared loss gives the mean, check loss gives a quantile,
and a test is accepted when its posterior probability beats the ratio of error costs. Check every method by simulation
against known truths: shrinkage pays when its prior is right and costs coverage when it is wrong.

## What the model already does in the book's terms
| Book concept | Where it is in the model |
|---|---|
| Normal-normal sequential update (2.1.3, 2.1.6) | The Kalman filter is exactly this. p0 0.4 is the prior, s 0.25 the measurement noise, q_day the variance added between dates, off_shrink 0.75 season-level pooling toward the league mean, and the full covariance is Σβ. The Ratings tab's 95% band is its posterior sd. |
| MAP = MLE + log-prior penalty; ridge = Gaussian prior (1.4, 4.2) | Why ridge 0.5 beat least squares (11a), and why the xG ridge and team-totals ridge 0.25 are fixed priors. |
| Pseudo-observations / one-way random effects (2.1.5, 4.4, 6.1) | Club home edges (k = 50 pseudo-games), player values (900 pseudo-minutes toward the club rate), keepers (3000), backup keepers (5000), the expansion prior (-0.25 from 13 historical sides). These are coherent partial pooling **with fixed m**. The book would estimate m = σ²within / τ²between from the replication. k = 50 was grid-picked (held out, 2026-10-12); the pseudo-minutes look hand-set (no calibration file found). |
| Posterior predictive (1.5, 4.2.4) | The sim integrates over uncertainty with one season-long N(0, 0.10) draw per club plus drift. It is set by calibration on the backtest (tails, log-pmf), which is the book's "calibrated Bayes" stance. It differs from the textbook predictive in two ways: the draw is independent across clubs (the filter's posterior is correlated: ratings are identified only as differences, and cross-conference offsets are pinned by few games), and it is 0.10 where the filter's posterior sd is 0.13 (section 15), with tails slightly narrow (22% in the 20% tails). Drift and the dock interact with this, so the gap is a question, not a finding. |
| Walk-forward validation with a proper score (5.1) | The two yardsticks are the book's ideal: a validation set that arrives later in time, scored by log score (points log-pmf, pool log-loss) and coverage/PIT (tails). Rmse against the close is a point score, right for ratings and wrong for variance, which is how the work is split. |
| Monte Carlo (3.2) | The sim is plain independent Monte Carlo (the Dixon-Coles rejection is exact), so ESS = seasons and the SE is √(p(1-p)/S). Paired seeds are common random numbers: Var(Δ) = 2σ²(1-ρ), which is why the page's Run is differenced against its own baseline. |
| Inverse-variance fusion (3.24, A.2) | The principled form of the 85/15 blend. Fusing xG inside the filter was already tested and lost to the blend (13). |
| Bivariate-count GLM (4.3) | Poisson + shared component + Dixon-Coles. Negative binomial and zero-inflation are not needed: the draw rate and 0-0 are closed (11f). |

## What it says we are missing or should check
1. **Monte Carlo error of each price.** Formula, not yet measured. In probability points at 20k / 100k / 200k seasons:
   50% price ±0.35 / 0.16 / 0.11; 20% ±0.28 / 0.13 / 0.09; 5% ±0.15 / 0.07 / 0.05; 2% ±0.10 / 0.04 / 0.03. At 200k it is
   negligible next to venue holds and model error. At the page's 20k Run a 2% longshot carries about 5% relative error
   (about 5 points of EV at +4900), so **edges are read from the 200k run, never from the page's Run.** The 0.3-point
   "moved" rule is about 3 SE unpaired at 200k: sound.
2. **"Better in N of 15 seasons" is a sign count.** Under a coin-flip null: 10 of 15 happens about 15% of the time, 12 of
   15 about 1.8%, 13 of 15 about 0.4%, 15 of 15 about 0.003%. The Kalman filter (15/15) and the full-health state (13/15 on
   points rmse) are solid. xG 25 → 15% (10/15) and Dixon-Coles (a wash) are judgment calls, as the decisions log already
   says. On top of that, the best of 146 recipes is biased upward, and the 15 seasons have been reused for every choice, so
   they are no longer fully out of sample for the choices already made.
3. **Width beside coverage.** The book pairs interval coverage with width; we report tails only. Of two honest pairs, the
   narrower one wins.
4. **Posterior predictive checks on season outcomes.** Draw rate and mean points would pass by construction (dc_rho and the
   ratings were fitted to them). Informative statistics, per season, from the sim at each backtest checkpoint:
   - points spread across the 30 clubs;
   - Shield winner's points and the last club's points;
   - top-rated clubs missing the playoffs;
   - ties at the 9/10 line;
   - the longest win and loss streaks;
   - the home/away points split;
   - draws per club (dispersion, which dc_rho doesn't set).

   Read the Bayesian p-values over 87 checkpoints as a histogram: a pile near 0 or 1 is misfit. 11h's "favourites win 1.2x
   their price" is exactly what a check on the top club's points would test.
5. **Per-source measurement noise for closes.** Every close enters the filter at the same s = 0.25 (checked in
   `sim/kalman.py`: closes carry sd NaN, so the default applies; only openers and xG get their own sd). That includes:
   - 10-minute captures;
   - `pinnacle_lastposted` fallbacks;
   - the 34 market-average closes of 2026;
   - football-data three-way closes converted at the 3.2 total.

   The book's data-fusion case study (6.2) gives each source its own noise and possibly a bias term. Optional: Student-t
   noise, so a close that moved on news the factors missed pulls less.
6. **Empirical-Bayes fit of the filter's knobs.** For a Kalman filter the sum of one-step-ahead predictive log densities is
   the exact marginal likelihood (prequential; a standard result, not stated in this book). q_day, p0, off_shrink and the
   per-source s can be fitted by maximum likelihood instead of by grid. The grid's flat ridge along q/s = 0.12 is what a
   likelihood ridge looks like, so the two should agree. The same run checks whether the standardised prediction errors are
   N(0,1): a calibration of the filter we don't run today.
7. **Coverage of the 95% band.** Never checked. Walk forward: is a club's later close-implied rating inside rating ± 1.96 sd
   93-97% of the time? The "truth" is itself noisy (deconvolve the 0.25 measurement noise).
8. **Simulation study of the pipeline (7.3).** Generate synthetic seasons from known strengths, with closes at noise 0.25 and
   Poisson/Dixon-Coles scores. Run the filter and the sim, then compare the futures prices with prices from the true
   strengths, by price bucket. This separates conversion error (longshot bias in particular) from rating error, which no
   backtest on real data can do.
9. **Uncertainty that is a range of models, not a draw.** Example: the absence price. Its sampling se (0.024) is negligible
   (about 0.002 goals on the largest live absence). The real uncertainty is which price applies, -0.30 to -0.70 (14d). Show
   it as a band; don't draw it in the sim.

## The bet decision in the book's terms (extends forecasting_principles 6 and proposal 7)
- **Combining our fair with the venue** is a two-model average. Three equivalent framings: a mixture prior whose weight
  updates by each side's predictive record (2.1.8); a precision-weighted normal-normal mean, w = σ²venue / (σ²ours + σ²venue)
  (A.2); or model averaging by log score (5.4). Do it on the **log-odds** scale, not as a linear average of probabilities:
  logit p* = w·logit(ours) + (1-w)·logit(venue).
- **The weight must be measured, not picked.** For futures venues there is no record yet, so start sceptical (w 0.5). Until
  venue history exists, test the machinery where data are plentiful: our lag-7 match price pooled with Pinnacle's opener,
  scored on the results and the close (6b's 903 pairs).
- **When to bet (7.1).** Bet when the posterior probability of the bet winning clears break-even after fees. If a wrong bet
  costs more than a missed one (it does, with a hold), use a lower quantile instead of the mean (check loss). In practice:
  flag only when the **τ ≈ 0.2 quantile** of p* clears break-even plus fees. That formalises edge_finding proposal 2's "outside
  our confidence range". While the record is short, the weight's own uncertainty (a beta posterior on "our side was right")
  enters through its lower quantile.
- **Stake size is not in the book** (no Kelly or utility of wealth). Out of scope here, and Zac's domain.

## Proposals (put to Zac 2026-10-20; nothing applied; numbering continues edge_finding 1-6 and forecasting_principles 7-11)
12. **Monte Carlo SE on every price and paired change**: printed in the run line, the Risk tab and the Edges tab. Edges
    marked 200k only. Check: 5 seeds at 20k and 200k, with the spread matching the formula. Display only.
13. **Honest significance on every comparison**: next to "N of 15 seasons", the sign-test p and the paired mean difference
    with a season-block bootstrap SE. For any grid over about 10 recipes, confirm the winner on held-out seasons (pick on one
    set, score on the other). Reporting only.
14. **Season posterior predictive check card** on the Risk tab, with the statistics in item 4 over the 87 backtest
    checkpoints. Display only.
15. **Correlated season rating draw** (all three readers of chapters 1-5 raised it independently): draw the season-long
    ratings from the filter's posterior covariance of the contrasts, scaled by a factor tuned on the backtest, instead of an
    independent 0.10 per club. Matters most for joint pools and same-club combos, season starts, expansion sides and the 2027
    transition season (posterior sd 0.19-0.30 and uneven there). Probably small in 2026 (sd 0.13 ± 0.002). Frozen-knob rule:
    rest-of-season backtest, then Zac's word.
16. **Per-source close noise plus the empirical-Bayes filter fit** (items 5-6): separate s for captures, last-posted lines,
    average closes and old three-way closes, with an optional Student-t variant. Fit by the prequential likelihood, then check
    the standardised errors. Yardstick: close_track lag 7, then the season backtest. Expected gain under 0.002 rmse; mostly
    correctness, and insurance if captures fail.
17. **Estimated pooling strengths**: estimate between-unit spread walk-forward and set k = σ²/τ² for club home edges (with
    turf and altitude as fixed effects) and for player and keeper values. Compare with k 50 / 900 / 3000 on the held-out
    next-ten rmse and the 14d close tracking. Likely a wash; replaces hand constants with measured ones.
18. **Coverage check of the Ratings tab's 95% band** (item 7). Rescale the displayed sd if it misses. Display only.
19. **Synthetic-season simulation study** (item 8): the one test that isolates our longshot conversion error. It matters
    because longshots are where retail futures books are loosest.
20. **Edge rule on the Edges tab**: log-odds pooling of our fair with the venue at a measured weight. Flag only when the
    0.2 quantile clears break-even plus fees, and show P(true probability > break-even) as one number per runner. Merges
    with forecasting_principles proposal 7. Display only.

Not proposed:
- Negative-binomial or zero-inflated goals (Dixon-Coles already fits the draw rate).
- LASSO or horseshoe on the ratings (every club needs a rating; there is no variable selection).
- A full hierarchical Stan goals model: a results-based source, and section 13 shows the market-implied ratings track the close
  better. At most a benchmark, last in line.
- Drawing the absence coefficient inside the sim (item 9: display the range instead).
