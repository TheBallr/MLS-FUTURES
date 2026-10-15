"""CLV log: the earliest run that saw a posted line is the opener view; once the close lands, record whether the close moved
the model's way and by how much. Attack threshold from config (0.15 goals)."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sim import data
from sim.knobs import load_config, knobs
from sim.ratings import gd_fit_row


def update_clv(preds: list[dict], run_stamp: str, asof: str):
    kn = knobs(load_config())
    log = data.load("clv_log")
    key = set(zip(log["date"], log["home"], log["away"]))
    new = []
    for p in preds:
        if p.get("g_pinn") in ("", None) or (p["date"], p["home"], p["away"]) in key:
            continue
        dis = float(p["g_model"]) - float(p["g_pinn"])
        new.append({"date": p["date"], "home": p["home"], "away": p["away"], "opener_run": run_stamp, "g_model_opener": p["g_model"], "g_pinn_opener": p["g_pinn"],
                    "g_pinn_close": "", "disagree": round(dis, 3), "attack": int(abs(dis) >= kn["clv_attack_threshold"]), "moved_our_way": "", "move_goals": "", "updated": asof})
    if new:
        log = pd.concat([log, pd.DataFrame(new)], ignore_index=True)
    # fill closes
    cl = data.load("closing_lines")
    if len(cl) and len(log):
        cl = cl.copy(); cl["_p"] = cl["book"].map({"pinnacle_close": 0, "pinnacle_last": 1}).fillna(2)
        cl = cl.sort_values("_p").drop_duplicates(["date", "home", "away"])
        cmap = {(r["date"], r["home"], r["away"]): r for r in cl.to_dict("records")}
        for i, r in log.iterrows():
            if str(r["g_pinn_close"]) != "":
                continue
            c = cmap.get((r["date"], r["home"], r["away"]))
            if not c:
                continue
            gf = gd_fit_row(c.get("h"), c.get("d"), c.get("a"), c.get("ah_line") or None, c.get("ah_home"), c.get("ah_away"), c.get("total_line") or None, c.get("over"), c.get("under"),
                            kn["avg_total_goals"], kn["goal_floor"], kn["shared_goals_mean"])
            if not np.isfinite(gf["gd_fit"]):
                continue
            close = float(gf["gd_fit"]); opener = float(r["g_pinn_opener"]); model = float(r["g_model_opener"])
            move = close - opener
            log.at[i, "g_pinn_close"] = str(round(close, 3)); log.at[i, "move_goals"] = str(round(move, 3))  # the log loads as text
            log.at[i, "moved_our_way"] = str(int(np.sign(move) == np.sign(model - opener))) if abs(model - opener) > 1e-9 and abs(move) > 1e-9 else ""
            log.at[i, "updated"] = asof
    data.save("clv_log", log)
    return log


def summary(log: pd.DataFrame) -> dict:
    d = log[(log["attack"].astype(str) == "1") & (log["moved_our_way"].astype(str) != "")]
    if len(d) == 0:
        return {"attacks_closed": 0}
    mw = d["moved_our_way"].astype(int)
    return {"attacks_closed": int(len(d)), "moved_our_way": float(mw.mean()), "mean_move": float(d["move_goals"].astype(float).abs().mean())}


if __name__ == "__main__":
    print(summary(data.load("clv_log")))
