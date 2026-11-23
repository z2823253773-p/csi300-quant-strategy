"""Member 2 research. Original implementation of cited Alpha101 formulas.
Run: python code/research.py --data PATH_TO_MEMBER1_PROCESSED
All fitted choices use 2019-2022 only; 2023-24 validation; 2025+ holdout.
"""
from pathlib import Path
import argparse, json, math, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ALPHAS=['alpha006','alpha012','alpha014','alpha033','alpha101']
def rank(x): return x.rank(axis=1, method='average', pct=True)
def factors(m):
    o,c,h,l,v,r=[m[k] for k in ['open_hfq','close_hfq','high_hfq','low_hfq','volume','returns']]
    # Missing/nontrading raw observations invalidate full rolling windows.
    corr=o.rolling(10,min_periods=10).corr(v).clip(-1,1)
    return {'alpha006':-corr, 'alpha012':-np.sign(v.diff())*c.diff(),
            'alpha014':-rank(r.diff(3).where(m['mask']))*corr,
            'alpha033':rank((o/c-1).where(m['mask'])),
            'alpha101':(c-o)/(h-l+0.001)}

def clean(x,mask,size,industry,neutral=False):
    a=x.where(mask).replace([np.inf,-np.inf],np.nan)
    med=a.median(axis=1); mad=a.sub(med,axis=0).abs().median(axis=1)
    # A degenerate MAD falls back to IQR; an entirely constant row stays missing.
    scale=1.4826*mad
    scale=scale.where(scale>1e-12,(a.quantile(.75,axis=1)-a.quantile(.25,axis=1))/1.349)
    a=a.clip(med-5*scale,med+5*scale,axis=0)
    if neutral:
        out=np.full(a.shape,np.nan)
        for t in range(len(a)):
            y=a.iloc[t].to_numpy(float); s=size.iloc[t].to_numpy(float)
            ok=np.isfinite(y)&np.isfinite(s)&industry.iloc[t].notna().to_numpy()
            if ok.sum()<30: continue
            d=pd.get_dummies(industry.iloc[t][ok],dtype=float).to_numpy()
            sv=s[ok]; sv=(sv-sv.mean())/(sv.std()+1e-12)
            X=np.column_stack([d,sv]); beta,_,rk,_=np.linalg.lstsq(X,y[ok],rcond=None)
            if ok.sum()<=rk+10: continue
            out[t,ok]=y[ok]-X@beta
        a=pd.DataFrame(out,index=a.index,columns=a.columns)
    return a.sub(a.mean(axis=1),axis=0).div(a.std(axis=1).replace(0,np.nan),axis=0)

def hac(x,lag=5):
    x=x.dropna().to_numpy(); n=len(x)
    if n<20:return np.nan,np.nan
    z=x-x.mean(); lr=z@z/n
    for k in range(1,lag+1):lr+=2*(1-k/(lag+1))*(z[k:]@z[:-k])/n
    t=x.mean()/np.sqrt(max(lr,1e-20)/n)
    return t,math.erfc(abs(t)/np.sqrt(2))

def ic(x,y):
    ok=x.notna()&y.notna(); a=x.where(ok); b=y.where(ok)
    return a.rank(axis=1).corrwith(b.rank(axis=1),axis=1).where(ok.sum(axis=1)>=30)

def label(o,h): return o.shift(-(h+1))/o.shift(-1)-1
def phase(d):return np.where(d.year<=2022,'train',np.where(d.year<=2024,'validation','test'))
def summary(s,lag=5):
    t,p=hac(s,lag); sd=s.std()
    return dict(n=int(s.count()),mean=s.mean(),std=sd,icir=s.mean()/sd if sd else np.nan,
                positive_ratio=(s.dropna()>0).mean(),hac_t=t,hac_p=p)
def savecsv(df,p):df.to_csv(p,index=True,encoding='utf-8-sig')

def main(data,out):
    for x in ['results','figures','signals']: (out/x).mkdir(parents=True,exist_ok=True)
    metadata=json.loads((data/'RUN_METADATA.json').read_text(encoding='utf-8'))
    if metadata.get('mode')!='online':raise ValueError('Requires online market data')
    m={k:pd.read_parquet(data/f'matrix_{k}.parquet').sort_index() for k in ['open_hfq','close_hfq','high_hfq','low_hfq','volume','returns','tradable_mask','ln_float_mv_proxy','bp','ep']}
    idx=m['close_hfq'].index; cols=m['close_hfq'].columns
    assert all(x.index.equals(idx) and x.columns.equals(cols) for x in m.values())
    panel=pd.read_parquet(data/'clean_daily_panel.parquet',columns=['trade_date','stock_code','industry_scheme','sw_l1_name','is_suspended','raw_valid_open','raw_valid_close','raw_valid_high','raw_valid_low','raw_valid_volume'])
    assert not panel.duplicated(['trade_date','stock_code']).any()
    def pivot(k):return panel.pivot(index='trade_date',columns='stock_code',values=k).reindex(index=idx,columns=cols)
    industry=pivot('industry_scheme').fillna('未知')+':'+pivot('sw_l1_name').fillna('未分类')
    valid=(~pivot('is_suspended').fillna(True).astype(bool))
    for k in ['open','close','high','low','volume']:valid &= pivot('raw_valid_'+k).fillna(False).astype(bool)
    valid &= m['volume']>0
    m['mask']=m['tradable_mask'].fillna(False).astype(bool)&valid
    open_label=m['open_hfq'].where(valid)
    # Price history is not cut at index-entry dates; only cross-section ranks use today's universe.
    for k in ['open_hfq','close_hfq','high_hfq','low_hfq','volume','returns']:m[k]=m[k].where(valid)
    raw=factors(m); size=m['ln_float_mv_proxy']; mask=m['mask']
    z={k:clean(v,mask,size,industry,True) for k,v in raw.items()}
    pre={k:clean(v,mask,size,industry,False) for k,v in raw.items()}
    for k in ['bp','ep']:z[k]=clean(m[k],mask,size,industry,False)
    z['small']=clean(-size,mask,size,industry,False)
    ys={h:label(open_label,h) for h in [1,5,20]}
    # Purge observations whose label exits the assigned period.
    ends={h:pd.Series(idx,index=idx).shift(-(h+1)) for h in ys}
    splits=pd.Series(phase(idx),index=idx)
    records=[]; daily={}
    for h,y in ys.items():
        for k in ALPHAS:
            for stage,mat in [('raw_z',pre[k]),('neutral',z[k])]:
                s=ic(mat,y); daily[k,stage,h]=s
                for period in ['train','validation','test']:
                    ok=(splits==period)&(pd.Series(phase(pd.DatetimeIndex(ends[h].fillna(pd.Timestamp('2100-01-01')))),index=idx)==period)&ends[h].notna()
                    row=dict(factor=k,stage=stage,horizon=h,period=period,**summary(s[ok],lag=max(5,h))); records.append(row)
    stats=pd.DataFrame(records)
    # Holm family-wise correction on the five training hypotheses at primary horizon.
    train=stats.query("stage=='neutral' and horizon==5 and period=='train'").set_index('factor').copy()
    order=train.hac_p.sort_values().index; adj=0.
    for j,k in enumerate(order):adj=max(adj,min(1.,(len(order)-j)*train.loc[k,'hac_p'])); train.loc[k,'holm_p']=adj
    corr=pd.DataFrame(index=ALPHAS,columns=ALPHAS,dtype=float)
    for a in ALPHAS:
        for b in ALPHAS:corr.loc[a,b]=ic(z[a].loc[:'2022-12-31'],z[b].loc[:'2022-12-31']).mean()
    selected=[]; signs={}; reasons={}
    for k in train['mean'].abs().sort_values(ascending=False).index:
        if not np.isfinite(train.loc[k,'holm_p']) or train.loc[k,'holm_p']>.05:reasons[k]='Holm p > 0.05';continue
        if any(abs(corr.loc[k,b])>=.7 for b in selected):reasons[k]='absolute training correlation >= 0.7';continue
        if len(selected)>=3:reasons[k]='maximum 3 factors';continue
        selected.append(k);signs[k]=1 if train.loc[k,'mean']>=0 else -1;reasons[k]='selected'
    train['decision']=pd.Series(reasons);train['direction']=pd.Series(signs)
    baseline=(z['bp']+z['ep']+z['small'])/3
    alpha=sum(signs[k]*z[k] for k in selected)/len(selected) if selected else baseline*0
    enhanced=.5*baseline+.5*alpha if selected else baseline.copy()
    # Both models use identical eligible names each day.
    common=baseline.notna()&enhanced.notna();baseline=baseline.where(common);enhanced=enhanced.where(common)
    models={'baseline':baseline,'research':enhanced}
    model_rows=[]; group_rows=[]
    for name,x in {**{k:z[k] for k in ALPHAS},**models}.items():
        s=ic(x,ys[5]);savecsv(s.to_frame('rank_ic_5d'),out/'results'/f'ic_{name}.csv')
        for period in ['train','validation','test']:
            ok=(splits==period)&ends[5].notna()&(pd.Series(phase(pd.DatetimeIndex(ends[5].fillna(pd.Timestamp('2100-01-01')))),index=idx)==period)
            model_rows.append(dict(model=name,period=period,**summary(s[ok])))
        # Every 5 trading days, fixed origin; equal-count sorting, code is deterministic tie breaker.
        for t in range(20,len(idx)-6,5):
            if splits.iloc[t]!=splits.iloc[t+6]:continue
            a=x.iloc[t]; y=ys[5].iloc[t]; ok=a.notna()
            if ok.sum()<50:continue
            ranks=a[ok].rank(method='first',pct=True); groups=np.minimum(np.ceil(ranks*5),5)
            for q in range(1,6):
                yy=y[ok][groups==q]
                group_rows.append(dict(date=idx[t],model=name,period=splits.iloc[t],group=q,mean_return=yy.mean(),n=yy.count(),n_signal=len(yy),missing_labels=yy.isna().sum()))
    groups=pd.DataFrame(group_rows); modelstats=pd.DataFrame(model_rows)
    savecsv(stats,out/'results'/'factor_tests.csv');savecsv(train,out/'results'/'selection.csv');savecsv(corr,out/'results'/'training_correlation.csv')
    savecsv(modelstats,out/'results'/'model_ic.csv');savecsv(groups,out/'results'/'quintile_observations.csv')
    g=groups.groupby(['model','period','group']).mean(numeric_only=True);savecsv(g,out/'results'/'quintile_summary.csv')
    for k,v in z.items():v.astype('float32').to_parquet(out/'signals'/f'factor_{k}.parquet')
    for name,x in models.items():
        # Do not release training scores based on end-of-training selections as tradable history.
        x=x.loc['2023-01-01':];x.astype('float32').to_parquet(out/'signals'/f'score_{name}.parquet')
    schedule=[]
    for t in range(20,len(idx)-1,5):
        if idx[t].year<2023:continue
        for name,x in models.items():
            top=x.iloc[t].dropna().sort_values(ascending=False,kind='stable').head(50)
            for code,score in top.items():schedule.append(dict(signal_date=idx[t],execution_date=idx[t+1],model=name,stock_code=code,score=score,target_weight=1/len(top),period=splits.iloc[t]))
    savecsv(pd.DataFrame(schedule),out/'signals'/'target_weights.csv')
    coverage=pd.DataFrame({k:v.notna().sum(axis=1)/mask.sum(axis=1) for k,v in z.items()});savecsv(coverage,out/'results'/'coverage.csv')
    config=dict(selected=selected,directions=signs,train_end='2022-12-31',validation_end='2024-12-31',test_start='2025-01-01',horizon=5,rebalance=5,top_n=50,alpha_weight=.5,selection='Holm p<=0.05, abs corr<0.7, max3; primary 5d neutral RankIC',metadata=metadata)
    (out/'results'/'model_config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(data.glob('*.parquet'))+[data/'RUN_METADATA.json']}
    (out/'results'/'input_sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'figure.dpi':150})
    fig,ax=plt.subplots(figsize=(9,4));q=stats.query("stage=='neutral' and horizon==5").pivot(index='factor',columns='period',values='mean');q[['train','validation','test']].plot.bar(ax=ax);ax.axhline(0,color='black',lw=.7);ax.set_ylabel('Mean 5-day Rank IC (original direction)');ax.set_title('Factor stability by period');plt.xticks(rotation=0);fig.tight_layout();fig.savefig(out/'figures'/'01_factor_ic.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,5));im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(5),ALPHAS,rotation=30);ax.set_yticks(range(5),ALPHAS)
    for i in range(5):
        for j in range(5):ax.text(j,i,f'{corr.iloc[i,j]:.2f}',ha='center',va='center',color='black')
    fig.colorbar(im,ax=ax);ax.set_title('Training mean cross-sectional Spearman correlation');fig.tight_layout();fig.savefig(out/'figures'/'02_correlation.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4))
    for name in models:
        s=pd.read_csv(out/'results'/f'ic_{name}.csv',index_col=0,parse_dates=True).iloc[:,0].loc['2023-01-01':];s.rolling(60,min_periods=40).mean().plot(ax=ax,label=name)
    ax.axvline(pd.Timestamp('2025-01-01'),color='gray',ls='--');ax.axhline(0,color='black',lw=.7);ax.legend();ax.set_ylabel('60-day mean Rank IC');ax.set_title('Frozen models: validation and holdout');fig.tight_layout();fig.savefig(out/'figures'/'03_model_ic.png');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(10,4),sharey=True)
    for ax,period in zip(axs,['validation','test']):
        for name in models:ax.plot(range(1,6),g.loc[(name,period),'mean_return']*100,marker='o',label=name)
        ax.set_title(period);ax.set_xlabel('Score quintile (5 = highest)');ax.legend();ax.axhline(0,color='gray',lw=.6)
    axs[0].set_ylabel('Mean 5-day gross forward return (%)');fig.tight_layout();fig.savefig(out/'figures'/'04_quintiles.png');plt.close(fig)
    # Future perturbation: outputs prior to cutoff must be unchanged.
    cut=500;short={k:v.iloc[:cut+1] for k,v in m.items()};fr=factors(short)
    for k in ALPHAS:np.testing.assert_allclose(fr[k].iloc[-1],raw[k].iloc[cut],equal_nan=True)
    testlog={'matrix_alignment':'PASS','unique_panel_keys':'PASS','factor_prefix_causality':'PASS','label_alignment':'PASS','released_scores_start':'2023-01-03 or first available 2023 session','selected':selected}
    np.testing.assert_allclose(ys[5].iloc[30].to_numpy(),(open_label.iloc[36]/open_label.iloc[31]-1).to_numpy(),equal_nan=True)
    (out/'results'/'verification.json').write_text(json.dumps(testlog,indent=2),encoding='utf-8')
    print(json.dumps(config,ensure_ascii=False));print(modelstats.to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();main(a.data,a.out)
