"""Fixed diagnostic variants; never select parameters on post-2022 results."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from research import factors,clean,ic,label,phase,summary,savecsv
import matplotlib.pyplot as plt

def proportion_factors(m):
    c,o,h,l,v=[m[k] for k in ['close_hfq','open_hfq','high_hfq','low_hfq','volume']]
    return {'new012_return':-np.sign(v.diff())*(c/c.shift(1)-1),
            'new101_range':(c-o)/(h-l).where((h-l)>0)}

def drift(w,ret):
    gross=float(np.nansum(w*ret));return gross,w*(1+ret)/(1+gross)

def turnover(before,target):
    delta=target-before;return float(np.maximum(delta,0).sum()),float(np.maximum(-delta,0).sum())

def run(data,out):
    R=out/'results';S=out/'signals';cfg=json.loads((R/'model_config.json').read_text(encoding='utf8'))
    fields=['open_hfq','close_hfq','high_hfq','low_hfq','volume','returns','tradable_mask','ln_float_mv_proxy','is_limit_up','can_sell_held']
    m={k:pd.read_parquet(data/f'matrix_{k}.parquet').sort_index() for k in fields}
    for k in ['tradable_mask','can_sell_held']:m[k]=m[k].fillna(False).astype(bool)
    m['is_limit_up']=m['is_limit_up'].fillna(True).astype(bool)
    idx=m['open_hfq'].index;cols=m['open_hfq'].columns;opens=m['open_hfq'].copy()
    p=pd.read_parquet(data/'clean_daily_panel.parquet')
    def pivot(k):return p.pivot(index='trade_date',columns='stock_code',values=k).reindex(index=idx,columns=cols)
    valid=~pivot('is_suspended').fillna(True).astype(bool)
    for k in ['open','close','high','low','volume']:valid &= pivot('raw_valid_'+k).fillna(False).astype(bool)
    valid &= m['volume']>0;m['mask']=m['tradable_mask']&valid
    industry=pivot('industry_scheme').fillna('未知')+':'+pivot('sw_l1_name').fillna('未分类')
    known=pivot('sw_l1_name').notna()&pivot('sw_l1_name').ne('未分类');size=m['ln_float_mv_proxy']
    for k in ['open_hfq','close_hfq','high_hfq','low_hfq','volume','returns']:m[k]=m[k].where(valid)
    raw=factors(m);variants=proportion_factors(m)
    z={k:pd.read_parquet(S/f'factor_{k}.parquet') for k in raw}
    for k,v in variants.items():z[k]=clean(v,m['mask'],size,industry,True);z[k].astype('float32').to_parquet(S/f'diagnostic_{k}.parquet')
    rows=[]
    for h in [1,5,20]:
        y=label(opens.where(valid),h);end=pd.Series(idx,index=idx).shift(-h-1)
        for k in ['alpha012','new012_return','alpha101','new101_range']:
            s=ic(z[k],y)
            for per,lo,hi in [('train','2019-01-01','2022-12-31'),('validation','2023-01-01','2024-12-31'),('test','2025-01-01','2026-10-30')]:
                q=s[(idx>=lo)&(idx<=hi)&end.le(hi)&end.notna()]
                rows.append(dict(factor=k,horizon=h,period=per,**summary(q,lag=max(5,h))))
    savecsv(pd.DataFrame(rows),R/'proportional_ic.csv')
    # Rescale each stock by a time-constant positive multiplier. Price units should not matter for ratios.
    mult=pd.Series(np.geomspace(.1,10,len(cols)),index=cols);scaled=m.copy()
    for k in ['open_hfq','close_hfq','high_hfq','low_hfq']:scaled[k]=m[k].mul(mult,axis=1)
    scale_rows=[];changed={**factors(scaled),**proportion_factors(scaled)}
    for k,a in {**raw,**variants}.items():
        b=changed[k];both=(a.notna()&b.notna()&m['mask']);delta=(a-b).abs().where(both)
        same=np.isclose(a.to_numpy(),b.to_numpy(),atol=1e-10,rtol=1e-8)&both.to_numpy()
        scale_rows.append(dict(factor=k,rank_correlation_mean=ic(a.where(both),b.where(both)).mean(),changed_fraction=1-same.sum()/both.sum().sum(),max_absolute_change=delta.max().max()))
    savecsv(pd.DataFrame(scale_rows),R/'price_unit_stress.csv')
    eps=.001/(m['high_hfq']-m['low_hfq']+.001)
    eps=eps.where(m['mask']&((m['high_hfq']-m['low_hfq'])>0)).stack().dropna()
    savecsv(eps.quantile([.5,.95,.99,1]).to_frame('relative_epsilon_effect'),R/'alpha101_epsilon_effect.csv')
    # Hold final selected factors/directions fixed, changing only industry coverage.
    base=sum(pd.read_parquet(S/f'factor_{k}.parquet').astype(float) for k in ['bp','ep','small'])/3
    alpha=sum(cfg['directions'][k]*z[k] for k in cfg['selected'])/len(cfg['selected'])
    common=base.notna()&alpha.notna();base=base.where(common);alpha=alpha.where(common)
    y=label(opens.where(valid),5);end=pd.Series(idx,index=idx).shift(-6)
    sets={'unknown_group':(base,.5*base+.5*alpha)}
    kz={k:clean(raw[k],m['mask']&known,size,industry,True) for k in cfg['selected']}
    ka=sum(cfg['directions'][k]*kz[k] for k in cfg['selected'])/len(cfg['selected']);kb=base.where(ka.notna());sets['known_only']=(kb,.5*kb+.5*ka)
    pair_rows=[];ind_rows=[]
    for method,(b,s) in sets.items():
        ib=ic(b,y);irs=ic(s,y)
        for per,lo,hi in [('validation','2023-01-01','2024-12-31'),('test','2025-01-01','2026-10-30')]:
            ok=(idx>=lo)&(idx<=hi)&end.le(hi)&end.notna()
            pair_rows.append(dict(method=method,period=per,**summary((irs-ib)[ok])))
            for name,v,x in [('baseline',ib,b),('research',irs,s)]:ind_rows.append(dict(method=method,period=per,model=name,average_names=x[ok].notna().sum(axis=1).mean(),**summary(v[ok])))
    savecsv(pd.DataFrame(pair_rows),R/'paired_model_ic_test.csv');savecsv(pd.DataFrame(ind_rows),R/'industry_sensitivity.csv')
    # Full fixed grid is diagnostic. Full-fill open prices are a counterfactual, not an execution engine.
    valuation=opens.where(valid).ffill().to_numpy(float);buy=(m['tradable_mask']&~m['is_limit_up']&valid).to_numpy();sell=m['can_sell_held'].fillna(False).to_numpy()
    obs=[]
    for aweight in [0.,.25,.5,.75]:
        score=(1-aweight)*base+aweight*alpha
        for freq in [5,10,20]:
            before=np.zeros(len(cols));prev=None
            for t in range(20,len(idx)-freq-1,freq):
                per=phase(idx[[t]])[0]
                if per=='train' or per!=phase(idx[[t+freq+1]])[0]:continue
                if per!=prev:before=np.zeros(len(cols));prev=per
                selected=score.iloc[t].dropna().sort_values(ascending=False,kind='stable').head(50)
                if len(selected)==0:continue
                w=np.zeros(len(cols));w[cols.get_indexer(selected.index)]=1/len(selected)
                start,endpos=t+1,t+freq+1
                prices=valuation[[start,endpos]];held=(w>0)|(before>0)
                if not np.isfinite(prices[:,held]).all():raise ValueError('Unpriced held stock; requires explicit handling')
                ret=np.divide(prices[1],prices[0],out=np.ones(len(cols)),where=np.isfinite(prices).all(axis=0))-1
                B,D=turnover(before,w);delta=w-before
                blocked_buy=np.maximum(delta,0)[~buy[start]].sum();blocked_sell=np.maximum(-delta,0)[~sell[start]].sum()
                gross,after=drift(w,ret)
                stale_entry=w[~valid.iloc[start].to_numpy()].sum();stale_exit=w[~valid.iloc[endpos].to_numpy()].sum()
                obs.append(dict(alpha_weight=aweight,rebalance=freq,period=per,signal_date=idx[t],execution_date=idx[start],exit_date=idx[endpos],gross_return=gross,buy_weight=B,sell_weight=D,traded_weight=B+D,blocked_buy_weight=blocked_buy,blocked_sell_weight=blocked_sell,stale_entry_weight=stale_entry,stale_exit_weight=stale_exit))
                before=after
    obs=pd.DataFrame(obs);savecsv(obs,R/'cost_interval_observations.csv');cost_rows=[]
    for (aw,freq,per),d in obs.groupby(['alpha_weight','rebalance','period']):
        n=len(d);days=n*freq;gross_ann=np.exp(np.log1p(d.gross_return).sum()*252/days)-1
        for bp in [0,5,10,20,50]:
            net=(1+d.gross_return)*(1-bp/10000*d.traded_weight)-1
            ann=np.exp(np.log1p(net).sum()*252/days)-1
            cost_rows.append(dict(alpha_weight=aw,rebalance=freq,period=per,cost_bp=bp,intervals=n,start=d.execution_date.min(),end=d.exit_date.max(),gross_annualized=gross_ann,net_annualized=ann,annual_return_drag=gross_ann-ann,mean_traded_weight=d.traded_weight.mean(),annual_traded_weight=d.traded_weight.sum()*252/days,blocked_trade_fraction=(d.blocked_buy_weight.sum()+d.blocked_sell_weight.sum())/d.traded_weight.sum(),max_stale_weight=max(d.stale_entry_weight.max(),d.stale_exit_weight.max())))
    costs=pd.DataFrame(cost_rows);savecsv(costs,R/'cost_sensitivity.csv')
    fig,axs=plt.subplots(1,2,figsize=(10,4),sharey=True)
    for ax,per in zip(axs,['validation','test']):
        for aw in [0,.25,.5,.75]:
            d=costs[(costs.period==per)&(costs.rebalance==5)&(costs.alpha_weight==aw)]
            ax.plot(d.cost_bp,100*d.net_annualized,marker='o',label=f'alpha weight {aw:.0%}')
        ax.set_title(per+' (ideal full fills)');ax.set_xlabel('Assumed cost per traded value (bp)');ax.legend(fontsize=8);ax.axhline(0,color='gray',lw=.7)
    axs[0].set_ylabel('Diagnostic annualized net return (%)');fig.tight_layout();fig.savefig(out/'figures/05_cost_sensitivity.png',dpi=180);plt.close(fig)
    print(pd.DataFrame(pair_rows).to_string(index=False));print(costs[(costs.alpha_weight.isin([0,.5]))&(costs.rebalance==5)&(costs.cost_bp==10)].to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();run(a.data,a.out)
