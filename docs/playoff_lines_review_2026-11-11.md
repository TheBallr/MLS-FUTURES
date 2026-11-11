# Playoff lines v the model, 2026-11-11 (run 20261111T172702Z; nothing changed)

Zac: "review the model in its entirety, then look at the upcoming games ... where we are obviously off and what needs to change".

## The eight posted lines (home margin, goals; ours = ratings without the lines)
| game | ours | Pinnacle | gap | note |
|---|---|---|---|---|
| ORL v CIN (WC, Nov 19) | -0.01 | +0.03 | -0.04 | |
| SEA v RSL (WC, Nov 19) | +0.64 | +0.49 | +0.15 | SEA hand +0.14, RSL hand +0.12 |
| NE v PHI (G1, Nov 21) | -0.37 | -0.35 | -0.02 | |
| DAL v POR (G1, Nov 21) | +0.44 | +0.59 | -0.15 | Dallas: market +0.03, xG +0.36, Opta +0.36 |
| MIA v CLB (G1, Nov 21) | +1.15 | +0.79 | +0.36 | the one outlier |
| CHI v CLT (G1, Nov 22) | +1.05 | +1.11 | -0.06 | |
| STL v LAFC (G1, Nov 23) | +0.25 | +0.02 | +0.22 | |
| SJ v HOU (G1, Nov 24) | +0.36 | +0.33 | +0.03 | |
rmse 0.169, bias +0.06 (normal a week out 0.24). Six of eight inside 0.15. These are openers 8-13 days out (opener v close 0.26).

## MIA v CLB
Pinnacle's closes on Miami implied +0.70 to +1.05 in every one of its last seven games (Decision Day v CLT +1.05); the Game 1 opener
implies +0.44 with Columbus at our rating, or Columbus +0.39 with Miami at ours (its closes: +0.01 to +0.24). No absence on file
explains it: Messi played Nov 1 and Nov 7, Allende and Silvetti have been out since Oct 13 (in the state), the Nov 6 report adds
nobody of value, a web search on Nov 11 found no Miami or Columbus team news. Columbus has won five straight (three away at playoff
clubs) and beat Miami 2-1 in September. Unexplained; one opener. Game 1 is priced off the line either way.

## Finding 1: games 2 and 3 of a series ignore the game 1 line (logic)
The bracket prices game 1 off Pinnacle and games 2-3 off the ratings; the filter absorbs about a quarter of the game 1 gap
(MIA v CLB +1.15 -> +1.06 at Miami for game 3 while Pinnacle says +0.79 for the same game at the same ground).
`scripts/series_carry.py` (`outputs/calibration/series_carry.md`): for pairs that met twice or more in one playoffs, the share of
the game 1 close's gap to the ratings still in the later games' closes is 0.83 (se 0.09) in the best-of-three era (36 later games
2023-2025; later-close rmse 0.298 off the ratings, 0.159 off the game 1 line), 0.80 (se 0.08) over all 78. Game 1's result does not
move the later line (+0.000, se 0.021). Caveat: measured on game 1 closes, with the retired least-squares ratings as the base.
What-if (100k paired, games 2-3 priced at ratings + 0.8 x the game 1 gap; a control with games 2-3 as lines at the ratings price
moves nothing): conf semi Miami 69.5 -> 66.0, Columbus 30.5 -> 34.0, LAFC 55.6 -> 58.3, St. Louis 44.4 -> 41.7, Dallas 56.7 -> 58.3;
conf final Miami 44.6 -> 42.5, LAFC 31.8 -> 33.1; Reach MLS Cup Miami 22.5 -> 21.3; Cup Miami 14.0 -> 13.3.

## Finding 2: Decision Day closes of the two locked 1 seeds are in the ratings as ordinary closes
CIN v NSH (Nashville implied +0.66 v +0.81 to +1.07 before) and MTL v VAN (Vancouver +0.31 v +0.44 to +0.78). Without those two
closes: Vancouver +0.063, Nashville +0.026 (it already carries a +0.05 hand for this), Montréal -0.064, Cincinnati -0.028. What-if
(100k): Cup Vancouver 17.6 -> 19.0, Nashville 27.5 -> 28.1, Miami 14.0 -> 13.5; Reach MLS Cup Vancouver 34.9 -> 36.9. History does
not back a rule (`locked_seed.md`: close minus ratings +0.06 for a locked top seed, n 25), so this is a hand, not a model change.
Vancouver's slide is also real before that: Nov 1 v SEA implied +0.44 with the seed still open.

## Checked, no change indicated
- Home edge and playoff strength: Pinnacle prices playoff games as the regular-season ratings imply (11j).
- Injury list: largest bracket absences LAFC 0.10 (Lloris, Long), St. Louis 0.11 (Holse), all undated and short, so not in the bracket;
  no report between Nov 6 and the Wild Card report. The 14-17 day break returns players the list cannot see.
- FIFA window Nov 9-17: only the two Wild Card games follow it directly and both are priced off their lines.
- Seattle: the hand review says raise (+0.18), the line says lower (SEA v RSL +0.15 our way). Left to Zac (proposal 3).
- xG share: Miami market +0.81 v xG +0.19 (-0.09 on the rating), Houston -0.07, Seattle -0.10; Dallas +0.05 the other way.

## Proposals (none applied)
1. Series carry: price games 2 and 3 of a Round One series at the ratings price plus 0.8 x the game 1 line's gap (mirrored for
   game 2), from the newest game 1 line, then its close. Engine + page worker + test. Moves: above.
2. Vancouver hand +0.06 (the Decision Day close taken out, as Nashville's +0.05). Cup Vancouver about +1.4.
3. Seattle hand +0.14 -> +0.07 (halves the SEA v RSL gap to the line; matters only if Seattle wins the Wild Card).
4. Leave Miami at 0 hand and re-read MIA v CLB when the line matures (Nov 18-20) and the Wild Card report lands; with proposal 1 the
   bracket follows the line by itself.
