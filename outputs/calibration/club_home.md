# Per-club home edge: held-out test (deltas from the other seasons, walk-forward next-ten rmse)

| season | n | no club edge | k=50 | k=100 | k=200 | k=400 |
|---|---|---|---|---|---|---|
| 2022 | 865 | 0.2553 | 0.2546 | 0.2546 | 0.2547 | 0.2548 |
| 2023 | 713 | 0.2643 | 0.2629 | 0.2630 | 0.2632 | 0.2635 |
| 2024 | 686 | 0.2780 | 0.2762 | 0.2763 | 0.2766 | 0.2769 |
| 2025 | 839 | 0.2547 | 0.2526 | 0.2529 | 0.2532 | 0.2537 |
| 2026 | 521 | 0.2612 | 0.2589 | 0.2592 | 0.2595 | 0.2600 |

Pooled: none: 0.2622, k=50: 0.2606, k=100: 0.2608, k=200: 0.2610, k=400: 0.2613
Best: k=50

## Deltas from all seasons, k=50 (data/ratings/home_edges.csv)

| club | n home closes | raw mean | se | delta |
|---|---|---|---|---|
| Real Salt Lake | 256 | +0.061 | 0.015 | +0.050 |
| LAFC | 159 | +0.063 | 0.022 | +0.047 |
| Seattle Sounders | 274 | +0.052 | 0.015 | +0.043 |
| Colorado Rapids | 246 | +0.037 | 0.016 | +0.030 |
| Atlanta United | 172 | +0.029 | 0.019 | +0.022 |
| San Diego FC | 35 | +0.056 | 0.044 | +0.022 |
| Portland Timbers | 263 | +0.015 | 0.015 | +0.012 |
| Houston Dynamo | 257 | +0.015 | 0.016 | +0.011 |
| Inter Miami | 115 | +0.014 | 0.034 | +0.009 |
| FC Dallas | 255 | +0.011 | 0.015 | +0.008 |
| Minnesota United | 164 | +0.011 | 0.019 | +0.007 |
| Sporting Kansas City | 259 | +0.005 | 0.014 | +0.003 |
| St. Louis City | 66 | +0.007 | 0.025 | +0.003 |
| Columbus Crew | 263 | +0.002 | 0.015 | +0.001 |
| New York Red Bulls | 260 | +0.001 | 0.015 | -0.000 |
| LA Galaxy | 263 | +0.001 | 0.018 | +0.000 |
| Nashville SC | 114 | -0.001 | 0.021 | -0.002 |
| New England Revolution | 250 | -0.001 | 0.016 | -0.002 |
| Philadelphia Union | 259 | -0.006 | 0.015 | -0.006 |
| Orlando City | 206 | -0.014 | 0.016 | -0.012 |
| Toronto FC | 258 | -0.014 | 0.016 | -0.012 |
| San Jose Earthquakes | 249 | -0.014 | 0.017 | -0.012 |
| Vancouver Whitecaps | 255 | -0.014 | 0.017 | -0.013 |
| Charlotte FC | 86 | -0.026 | 0.025 | -0.017 |
| Chicago Fire | 251 | -0.021 | 0.014 | -0.018 |
| Austin FC | 102 | -0.028 | 0.025 | -0.020 |
| CF Montréal | 255 | -0.026 | 0.015 | -0.023 |
| New York City FC | 206 | -0.035 | 0.017 | -0.029 |
| FC Cincinnati | 133 | -0.069 | 0.026 | -0.051 |
| D.C. United | 254 | -0.063 | 0.018 | -0.053 |

Decision rule: switch `club_home_edge_enabled` on only if a k beats 'none' pooled and in most test seasons. Result here: ENABLE k=50.