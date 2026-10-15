# Rest and congestion against the close

```

== MLS + cups, 2025-2026: 975 lined matches, residual sd 0.252 (close minus kf at lag 0)
  const -0.0342 (se 0.0080), rest_diff (days, capped 10) +0.0176 (se 0.0038)
  const -0.0353 (se 0.0080), matches_last7_diff -0.0545 (se 0.0134)
  const -0.0354 (se 0.0080), matches_last14_diff -0.0304 (se 0.0091)
  const -0.0338 (se 0.0080), short_week(<=3d) h-a -0.0543 (se 0.0232), long_rest(>=7d) h-a +0.0344 (se 0.0185)
  close on model + rest: const -0.0341 (se 0.0080), model +0.9788 (se 0.0159), rest_diff +0.0167 (se 0.0039)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5] -0.117876     79
(-3.5, -0.5]  -0.059795    111
(-0.5, 0.5]   -0.037311    603
(0.5, 3.5]     0.006183    112
(3.5, 11.0]    0.055176     70

== MLS only, 2025-2026: 975 lined matches, residual sd 0.252 (close minus kf at lag 0)
  const -0.0348 (se 0.0081), rest_diff (days, capped 10) +0.0039 (se 0.0061)
  const -0.0350 (se 0.0081), matches_last7_diff -0.0116 (se 0.0214)
  const -0.0348 (se 0.0081), matches_last14_diff -0.0050 (se 0.0160)
  const -0.0345 (se 0.0081), short_week(<=3d) h-a -0.0220 (se 0.0356), long_rest(>=7d) h-a -0.0147 (se 0.0222)
  close on model + rest: const -0.0345 (se 0.0081), model +0.9676 (se 0.0159), rest_diff +0.0032 (se 0.0061)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5] -0.024682     25
(-3.5, -0.5]  -0.040698     93
(-0.5, 0.5]   -0.035051    737
(0.5, 3.5]    -0.047755     92
(3.5, 11.0]    0.026226     28

== MLS only, 2012-2026: 6251 lined matches, residual sd 0.249 (close minus kf at lag 0)
  const +0.0039 (se 0.0031), rest_diff (days, capped 10) +0.0076 (se 0.0017)
  const +0.0040 (se 0.0031), matches_last7_diff -0.0243 (se 0.0060)
  const +0.0040 (se 0.0031), matches_last14_diff -0.0125 (se 0.0045)
  const +0.0042 (se 0.0031), short_week(<=3d) h-a -0.0440 (se 0.0104), long_rest(>=7d) h-a +0.0067 (se 0.0071)
  close on model + rest: const +0.0040 (se 0.0031), model +0.9510 (se 0.0068), rest_diff +0.0074 (se 0.0017)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5] -0.034985    366
(-3.5, -0.5]  -0.007500    928
(-0.5, 0.5]    0.003653   3650
(0.5, 3.5]     0.011933    944
(3.5, 11.0]    0.054636    363
```
