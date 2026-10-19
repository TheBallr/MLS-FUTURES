# MLS-FUTURES

Futures pricing model for Major League Soccer 2026 (Supporters' Shield, conference seeds, playoffs, conference titles,
MLS Cup), built for Zac (Sierra Advisory). Ratings: a Kalman filter on Pinnacle closing lines plus the current round's posted
lines, blended 85/15 with ASA xG, plus Zac's weekly hand adjustments. 200,000 simulated seasons with the 2026 tiebreakers
and bracket, fixed seed; published to a private claude.ai page with a Risk tab.

## Start here
- `CLAUDE.md`: the rules (sections 0-2), branches, known gaps (4), decisions log newest first (5), measurements. Read before
  changing anything.
- `PLAN.md`: the method as it runs today. `config.json`: every knob, its value and a dated provenance note.
- `data/ratings/method_log.csv`: every applied model change with its time. `MLS_BUILD_PROMPT.md`: the original spec.
- `scripts/README.md`: what each script is for (live / research / historical). `outputs/calibration/README.md`: which
  reports describe the live model.

## Branches
`claude/gallant-heisenberg-o7xbg9` is the live branch: the scheduled tasks (7:40 and 8:52 ET, close captures) pull, push
and publish from it. Merge finished work into it before a task fires. Work branches and old branches: CLAUDE.md, top.
`main` holds only the initial commit.

## Run
    python3 scripts/weekly.py [--force]   # fetch; on a completed match-day: settings, run, Risk report, site
    python3 scripts/run_sim.py [--quick]  # a full run -> outputs/latest/, archived in outputs/runs/<stamp>/
    python3 scripts/risk.py && python3 scripts/site_data.py && python3 scripts/build_site.py && python3 scripts/check_site.py
    python3 scripts/what_if.py --alt "name:knob=value"   # futures under other knobs; writes nothing
    python3 scripts/close_track.py        # the ratings yardstick (tracking Pinnacle's close)
    python3 scripts/backtest_season.py    # the variance yardstick (rest-of-season backtest)
    python3 tests/run_tests.py            # after any engine change
    python3 scripts/check_secrets.py      # before every push

## Layout
- `sim/`: goal model, ratings building blocks, Kalman filter, season engine, standings, playoffs, markets, layers.
- `scripts/`: fetchers, the run, the Risk report, the site, calibration and research.
- `site/index.html`: the page template. `data/`: schedule, results, closes, odds, ratings inputs, history.
- `outputs/latest/`: the current run and page (`site.html` is what gets published); `outputs/runs/`: every run.
- Page: https://claude.ai/artifact/PYXHJ1tuZhpRqgoub1Nfao. Secrets: `OPTIC_API_KEY` from the environment only.
