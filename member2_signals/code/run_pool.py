"""Run one pool against the supplied processed directory."""
import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from operators import evaluate, parse

STAGES = {'train': ('2019-01-02','2022-12-31'), 'validation': ('2023-01-01','2024-12-31'),
          'seen': ('2025-01-01','2026-10-30')}

def rank_ic(x, y):
    ok = x.notna() & y.notna()
    a = x.where(ok).rank(axis=1).to_numpy()
    b = y.where(ok).rank(axis=1).to_numpy()
    n = ok.sum(axis=1).to_numpy()
    a = np.nan_to_num(a - (n[:,None]+1)/2)
    b = np.nan_to_num(b - (n[:,None]+1)/2)
    denom = np.sqrt((a*a).sum(1)*(b*b).sum(1))
    return pd.Series(np.divide((a*b).sum(1),denom,out=np.full(len(n),np.nan),
                               where=(denom>0)&(n>=30)), index=x.index)

def stats(s, lag):
    s = s.dropna()
    n = len(s)
    mean, sd = s.mean(), s.std()
    z = (s-mean).to_numpy()
    t = p = np.nan
    if n >= 20:
        variance = (z@z + sum(2*(1-k/(lag+1))*(z[k:]@z[:-k]) for k in range(1,lag+1)))/n
        if variance > 0:
            t = mean/np.sqrt(variance/n)
            p = math.erfc(abs(t)/np.sqrt(2))
    return dict(n=n,mean_ic=mean,std_ic=sd,icir=mean/sd if sd>0 else np.nan,
                pos_ratio=(s>0).mean(),hac_t=t,hac_p=p)

def zscore(frame):
    return frame.sub(frame.mean(axis=1),axis=0).div(frame.std(axis=1).where(lambda s:s>1e-10),axis=0)

def run(data, out, cache):
    config = json.loads((data/'RUN_METADATA.json').read_text(encoding='utf8'))
    assert config['source_variant'].startswith('tushare')
    signals, results = out/'signals', out/'results'
    for folder in [signals,results]: folder.mkdir(parents=True,exist_ok=True)
    def read(key): return pd.read_parquet(data/f'matrix_{key}.parquet').sort_index().sort_index(axis=1)
    mask = read('tradable_mask').fillna(False).astype(bool)
    dates, codes = mask.index, mask.columns
    assert dates.is_unique and dates.is_monotonic_increasing and codes.is_unique
    cols = ['open','close','close_hfq','high','low','volume','amount']
    panel = pd.read_parquet(data/'clean_daily_panel.parquet',columns=['trade_date','stock_code','is_suspended','sw_l1_name','tradestatus']+['raw_valid_'+k for k in cols])
    def wide(k): return panel.pivot(index='trade_date',columns='stock_code',values=k).reindex_like(mask)
    valid = wide('tradestatus').astype(str).isin(['1','1.0','True']) & ~wide('is_suspended').fillna(True).astype(bool)
    for key in cols: valid &= wide('raw_valid_'+key).eq(True)
    valid &= read('volume').gt(0)
    mask &= valid
    env = {k:read(k+'_hfq').where(valid) for k in ['open','high','low','close','vwap']}
    env.update({k:read(k).where(valid) for k in ['volume','amount']})
    env['returns'] = env['close'].pct_change(fill_method=None)
    size = read('ln_float_mv_proxy')
    env['cap'] = np.exp(size)
    sector = wide('sw_l1_name').fillna('未分类')
    groups = pd.Categorical(sector.to_numpy().ravel()).codes.reshape(mask.shape).astype(int)
    unknown = sector.eq('未分类').to_numpy()
    sizes = size.to_numpy()
    del panel
    def residual(frame,outer=False):
        vals=frame.to_numpy()
        outvals=np.full(vals.shape,np.nan)
        for i in range(len(vals)):
            ok=np.isfinite(vals[i]) & (np.isfinite(sizes[i]) if outer else ~unknown[i])
            if ok.sum()<30: continue
            g=groups[i,ok]
            count=np.bincount(g).clip(1)
            v=vals[i,ok]
            a=v-np.bincount(g,weights=v)[g]/count[g]
            if outer:
                s=sizes[i,ok]
                s=s-np.bincount(g,weights=s)[g]/count[g]
                ss=s@s
                if ok.sum()<=len(np.unique(g))+int(ss>1e-12)+10: continue
                if ss>1e-12: a-=s*((s@a)/ss)
                sd=a.std(ddof=1)
                if sd<1e-10: continue
                a/=sd
            outvals[i,ok]=a
        return pd.DataFrame(outvals,index=dates,columns=codes)
    def clean(raw,neutral=True):
        v=raw.where(mask).replace([np.inf,-np.inf],np.nan)
        med=v.median(axis=1)
        s=1.4826*v.sub(med,axis=0).abs().median(axis=1)
        s=s.where(s>1e-12,(v.quantile(.75,axis=1)-v.quantile(.25,axis=1))/1.349)
        v=v.clip(med-5*s,med+5*s,axis=0)
        return (residual(v,True) if neutral else zscore(v)).astype('float32')

    op=env['open']
    labels={h:op.shift(-h-1)/op.shift(-1)-1 for h in [5,20]}
    def period(h,start,end):
        return (dates>=start)&pd.Series(dates,index=dates).shift(-h-1).le(end)
    forms=json.loads((Path(__file__).parent/'expressions.json').read_text())
    assert set(map(int,forms))==set(range(1,102))
    rows=[]
    for key,expr in forms.items():
        with np.errstate(all='ignore'):
            factor=clean(evaluate(parse(expr),env,mask,residual))
        factor.to_parquet(cache/f'{key}.parquet')
        series=rank_ic(factor,labels[5])
        for stage,(start,end) in STAGES.items():
            ix=period(5,start,end)
            rows.append(dict(id=int(key),proxy=('indclass.' in expr.lower() or 'cap' in expr.lower()),
                             stage=stage,horizon=5,coverage=factor[ix].count().sum()/mask[ix].sum().sum(),**stats(series[ix],5)))
        if int(key)%10==0: print(config['universe_index'],key,flush=True)
    table=pd.DataFrame(rows)
    table.to_csv(results/'alpha101_ic.csv',index=False)
    train=table.query("stage=='train'").copy()
    order=train.hac_p.fillna(1).sort_values().index
    train.loc[order,'holm_p']=np.minimum(1,np.maximum.accumulate(train.loc[order,'hac_p'].fillna(1)*np.arange(101,0,-1)))
    picked={}
    for row in train.assign(strength=train.mean_ic.abs()).sort_values(['strength','id'],ascending=[False,True]).itertuples():
        if row.proxy: reason='proxy'
        elif row.n<600 or row.coverage<.60: reason='coverage'
        elif row.holm_p>.05: reason='holm'
        elif len(picked)>=3: reason='quota'
        else:
            x=pd.read_parquet(cache/f'{row.id}.parquet')
            if any(abs(rank_ic(x.loc[:'2022'],old.loc[:'2022']).mean())>=.70 for old in picked.values()): reason='correlated'
            else:
                picked[row.id]=x*np.sign(row.mean_ic)
                reason='selected'
        train.loc[row.Index,'decision']=reason
    train.to_csv(results/'selection.csv',index=False)
    from models import finish
    finish(data, signals, results, cache, config, picked, read, clean, mask, env, size, labels, period, dates, codes, valid)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as cache:
        run(args.data,args.out,Path(cache))


