# -*- coding: utf-8 -*-
"""
组员3：收益归因与风险分析（v2 修订版）

修订要点（对齐评审意见）：
1. 组合毛收益改用回测输出的「开盘调仓后持仓 open_weights × 当日收益」，
   纳入 t+1 开盘调仓，与实际交易路径一致，可对账回测净值。
2. 因子暴露 = 开盘持仓 × 信号日因子（持仓形成时点的因子）。
3. 路径参数化（相对总包根目录，可命令行覆盖）。

方法：Fama-MacBeth 式逐日横截面回归（np.linalg.lstsq）。
  因子收益：r_{i,d} = alpha_s + sum_k beta_{k,s} * f_{k,i,s} + eps
  其中 s 为信号日，d 为 s 的下一个交易日（执行日）。
  组合毛收益 = sum_i w_open_{i,d} * r_{i,d}
  分解 = sum_k (w_open_d · f_{k,s}) * beta_{k,s} + alpha_s + 特异项
"""
import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--proc', default=str(ROOT / 'quant_project' / 'quant_project_data' / 'processed'))
ap.add_argument('--member2', default=str(ROOT / 'member2_v2' / 'signals'))
ap.add_argument('--out', default=str(ROOT / 'member3'))
args = ap.parse_args()
PROC = Path(args.proc)
MEMBER2 = Path(args.member2)
OUT = Path(args.out)

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

FACTORS = ['bp', 'ep', 'small', 'alpha006', 'alpha033']
FACTOR_CN = {'bp': 'BP(账面市值比)', 'ep': 'EP(盈利收益率)', 'small': 'Small(-ln市值)',
             'alpha006': 'Alpha006', 'alpha033': 'Alpha033'}


def load(name):
    return pd.read_parquet(PROC / f'{name}.parquet').sort_index()


def load_factor(name):
    return pd.read_parquet(MEMBER2 / f'{name}.parquet').sort_index()


print('加载因子、收益与持仓 ...')
factor_dfs = {f: load_factor(f'factor_{f}') for f in FACTORS}
ret_df = load('matrix_returns')
tradable = load('matrix_tradable_mask').fillna(False).astype(bool)

w_base = pd.read_parquet(OUT / 'results' / 'open_weights_baseline.parquet').fillna(0.0)
w_res = pd.read_parquet(OUT / 'results' / 'open_weights_research.parquet').fillna(0.0)

cols = w_base.columns.intersection(w_res.columns)
w_base = w_base.reindex(columns=cols, fill_value=0.0)
w_res = w_res.reindex(columns=cols, fill_value=0.0)

all_dates = pd.DatetimeIndex(sorted(ret_df.index))
common_dates = w_base.index

# ---------- 因子收益：s 日因子 -> d 日收益（d = s 的下一个交易日） ----------
# 只覆盖回测期的信号日（解释回测收益），不用训练期数据
exec_dates = pd.DatetimeIndex(sorted(w_base.index))
signal_dates = sorted({all_dates[i - 1] for i, d in enumerate(all_dates)
                       if i > 0 and d in exec_dates})

factor_ret = {f: [] for f in FACTORS}
alpha_ts = []
reg_signal_dates = []   # 记录信号日 s

for s in signal_dates:
    if s not in factor_dfs['bp'].index:
        continue
    nxt = all_dates[all_dates > s]
    if len(nxt) == 0:
        continue
    d = nxt[0]
    y = ret_df.loc[d]
    X = pd.DataFrame({f: factor_dfs[f].loc[s] for f in FACTORS})
    X['const'] = 1.0
    valid = y.notna() & tradable.loc[s] & X.notna().all(axis=1)
    if valid.sum() < 60:
        continue
    yy = y[valid].values.astype(float)
    XX = X[valid].values.astype(float)
    coef, *_ = np.linalg.lstsq(XX, yy, rcond=None)
    for i, f in enumerate(FACTORS):
        factor_ret[f].append(coef[i])
    alpha_ts.append(coef[-1])
    reg_signal_dates.append(s)

fr = pd.DataFrame(factor_ret, index=reg_signal_dates)
fr['alpha'] = alpha_ts
fr.index = pd.to_datetime(fr.index)

# 信号日 -> 前一个交易日（用于组合分解：执行日 d 的信号日 s = 前一日）
all_dates_idx = all_dates
date_to_prev = {d: all_dates_idx[i - 1] for i, d in enumerate(all_dates_idx) if i > 0}


def combo_decomp(wdf, label):
    rows = []
    for d in wdf.index:
        if d not in date_to_prev:
            continue
        s = date_to_prev[d]
        if s not in fr.index:
            continue
        w = wdf.loc[d]
        # 因子暴露（信号日 s 的因子，与持仓形成时点一致）
        expo = {f: float((w * factor_dfs[f].loc[s].reindex(w.index).fillna(0.0)).sum()) for f in FACTORS}
        # 组合毛收益：开盘调仓后持仓 × 当日 close-to-close 收益
        r = ret_df.loc[d].reindex(w.index).fillna(0.0)
        rp = float((w * r).sum())
        contrib = {f: expo[f] * fr.loc[s, f] for f in FACTORS}
        alpha_c = fr.loc[s, 'alpha']
        resid = rp - sum(contrib.values()) - alpha_c
        rows.append(dict(t=d, 组合毛收益=rp, **{f'贡献_{f}': v for f, v in contrib.items()},
                         alpha贡献=alpha_c, 特异贡献=resid,
                         **{f'暴露_{f}': expo[f] for f in FACTORS}))
    df = pd.DataFrame(rows).set_index('t')
    df.index = pd.to_datetime(df.index)
    return df


print('归因 baseline ...')
dec_base = combo_decomp(w_base, 'baseline')
print('归因 research ...')
dec_res = combo_decomp(w_res, 'research')

dec_base.to_csv(OUT / 'results' / 'decomp_baseline.csv', encoding='utf-8-sig')
dec_res.to_csv(OUT / 'results' / 'decomp_research.csv', encoding='utf-8-sig')

# 对账：归因组合毛收益 vs 回测净值
nav = pd.read_csv(OUT / 'results' / 'nav.csv', index_col=0, parse_dates=True)
base_gross_cum = (1 + dec_base['组合毛收益']).cumprod()
res_gross_cum = (1 + dec_res['组合毛收益']).cumprod()
print('\n===== 对账（归因毛收益 vs 回测净值，期末）=====')
print('baseline 归因毛收益累计 %.4f | 回测净值 %.4f | 理想版 %.4f' %
      (base_gross_cum.iloc[-1], nav['baseline'].iloc[-1], nav['baseline_ideal'].iloc[-1]))
print('research 归因毛收益累计 %.4f | 回测净值 %.4f | 理想版 %.4f' %
      (res_gross_cum.iloc[-1], nav['research'].iloc[-1], nav['research_ideal'].iloc[-1]))

# 因子收益显著性（年化）
print('\n===== 因子收益（逐日横截面回归系数）=====')
rows = []
for f in FACTORS + ['alpha']:
    s = fr[f]
    mean_d = s.mean()
    tstat = mean_d / s.std() * np.sqrt(len(s)) if s.std() > 0 else np.nan
    ann = mean_d * 252
    rows.append(dict(因子=FACTOR_CN.get(f, '截距alpha'), 日均值=mean_d, t值=tstat, 年化=ann))
fr_sig = pd.DataFrame(rows)
print(fr_sig.to_string(index=False))
fr_sig.to_csv(OUT / 'results' / 'factor_returns.csv', index=False, encoding='utf-8-sig')

# 因子贡献均值（两模型对比）
print('\n===== 组合因子贡献（日均值）=====')
contrib_cols = [f'贡献_{f}' for f in FACTORS] + ['alpha贡献', '特异贡献', '组合毛收益']
comp = pd.DataFrame({
    'baseline': dec_base[contrib_cols].mean(),
    'research': dec_res[contrib_cols].mean(),
})
comp.columns = ['baseline', 'research']
comp['差值(research-baseline)'] = comp['research'] - comp['baseline']
print(comp.round(6).to_string())
comp.to_csv(OUT / 'results' / 'decomp_compare.csv', encoding='utf-8-sig')

# 因子暴露均值
print('\n===== 组合因子暴露（均值）=====')
expo_cols = [f'暴露_{f}' for f in FACTORS]
expo = pd.DataFrame({
    'baseline': dec_base[expo_cols].mean(),
    'research': dec_res[expo_cols].mean(),
})
print(expo.round(4).to_string())
expo.to_csv(OUT / 'results' / 'exposure.csv', encoding='utf-8-sig')

# 图：累计贡献
fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
for ax, (dec, label) in zip(axes, [(dec_base, 'baseline'), (dec_res, 'research')]):
    for f in FACTORS:
        ax.plot(dec.index, dec[f'贡献_{f}'].cumsum(), label=FACTOR_CN[f], lw=1.2)
    ax.plot(dec.index, dec['alpha贡献'].cumsum(), label='截距alpha', lw=1.2, ls='--')
    ax.plot(dec.index, dec['特异贡献'].cumsum(), label='特异项', lw=1.2, ls=':')
    ax.set_title(f'{label} 累计收益分解（横截面回归）')
    ax.legend(fontsize=8, ncol=3); ax.grid(alpha=0.3)
axes[-1].set_xlabel('交易日')
fig.tight_layout(); fig.savefig(OUT / 'figures' / 'attribution.png', dpi=150); plt.close(fig)

# 图：research 相对 baseline 累计收益差分解
diff_contrib = {}
for f in FACTORS:
    diff_contrib[f] = (dec_res[f'贡献_{f}'] - dec_base[f'贡献_{f}']).cumsum()
diff_contrib['alpha'] = (dec_res['alpha贡献'] - dec_base['alpha贡献']).cumsum()
diff_contrib['特异'] = (dec_res['特异贡献'] - dec_base['特异贡献']).cumsum()
fig, ax = plt.subplots(figsize=(12, 5))
for k, v in diff_contrib.items():
    ax.plot(v.index, v, label=FACTOR_CN.get(k, k), lw=1.3)
ax.set_title('research 相对 baseline 累计收益差的分解')
ax.legend(fontsize=9); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / 'figures' / 'attribution_diff.png', dpi=150); plt.close(fig)

print('\n输出目录:', OUT)
