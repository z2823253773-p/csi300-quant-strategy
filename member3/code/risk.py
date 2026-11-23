# -*- coding: utf-8 -*-
"""组员3：风险分析 —— 回撤曲线、风格暴露、波动与极端行情（路径参数化）"""
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
ap.add_argument('--out', default=str(ROOT / 'member3'))
args = ap.parse_args()
OUT = Path(args.out)
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

nav = pd.read_csv(OUT / 'results' / 'nav.csv', parse_dates=[0], index_col=0)

# ---------------------------------------------------------------------------
# 最大回撤区间
# ---------------------------------------------------------------------------
def max_dd_info(s):
    s = s.dropna()
    cummax = s.cummax()
    dd = s / cummax - 1
    trough = dd.idxmin()
    peak = s.loc[:trough].idxmax()
    # 恢复时间：谷底之后首次回到峰值
    recovered = None
    after = s.loc[trough:]
    if (after >= s.loc[peak]).any():
        recovered = after[after >= s.loc[peak]].index[0]
    return dict(峰值=peak, 谷底=trough, 最大回撤=dd.min(), 恢复日=recovered)

print('===== 最大回撤区间 =====')
for col in ['baseline', 'research', 'hs300']:
    info = max_dd_info(nav[col])
    print(f'{col}: 峰值 {info["峰值"].date()} 谷底 {info["谷底"].date()} '
          f'回撤 {info["最大回撤"]:.4f} 恢复 {info["恢复日"].date() if info["恢复日"] is not None else "未恢复"}')

# 回撤曲线
fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
for ax, col in zip(axes, ['baseline', 'research', 'hs300']):
    s = nav[col].dropna()
    dd = s / s.cummax() - 1
    ax.fill_between(dd.index, dd.values, 0, alpha=0.4)
    ax.plot(dd.index, dd.values, lw=1)
    ax.set_title(f'{col} 回撤曲线')
    ax.set_ylabel('回撤'); ax.grid(alpha=0.3)
axes[-1].set_xlabel('交易日')
fig.tight_layout(); fig.savefig(OUT / 'figures' / 'drawdown.png', dpi=150); plt.close(fig)

# ---------------------------------------------------------------------------
# 风格暴露时间序列（价值/规模）
# ---------------------------------------------------------------------------
dec_base = pd.read_csv(OUT / 'results' / 'decomp_baseline.csv', parse_dates=[0], index_col=0)
dec_res = pd.read_csv(OUT / 'results' / 'decomp_research.csv', parse_dates=[0], index_col=0)

fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
for ax, fac, cn in zip(axes, ['bp', 'ep', 'small'], ['BP暴露', 'EP暴露', 'Small暴露']):
    ax.plot(dec_base.index, dec_base[f'暴露_{fac}'], label='baseline', lw=1.2)
    ax.plot(dec_res.index, dec_res[f'暴露_{fac}'], label='research', lw=1.2)
    ax.axhline(0, color='k', lw=0.6)
    ax.set_title(cn); ax.legend(fontsize=8); ax.grid(alpha=0.3)
axes[-1].set_xlabel('交易日')
fig.tight_layout(); fig.savefig(OUT / 'figures' / 'style_exposure.png', dpi=150); plt.close(fig)

# ---------------------------------------------------------------------------
# 月度收益与滚动波动
# ---------------------------------------------------------------------------
def monthly_ret(s):
    r = s.pct_change()
    m = r.resample('ME').apply(lambda x: (1 + x).prod() - 1)
    return m

mret = pd.DataFrame({c: monthly_ret(nav[c]) for c in ['baseline', 'research', 'hs300']})
mret.to_csv(OUT / 'results' / 'monthly_returns.csv', encoding='utf-8-sig')
print('\n===== 月度收益统计 =====')
print('正收益月份占比:')
for c in ['baseline', 'research', 'hs300']:
    pos = (mret[c] > 0).mean()
    print(f'  {c}: {pos:.3f}  最差月 {mret[c].min():.4f}  最好月 {mret[c].max():.4f}')

# 滚动30日波动
fig, ax = plt.subplots(figsize=(12, 5))
for c in ['baseline', 'research', 'hs300']:
    r = nav[c].pct_change()
    rv = r.rolling(30).std() * np.sqrt(252)
    ax.plot(rv.index, rv, label=c, lw=1.2)
ax.set_title('滚动30日年化波动率')
ax.legend(); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / 'figures' / 'rolling_vol.png', dpi=150); plt.close(fig)

print('\n输出目录:', OUT)
