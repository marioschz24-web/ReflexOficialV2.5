import datetime as dt, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from timesfm_forecast import synthetic, CATS
from statsforecast import StatsForecast
from statsforecast.models import AutoETS, SeasonalNaive, WindowAverage
from statsforecast.utils import ConformalIntervals
days,ser=synthetic(dt.date(2026,10,14))
df=pd.concat([pd.DataFrame({"unique_id":k,"ds":pd.to_datetime(days),"y":np.asarray(ser[k],float)}) for k in CATS])
sf=StatsForecast(models=[AutoETS(season_length=7),SeasonalNaive(season_length=7),WindowAverage(window_size=28,prediction_intervals=ConformalIntervals(h=7,n_windows=2))],freq="D")
cv=sf.cross_validation(df=df,h=7,n_windows=8,step_size=7,level=[80])
cv=cv.reset_index() if 'unique_id' not in cv.columns else cv
res={}
for m in ['AutoETS','SeasonalNaive','WindowAverage']:
    res[m+'_mae']=float(np.mean(np.abs(cv['y']-cv[m])))
cov=float(np.mean((cv['y']>=cv['AutoETS-lo-80'])&(cv['y']<=cv['AutoETS-hi-80'])))
# weekly totals all cats
cv['w']=cv['cutoff']
wk=cv.groupby('w').agg(y=('y','sum'),f=('AutoETS','sum'),n=('SeasonalNaive','sum'),a=('WindowAverage','sum'))
wape=float(np.mean(np.abs(wk['y']-wk['f'])/wk['y']))
wape_n=float(np.mean(np.abs(wk['y']-wk['n'])/wk['y']));wape_a=float(np.mean(np.abs(wk['y']-wk['a'])/wk['y']))
# daily totals coverage approx: per-day all cats
res.update(dict(cov80=cov,weeks=int(wk.shape[0]),n_points=int(cv.shape[0]),wape_week_ets=wape,wape_week_naive=wape_n,wape_week_avg=wape_a,
  week_err=[round(float(x),3) for x in (np.abs(wk['y']-wk['f'])/wk['y'])],
  hist_days=len(days),hist_start=str(days[0]),hist_end=str(days[-1])))
# last 28 days history daily total for the chart + percategory last 28
tot=np.sum([ser[k] for k in CATS],axis=0)
res['hist28']=[int(x) for x in tot[-28:]]
print(json.dumps(res,indent=1))
json.dump(res,open('bt.json','w'))
