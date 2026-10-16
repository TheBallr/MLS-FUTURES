"""Do Pinnacle's playoff closes price teams differently from their regular-season ratings (NBA-style), and do playoff
results beat those closes? Regular-season ratings fit on that season's regular-season closes only (hl 28, ridge 0.5, home
edge fitted), as of the day before the playoffs; control = the last 3 weeks of the regular season predicted the same way."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from scripts.replay import all_closes
from sim.data import load_history
from sim.ratings import market_fit
cl = all_closes().copy(); cl = cl[cl.season.isin([str(y) for y in range(2012, 2026) if y != 2020])]
hist = load_history(); hist = hist[hist.season.isin(cl.season.unique())].drop_duplicates(["date","home","away"]).copy()
hist["hg"] = pd.to_numeric(hist.hg, errors="coerce"); hist["ag"] = pd.to_numeric(hist.ag, errors="coerce")
rows = []
for s, hs in hist.groupby("season"):
    hs = hs.sort_values("date"); cnt = {}; po = []
    games = pd.concat([hs.home, hs.away]).value_counts(); quota = 34
    for r in hs.itertuples():
        cnt[r.home] = cnt.get(r.home, 0) + 1; cnt[r.away] = cnt.get(r.away, 0) + 1
        po.append(cnt[r.home] > quota and cnt[r.away] > quota)
    hs = hs.assign(playoff=po)
    p_start = hs[hs.playoff].date.min()
    if pd.isna(p_start): continue
    reg_end = hs[~hs.playoff].date.max()
    ctrl_start = (pd.Timestamp(reg_end) - pd.Timedelta(days=21)).strftime("%Y-%m-%d")
    c = cl[cl.season == s].merge(hs[["date", "home", "away", "hg", "ag", "playoff"]], on=["date", "home", "away"], how="left")
    T = sorted(set(c.home) | set(c.away))
    for label, asof, sel in (("control", ctrl_start, (c.date >= ctrl_start) & (c.playoff == False)), ("playoff", p_start, c.playoff == True)):
        reg = c[c.playoff == False]
        mk = market_fit(reg, T, asof, 28, 0.5, fit_home_edge=True, before=True)
        R = mk["ratings"]; he = mk.get("home_edge", 0.44)
        for r in c[sel].itertuples():
            if not np.isfinite(r.gd_fit): continue
            rows.append(dict(season=s, kind=label, date=r.date, home=r.home, away=r.away, pred=R[T.index(r.home)] - R[T.index(r.away)] if isinstance(R, (list, np.ndarray)) else R[r.home] - R[r.away],
                             he=he, close=float(r.gd_fit), hg=r.hg, ag=r.ag, ph=float(r.ph), pd_=float(r.pd), pa=float(r.pa)))
d = pd.DataFrame(rows); d["pred_full"] = d.pred + d.he
d.to_csv('/home/user/MLS-FUTURES/outputs/calibration/playoff_strength.csv', index=False)
for k, g in d.groupby("kind"):
    x = g.pred.values; y = g.close.values
    A = np.c_[np.ones_like(x), x]; b = np.linalg.lstsq(A, y, rcond=None)[0]
    res = y - g.pred_full.values
    print(f"{k}: n {len(g)}, close = {b[0]:+.3f} + {b[1]:.3f} x (rating gap); mean close-pred {res.mean():+.3f}; rmse {np.sqrt((res**2).mean()):.3f}; mean fitted home edge {g.he.mean():.3f}; mean |gap| {np.abs(x).mean():.3f}")
    # bootstrap slope se
    rng = np.random.default_rng(1); bs = []
    for _ in range(500):
        i = rng.integers(0, len(g), len(g)); bs.append(np.linalg.lstsq(A[i], y[i], rcond=None)[0][1])
    print(f"   slope se {np.std(bs):.3f}")
    gg = g.dropna(subset=["hg"]); m = (gg.hg - gg.ag).values; fav = np.sign(gg.close.values)
    print(f"   results: favourite (by close) margin beyond the close {np.mean((m - gg.close.values) * fav):+.3f} goals (se {np.std((m - gg.close.values) * fav)/np.sqrt(len(gg)):.3f}), n {len(gg)}")
    pfav = np.where(gg.close > 0, gg.ph, gg.pa); win = np.where(gg.close > 0, gg.hg > gg.ag, gg.ag > gg.hg)
    print(f"   favourite 90-min win rate {win.mean():.3f} vs close {pfav.mean():.3f}")
print(d[d.kind=='playoff'].groupby('season').size().to_dict())
