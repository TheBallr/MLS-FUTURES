# CLV test and the posted-line shrink (Pinnacle opener -> close, OpticOdds olv/clv)

Live CLV log: {'attacks_closed': 0}
Opener/close pairs on file: 903 ({'2024': 1, '2025': 516, '2026': 386})

Scored pairs: 903. Opener vs close rmse 0.2568; model vs close rmse 0.2612; model vs opener rmse 0.1624.

| s (weight on the opener) | rmse vs close | by season |
|---|---|---|
| 0.00 | 0.2612 | 2024 0.0873, 2025 0.2558, 2026 0.2686 |
| 0.20 | 0.2521 | 2024 0.0882, 2025 0.2487, 2026 0.2570 |
| 0.35 | 0.2479 | 2024 0.0888, 2025 0.2458, 2026 0.2509 |
| 0.50 | 0.2460 | 2024 0.0895, 2025 0.2453, 2026 0.2472 |
| 0.70 | 0.2472 | 2024 0.0904, 2025 0.2481, 2026 0.2463 |
| 1.00 | 0.2568 | 2024 0.0918, 2025 0.2596, 2026 0.2533 |

Shrink answer: s = 0.55 on true openers (fine grid); coarse best 0.50. Live posted lines are fresher than the opener, so the live s should sit between this and 1.0; keep the EPL 0.35 unless this says otherwise.

CLV: 267 attacks (|model - opener| >= 0.15 goals) of 903 pairs; the close moved the model's way 67.4% of the time; mean signed move +0.111 goals; mean |close - opener| on attacks 0.224 vs 0.188 on non-attacks.
Where the model disagreed by >= 0.30: n 65, moved our way 73.8%.