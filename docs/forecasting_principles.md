# Forecasting principles: "The Signal and the Noise" applied to this model

Source: Nate Silver, *The Signal and the Noise* (2012). Zac uploaded a **Bookey summary** on 2026-10-20 and it was read in full:
chapter summaries, quotes, Q&A. It is not the book. Several chapters stop mid-sentence (the "unlock full text" cuts in
chapters 3, 6, 10 and 13). Points marked [book] come from the full book as Claude knows it, not from the upload.
Only these notes are committed. Companion to `docs/edge_finding.md`: Miller says **where** the edges are; Silver says how
to tell whether **our number** deserves to be bet.

## The book's thesis in five lines
1. Data grows faster than forecasting skill. Most failures come from mistaking **precision for accuracy** and refusing to
   state uncertainty.
2. **Calibration** is the test: things priced at 30% should happen 30% of the time.
3. **Overfitting** is the standard error in noisy data. Finding patterns is easy; that is what mediocre gamblers do. The
   work is telling signal from noise.
4. Think **Bayesian**: start from an honest prior, update by the weight of the evidence, and keep updating. Be a **fox**
   (many sources, adaptable, owns its mistakes), not a **hedgehog** (one big idea).
5. Skill is **relative to the competition**. Markets are hard to out-predict, but sometimes the price is wrong, and a
   field full of weak players (the poker bubble) is where a modest edge pays.

## Concepts, each mapped to this model
| # | Concept | What it means here |
|---|---|---|
| 1 | Precision ≠ accuracy (the target-practice analogy) | 100k-200k seasons give prices to a tenth of a point. That is precision. Accuracy is bounded by the ratings and the knobs. The Risk tab's futures-confidence ranges (no recent lines / xG 0 or 30% / spread x1.06 / +0.10 per club) measure the gap. **An edge smaller than our own confidence range is noise, however many decimals it has.** |
| 2 | Risk v uncertainty | The sim prices *risk*: the dice, the season-long rating draw (rating_sd 0.10), drift, the dock. *Uncertainty* is what the sim cannot draw: is the model's structure right, is 2026 unusual (14j: carry-over 0.16 v 0.05 historically), are the hands right, does the bracket rule hold. The Risk tab's ranges are the only uncertainty measure on the page. Keep that distinction when sizing a disagreement with a market. |
| 3 | Calibration | Already the core of the variance work: PIT tails (20% honest; 22.0% at the live pair, 13), longshot ratios (0.81x at 2-5% in the conference pools), per-pool log-loss in the season backtest. It has never been shown in one place by market type, and it is what decides whether a 6% price of ours can be trusted against a 3% price on Polymarket. |
| 4 | Overfitting; "finding patterns is easy" | We test many recipes (146 in 11a, 67 Kalman pairs, 25 full-health recipes). Picking the best of many inflates its score. The defences in place are the right ones: 15 seasons, walk-forward, "better in N of 15", held-out seasons, a wash means no change, and Zac's word for every adoption. Same test as Miller's trend v angle: a mechanism, one direction, a smooth glide. Examples on file: the fading ridge (fixes one score, loses the rest: rejected), the goal-difference source (better on closes, worse on futures pools: rejected, 14l), 2026's carry-over (a season's pattern, not a law: no change, 14j). |
| 5 | Bayes's theorem | The Kalman filter *is* the Bayesian update: a prior strength and its variance (p0 0.4, off-season reversion, expansion prior -0.25), each close a measurement weighted by its noise, the posterior sd shown as the Ratings tab's 95% band. A hand adjustment is a judgment prior. The morning report's hand review (judged only on closes after the hand was set) is its update. |
| 6 | Bayes applied to an edge | Before betting a disagreement, the prior that the market is right is high. Silver's "markets aren't easy to out-predict", Miller's picked-over effect and our own match record (58% of Pinnacle's edge) all say so. The bet-sized number is therefore not our fair but our fair **shrunk toward the market** by how much our disagreements have historically been right. For match lines this is measured (6b: where we disagreed with Pinnacle's opener by 0.15+, the close moved our way 67%). For futures venues it is not measured yet (proposal 1). |
| 7 | Fox v hedgehog; scouts + stats | The ratings are a fox: market (Kalman on Pinnacle) + xG 15% + factors (absences, rest, eliminated), with Opta as an independent check, each weight set on the yardstick. The scouts are Zac's hands and the injury/news layer. In Silver's weather chapter, human forecasters improve the computer by 25% on rain and 10% on temperature, but they can also make it worse. So the hand review must keep scoring hands against the closes, and a hand that doesn't help gets dropped. The hedgehog risk here is one big story ("Nashville's path is mispriced everywhere"): check it against every source before backing it heavily. |
| 8 | Relative skill; the poker bubble | Our edge is not against the truth. It is against the venue's price. Against Pinnacle's match lines we are a 95% forecaster at a 99% table. Against thinly traded MLS futures on exchanges and soft books we may be the better player at a soft table. This is Silver's version of Miller's weak-market rule: play where the competition isn't trying to be accurate. |
| 9 | Markets are sometimes wrong; herding and bubbles | Don't presume the venue price is right (that's why we compare at all). Don't presume it is wrong either: an exchange price moved by many independent traders carries information, a price moved by one stale book or by herding on a popular club carries little. [book] The favourite-longshot bias in betting and prediction markets is a known herding pattern. Test it on the venues before relying on it. |
| 10 | Process over results | Futures settle once a season, so results can't tell a good forecaster from a lucky one for years. Judge by the process: calibration, CLV against later prices (edge_finding 10), and whether each bet's stated reason held. |
| 11 | Correlation ≠ causation | Every factor in the model has a mechanism and was measured with the confounders alongside (14b regresses absences, rest, short week and eliminated status together). Any new angle needs the same before it reaches Zac. |
| 12 | Unknown unknowns; power laws; imagine the implausible | MLS is a high-parity league (11c: per-season tails 0.09 to 0.31; LAFC top-rated in July 2021 and missed the playoffs). Selling a tail cheaply, such as laying a heavy Anyone-But or a 95% playoff price, is where the unknowns bite: a format quirk (PK Wild Card, coin-flip simplification of a level semi), a suspension wave, a schedule change (the 2027 calendar), a key injury after the bet. Before laying a heavy price, list what isn't in the sim. |
| 13 | Forecasting's original sin: putting anything before accuracy | Once Zac holds futures positions there's a conflict: a model change that flatters a position is tempting. The bar for any change stays the yardstick and Zac's word, and every proposal should say which positions it moves. Our method_log and the "say how much it moves" rule already make this visible. |
| 14 | Group forecasts beat individuals when independent | Aggregating independent sources is why the blend beats market-only (13b) and why Opta is shown but never weighted (it would no longer be an independent check). Several venues' prices for the same future, if independent, form a consensus worth showing next to ours. One venue copying another adds nothing. |
| 15 | Say the uncertainty out loud; the worst failure is making no forecast | The page already shows ranges, the 95% band and the Risk tab. Edges should carry their range too. Silence ("not enough data") is not an answer: give the number and the band. |

## Proposals (put to Zac 2026-10-20; nothing applied; these extend edge_finding.md's 1-6)
7. **Shrunk edge for bet decisions**: on the Edges tab (edge_finding proposal 2), show the edge after shrinking our fair toward
   the venue price by a measured weight. Start conservative (half), then set the weight from history: how often the venue's
   later prices moved toward our fair when we disagreed. UNVERIFIED: whether Kalshi/Polymarket expose price history for
   past MLS markets. Display only; the model is untouched.
8. **Calibration card on the Risk tab**: reliability by market type (Conf 1st, Playoffs, Semi, Final, Win conf, Cup) in
   price buckets, from the 15-season backtest at the live configuration, with the 2026 archived runs as they settle.
   Display only.
9. **State the test before running it**: every proposal names its yardstick, threshold and seasons-won bar before the run,
   recorded in the proposal text, so a grid can't be read after the fact.
10. **Position-aware proposals**: once a futures bet log exists (edge_finding proposal 3), every proposed model change lists
    the positions it moves and by how much.
11. **Tail checklist before laying heavy prices**: for any bet at 85%+ (or an Anyone-But), the Edges tab lists what isn't in
    the sim: format simplifications, suspensions, the calendar, open injury risk.
