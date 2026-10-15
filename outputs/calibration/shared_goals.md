# Shared goals (bivariate Poisson common component)

## From Pinnacle's posted ladders (guest API captures)

| c | ladder rmse (fair prob) | n prices |
|---|---|---|
| 0.00 | 0.0132 | 259 |
| 0.05 | 0.0120 | 259 |
| 0.10 | 0.0112 | 259 |
| 0.15 | 0.0109 | 259 |
| 0.20 | 0.0113 | 259 |
| 0.25 | 0.0122 | 259 |
| 0.30 | 0.0136 | 259 |
| 0.40 | 0.0176 | 259 |

Ladder answer: c = 0.15

## From Pinnacle's closing ladders (OpticOdds harvest, clv)

| c | ladder rmse (fair prob) | n prices |
|---|---|---|
| 0.00 | 0.0159 | 6049 |
| 0.05 | 0.0152 | 6049 |
| 0.10 | 0.0150 | 6049 |
| 0.15 | 0.0154 | 6049 |
| 0.20 | 0.0165 | 6049 |
| 0.25 | 0.0181 | 6049 |
| 0.30 | 0.0201 | 6049 |
| 0.40 | 0.0253 | 6049 |

Ladder answer: c = 0.10

## From realised variance around the closes

Realised over 6236 lined matches: var(margin) 2.805, var(total) 2.964, E[margin - gd_fit] -0.004, E[total - T_fit] -0.097

| c | model var(margin) | model var(total) | gap (abs sum) |
|---|---|---|---|
| 0.00 | 3.011 | 3.011 | 0.252 |
| 0.05 | 2.911 | 3.111 | 0.252 |
| 0.10 | 2.811 | 3.211 | 0.252 |
| 0.15 | 2.711 | 3.311 | 0.441 |
| 0.20 | 2.611 | 3.411 | 0.641 |
| 0.25 | 2.511 | 3.511 | 0.841 |
| 0.30 | 2.411 | 3.611 | 1.041 |
| 0.40 | 2.211 | 3.811 | 1.440 |

Realised-variance answer: c = 0.10