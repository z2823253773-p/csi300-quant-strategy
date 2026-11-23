"""Build the results chapter, figures and independent target-file checks."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
rows=['# 双股票池因子与模型检验','',
      '两个股票池各自筛选、各自建模。下表的 IC 是当日因子排名与随后持有期收益排名的截面相关，再按日期取平均。数值 0.02 表示很弱的正排序关系，不代表 2% 的投资收益。','']
for pool,title in [('hs300','沪深300'),('zz500','中证500')]:
    src=root/pool/'results'
    sig=root/pool/'signals'
    cfg=json.loads((src/'model_config_v3.json').read_text(encoding='utf8'))
    alpha=pd.read_csv(src/'alpha101_ic.csv')
    picked=list(map(int,cfg['selected_directions']))
    assert len(alpha)==303 and alpha.groupby('stage').id.nunique().eq(101).all()
    piv=alpha.pivot(index='id',columns='stage',values='mean_ic')[['train','validation','seen']]
    miss=piv.index[piv.isna().any(axis=1)].tolist()
    coverage=alpha.pivot(index='id',columns='stage',values='coverage')
    rows.extend([f'## {title}', '', f'101 个公式均已执行，{101-len(miss)} 个在三个阶段都有可报告的平均 IC。至少一段无法形成统计的编号为 {miss}。缺失保留为空。','',
                 '|入选因子|训练 IC|验证 IC|历史后段 IC|训练覆盖|验证覆盖|后段覆盖|训练 Holm p|',
                 '|---|---:|---:|---:|---:|---:|---:|---:|'])
    sel=pd.read_csv(src/'selection.csv').set_index('id')
    for n in picked:
        rows.append(f'|Alpha{n:03}|'+ '|'.join(f'{piv.loc[n,k]:.4f}' for k in piv)+'|'+
                    '|'.join(f'{coverage.loc[n,k]:.1%}' for k in piv)+f'|{sel.loc[n,"holm_p"]:.4g}|')
    rows.extend(['','以下为研究模型减对照模型的 5 日配对 IC 差，括号内为双侧 HAC p 值。多组模型对照的 p 值仅作探索性描述。','',
                 '|比较|验证期|已看过的历史后段|','|---|---:|---:|'])
    pairs=pd.read_csv(src/'paired_ic_v3.csv').query('horizon==5')
    for (a,b),g in pairs.groupby(['model_a','model_b']):
        g=g.set_index('stage')
        rows.append(f'|{a} − {b}|'+ '|'.join(f'{g.loc[k,"mean_diff"]:+.5f} ({g.loc[k,"hac_p"]:.3g})' for k in ['validation','seen'])+'|')
    weights=pd.read_csv(sig/'target_weights_v3.csv',parse_dates=['signal_date','execution_date'])
    common=pd.read_parquet(sig/'common.parquet')
    first=common.index.get_loc('2023-01-06')
    schedule=common.index[first:-1:5]
    coverage=pd.read_csv(src/'coverage.csv',index_col=0,parse_dates=True).loc[schedule]
    turns=[]
    for model,g in weights.groupby('model'):
        x=pd.read_parquet(sig/f'score_{model}.parquet')
        if not model.startswith('M0'): assert x.notna().equals(common)
        prev=set()
        assert list(g.signal_date.unique())==list(schedule)
        for t,group in g.groupby('signal_date'):
            expected=common.index[common.index.get_loc(t)+1]
            assert group.execution_date.eq(expected).all()
            assert len(group)==group.stock_code.nunique()==50
            assert np.allclose(group.target_weight,.02)
            ranking=x.loc[t].dropna().sort_index().sort_values(ascending=False,kind='stable')
            kept=set() if model.startswith('M0') else prev.intersection(ranking.index[:75])
            need=[k for k in ranking.index if k not in kept][:50-len(kept)]
            names=set(group.stock_code)
            assert names==kept.union(need)
            np.testing.assert_allclose(group.score,ranking[group.stock_code],rtol=1e-6,atol=1e-7)
            turns.append(dict(model=model,signal_date=t,target_replacement=len(names-prev)/50 if prev else np.nan))
            prev=names
    turn=pd.DataFrame(turns)
    turn.to_csv(src/'target_replacement.csv',index=False)
    avg=turn.groupby('model').target_replacement.mean()
    rows.extend(['',f'核验通过。8 套模型各有 {len(schedule)} 次目标调仓、每期 50 只。新模型共同池在调仓日最少 {coverage.common.min()} 只，中位数 {coverage.common.median():.0f} 只；同期入池资格股票数中位数为 {coverage.eligible.median():.0f}。M1 与 M3a 每期平均目标名单替换比例为 {avg.M1:.2%} 和 {avg.M3a:.2%}（剔除首期）。实际换手还取决于权重漂移和成交。',''])
    scale=pd.read_csv(src/'price_scale_check.csv').query("horizon==5")
    for n in [12,101]:
        orig=scale[scale.variant==f'{n:03}_original'].set_index('stage')
        alt=scale[scale.variant==f'{n:03}_relative'].set_index('stage')
        np.testing.assert_allclose(orig.loc[piv.columns,'mean_ic'],piv.loc[n],atol=1e-5)
        rows.append(f'- Alpha{n:03} 价格尺度检验。验证期原式与比例式 IC 分别为 {orig.loc["validation","mean_ic"]:.4f}、{alt.loc["validation","mean_ic"]:.4f}；历史后段为 {orig.loc["seen","mean_ic"]:.4f}、{alt.loc["seen","mean_ic"]:.4f}。')
    fig,ax=plt.subplots(figsize=(7,3))
    piv.loc[picked].rename(index=lambda n:f'Alpha{n:03}').plot.bar(ax=ax,rot=0)
    ax.axhline(0,color='#555',lw=.7)
    ax.set(xlabel='',ylabel='Mean 5-day Rank IC',title=f'{pool.upper()} | Training-selected factors')
    fig.tight_layout()
    fig.savefig(src/'selected_ic.png',dpi=170)
    plt.close(fig)
    rows.extend(['',f'![{title}入选因子分期IC]({pool}/results/selected_ic.png)',''])
(root/'因子与模型检验.md').write_text('\n'.join(rows)+'\n',encoding='utf8')
