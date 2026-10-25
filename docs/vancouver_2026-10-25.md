# Vancouver deep dive, 2026-10-25 (Zac: "are we correct about their strength ... should they be weaker based on how they have performed")

Run 20261025T175819Z (results through Oct 24, 29 posted lines). Nothing changed in the model.

## Where the rating comes from
| piece | value | note |
|---|---|---|
| Rating (blend, no hand) | **+0.74** | 4th in MLS (NSH +0.88 w/ hand, PHI +0.77, MIA +0.75 w/ hand); 1st in the West by 0.30 (LAFC +0.44, STL +0.21, DAL +0.05) |
| Market source (Kalman on Pinnacle, full health, posted line in) | +0.84 | plain state: +1.06 on Oct 1, +0.99 Oct 11, +0.91 Oct 15, +0.86 Oct 25: Pinnacle has cut them 0.20 goals in three weeks |
| Pinnacle-implied windows | last 4 +0.75, last 8 +0.84, last 12 +0.98, season +0.98 | the Oct 28 line v San Diego (1.47/5.13/5.55, AH -1.25) implies +0.83 |
| xG source (45-day half-life, rescaled) | +0.20 | fell +0.35 -> +0.20 today on the Colorado game (xG -2.1); season xG margin +0.93/g is the best in MLS, the last 8 games -0.18/g |
| Opta | +0.52 | |
| Posterior sd / 95% band | 0.12 / +0.51 to +0.97 | |
| Hand | none | |

## How they have performed (31 games, Pinnacle close as the yardstick)
| window | ppg | GD/g | close margin/g | results v close /g | xG margin/g | xG v close /g |
|---|---|---|---|---|---|---|
| season | 1.77 | +1.00 | +1.01 | -0.01 | +0.93 | -0.09 |
| before the World Cup (14) | 2.29 | +1.57 | +1.14 | +0.43 | +1.60 | +0.46 |
| after (17) | 1.35 | +0.53 | +0.90 | -0.37 | +0.37 | -0.54 |
| last 12 | 1.50 | +0.75 | +1.00 | -0.25 | +0.23 | -0.78 |
| last 8 | 1.12 | 0.00 | +0.69 | -0.69 (se 0.58) | -0.18 | -0.88 |
| last 5 | 1.00 | -0.40 | +0.27 | -0.67 | -0.76 | -1.03 |
Over the season the results match Pinnacle's lines exactly; the last eight are a real slump (0 goal difference, xG below the
close by 0.9 a game, 5 of 8 misses one way). Absences explain none of it: missing value 0.00-0.12 goals a game in those games
(Berhalter, Ocampo, Gauld doubt), Müller valued at -0.01 per 96 on goals added (star tier is Zac's, no model cost), out to Nov 1.

## Does a slump like this predict more of it? (`scripts/form_persistence.py`, 15 seasons, 11,622 club-matches, plain filter)
Regression of the next close on the club's trailing-8 results-v-close and xG-v-close (home minus away): close moves beyond
the state by 0.047 x results (se 0.004) and 0.102 x xG (se 0.007). For Vancouver (-0.69, -0.88) that is about -0.12 goals
more cut to come, which the xG share already carries (we sit 0.10 under the market source and 0.09 under Pinnacle's live line).
Regression of the next RESULT on the same: results -0.039 (se 0.029), xG +0.063 (se 0.045): nothing. Favourites in a
Vancouver-shaped slump (close +0.5/g or more over the last 8, results -0.4 or worse, xG -0.5 or worse v the close: n 64, 13 clubs,
14 seasons, e.g. LAFC 2020, Galaxy 2015, Seattle 2025) beat the close by +0.05 in the next game (se 0.22) and ran -0.03 v the
close over the next eight: the close already prices the slump. All big favourites run -0.07 v the close (se 0.05, 1027 games).

## What the price rests on
| Vancouver at rating | Win MLS Cup | Reach MLS Cup | West 1 seed | NSH Cup |
|---|---|---|---|---|
| +0.84 (market only) | 23.0 | 42.2 | 80.5 | 25.2 |
| **+0.74 (live)** | **19.9** | **38.6** | **79.4** | 26.0 |
| +0.64 | 17.5 | 35.2 | 77.6 | 26.6 |
| +0.54 | 15.3 | 32.0 | 76.5 | 27.0 |
| +0.44 (= LAFC) | 13.1 | 28.7 | 75.4 | 27.0 |
| +0.30 | 10.5 | 24.7 | 73.5 | 27.1 |
(40k seasons, paired.) Neutral playoff home edge: Cup 19.9 -> 15.7, Reach Cup 38.6 -> 29.2 (Nashville 26.0 -> 16.8): about 4
points of the Cup price is hosting. The 1 seed is the table, not the rating: 55 pts and 16 wins v Dallas 54 and 15 (wins is the
first tiebreak, then GD +31 v +11); VAN v SD, v SEA, at MTL; DAL v CLB, at SKC, v COL. The 95% band on the rating maps to a Cup price
of roughly 14.5 to 26.5.
Reading: the Reach-MLS-Cup price (38.6, the West's favourite by 24 points over LAFC) is more about the West than about Vancouver:
every other West club is rated +0.44 or lower and Dallas, the likely 2 seed, is +0.05. The review's extra-time item (coin flips
in the semis, final and Cup) runs the other way: the favourite's price is 1-2 points low per knockout match.

## Verdict
The rating is not too high against the evidence we have: Pinnacle's live line still has them at +0.83, our +0.74 is below it
because the recent xG is poor, and the history says a favourite's slump is already in the close and does not predict the next
results. The uncertainty is the band (+0.51 to +0.97), not a bias. What would move them: the Oct 28 and Nov 1 lines (priced off
Pinnacle whatever we think) and their closes entering the filter; a hand on top of the xG pull would count the slump twice.
