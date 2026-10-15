# Rest and congestion against the close

```

== MLS + cups, 2025-2026: 975 lined matches, residual sd 0.257 (close minus live at lag 0)
  const -0.0281 (se 0.0082), rest_diff (days, capped 10) +0.0067 (se 0.0039)
  const -0.0285 (se 0.0082), matches_last7_diff -0.0249 (se 0.0137)
  const -0.0283 (se 0.0082), matches_last14_diff -0.0027 (se 0.0093)
  const -0.0275 (se 0.0082), short_week(<=3d) h-a -0.0431 (se 0.0238), long_rest(>=7d) h-a -0.0009 (se 0.0189)
  close on model + rest: const -0.0284 (se 0.0075), model +1.2740 (se 0.0190), rest_diff +0.0151 (se 0.0036)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5] -0.062029     79
(-3.5, -0.5]  -0.051384    111
(-0.5, 0.5]   -0.026216    603
(0.5, 3.5]    -0.019777    112
(3.5, 11.0]    0.015010     70

== MLS only, 2025-2026: 975 lined matches, residual sd 0.257 (close minus live at lag 0)
  const -0.0283 (se 0.0082), rest_diff (days, capped 10) +0.0005 (se 0.0062)
  const -0.0282 (se 0.0082), matches_last7_diff +0.0031 (se 0.0217)
  const -0.0283 (se 0.0082), matches_last14_diff -0.0037 (se 0.0163)
  const -0.0284 (se 0.0082), short_week(<=3d) h-a +0.0059 (se 0.0362), long_rest(>=7d) h-a -0.0188 (se 0.0226)
  close on model + rest: const -0.0289 (se 0.0075), model +1.2620 (se 0.0189), rest_diff +0.0046 (se 0.0057)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5]  0.002210     25
(-3.5, -0.5]  -0.023075     93
(-0.5, 0.5]   -0.028630    737
(0.5, 3.5]    -0.053782     92
(3.5, 11.0]    0.020088     28

== MLS only, 2012-2026: 6251 lined matches, residual sd 0.251 (close minus live at lag 0)
  const +0.0046 (se 0.0032), rest_diff (days, capped 10) +0.0062 (se 0.0017)
  const +0.0047 (se 0.0032), matches_last7_diff -0.0193 (se 0.0060)
  const +0.0047 (se 0.0032), matches_last14_diff -0.0134 (se 0.0046)
  const +0.0050 (se 0.0032), short_week(<=3d) h-a -0.0528 (se 0.0104), long_rest(>=7d) h-a -0.0040 (se 0.0071)
  close on model + rest: const +0.0041 (se 0.0030), model +1.2099 (se 0.0083), rest_diff +0.0069 (se 0.0016)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5] -0.028793    366
(-3.5, -0.5]  -0.003079    928
(-0.5, 0.5]    0.005767   3650
(0.5, 3.5]     0.006791    944
(3.5, 11.0]    0.041678    363
```
