#!/usr/bin/env python3
"""Before every run: read settings/pending and settings/pending.scenario from the artifact's database (exported by the
session to outputs/latest/pending_settings.json via the ArtifactData tool), apply knobs/sources/scenario to config and CSVs
on Zac's saved word, then mark them applied. Without a pending file it prints one line.
The session, not this script, talks to the artifact database: it writes the two documents to the JSON file first."""
import datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sim import data
from sim.teams import ROOT, canon

PENDING = os.path.join(ROOT, "outputs", "latest", "pending_settings.json")
FROZEN = {"rating_sd", "drift_k_sim", "drift_cap", "shared_goals_mean", "home_edge_goals", "avg_total_goals"}


def main():
    if not os.path.exists(PENDING):
        print("apply_site_settings: nothing pending"); return 0
    p = json.load(open(PENDING))
    applied = []
    cfg_path = os.path.join(ROOT, "config.json"); cfg = json.load(open(cfg_path))
    s = p.get("settings") or {}
    if s and not s.get("applied"):
        frozen_on = cfg.get("frozen", {}).get("frozen_on")
        for k, v in (s.get("knobs") or {}).items():
            if k in cfg["knobs"] and (k not in FROZEN or not frozen_on):
                cfg["knobs"][k]["value"] = v; cfg["knobs"][k]["note"] += f" | set from the site Settings tab {dt.date.today()}"; applied.append(f"knob {k}={v}")
            elif k in FROZEN:
                applied.append(f"knob {k} is frozen: not applied")
        src = s.get("sources") or {}
        if src:
            sc = data.load("source_config")
            for name, w in src.items():
                sc.loc[sc["source"] == name, "weight"] = float(w)
            data.save("source_config", sc); applied.append(f"source weights {src}")
        s["applied"] = dt.datetime.utcnow().isoformat() + "Z"
    sc_doc = p.get("scenario") or {}
    if sc_doc and not sc_doc.get("applied"):
        rows = sc_doc.get("rows") or ([sc_doc] if sc_doc.get("team") else [])
        scen = data.load("scenarios")
        for r in rows:
            team = canon(r["team"])
            scen = scen[scen["team"] != team] if r.get("replace", True) else scen
            if float(r.get("prob", 0)) > 0:
                scen = pd.concat([scen, pd.DataFrame([{"team": team, "type": r.get("type", "points"), "prob": r.get("prob"), "mean": r.get("mean", r.get("size", 0)),
                                                       "sd": r.get("sd", r.get("spread", 0)), "min": r.get("min", 0), "from": r.get("from", ""), "to": r.get("to", ""),
                                                       "note": f"site {dt.date.today()}: {r.get('note', '')}"}])], ignore_index=True)
            applied.append(f"scenario {team} {r.get('type')} p={r.get('prob')}")
        data.save("scenarios", scen); sc_doc["applied"] = dt.datetime.utcnow().isoformat() + "Z"
    # Ratings-tab hand edits live inside settings/pending (keys adjustments / adjustments_saved_at / adjustments_applied, the document the
    # routine already exports); a separate settings/pending.adjustments document is accepted too
    ad = p.get("adjustments") or {}
    if not ad and s and s.get("adjustments") and not s.get("adjustments_applied"):
        ad = {"adjustments": s["adjustments"], "saved_at": s.get("adjustments_saved_at", ""), "_in_settings": True}
    if ad and not ad.get("applied"):  # one open-ended (rating-level) row per club; 0 removes the club's row
        adj = data.load("adjustments")
        today = dt.date.today().isoformat()
        for team, goals in (ad.get("adjustments") or {}).items():
            t = canon(team, strict=False)
            if not t:
                applied.append(f"adjustment: unknown club {team}"); continue
            keep = ~((adj["team"] == t) & (adj["to"].astype(str).str.strip() == ""))
            adj = adj[keep]
            if abs(float(goals)) > 1e-9:
                adj = pd.concat([adj, pd.DataFrame([{"team": t, "goals": f"{float(goals):+.2f}", "from": today, "to": "", "reason": f"site Ratings tab {today} (saved {str(ad.get('saved_at',''))[:16]})", "date_set": today}])], ignore_index=True)
            applied.append(f"hand {t} {float(goals):+.2f}")
        data.save("adjustments", adj); ad["applied"] = dt.datetime.utcnow().isoformat() + "Z"
        if ad.get("_in_settings"):
            s["adjustments_applied"] = ad["applied"]
    json.dump(cfg, open(cfg_path, "w"), indent=2)
    json.dump(p, open(PENDING, "w"), indent=1)
    print("apply_site_settings: " + ("; ".join(applied) if applied else "nothing new"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
