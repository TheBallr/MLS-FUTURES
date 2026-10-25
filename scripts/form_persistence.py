import sys, numpy as np, pandas as pd
sys.path.insert(0,'/home/user/MLS-FUTURES')
from sim.knobs import load_config, knobs
from sim import data
from scripts.refresh_ratings import closes_with_targets
from scripts.close_track import obs_cached
from sim.kalman import KalmanRatings
from sim.ratings import load_club_home_edges
cfg=load_config(); kn=knobs(cfg)
cl=closes_with_targets(cfg); cl=cl[cl.season.astype(str)!='posted'].dropna(subset=['gd_fit'])
h=data.load_history()[['date','home','away','hg','ag']]; r=data.load('results'); r=r[r.competition.isin(['MLS',''])][['date','home','away','hg','ag']]
res=pd.concat([h,r]).drop_duplicates(['date','home','away']); res['date']=pd.to_datetime(res.date).dt.strftime('%Y-%m-%d')
for c in('hg','ag'): res[c]=pd.to_numeric(res[c],errors='coerce')
xg=data.num(data.load('xg_history'),['home_xg','away_xg']); xg['date']=pd.to_datetime(xg.date).dt.strftime('%Y-%m-%d')
deltas=load_club_home_edges(True)
obs=obs_cached(cl,False,0.0,None,deltas,0.0,None)
uni=sorted(set(obs.home)|set(obs.away))
knk={"q_day":kn["kalman_q_day"],"s":kn["kalman_s"],"p0":kn["kalman_p0"],"q_off":kn["kalman_q_off"],"prior_new":kn["expansion_prior_rating"],"off_shrink":kn["kalman_off_shrink"]}
kf=KalmanRatings(uni,knk); rec=kf.run(obs,record=True)
d=obs.merge(rec[['date','home','away','pred']],on=['date','home','away']).merge(cl[['date','home','away','gd_fit']],on=['date','home','away']).merge(res,on=['date','home','away'],how='left').merge(xg[['date','home','away','home_xg','away_xg']],on=['date','home','away'],how='left')
d['close_resid']=d.y-d.pred            # close minus the morning state (Pinnacle's move beyond the state)
d['res_v_close']=(d.hg-d.ag)-d.gd_fit  # result v close
d['xg_v_close']=(d.home_xg-d.away_xg)-d.gd_fit
# per club rows
rows=[]
for side,sg in (('home',1),('away',-1)):
    t=d.copy(); t['team']=t[side]; t['rv']=sg*t.res_v_close; t['xv']=sg*t.xg_v_close; t['cm']=sg*t.gd_fit; t['cr']=sg*t.close_resid
    rows.append(t[['date','team','rv','xv','cm','cr']])
tm=pd.concat(rows).sort_values(['team','date']).reset_index(drop=True)
N=8
def trail(s): return s.shift(1).rolling(N,min_periods=N).mean()
def fwd(s): return s[::-1].shift(1).rolling(N,min_periods=4).mean()[::-1]
tm['rv8']=tm.groupby('team').rv.transform(trail); tm['xv8']=tm.groupby('team').xv.transform(trail); tm['cm8']=tm.groupby('team').cm.transform(trail)
tm['rv_next8']=tm.groupby('team').rv.transform(fwd); tm['cr_next8']=tm.groupby('team').cr.transform(fwd)
k=tm.dropna(subset=['rv8','xv8','cr','rv'])
print("club-matches", len(k))
import numpy.linalg as la
def reg(y,X,names):
    X=np.column_stack([np.ones(len(y))]+X); b,res_,_,_=la.lstsq(X,y,rcond=None); e=y-X@b; s2=(e@e)/(len(y)-X.shape[1]); se=np.sqrt(np.diag(s2*la.inv(X.T@X)))
    return ", ".join(f"{n} {bb:+.3f} (se {ss:.3f})" for n,bb,ss in zip(['const']+names,b,se))
print("next close v state ON trailing-8 results-v-close & xG-v-close:", reg(k.cr.values,[k.rv8.values,k.xv8.values],['res8','xg8']))
print("next RESULT v close ON trailing-8 results-v-close & xG-v-close:", reg(k.rv.values,[k.rv8.values,k.xv8.values],['res8','xg8']))
print("next RESULT v close ON xG-v-close alone:", reg(k.rv.values,[k.xv8.values],['xg8']))
# Vancouver-like bucket: trailing-8 close margin >= +0.5 (a big favourite in its lines), results v close <= -0.4 and xG v close <= -0.5
b=k[(k.cm8>=0.5)&(k.rv8<=-0.4)&(k.xv8<=-0.5)]
print(f"\nVAN-like slumps (fav by >=0.5/g over last 8, results <= -0.4 v close, xG <= -0.5 v close): n {len(b)}, clubs {b.team.nunique()}, seasons {b.date.str[:4].nunique()}")
print(f"  next close v state {b.cr.mean():+.3f} (se {b.cr.std()/np.sqrt(len(b)):.3f}); next result v close {b.rv.mean():+.3f} (se {b.rv.std()/np.sqrt(len(b)):.3f}); next-8 results v close {b.rv_next8.mean():+.3f}; next-8 close v state {b.cr_next8.mean():+.3f}")
b2=k[(k.cm8>=0.5)&(k.rv8<=-0.4)]
print(f"fav slump on results only: n {len(b2)}: next close v state {b2.cr.mean():+.3f} (se {b2.cr.std()/np.sqrt(len(b2)):.3f}), next result v close {b2.rv.mean():+.3f} (se {b2.rv.std()/np.sqrt(len(b2)):.3f}), next-8 results v close {b2.rv_next8.mean():+.3f}")
b3=k[(k.cm8>=0.5)&(k.xv8<=-0.5)]
print(f"fav slump on xG only: n {len(b3)}: next close v state {b3.cr.mean():+.3f} (se {b3.cr.std()/np.sqrt(len(b3)):.3f}), next result v close {b3.rv.mean():+.3f} (se {b3.rv.std()/np.sqrt(len(b3)):.3f}), next-8 results v close {b3.rv_next8.mean():+.3f}")
b4=k[(k.cm8>=0.5)]
print(f"all big favourites: n {len(b4)}: next result v close {b4.rv.mean():+.3f} (se {b4.rv.std()/np.sqrt(len(b4)):.3f})")
# late-season (Oct+) big favourites in a slump
b5=b2[b2.date.str[5:7].isin(['09','10'])]
print(f"fav slump Sep-Oct: n {len(b5)}: next result v close {b5.rv.mean():+.3f} (se {b5.rv.std()/np.sqrt(len(b5)):.3f}), next-8 {b5.rv_next8.mean():+.3f}")
# examples: list distinct club-seasons in b
ex=b.assign(season=b.date.str[:4]).groupby(['team','season']).agg(n=('rv','size'),first=('date','min'),rv8=('rv8','mean'),xv8=('xv8','mean'),next_res=('rv','mean')).reset_index()
print(ex.round(2).to_string(index=False))
