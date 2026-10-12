# Home edge and average total from Pinnacle closes

| season | matches | mean gd_fit (home edge) | mean T_fit | realised margin | realised total | fitted HE (full-season WLS) |
|---|---|---|---|---|---|---|
| 2012 | 338 | +0.483 | 3.000 | +0.485 | 2.627 | +0.481 |
| 2013 | 338 | +0.469 | 3.000 | +0.515 | 2.615 | +0.465 |
| 2014 | 338 | +0.480 | 3.000 | +0.470 | 2.855 | +0.478 |
| 2015 | 357 | +0.505 | 3.000 | +0.594 | 2.745 | +0.507 |
| 2016 | 357 | +0.587 | 3.000 | +0.549 | 2.812 | +0.585 |
| 2017 | 391 | +0.625 | 3.000 | +0.770 | 2.923 | +0.626 |
| 2018 | 408 | +0.647 | 3.000 | +0.659 | 3.174 | +0.644 |
| 2019 | 421 | +0.603 | 3.000 | +0.527 | 3.059 | +0.596 |
| 2020 | 324 | +0.344 | 3.000 | +0.404 | 2.867 | +0.327 |
| 2021 | 472 | +0.492 | 3.000 | +0.483 | 2.775 | +0.490 |
| 2022 | 489 | +0.507 | 3.000 | +0.540 | 2.965 | +0.502 |
| 2023 | 521 | +0.518 | 3.000 | +0.630 | 2.752 | +0.517 |
| 2024 | 522 | +0.536 | 3.000 | +0.347 | 3.113 | +0.534 |
| 2025 | 540 | +0.449 | 3.000 | +0.298 | 3.017 | +0.449 |
| 2026 | 405 | +0.432 | 3.000 | +0.444 | 3.225 | +0.427 |

Pooled: 6221 matches, home edge +0.514 (se 0.006), average total 3.000 (se 0.000).

## Per-club home residual (goals; a per-club edge is justified only if |mean| > 2 se over several seasons)

| club | n | mean | se |
|---|---|---|---|
| Chivas USA | 51 | -0.141 | 0.038 |
| FC Cincinnati | 133 | -0.066 | 0.025 |
| LAFC | 158 | +0.060 | 0.020 |
| D.C. United | 254 | -0.059 | 0.017 |
| Real Salt Lake | 256 | +0.057 | 0.014 |
| San Diego FC | 35 | +0.057 | 0.042 |
| Seattle Sounders | 274 | +0.050 | 0.014 |
| Colorado Rapids | 245 | +0.036 | 0.015 |
| New York City FC | 206 | -0.032 | 0.016 |
| Atlanta United | 171 | +0.029 | 0.018 |
| CF Montréal | 255 | -0.024 | 0.014 |
| Austin FC | 101 | -0.022 | 0.024 |
| Charlotte FC | 85 | -0.022 | 0.024 |
| Chicago Fire | 250 | -0.020 | 0.014 |
| Vancouver Whitecaps | 255 | -0.016 | 0.016 |
| Orlando City | 205 | -0.015 | 0.015 |
| Houston Dynamo | 257 | +0.015 | 0.015 |
| Portland Timbers | 263 | +0.014 | 0.014 |
| San Jose Earthquakes | 249 | -0.013 | 0.016 |
| Toronto FC | 257 | -0.013 | 0.016 |
| Minnesota United | 163 | +0.012 | 0.018 |
| FC Dallas | 255 | +0.011 | 0.014 |
| Inter Miami | 114 | +0.009 | 0.032 |
| St. Louis City | 65 | +0.007 | 0.022 |
| Philadelphia Union | 258 | -0.007 | 0.013 |
| Sporting Kansas City | 258 | +0.004 | 0.013 |
| Nashville SC | 114 | +0.002 | 0.020 |
| Columbus Crew | 263 | +0.002 | 0.014 |
| LA Galaxy | 263 | -0.001 | 0.017 |
| New England Revolution | 249 | -0.001 | 0.015 |
| New York Red Bulls | 259 | +0.000 | 0.015 |

Recommendation: home_edge_goals = 0.51, avg_total_goals = 3.00 (last two seasons: +0.442 / 3.000). Set in config.json with this report as the note, then freeze.