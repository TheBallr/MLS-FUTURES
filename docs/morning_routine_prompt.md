MLS Futures morning refresh, the one daily routine (Zac, 2026-10-19). You run in a fresh session; this prompt is the whole brief.
Repo TheBallr/MLS-FUTURES at /home/user/MLS-FUTURES. Before anything else read CLAUDE.md sections 0, 2, 9 and 10 (rules: Zac does
not code; never change a tier, rating, hand adjustment, scenario or calibrated knob on your own; routine maintenance is done and said;
lead with the answer, short, no gambling caveats).

1. Git. If /home/user/MLS-FUTURES is not there, attach the repo with the add_repo tool (owner TheBallr, repo MLS-FUTURES, access
   push), clone it to /home/user/MLS-FUTURES as that tool's result says, and call register_repo_root. Then `cd /home/user/MLS-FUTURES
   && git fetch origin claude/gallant-heisenberg-o7xbg9 && git checkout claude/gallant-heisenberg-o7xbg9 && git pull origin
   claude/gallant-heisenberg-o7xbg9 && python3 -m pip install -q -r requirements.txt` (a fresh container has no packages; the
   page check uses the Chromium already in /opt/pw-browsers). If /root/.config/optic/key exists or OPTIC_API_KEY is set, the scripts use it;
   without it everything still runs off the keyless feeds.
2. Site edits. With ArtifactData (url https://claude.ai/artifact/PYXHJ1tuZhpRqgoub1Nfao, collection settings) get doc `pending` and doc
   `pending.scenario`, noting each version. If either exists write outputs/latest/pending_settings.json as {"settings": <pending
   fields>, "scenario": <pending.scenario fields>} (leave out a missing one); if neither exists delete that file if present.
3. News. Run `python3 scripts/fetch_results.py`, `python3 scripts/fetch_injuries.py` and `python3 scripts/news_scan.py`, then read
   outputs/news/<today>.md. Judge each item against the model: a player out or back (injury, suspension), a manager change, a
   postponement or kickoff change, anything that changes a club's strength. Noise: match reports, punditry, transfer rumours. For an
   item that matters and is thin, one WebSearch (mode standard) for the fact. Routine maintenance, do it and say so: a player out that
   data/ratings/injuries.csv does not list goes in at squad tier with the dated return (prob_out 0.5 for a doubt). Anything bigger
   (a tier, a rating, a hand adjustment, a scenario) is a numbered proposal for Zac, not an edit.
4. The refresh. `python3 scripts/weekly.py` (about 12 minutes): results, Pinnacle's lines, injuries from four sources, lineups,
   absence values, disciplinary points, site edits, xG, Opta, the full 200k-season run, Risk tab, rating history, data checks,
   morning report, page build and page check. If it exits 1, publish nothing: commit what changed, push, report the failed step and
   send the push notification, then stop.
5. Write back. Read outputs/latest/pending_settings.json; for each timestamp apply_site_settings.py set (settings.applied,
   settings.adjustments_applied, scenario.applied) do ArtifactData update on the matching document with only that field and
   if_version = the version from step 2; on a version conflict re-read and write the field only if the saved edits are unchanged
   (otherwise leave it for tomorrow and say so).
6. Publish outputs/latest/site.html with the Artifact tool to https://claude.ai/artifact/PYXHJ1tuZhpRqgoub1Nfao (same URL, omit
   capabilities so db + user carry forward). If refused because a newer version is live: read the saved source it gives you; if the
   live page is an earlier build of the same template (only its embedded data differs, or the live branch already has its template
   changes), publish again; otherwise publish nothing and report it.
7. Commit everything changed ("morning <date>", ending with the session's attribution trailer), `python3 scripts/check_secrets.py`,
   `git push -u origin claude/gallant-heisenberg-o7xbg9` (if rejected: `git pull --rebase origin claude/gallant-heisenberg-o7xbg9` and
   push again, rerun nothing).
8. Close captures. `python3 scripts/close_schedule.py --json` lists the next eight days' capture slots (ten minutes before each
   distinct kickoff). Call list_triggers (all pages). A slot is covered when an enabled scheduled task whose name starts "MLS close capture" has
   run_once_at equal to its capture_utc. For every slot not covered, create one with create_trigger: name "MLS close capture
   <capture_et> ET", run_once_at = capture_utc, create_new_session_on_fire true, initiation human_schedule, prompt:
   "MLS close capture (fixtures: <fixtures>). In /home/user/MLS-FUTURES (if it is not there, attach TheBallr/MLS-FUTURES with add_repo,
   access push, and clone it there) run `git fetch origin claude/gallant-heisenberg-o7xbg9 &&
   git checkout claude/gallant-heisenberg-o7xbg9 && git pull origin claude/gallant-heisenberg-o7xbg9 && python3 -m pip install -q -r
   requirements.txt`, then `python3 scripts/fetch_pinnacle.py --close`, commit data/market with a one-line message, run `python3
   scripts/check_secrets.py`, push with `git push -u origin claude/gallant-heisenberg-o7xbg9` (if rejected, `git pull --rebase origin
   claude/gallant-heisenberg-o7xbg9` and push again), and print one line per fixture captured. Nothing else."
9. Report in chat, under 300 words, from weekly.py's printout, outputs/latest/freshness.json and outputs/latest/morning.json:
   "MLS morning, <Day Mon D>"
   - Data: "all current" or each check that is warn/bad, one line each.
   - Games to look at: each game flagged watch or big: teams, date, our margin v Pinnacle's, the gap, the first reason.
   - Moved: futures moves of 2 points or more, rating moves of 0.03 or more, results since yesterday.
   - Hands: each hand adjustment in force and the report's verdict (keep / raise / trim / drop / too early).
   - Act: numbered proposals in the model's terms (e.g. "1. Messi MIA star, out Oct 20 to Nov 7") so Zac can reply "do 1, 3";
     "nothing to change" if none.
   - Injury list: the maintenance done.
   Then send a PushNotification (status proactive), one line under 200 characters: the single most important item, or "MLS: all
   current, nothing to change".
