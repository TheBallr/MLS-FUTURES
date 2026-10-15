# Rest and congestion against the close

```

== MLS + cups, 2025-2026: 975 lined matches, residual sd 0.255 (close minus live at lag 0)
  const -0.0638 (se 0.0082), rest_diff (days, capped 10) +0.0058 (se 0.0039)
  const -0.0642 (se 0.0082), matches_last7_diff -0.0220 (se 0.0136)
  const -0.0640 (se 0.0082), matches_last14_diff -0.0008 (se 0.0093)
  const -0.0632 (se 0.0082), short_week(<=3d) h-a -0.0414 (se 0.0237), long_rest(>=7d) h-a -0.0043 (se 0.0189)
  close on model + rest: const -0.0648 (se 0.0074), model +1.2708 (se 0.0189), rest_diff +0.0140 (se 0.0036)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5] -0.086414     79
(-3.5, -0.5]  -0.085736    111
(-0.5, 0.5]   -0.063556    603
(0.5, 3.5]    -0.055843    112
(3.5, 11.0]   -0.020407     70

== MLS only, 2025-2026: 975 lined matches, residual sd 0.255 (close minus live at lag 0)
  const -0.0640 (se 0.0082), rest_diff (days, capped 10) +0.0002 (se 0.0062)
  const -0.0639 (se 0.0082), matches_last7_diff +0.0040 (se 0.0216)
  const -0.0640 (se 0.0082), matches_last14_diff -0.0025 (se 0.0162)
  const -0.0640 (se 0.0082), short_week(<=3d) h-a +0.0014 (se 0.0360), long_rest(>=7d) h-a -0.0223 (se 0.0225)
  close on model + rest: const -0.0652 (se 0.0075), model +1.2597 (se 0.0188), rest_diff +0.0042 (se 0.0057)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5] -0.045423     25
(-3.5, -0.5]  -0.060191     93
(-0.5, 0.5]   -0.062733    737
(0.5, 3.5]    -0.091927     92
(3.5, 11.0]   -0.033050     28

== MLS only, 2012-2026: 975 lined matches, residual sd 0.255 (close minus live at lag 0)
  const -0.0640 (se 0.0082), rest_diff (days, capped 10) +0.0002 (se 0.0062)
  const -0.0639 (se 0.0082), matches_last7_diff +0.0040 (se 0.0216)
  const -0.0640 (se 0.0082), matches_last14_diff -0.0025 (se 0.0162)
  const -0.0640 (se 0.0082), short_week(<=3d) h-a +0.0014 (se 0.0360), long_rest(>=7d) h-a -0.0223 (se 0.0225)
  close on model + rest: const -0.0652 (se 0.0075), model +1.2597 (se 0.0188), rest_diff +0.0042 (se 0.0057)
  residual by rest difference (home minus away days):
                   mean  count
drest                         
(-11.0, -3.5] -0.045423     25
(-3.5, -0.5]  -0.060191     93
(-0.5, 0.5]   -0.062733    737
(0.5, 3.5]    -0.091927     92
(3.5, 11.0]   -0.033050     28
```
