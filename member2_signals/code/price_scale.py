"""Price-scale diagnostics using the same cross-sectional cleaning as the main run."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from run_pool import rank_ic, stats, STAGES, zscore

def run(data, out):
    def read(k): return pd.read_parquet(data/f'matrix_{k}.parquet')
    cols=['open','close','close_hfq','high','low','amount','volume']
    panel=pd.read_parquet(data/'clean_daily_panel.parquet',columns=['trade_date','stock_code','is_suspended','tradestatus','sw_l1_name']+['raw_valid_'+x for x in cols])
    def wide(k): return panel.pivot(index='trade_date',columns='stock_code',values=k)
    valid=wide('tradestatus').astype(str).isin(['1','1.0','True']) & wide('is_suspended').eq(False) & read('volume').gt(0)
    for k in cols: valid &= wide('raw_valid_'+k).eq(True)
    mask=valid&read('tradable_mask').eq(True)
    close,op,high,low=[read(k+'_hfq').where(valid) for k in ['close','open','high','low']]
    size=read('ln_float_mv_proxy')
    group=wide('sw_l1_name').fillna('未分类')
    dv=np.sign(read('volume').where(valid).diff())
    raw={'012_original':-dv*close.diff(),'012_relative':-dv*close.pct_change(fill_method=None),
         '101_original':(close-op)/(high-low+.001),'101_relative':(close/op-1)/((high-low)/op+.001)}
    rows=[]
    for name,f in raw.items():
        x=f.where(mask)
        med=x.median(axis=1)
        sc=x.sub(med,axis=0).abs().median(axis=1)*1.4826
        sc=sc.where(sc>1e-12,(x.quantile(.75,axis=1)-x.quantile(.25,axis=1))/1.349)
        x=x.clip(med-5*sc,med+5*sc,axis=0)
        result=np.full(x.shape,np.nan)
        for i in range(len(x)):
            y=x.iloc[i].to_numpy()
            s=size.iloc[i].to_numpy()
            ok=np.isfinite(y)&np.isfinite(s)
            if ok.sum()<30: continue
            g=pd.Categorical(group.iloc[i][ok]).codes
            count=np.bincount(g)
            if ok.sum()<=len(count)+11: continue
            a=y[ok]-np.bincount(g,weights=y[ok])[g]/count[g]
            v=s[ok]-np.bincount(g,weights=s[ok])[g]/count[g]
            if v@v>1e-12: a-=v*((v@a)/(v@v))
            if a.std(ddof=1)>1e-10: result[i,ok]=a/a.std(ddof=1)
        f=pd.DataFrame(result,index=x.index,columns=x.columns).astype('float32')
        for h in [5,20]:
            s=rank_ic(f,op.shift(-h-1)/op.shift(-1)-1)
            exit_date=pd.Series(s.index,index=s.index).shift(-h-1)
            for stage,(start,end) in STAGES.items():
                rows.append(dict(variant=name,horizon=h,stage=stage,**stats(s[(s.index>=start)&exit_date.le(end)],h)))
    pd.DataFrame(rows).to_csv(out/'results'/'price_scale_check.csv',index=False)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.data,a.out)
