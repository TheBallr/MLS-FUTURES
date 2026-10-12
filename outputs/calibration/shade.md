# Shade per pool (leave-one-season-out)

| pool | b=1 ll | best b | best ll (held out) | apply |
|---|---|---|---|---|
| shield | 0.0770 | 1.2 | 0.0782 | no (raw) |
| conf | 0.1213 | 1.5 | 0.1205 | yes |
| playoffs | 0.2313 | 1.3 | 0.2427 | no (raw) |
| conf_top4 | 0.2194 | 1.0 | 0.2426 | no (raw) |
| spoon | 0.0762 | 1.1 | 0.0776 | no (raw) |
| conf_bottom | 0.0829 | 1.0 | 0.0829 | no (raw) |

## Longshot rule (all pools, raw prices)

| bucket | n | mean price | realised | ratio |
|---|---|---|---|---|
| 0%-2% | 6758 | 0.002 | 0.002 | 1.05 |
| 2%-5% | 656 | 0.033 | 0.021 | 0.64 |
| 5%-10% | 543 | 0.073 | 0.061 | 0.83 |
| 10%-20% | 564 | 0.146 | 0.115 | 0.79 |
| 20%-40% | 513 | 0.284 | 0.294 | 1.04 |
| 40%-100% | 795 | 0.724 | 0.756 | 1.04 |

Chosen shade: {'conf': 1.5} (set config knob `shade` with this report as the note; scenario teams exempt).