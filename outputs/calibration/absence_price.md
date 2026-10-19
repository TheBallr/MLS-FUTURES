# Does Pinnacle price absences? residual = close minus kf_plain at lag 0 (scripts/absence_price.py)

6265 scored closes; matched to an ASA team-game 0.904; residual sd 0.246; sd of dmv 0.126, drest 1.990, dshort 0.354, delim 0.200

Pooled, matched closes with an absence window (5602):
  const +0.0005 (se 0.0032); abs (goals per goal of missing value) -0.3927 (se 0.0239); rest (per day diff) +0.0052 (se 0.0020); short week (flag diff) -0.0320 (se 0.0111); eliminated (flag diff) -0.1928 (se 0.0156); resid sd 0.2375
  const +0.0006 (se 0.0032); abs alone -0.3873 (se 0.0243)
  close on model + factors: const +0.0006 (se 0.0032); model +0.9926 (se 0.0076); abs -0.3857 (se 0.0250); rest +0.0051 (se 0.0020); short -0.0322 (se 0.0111); elim -0.1968 (se 0.0162)
  home and away separately: const -0.0029 (se 0.0036); mv_home -0.3408 (se 0.0347); mv_away +0.4340 (se 0.0312); rest +0.0052 (se 0.0020); short -0.0319 (se 0.0111); elim -0.1919 (se 0.0156)

residual by dmv bucket (home minus away missing value):
                   mean  count
dmv                           
(-5.0, -0.3]   0.214115    129
(-0.3, -0.1]   0.048791   1147
(-0.1, -0.02]  0.016676   1336
(-0.02, 0.02] -0.008949    803
(0.02, 0.1]   -0.010030   1250
(0.1, 0.3]    -0.045704    871
(0.3, 5.0]    -0.181104     66

By season (abs coefficient, se; rest; short; elim; n):
  2013: abs -0.054 (se 0.100); rest +0.0079; short +0.013; elim -0.170; n 292
  2014: abs -0.275 (se 0.090); rest +0.0067; short -0.043; elim -0.274; n 323
  2015: abs -0.389 (se 0.094); rest +0.0065; short +0.020; elim -0.333; n 334
  2016: abs -0.634 (se 0.089); rest +0.0109; short +0.038; elim -0.286; n 340
  2017: abs -0.244 (se 0.079); rest +0.0068; short -0.037; elim -0.251; n 369
  2018: abs -0.485 (se 0.075); rest -0.0067; short -0.118; elim -0.258; n 388
  2019: abs -0.581 (se 0.093); rest +0.0103; short -0.009; elim -0.186; n 405
  2020: abs -0.240 (se 0.162); rest +0.0009; short -0.103; elim -0.035; n 284
  2021: abs -0.375 (se 0.089); rest +0.0051; short -0.006; elim -0.173; n 456
  2022: abs -0.422 (se 0.085); rest +0.0032; short -0.006; elim -0.136; n 473
  2023: abs -0.324 (se 0.075); rest -0.0017; short -0.075; elim -0.139; n 489
  2024: abs -0.455 (se 0.071); rest +0.0042; short -0.021; elim -0.153; n 493
  2025: abs -0.350 (se 0.079); rest +0.0114; short -0.039; elim -0.111; n 507
  2026: abs -0.445 (se 0.101); rest +0.0039; short -0.027; elim -0.067; n 449
  seasons with abs > 0: 0/14; mean of season coefficients -0.377 (sd across seasons 0.149, mean se 0.092)

Walk-forward (coefficients fitted on the seasons before each season; what a live netting would have used):
  2015: abs -0.174 (se 0.067); rest +0.0074; short -0.019; elim -0.219 (on 615 closes)
  2016: abs -0.250 (se 0.054); rest +0.0066; short -0.002; elim -0.251 (on 949 closes)
  2017: abs -0.348 (se 0.047); rest +0.0074; short +0.005; elim -0.260 (on 1289 closes)
  2018: abs -0.327 (se 0.040); rest +0.0074; short -0.005; elim -0.259 (on 1658 closes)
  2019: abs -0.366 (se 0.035); rest +0.0047; short -0.027; elim -0.260 (on 2046 closes)
  2020: abs -0.404 (se 0.033); rest +0.0059; short -0.023; elim -0.251 (on 2451 closes)
  2021: abs -0.389 (se 0.034); rest +0.0051; short -0.032; elim -0.244 (on 2735 closes)
  2022: abs -0.387 (se 0.032); rest +0.0053; short -0.027; elim -0.233 (on 3191 closes)
  2023: abs -0.390 (se 0.030); rest +0.0051; short -0.025; elim -0.223 (on 3664 closes)
  2024: abs -0.382 (se 0.028); rest +0.0046; short -0.029; elim -0.216 (on 4153 closes)
  2025: abs -0.391 (se 0.026); rest +0.0045; short -0.029; elim -0.211 (on 4646 closes)
  2026: abs -0.389 (se 0.025); rest +0.0053; short -0.033; elim -0.198 (on 5153 closes)

By phase (early < mw 10, mid, late):
  early: abs -0.397 (se 0.050); rest -0.0056; short -0.061; n 1709
  late: abs -0.379 (se 0.041); rest +0.0080; short -0.017; n 1845
  mid: abs -0.372 (se 0.037); rest +0.0089; short -0.029; n 2048

Absences of a keeper vs field players (abs coefficient with mv split; needs absence_players.csv):
  const +0.0004 (se 0.0032); field -0.4183 (se 0.0269); keeper -0.2919 (se 0.0543); rest +0.0052 (se 0.0020); short -0.0317 (se 0.0111); elim -0.1945 (se 0.0157)
