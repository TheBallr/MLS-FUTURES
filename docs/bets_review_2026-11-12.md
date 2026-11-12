# Eight futures bets checked, 2026-11-12 (run 20261112T155008Z; nothing in the model changed)

Zac's table: best book price v a fair that is 50% ours and 50% a second session's bracket from Pinnacle-implied team ratings (not a Pinnacle
futures price: the same match lines ours is built on). 21-step plan, all run. Files: `outputs/calibration/bets_2026-11-12/`.

## Verdicts
| Bet | Price | Ours | Pinnacle-only ratings | Outside markets | EV ours / market / pooled | Club 1 sd lower | Verdict |
|---|---|---|---|---|---|---|---|
| PHI reach MLS Cup | +1400 | 15.2 | 15.6 | Kalshi 8.5, BetOnline 9.5 (+800) | +127 / +35 / +77 | 13.2 (+98) | Bet |
| PHI win MLS Cup | +2500 | 8.2 | 8.3 | Kalshi 7, Polymarket 5-7, BetOnline 5.1 | +113 / +51 / +80 | 6.8 (+77) | Bet |
| NSH win MLS Cup | +400 | 27.2 | 25.3 | Kalshi 26, Polymarket 23, Dimers 27.4 | +36 / +20 / +28 | 23.1 (+15) | Bet |
| NSH reach MLS Cup | +200 | 37.5 | 35.6 | Kalshi 37.5, BetOnline 31.5 | +13 / +8 / +10 | 33.0 (-1) | Thin |
| LAFC reach MLS Cup | +850 | 15.5 | 15.3 | Kalshi 8.5, BetOnline 9.9 | +47 / -13 / +14 | 13.5 (+29) | Reduce |
| POR reach MLS Cup | +3000 | 5.5 | 5.0 | Kalshi 2.5, BetOnline 3.1 | +70 / -13 / +22 | 4.5 (+40) | Reduce |
| CHI reach MLS Cup | +850 | 12.8 | 12.4 | Kalshi 6.5, BetOnline 9.5 | +22 / -24 / -3 | 11.1 (+5) | Pass |
| LAFC win MLS Cup | +2000 | 5.5 | 5.4 | Kalshi 4, Polymarket 4, BetOnline 4.1 | +14 / -16 / -1 | 4.3 (-9) | Pass |
Market = average of the venues listed (devigged where a field was complete). Pooled = ours and the market, 50/50 in log odds. 60k paired
seasons per variant (se 0.15 on 15%).

## A. The "Pinnacle half"
Rebuilt here three ways (market source only with no xG and no hands; ratings set to Pinnacle's last 4 closes; last 12): every one of the
eight fairs within 2 points of ours except Portland on the last-12 window (3.6). So the 50/50 mix adds nothing independent. What the other
session's bracket assumed (home edge, penalties, extra time) is not known here.

## B. Books
- DraftKings +1400 on Philadelphia to reach is an outlier: BetOnline +800, Kalshi 8.5c. It is +EV at the market's own number.
- No house-rule text found. BetOnline and DraftKings (per an odds tracker) call the market "To Reach Final"; Kalshi's conference champion
  market prices Philadelphia 8.5 and Nashville 37.5, so it is the playoff bracket. Confirm the slip wording at each book.
- Only BetOnline's full field was readable: overround 115% Cup, 118% East, 112% West.
- Win given reach: ours PHI 0.55, NSH 0.73, LAFC 0.35; the books' raw pairs 0.58, 0.60, 0.45.

## C. Why we show value
- Break-even rating shift: PHI beyond -0.45 goals on both bets; POR -0.38; LAFC reach -0.36; NSH win -0.24; CHI -0.18; NSH reach -0.13; LAFC win -0.08.
- Round by round (ours): PHI semi 69.6, conf final 34.6, reach 15.0. Pinnacle's own Game 1 line (PHI -0.35 at New England) gives Philadelphia
  about 70% for the series; the market's 8.5-9.5 needs it to win the next two rounds 12-13% of the time, ours 22%.
- We are above the market on PHI, LAFC, CHI, POR at once; the market puts that mass on Vancouver (39.5 v ours 35), Miami (26 v 23.5), New
  England (6.5 v 3.5), Charlotte (4.5 v 2.3), St. Louis (12.5 v 9.5). On New England, Charlotte and St. Louis Pinnacle's Game 1 lines side with us.
- Home edge: playoff closes 2023-25 put it at 0.52 at level ratings v 0.54 fitted in those regular seasons. At 0.30 / 0.60 in the unlined
  games: PHI reach 16.2 / 14.3, NSH win 23.5 / 31.2, NSH reach 33.6 / 41.5.
- Lines closing at our ratings instead of the openers: PHI reach 14.4, LAFC 14.4, the rest within 0.6.

## D. Where we could be wrong
- Philadelphia: season results match the closes (+0.01 a game); last 12 they beat them by +0.74 a game (goal difference +1.58). The season
  goal-difference gap (-0.38) is the spring under the previous coach (7 points at the World Cup break; 43 of 57 since).
- LAFC: -0.26 a game v the closes on the season, -0.69 over the last 12; one win since Sep 12, interim coach, six away in the FIFA window.
  The edge rests on Pinnacle still making Game 1 a pick'em in St. Louis.
- Chicago: -0.26 v closes last 12, 10 conceded in 4; Charlotte beat its closes by +0.47 a game all season (+0.76 last 12) and gets
  Saint-Maximin back; both home games are at SeatGeek Stadium, not Soldier Field.
- Nashville: +0.80 a game v the closes all season. Decision Day at Cincinnati was NOT a rotation game (one change, 2-0 win), so the low close
  there was Pinnacle's guess, not a fact; the +0.05 hand's stated reason is wrong, its direction is supported by the results.
- Vancouver: market 39.5 to reach v ours 35; goal difference above rating (+0.30); supports the +0.05 hand not taken on Nov 11. It would
  take about 0.3 off LAFC and Portland to reach.
- Playoff history 2019-2025 (126 games, ESPN winners joined to the closes): single-game ties, home advanced 66.7% v 62.9% priced (se 5.9);
  Round One games 2023-25, home won 71.7% v 61.7% priced (se 6.1); Round One series, higher seed through 18 of 24 v 64.6% priced (se 9.3);
  shootouts, home won 17 of 27; 19 of 66 Wild Card and Round One games went to penalties v 24% priced. All inside two standard errors, all
  leaning to the home / higher seed. Taking half of the Round One excess as real costs Philadelphia about 2 points of series price
  (reach x0.97), the whole of it 5 points (x0.93).
- Top seeds after the layoff: Game 1 won 5 of 6, series 4 of 6 (priced 66.5%). Road favourites: won in 90 minutes 8 of 16 v 42.6% priced.
- News the lines may not carry (web sweep, Nov 12; no official playoff report until about Nov 17): Philadelphia: Lukic suspended Game 1,
  Cavan Sullivan left Decision Day holding his knee (no update), Iloski (19 goals) missed the last three and is expected back, Larsen
  concussion. Nashville: Yazbek withdrawn from Australia duty, club says available; Palacios missed Decision Day. LAFC: Lloris expected back,
  Shaffelburg in hospital (depth), Son and Bouanga travelling. Portland: four straight wins, Fory and Miller back. Miami v Columbus: no
  Messi news; Columbus six straight wins.

## E. Other models
KickoffHour (goals model, may predate Decision Day): win / reach NSH 28 / 42, PHI 4 / 10, LAFC 6 / 14, CHI 3 / 7. Dimers: NSH 27.4, VAN 20.2,
MIA 12.8 to win (rest paywalled). PlayoffStatus (record-based): NSH 40, PHI 2. Opta and ASA publish nothing for the 2026 bracket.

## F. Positions at one unit each
East: Nashville through 0 on the three East reach bets (+4 more if it wins the Cup); Philadelphia +12 (+25 more with the Cup); Chicago
+6.5; anyone else -3. West: LAFC +7.5 (+20 more with the Cup); Portland +29; anyone else -2. Cup bets not won: -1 each. No bet lands when
the East goes to Miami or a longshot and the West to Vancouver, Dallas, St. Louis, San Jose, Houston or Seattle: about 27%.

## Not possible from here
The books' full fields and rule text (bot-walled); the other session's bracket assumptions; anything from the Wild Card status report.
