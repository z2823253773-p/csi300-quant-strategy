import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from operators import evaluate, parse
from run_pool import STAGES, rank_ic, stats, zscore

def finish(data, signals, results, cache, config, picked, read, clean, mask, env, size, labels, period, dates, codes, valid):
    bp,ep=read('bp'),read('ep')
    r=env['returns']
    turn=read('turn').where(valid)
    impulse=-np.sign(env['amount'].diff())*r
    factors={
        'bp':clean(bp,False),'ep':clean(ep,False),'small':clean(-size,False),
        'new012_amt_ema10':clean(impulse.ewm(span=10,min_periods=5,adjust=True,ignore_na=False).mean().where(impulse.notna())),
        'lowvol_60':clean(-r.rolling(60,min_periods=40).std()),
        'lowturn_20':clean(-np.log(turn.rolling(20,min_periods=15).mean().where(lambda x:x>0))),
        'eb_proxy':clean(ep/bp.where(bp>0)),
    }
    for num in sorted({6,16,33,40,*picked}):
        factors[f'alpha{num:03}']=pd.read_parquet(cache/f'{num}.parquet')
    for name,x in factors.items():
        x.to_parquet(signals/f'factor_{name}.parquet')
    anchor=(factors['bp']+factors['ep']+factors['small'])/3
    old=.5*anchor+.25*factors['alpha006']+.25*factors['alpha033']
    active=['bp','ep','small','new012_amt_ema10','lowvol_60','lowturn_20','eb_proxy']+[f'alpha{n:03}' for n in picked]
    common=mask.copy()
    for name in active: common &= factors[name].notna()
    common.to_parquet(signals/'common.parquet')
    v=zscore(((factors['bp']+factors['ep'])/2).where(common))
    scores={'M0a':anchor.where(old.notna()),'M0b':old,'M1':anchor.where(common),'M2':v,
            'M3a':(.9*anchor+.1*sum(picked.values())/len(picked)).where(common) if picked else anchor.where(common),
            'M3b':.85*v+.15*factors['new012_amt_ema10'],
            'M4':((factors['bp']+factors['ep']+factors['lowvol_60']+factors['lowturn_20'])/4).where(common),
            'M5':((factors['bp']+factors['ep']+factors['lowvol_60']+factors['lowturn_20']+factors['eb_proxy'])/5).where(common)}
    target=[]
    first=dates.get_loc(pd.Timestamp('2023-01-06'))
    for model,x in scores.items():
        if not model.startswith('M0'): assert x.notna().equals(common)
        x.to_parquet(signals/f'score_{model}.parquet')
        previous=set()
        for i in range(first,len(dates)-1,5):
            ranked=x.iloc[i].dropna().sort_index().sort_values(ascending=False,kind='stable')
            kept=[] if model.startswith('M0') else [k for k in ranked.index[:75] if k in previous]
            chosen=kept+[k for k in ranked.index if k not in kept][:50-len(kept)]
            assert len(chosen)==50
            target.extend(dict(model=model,signal_date=dates[i],execution_date=dates[i+1],stock_code=k,
                               score=ranked[k],target_weight=1/len(chosen),stage='validation' if dates[i+1].year<=2024 else 'seen') for k in chosen)
            previous=set(chosen)
    tw=pd.DataFrame(target)
    assert not tw.duplicated(['model','execution_date','stock_code']).any()
    assert np.allclose(tw.groupby(['model','execution_date']).target_weight.sum(),1)
    tw.to_csv(signals/'target_weights_v3.csv',index=False)

    factor_rows=[]
    for name,x in factors.items():
        ac={h:rank_ic(x,x.shift(h)) for h in [5,20]}
        for h,y in labels.items():
            s=rank_ic(x,y)
            for stage,(start,end) in STAGES.items():
                ix=period(h,start,end)
                factor_rows.append(dict(factor=name,horizon=h,stage=stage,**stats(s[ix],h),
                                        **{f'ac_{k}d':a[(dates<=end)&pd.Series(dates,index=dates).shift(k).ge(start)].mean() for k,a in ac.items()}))
    pd.DataFrame(factor_rows).to_csv(results/'factor_ic_v3.csv',index=False)
    pairs=[('M2','M1'),('M3a','M1'),('M3b','M2'),('M4','M2'),('M5','M4'),('M0b','M0a')]
    paired=[]
    model_rows=[]
    for h,y in labels.items():
        daily=pd.DataFrame({k:rank_ic(x,y) for k,x in scores.items()})
        daily['label_exit']=pd.Series(dates,index=dates).shift(-h-1)
        daily.to_csv(results/f'daily_model_ic_{h}d.csv',index_label='trade_date')
        for stage,(start,end) in STAGES.items():
            ix=period(h,start,end)
            for k in scores:
                model_rows.append(dict(model=k,stage=stage,horizon=h,**stats(daily[k][ix],h)))
            for a,b in pairs:
                d=stats((daily[a]-daily[b])[ix],h)
                paired.append(dict(model_a=a,model_b=b,horizon=h,stage=stage,n=d['n'],mean_diff=d['mean_ic'],hac_t=d['hac_t'],hac_p=d['hac_p']))
    pd.DataFrame(paired).to_csv(results/'paired_ic_v3.csv',index=False)
    pd.DataFrame(model_rows).to_csv(results/'model_ic.csv',index=False)
    corr=[]
    names=list(factors)
    for i,a in enumerate(names):
        for b in names[i:]:
            s=rank_ic(factors[a],factors[b])
            for stage,sub in [('train',s.loc[:'2022']),('all',s)]:
                corr.append(dict(stage=stage,factor_a=a,factor_b=b,n_days=sub.count(),mean_rank_corr=sub.mean()))
    pd.DataFrame(corr).to_csv(results/'factor_corr_v3.csv',index=False)
    pd.DataFrame({'eligible':mask.sum(axis=1),'common':common.sum(axis=1)}).to_csv(results/'coverage.csv',index_label='trade_date')
    forms=json.loads((Path(__file__).parent/'expressions.json').read_text())
    cut=dates.get_loc(pd.Timestamp('2022-12-30'))+1
    for n in picked:
        ast=parse(forms[str(n)])
        def unused(*args): raise AssertionError('selected proxy factor')
        short=evaluate(ast,{k:v.iloc[:cut] for k,v in env.items()},mask.iloc[:cut],unused)
        full=evaluate(ast,env,mask,unused)
        np.testing.assert_allclose(short.iloc[-5:],full.iloc[cut-5:cut],equal_nan=True)
    hashes={f.name:hashlib.file_digest(f.open('rb'),'sha256').hexdigest() for f in sorted(data.glob('*.parquet'))}
    selected={str(n):int(np.sign(pd.read_csv(results/'selection.csv').set_index('id').loc[n,'mean_ic'])) for n in picked}
    settings=dict(data=config,sha256=hashes,selected_directions=selected,primary_horizon=5,stages=STAGES,
                  signal_anchor='2023-01-06',frequency=5,keep=75,top=50,buffer_state='prev_target',
                  model_formulas={'M0a':'B on M0b support','M0b':'0.5B+0.25A006+0.25A033','M1':'B=(bp+ep+small)/3',
                                  'M2':'Z((bp+ep)/2)','M3a':'0.9B+0.1 mean(signed selected); B if none','M3b':'0.85M2+0.15new012',
                                  'M4':'mean(bp,ep,lowvol,lowturn)','M5':'mean(bp,ep,lowvol,lowturn,eb)'})
    (results/'model_config_v3.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf8')
    print('DONE',config['universe_index'],selected,flush=True)
