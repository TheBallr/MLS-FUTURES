# Edge finding: "The Logic of Sports Betting" applied to this model

Source: Ed Miller and Matthew Davidow, *The Logic of Sports Betting* (2019), uploaded by Zac 2026-10-20 and read in full.
The book is copyrighted, so only these notes are committed, not the text. Purpose (Zac, 2026-10-20): move from building the
model to finding edges in the market. This file is standing context for every session. Proposals at the end need Zac's word.

## The book's thesis in five lines
1. Betting is a multiplayer game. Every price you see has been picked over by the market maker's sharp customers. Major
   markets after the frenzy are efficient, and an opinion bet into a 4-5% hold with no structural reason loses.
2. Lines come from a few **market makers** (price discovery: take a bet, move the line, weight sharp accounts). **Retail**
   books copy the major markets and peg to them, but they open **derivatives, props, multiway markets and futures** cheaply
   (charts, rules of thumb, a guess) and rarely reprice them properly as the strong markets or the news move.
3. The edge is not out-predicting the strong market. It is **deriving a fair price for a weak market from the strong one**
   and betting the logical inconsistencies ("attack surface").
4. **Chop the hold**: start from the book's hold, and cut it with best price across books (synthetic markets), related-market
   conversions, steam, angles, a model and judgment. Bet once it is below zero. Never play hero into a full hold.
5. Every winning bet rests on **more information** or **better use of the same information**. If you can't name which one a
   bet rests on, and who is wrong on the other side, it isn't a bet.

## Concepts, each mapped to this model
| # | Book concept | What it means here |
|---|---|---|
| 1 | Picked-over effect; strong markets get respect | Pinnacle's MLS match closes are the strong market. We do not try to beat them: we track them (section 1 yardstick). Measured 2026-10-19: results log-loss ours 1.041 v Pinnacle 1.022 v no-skill 1.067. Our ratings alone get 58% of Pinnacle's edge. **Match games are not bet** (standing rule); the book agrees. |
| 2 | Market maker v retail | Pinnacle is the MLS match-line market maker we anchor to. **No market maker posts MLS futures** (Pinnacle's guest feed has none, checked 2026-10-19). So every MLS futures price (soft books, Kalshi, Polymarket) is retail-made or exchange-made, and none of it is hammered into place. That makes futures a weak market by the book's own tests: no market maker, low limits, a US-only league, thin injury information (the MLS PSR is the only official list). |
| 3 | Derivatives priced off the strong market | **Our whole sim is the derivative engine**: Pinnacle lines → full-health Kalman ratings → the real schedule, tiebreakers, bracket, dock, Dixon-Coles → 100k+ seasons → fair price for every futures market. Its job is to convert, and the book's warning applies: a conversion that is 3% off kills the edge. Our conversion error is measured (Risk tab futures-confidence ranges; longshot ratio 0.81x at 2-5% in the conference pools; 14e backtest). |
| 4 | Multiway markets and futures: hold 10-30%, but hard to price and maintain | Books price the popular clubs carefully and fill in the back of the curve with a lazy distribution. After results or one-sided action they reprice only part of the curve. Reframe each runner as a two-way market (Club X v Anyone-But-X). **Expect one or two good bets per market, not fifteen.** If the screen shows fifteen, suspect the model before the market. |
| 5 | Break-even percentages, not American odds | Compare fair probability to the price's break-even. Devig only complete pools (power method, standing rule) and report each source's pool hold. Edges are in probability points and EV %, never in "cents". |
| 6 | Synthetic zero-hold markets | Kalshi and Polymarket contracts are natively two-sided (yes/no) with tight spreads, so the hold can be close to zero. That is the book's "bet your ideas into zero hold" case, and the idea is our fair price. Best yes across sources against best no across sources gives the synthetic hold per runner. Exchange fees count as hold. |
| 7 | Angles: predictable, quantifiable, unaccounted for in the line; a realistic reason, one direction, and it **glides** (shrinks smoothly as the condition loosens) | Our measured factors pass all three tests on Pinnacle's own lines: eliminated collapse (-0.36 v the ratings, 11g), absences (-0.48 per goal of missing value, 14b-14d), rest and short week (13, 14b), Dixon-Coles draws (11f), playoff home edge (11j). A retail futures book running a power-rating table is unlikely to carry them. Use the glide test before taking any new idea to Zac. Example: 14j's "last-4 miss carries over" is 0.05 historically and 0.16 only in 2026, so it is a trend, not an angle, and that is why hands stay judgment calls. |
| 8 | Structural mispricing beats opinion | The clearest candidate on file is **playoff path value**: Nashville's Cup price is about 7 points of seeding and home edge (14k: 22.9 v 14.4 at neutral venues), Pinnacle prices playoff games at the regular-season home edge (11j), and soft/exchange futures price Nashville like Miami (16-18%). It is predictable, quantifiable and arguably unaccounted for, which is exactly the book's shape. Other bracket structure books likely flatten: the Wild Card on PKs with no extra time, the best-of-three Round One with every game decided, the higher seed hosting games 1 and 3, the Cup hosted by the better record. |
| 9 | Correlated parlays | Futures on one club are correlated (Seed 1 ↔ Shield ↔ home path ↔ Win conf ↔ Cup; Win conf → Cup finalist). A venue that prices a same-club combo as independent legs is offering an edge. The sim holds the joint distribution, so any combo can be priced exactly. |
| 10 | Market agreement / resistance; CLV; "half the hold" | These only apply where a liquid market exists. For futures the useful feedback is the same venue's later price and our own later fair. CLV of at least half the hold over hundreds of bets is a good sign. Resistance (the price moving away from us) is a red flag: stop adding and find what the model missed. Never average down into resistance. |
| 11 | Timing: virgin lines, slow repricing, graveyard shifts | MLS futures go stale after **structural events**: a clinch, an elimination, a seed lock, a star absence (PSR), a playoff result, Decision Day. The model reruns every morning at 8:30 ET, so the window is the morning after the event, before the books catch up. |
| 12 | Every bet has a named reason | For a futures bet the reason is usually "better use of information": a book's back-of-curve price, a missed path or format effect, a stale price after an event. Write the reason in the bet log. |
| 13 | How do I know I'm winning | Futures settle once a season, so results say almost nothing for years. Track bets and CLV against later prices. Point to the opponent's mistake for each bet. |
| 14 | Marketing money: boosts, free bets, deposit bonuses | Zac's ops domain. Two rules from the book: put a free bet (stake not returned) on the longest price with an edge, because value rises with the odds; and bet a boosted price to the maximum. A boosted MLS future checked against our fair is a quick screen. |
| 15 | Delays, limits, account curation | Retail books limit winners and hold bets on a delay, and the bets they refuse are the best ones. Exchanges (Kalshi, Polymarket) don't curate accounts but have fees and finite depth. Count both as hold. |

Not applicable to us: in-play betting, player props (except Top Goalscorer, which we don't model), parlay cards, scalping
scripts.

## How the standing rules read in this light
- Section 1 rule kept: **Kalshi, Polymarket and soft-book prices never enter the model** (no ratings, no sim input). The book
  says they shouldn't: they are the weak markets being attacked, not information about the strong one. They can be the
  *comparison target*, which section 1 currently reserves to Pinnacle. Changing that is proposal 1 below and Zac's call.
- Pinnacle stays the only match-line source. The book's whole method depends on anchoring to the strongest market.
- The frozen variance pair and the dock matter more now: they decide how wide our futures are, and an edge on a 3% longshot
  is mostly a statement about rating_sd and drift. Before betting a long price, check the Risk tab's confidence range.
- "Futures edges are Zac's, by hand, from the site" stays. The site should hand him the short list, the reasons and the
  thresholds. It should not place anything.

## Proposals (put to Zac 2026-10-20; nothing applied)
1. **Futures price snapshots from the weak markets** (comparison only, never a model input): Kalshi and Polymarket MLS
   futures (Cup, conference, Shield, and whatever else is listed), fetched in the 8:30 routine to
   `data/market/futures_<source>.csv` with bid/ask and depth. Soft-book prices only where a keyless feed exists, or pasted
   by Zac. UNVERIFIED: that both public APIs answer from this container and list MLS markets; to check first.
2. **Edges tab**: per market and club: our fair probability and confidence range (Risk tab), best yes and best no with
   venue, break-even after fees, edge in points and EV %, each source's pool hold, the Anyone-But view. Flag only when the
   edge clears the hold AND lies outside our confidence range; at most a few per market (the book's sanity check).
3. **Futures bet log and CLV**: Zac's bets (venue, price, stake, reason), marked every morning against the venue's price and
   our fair; CLV judged against half the hold.
4. **Correlated combos**: price same-club combos from the sim's joint distribution (Seed 1 + Win conf, Win conf + Cup) for
   venues that allow them.
5. **Event alerts in the morning report**: after a structural event, list the futures whose fair moved 2+ points so stale
   prices can be checked first.
6. **Angle register**: each model factor scored on the three tests (predictable, quantifiable, unaccounted for at the
   futures venues) and the glide test, starting with playoff path value, the eliminated collapse and the bracket format
   (PK Wild Card, best-of-three).
