# Shade per pool (leave-one-season-out)

| pool | b=1 ll | best b | best ll (held out) | apply |
|---|---|---|---|---|
| shield | 0.0765 | 1.2 | 0.0771 | no (raw) |
| conf | 0.1211 | 1.5 | 0.1192 | yes |
| playoffs | 0.2315 | 1.2 | 0.2428 | no (raw) |
| conf_top4 | 0.2217 | 1.0 | 0.2454 | no (raw) |
| spoon | 0.0759 | 1.1 | 0.0772 | no (raw) |
| conf_bottom | 0.0844 | 1.0 | 0.0844 | no (raw) |

## Longshot rule (all pools, raw prices)

| bucket | n | mean price | realised | ratio |
|---|---|---|---|---|
| 0%-2% | 6754 | 0.002 | 0.002 | 1.14 |
| 2%-5% | 651 | 0.033 | 0.018 | 0.55 |
| 5%-10% | 540 | 0.073 | 0.067 | 0.92 |
| 10%-20% | 576 | 0.145 | 0.115 | 0.79 |
| 20%-40% | 522 | 0.285 | 0.285 | 1.00 |
| 40%-100% | 788 | 0.728 | 0.764 | 1.05 |

Chosen shade: {'conf': 1.5} (set config knob `shade` with this report as the note; scenario teams exempt).