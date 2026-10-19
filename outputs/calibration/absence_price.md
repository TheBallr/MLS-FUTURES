# Does Pinnacle price absences? residual = close minus kf_plain at lag 0 (scripts/absence_price.py)

6265 scored closes; matched to an ASA team-game 0.904; residual sd 0.246; sd of dmv 0.108, drest 1.990, dshort 0.354, delim 0.200

Pooled, matched closes with an absence window (5602):
  const +0.0006 (se 0.0032); abs (goals per goal of missing value) -0.4819 (se 0.0278); rest (per day diff) +0.0052 (se 0.0020); short week (flag diff) -0.0309 (se 0.0111); eliminated (flag diff) -0.1885 (se 0.0156); resid sd 0.2369
  const +0.0006 (se 0.0032); abs alone -0.4826 (se 0.0282)
  close on model + factors: const +0.0006 (se 0.0032); model +0.9970 (se 0.0076); abs -0.4784 (se 0.0292); rest +0.0052 (se 0.0020); short -0.0309 (se 0.0111); elim -0.1902 (se 0.0161)
  home and away separately: const -0.0065 (se 0.0039); mv_home -0.3913 (se 0.0408); mv_away +0.5538 (se 0.0365); rest +0.0052 (se 0.0020); short -0.0309 (se 0.0111); elim -0.1873 (se 0.0156)

residual by dmv bucket (home minus away missing value):
                   mean  count
dmv                           
(-5.0, -0.3]   0.286302     76
(-0.3, -0.1]   0.066556    905
(-0.1, -0.02]  0.015565   1497
(-0.02, 0.02]  0.005059   1059
(0.02, 0.1]   -0.015008   1338
(0.1, 0.3]    -0.064563    680
(0.3, 5.0]    -0.261429     47

By season (abs coefficient, se; rest; short; elim; n):
  2013: abs -0.119 (se 0.118); rest +0.0077; short +0.012; elim -0.172; n 292
  2014: abs -0.433 (se 0.105); rest +0.0058; short -0.048; elim -0.267; n 323
  2015: abs -0.472 (se 0.113); rest +0.0056; short +0.023; elim -0.326; n 334
  2016: abs -0.808 (se 0.111); rest +0.0120; short +0.055; elim -0.286; n 340
  2017: abs -0.315 (se 0.102); rest +0.0063; short -0.040; elim -0.251; n 369
  2018: abs -0.641 (se 0.092); rest -0.0061; short -0.111; elim -0.274; n 388
  2019: abs -0.596 (se 0.106); rest +0.0119; short -0.005; elim -0.180; n 405
  2020: abs -0.420 (se 0.192); rest +0.0012; short -0.097; elim -0.048; n 284
  2021: abs -0.393 (se 0.102); rest +0.0050; short -0.005; elim -0.162; n 456
  2022: abs -0.448 (se 0.092); rest +0.0034; short -0.009; elim -0.133; n 473
  2023: abs -0.409 (se 0.084); rest -0.0012; short -0.072; elim -0.132; n 489
  2024: abs -0.613 (se 0.082); rest +0.0053; short -0.010; elim -0.149; n 493
  2025: abs -0.432 (se 0.085); rest +0.0119; short -0.036; elim -0.099; n 507
  2026: abs -0.498 (se 0.116); rest +0.0036; short -0.029; elim -0.065; n 449
  seasons with abs > 0: 0/14; mean of season coefficients -0.471 (sd across seasons 0.163, mean se 0.107)

Walk-forward (coefficients fitted on the seasons before each season; what a live netting would have used):
  2015: abs -0.295 (se 0.079); rest +0.0068; short -0.022; elim -0.218 (on 615 closes)
  2016: abs -0.354 (se 0.064); rest +0.0060; short -0.003; elim -0.247 (on 949 closes)
  2017: abs -0.460 (se 0.056); rest +0.0069; short +0.007; elim -0.255 (on 1289 closes)
  2018: abs -0.432 (se 0.049); rest +0.0069; short -0.005; elim -0.256 (on 1658 closes)
  2019: abs -0.484 (se 0.043); rest +0.0044; short -0.026; elim -0.260 (on 2046 closes)
  2020: abs -0.507 (se 0.040); rest +0.0056; short -0.023; elim -0.250 (on 2451 closes)
  2021: abs -0.501 (se 0.041); rest +0.0048; short -0.030; elim -0.244 (on 2735 closes)
  2022: abs -0.482 (se 0.038); rest +0.0051; short -0.026; elim -0.231 (on 3191 closes)
  2023: abs -0.477 (se 0.035); rest +0.0050; short -0.024; elim -0.221 (on 3664 closes)
  2024: abs -0.468 (se 0.033); rest +0.0045; short -0.028; elim -0.214 (on 4153 closes)
  2025: abs -0.486 (se 0.030); rest +0.0044; short -0.027; elim -0.208 (on 4646 closes)
  2026: abs -0.481 (se 0.029); rest +0.0053; short -0.031; elim -0.194 (on 5153 closes)

By phase (early < mw 10, mid, late):
  early: abs -0.487 (se 0.058); rest -0.0055; short -0.058; n 1709
  late: abs -0.513 (se 0.047); rest +0.0080; short -0.015; n 1845
  mid: abs -0.435 (se 0.044); rest +0.0089; short -0.029; n 2048

Absences of a keeper vs field players (abs coefficient with mv split; needs absence_players.csv):
  const +0.0004 (se 0.0032); field -0.5558 (se 0.0330); keeper -0.2881 (se 0.0544); rest +0.0051 (se 0.0020); short -0.0304 (se 0.0111); elim -0.1919 (se 0.0156)
