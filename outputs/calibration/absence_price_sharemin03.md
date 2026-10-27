# Does Pinnacle price absences? residual = close minus kf_plain at lag 0 (scripts/absence_price.py)

6265 scored closes; matched to an ASA team-game 0.904; residual sd 0.246; sd of dmv 0.121, drest 1.989, dshort 0.354, delim 0.196

Pooled, matched closes with an absence window (5602):
  const +0.0008 (se 0.0032); abs (goals per goal of missing value) -0.3991 (se 0.0250); rest (per day diff) +0.0051 (se 0.0020); short week (flag diff) -0.0322 (se 0.0112); eliminated (flag diff) -0.1963 (se 0.0160); resid sd 0.2378
  const +0.0009 (se 0.0032); abs alone -0.3954 (se 0.0253)
  close on model + factors: const +0.0007 (se 0.0032); model +1.0004 (se 0.0078); abs -0.3996 (se 0.0267); rest +0.0051 (se 0.0020); short -0.0322 (se 0.0112); elim -0.1961 (se 0.0165)
  home and away separately: const -0.0078 (se 0.0040); mv_home -0.3095 (se 0.0360); mv_away +0.4722 (se 0.0328); rest +0.0051 (se 0.0020); short -0.0323 (se 0.0111); elim -0.1949 (se 0.0160)

residual by dmv bucket (home minus away missing value):
                   mean  count
dmv                           
(-5.0, -0.3]   0.231627    107
(-0.3, -0.1]   0.045094   1117
(-0.1, -0.02]  0.023856   1383
(-0.02, 0.02] -0.000333    828
(0.02, 0.1]   -0.014077   1256
(0.1, 0.3]    -0.050094    847
(0.3, 5.0]    -0.209072     64

By season (abs coefficient, se; rest; short; elim; n):
  2013: abs -0.016 (se 0.103); rest +0.0079; short +0.014; elim -0.167; n 292
  2014: abs -0.374 (se 0.097); rest +0.0059; short -0.048; elim -0.265; n 323
  2015: abs -0.419 (se 0.101); rest +0.0056; short +0.021; elim -0.328; n 334
  2016: abs -0.772 (se 0.102); rest +0.0127; short +0.051; elim -0.298; n 340
  2017: abs -0.225 (se 0.088); rest +0.0057; short -0.045; elim -0.252; n 369
  2018: abs -0.573 (se 0.086); rest -0.0062; short -0.118; elim -0.265; n 388
  2019: abs -0.543 (se 0.098); rest +0.0115; short -0.008; elim -0.187; n 405
  2020: abs -0.231 (se 0.164); rest +0.0009; short -0.100; elim -0.051; n 284
  2021: abs -0.337 (se 0.092); rest +0.0048; short -0.003; elim -0.166; n 456
  2022: abs -0.363 (se 0.080); rest +0.0026; short -0.008; elim -0.137; n 473
  2023: abs -0.317 (se 0.074); rest -0.0012; short -0.074; elim -0.137; n 489
  2024: abs -0.553 (se 0.075); rest +0.0045; short -0.017; elim -0.162; n 493
  2025: abs -0.347 (se 0.078); rest +0.0114; short -0.039; elim -0.106; n 507
  2026: abs -0.375 (se 0.104); rest +0.0040; short -0.028; elim +0.048; n 449
  seasons with abs > 0: 0/14; mean of season coefficients -0.389 (sd across seasons 0.183, mean se 0.096)

Walk-forward (coefficients fitted on the seasons before each season; what a live netting would have used):
  2015: abs -0.208 (se 0.071); rest +0.0070; short -0.021; elim -0.216 (on 615 closes)
  2016: abs -0.278 (se 0.058); rest +0.0061; short -0.003; elim -0.247 (on 949 closes)
  2017: abs -0.389 (se 0.050); rest +0.0070; short +0.005; elim -0.257 (on 1289 closes)
  2018: abs -0.355 (se 0.044); rest +0.0069; short -0.007; elim -0.258 (on 1658 closes)
  2019: abs -0.406 (se 0.039); rest +0.0043; short -0.029; elim -0.260 (on 2046 closes)
  2020: abs -0.433 (se 0.036); rest +0.0056; short -0.025; elim -0.251 (on 2451 closes)
  2021: abs -0.414 (se 0.037); rest +0.0049; short -0.033; elim -0.245 (on 2735 closes)
  2022: abs -0.401 (se 0.034); rest +0.0051; short -0.028; elim -0.233 (on 3191 closes)
  2023: abs -0.396 (se 0.032); rest +0.0049; short -0.026; elim -0.223 (on 3664 closes)
  2024: abs -0.385 (se 0.029); rest +0.0044; short -0.029; elim -0.216 (on 4153 closes)
  2025: abs -0.405 (se 0.027); rest +0.0043; short -0.029; elim -0.211 (on 4646 closes)
  2026: abs -0.401 (se 0.026); rest +0.0052; short -0.033; elim -0.197 (on 5153 closes)

By phase (early < mw 10, mid, late):
  early: abs -0.420 (se 0.052); rest -0.0057; short -0.058; n 1709
  late: abs -0.421 (se 0.043); rest +0.0077; short -0.017; n 1845
  mid: abs -0.343 (se 0.039); rest +0.0088; short -0.031; n 2048

Absences of a keeper vs field players (abs coefficient with mv split; needs absence_players.csv):
  const +0.0006 (se 0.0032); field -0.4496 (se 0.0289); keeper -0.2396 (se 0.0521); rest +0.0051 (se 0.0020); short -0.0315 (se 0.0111); elim -0.1995 (se 0.0160)
