# -*- coding: utf-8 -*-
"""
组员3：回测引擎（v2 修订版）

修订要点（对齐评审意见）：
1. 前视偏差修正：开盘成交资格改用「开盘价 / 昨收价」判断开盘一字涨跌停，
   不再使用依赖当日收盘收益/最高最低/成交量的 matrix_is_limit_up/down。
2. 卖出资格：采用组员1新增 can_sell_held 的语义（出池/ST 仍可卖），
   但其中的「一字跌停」改用开盘价判断，避免收盘信息前视。
3. 首日收益：初始资金 1.0 为首日开盘前基准，首日建仓盈亏与成本计入累计收益，
   不再按首日收盘净值归一化抹去。
4. 复现路径：数据/信号/输出目录均参数化，默认相对总包根目录，可命令行覆盖。
5. 输出每日开盘调仓后持仓权重（open_weights_*.parquet），供归因对齐实际交易路径。

成交价：后复权开盘价；成交额/股数用不复权口径。
成本（组员3设定）：佣金双边万3、印花税卖出千1、滑点双边千1、现金不计息。
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

# ---------- 路径（相对总包根目录，可命令行覆盖） ----------
ROOT = Path(__file__).resolve().parent.parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--proc', default=str(ROOT / 'quant_project' / 'quant_project_data' / 'processed'),
                help='组员1 processed 目录')
ap.add_argument('--member2', default=str(ROOT / 'member2_v2' / 'signals'),
                help='组员2 signals 目录')
ap.add_argument('--out', default=str(ROOT / 'member3'), help='组员3 输出目录')
args = ap.parse_args()
PROC = Path(args.proc)
MEMBER2 = Path(args.member2)
OUT = Path(args.out)
(OUT / 'results').mkdir(parents=True, exist_ok=True)
(OUT / 'figures').mkdir(parents=True, exist_ok=True)

COMMISSION = 0.0003     # 佣金 双边万3
STAMP_TAX = 0.001       # 印花税 卖出千1
SLIPPAGE = 0.001        # 滑点 双边千1
CASH_RATE = 0.0         # 现金不计息

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def load(name):
    return pd.read_parquet(PROC / f'{name}.parquet').sort_index()


def board_threshold(code):
    """按板块返回一字板识别阈值（与组员1 is_limit_up/down 口径一致）。"""
    num = code.split('.')[0]
    if num.startswith(('688', '300', '301', '302')):
        return 0.195   # 科创板/创业板
    return 0.095       # 主板


print('加载行情与状态 ...')
open_df = load('matrix_open_hfq').ffill()    # 后复权开盘价
close_df = load('matrix_close_hfq').ffill()  # 后复权收盘价

# 从长表提取「开盘时点可获得」的状态（不复权昨收/开盘、停牌、ST、次新、成分股）
panel_cols = ['trade_date', 'stock_code', 'open', 'preclose',
              'is_suspended', 'is_st', 'is_new_stock', 'in_index_universe']
panel = pd.read_parquet(PROC / 'clean_daily_panel.parquet', columns=panel_cols)
panel['trade_date'] = pd.to_datetime(panel['trade_date'])


def pivot(col):
    return panel.pivot(index='trade_date', columns='stock_code', values=col).sort_index()


preclose_df = pivot('preclose').ffill()      # 不复权昨收
open_raw_df = pivot('open').ffill()          # 不复权开盘
susp_df = pivot('is_suspended').fillna(False).astype(bool)
st_df = pivot('is_st').fillna(False).astype(bool)
new_df = pivot('is_new_stock').fillna(False).astype(bool)
idx_df = pivot('in_index_universe').fillna(False).astype(bool)

# 开盘一字涨跌停（开盘时点判断，无前视）
open_ret = open_raw_df / preclose_df - 1.0
limit_up_open = pd.DataFrame(False, index=open_ret.index, columns=open_ret.columns)
limit_down_open = pd.DataFrame(False, index=open_ret.index, columns=open_ret.columns)
for c in open_ret.columns:
    th = board_threshold(c)
    limit_up_open[c] = open_ret[c] >= th
    limit_down_open[c] = open_ret[c] <= -th

# 成交资格（开盘时点）
can_buy_open = idx_df & ~st_df & ~new_df & ~susp_df & ~limit_up_open
can_sell_open = ~susp_df & ~limit_down_open

# 组员1 can_sell_held 接口（读入做交叉核对，语义=出池/ST可卖，停牌/一字跌停/异常不可卖）
can_sell_held = load('matrix_can_sell_held').fillna(False).astype(bool)
print('can_sell_held True=%d | 开盘时点 can_sell_open True=%d'
      % (int(can_sell_held.sum().sum()), int(can_sell_open.sum().sum())))

bench = pd.read_parquet(PROC / 'benchmark_daily.parquet')
bench300 = bench[bench['benchmark_code'] == '000300.SH'].copy()
bench300['trade_date'] = pd.to_datetime(bench300['trade_date'])
bench300 = bench300.set_index('trade_date')['benchmark_ret'].sort_index()

tw = pd.read_csv(MEMBER2 / 'target_weights.csv')
tw['execution_date'] = pd.to_datetime(tw['execution_date'])
tw['signal_date'] = pd.to_datetime(tw['signal_date'])


def px(row, c):
    v = row.get(c, np.nan)
    return v if np.isfinite(v) else np.nan


def run_backtest(model, use_cost=True, use_constraint=True):
    """返回 (nav, close_wdf, open_wdf, turnover_list, cash_min, avg_pos)"""
    sub = tw[tw['model'] == model]
    target_map = {}
    for ed, g in sub.groupby('execution_date'):
        target_map[ed] = dict(zip(g['stock_code'], g['target_weight']))

    exec_dates = sorted(target_map.keys())
    start, end = exec_dates[0], exec_dates[-1]
    dates = close_df.index[(close_df.index >= start) & (close_df.index <= end)]

    cash = 1.0            # 首日开盘前初始资金（净值基准 1.0）
    shares = {}
    nav = {}
    close_weight_rows = {}
    open_weight_rows = {}
    turnovers = []
    cash_min = 1.0
    position_ratios = []

    for d in dates:
        open_row = open_df.loc[d]
        close_row = close_df.loc[d]

        if d in target_map:
            tgt = target_map[d]

            # 调仓前开盘总资产（用开盘价）
            open_total = cash
            for c, s in shares.items():
                p = px(open_row, c)
                if np.isfinite(p):
                    open_total += s * p

            sell_gross = 0.0
            buy_gross = 0.0
            target_val = {c: open_total * w for c, w in tgt.items()}

            # 第一步：卖出（目标外全卖 + 目标内超配减持；开盘时点判断跌停/停牌）
            for c in list(shares.keys()):
                p = px(open_row, c)
                if not np.isfinite(p):
                    continue
                cur = shares[c] * p
                if not use_constraint:
                    ok = True
                else:
                    ok = bool(can_sell_open.loc[d, c])
                if c not in tgt:
                    if ok:
                        sell_gross += cur
                        proceeds = cur * (1 - SLIPPAGE if use_cost else 1.0)
                        proceeds *= (1 - COMMISSION - STAMP_TAX) if use_cost else 1.0
                        cash += proceeds
                        del shares[c]
                else:
                    tval = target_val[c]
                    if cur > tval and ok:
                        sell_gross += (cur - tval)
                        sell_val = cur - tval
                        proceeds = sell_val * (1 - SLIPPAGE if use_cost else 1.0)
                        proceeds *= (1 - COMMISSION - STAMP_TAX) if use_cost else 1.0
                        cash += proceeds
                        shares[c] = tval / p

            # 第二步：买入（目标内欠配增持；开盘时点判断涨停/停牌；现金硬约束）
            buys = []
            for c, w in tgt.items():
                p = px(open_row, c)
                if not np.isfinite(p):
                    continue
                cur = shares.get(c, 0.0) * p
                tval = target_val[c]
                need = tval - cur
                if need > 0:
                    if not use_constraint:
                        ok = True
                    else:
                        ok = bool(can_buy_open.loc[d, c])
                    if ok:
                        buys.append((c, p, need))

            total_cost = sum(b[2] * (1 + (COMMISSION if use_cost else 0)) for b in buys)
            scale = 1.0
            if total_cost > 0 and cash < total_cost:
                scale = cash / total_cost
            for c, p, need in buys:
                amt = need * scale
                if amt <= 0:
                    continue
                buy_gross += amt
                cash -= amt * (1 + COMMISSION if use_cost else 1.0)
                shares[c] = shares.get(c, 0.0) + amt / (p * (1 + SLIPPAGE if use_cost else 1.0))

            cash_min = min(cash_min, cash)
            turnover = (sell_gross + buy_gross) / 2.0 / open_total if open_total > 0 else 0.0
            turnovers.append((d, turnover))

        # 开盘持仓权重（调仓后；非调仓日=前一交易日持仓，按开盘价估值）
        ow = {}
        ow_total = cash
        for c, s in shares.items():
            p = px(open_row, c)
            if np.isfinite(p):
                ow[c] = s * p
                ow_total += s * p
        if ow_total > 0:
            open_weight_rows[d] = {c: v / ow_total for c, v in ow.items()}
        else:
            open_weight_rows[d] = {}

        # 收盘估值
        total_close = cash
        for c, s in shares.items():
            p = px(close_row, c)
            if np.isfinite(p):
                total_close += s * p
        nav[d] = total_close
        position_ratios.append((total_close - cash) / total_close if total_close > 0 else 0.0)

        cw = {}
        if total_close > 0:
            for c, s in shares.items():
                p = px(close_row, c)
                if np.isfinite(p):
                    cw[c] = s * p / total_close
        close_weight_rows[d] = cw

    nav_s = pd.Series(nav, name=model).sort_index()   # 相对初始资金 1.0，首日收益保留
    cwdf = pd.DataFrame.from_dict(close_weight_rows, orient='index').sort_index()
    owdf = pd.DataFrame.from_dict(open_weight_rows, orient='index').sort_index()
    return nav_s, cwdf, owdf, turnovers, cash_min, float(np.mean(position_ratios))


print('回测 baseline（计成本+约束）...')
nav_base, cw_base, ow_base, tr_base, cmin_base, pos_base = run_backtest('baseline')
print('回测 research（计成本+约束）...')
nav_res, cw_res, ow_res, tr_res, cmin_res, pos_res = run_backtest('research')
print('回测 baseline（无成本理想）...')
nav_base0, _, _, _, _, _ = run_backtest('baseline', use_cost=False, use_constraint=False)
print('回测 research（无成本理想）...')
nav_res0, _, _, _, _, _ = run_backtest('research', use_cost=False, use_constraint=False)

print('现金最小值: baseline=%.4f research=%.4f' % (cmin_base, cmin_res))
print('平均仓位: baseline=%.4f research=%.4f' % (pos_base, pos_res))

start = nav_base.index[0]
b = bench300[bench300.index >= start]
nav_bench = (1 + b.fillna(0)).cumprod()   # 首日基准收益保留，不再按首日归一化

nav_df = pd.concat([nav_base, nav_res, nav_bench], axis=1)
nav_df.columns = ['baseline', 'research', 'hs300']
nav_df = nav_df.ffill()
nav_df['baseline_ideal'] = nav_base0.reindex(nav_df.index).ffill()
nav_df['research_ideal'] = nav_res0.reindex(nav_df.index).ffill()


def metrics(nav, base=1.0):
    """base=1.0 表示首日开盘前初始资金（全样本）；base=首日收盘表示区间内统计。"""
    nav = nav.dropna()
    r = nav.pct_change().dropna()
    first_r = nav.iloc[0] / base - 1.0
    all_r = pd.concat([pd.Series([first_r]), r])
    n = len(all_r)
    cum = nav.iloc[-1] / base - 1.0
    ann_ret = (nav.iloc[-1] / base) ** (252 / n) - 1.0 if n > 0 else np.nan
    ann_vol = all_r.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
    dd = (nav / nav.cummax() - 1).min()
    return dict(累计收益=cum, 年化收益=ann_ret, 年化波动=ann_vol, 夏普=sharpe, 最大回撤=dd, 样本数=n)


def period_table(df):
    seg = {
        '全样本(2023-2026.10)': (df.index[0], df.index[-1], True),
        '验证期(2023-2024)': (pd.Timestamp('2023-01-09'), pd.Timestamp('2024-12-31'), False),
        '样本外(2025-2026.10)': (pd.Timestamp('2025-01-01'), pd.Timestamp('2026-10-30'), False),
    }
    rows = []
    for name, (s, e, is_full) in seg.items():
        seg_df = df[(df.index >= s) & (df.index <= e)]
        for col in ['baseline', 'research', 'hs300']:
            col_nav = seg_df[col].dropna()
            base = 1.0 if is_full else col_nav.iloc[0]
            m = metrics(col_nav, base=base)
            rows.append(dict(区间=name, 组合=col, **m))
    return pd.DataFrame(rows)


metric_df = period_table(nav_df)
metric_df.to_csv(OUT / 'results' / 'metrics.csv', index=False, encoding='utf-8-sig')

nav_df['research_excess_hs300'] = nav_df['research'] - nav_df['hs300']
nav_df['research_excess_base'] = nav_df['research'] - nav_df['baseline']
nav_df['baseline_excess_hs300'] = nav_df['baseline'] - nav_df['hs300']

tr_base_s = pd.Series(dict(tr_base)).rename('baseline_turnover')
tr_res_s = pd.Series(dict(tr_res)).rename('research_turnover')
tr_df = pd.concat([tr_base_s, tr_res_s], axis=1)
tr_df.to_csv(OUT / 'results' / 'turnover.csv', encoding='utf-8-sig')

cw_base.to_parquet(OUT / 'results' / 'weights_baseline.parquet')
cw_res.to_parquet(OUT / 'results' / 'weights_research.parquet')
ow_base.to_parquet(OUT / 'results' / 'open_weights_baseline.parquet')
ow_res.to_parquet(OUT / 'results' / 'open_weights_research.parquet')
nav_df.to_csv(OUT / 'results' / 'nav.csv', encoding='utf-8-sig')

# 图1 净值
fig, ax = plt.subplots(figsize=(12, 6.5))
ax.plot(nav_df.index, nav_df['baseline'], label='baseline(基准模型)', lw=1.6)
ax.plot(nav_df.index, nav_df['research'], label='research(研究模型)', lw=1.6)
ax.plot(nav_df.index, nav_df['hs300'], label='沪深300', lw=1.6, color='gray')
ax.axvline(pd.Timestamp('2025-01-01'), color='k', ls='--', lw=0.8)
ax.set_title('沪深300 vs baseline vs research 净值（计成本）')
ax.set_xlabel('交易日'); ax.set_ylabel('净值(初始资金=1)')
ax.legend(); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / 'figures' / 'nav_curve.png', dpi=150); plt.close(fig)

# 图2 超额收益
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(nav_df.index, nav_df['baseline_excess_hs300'], label='baseline超额(对沪深300)', lw=1.3)
ax.plot(nav_df.index, nav_df['research_excess_hs300'], label='research超额(对沪深300)', lw=1.3)
ax.axhline(0, color='k', lw=0.8)
ax.axvline(pd.Timestamp('2025-01-01'), color='k', ls='--', lw=0.8)
ax.set_title('相对沪深300累计超额收益')
ax.legend(); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / 'figures' / 'excess_curve.png', dpi=150); plt.close(fig)

print('\n===== 指标表 =====')
print(metric_df.to_string(index=False))
print('\n===== 换手率(单边) =====')
print('baseline 均值 %.4f 最大 %.4f | research 均值 %.4f 最大 %.4f' %
      (tr_base_s.mean(), tr_base_s.max(), tr_res_s.mean(), tr_res_s.max()))
print('\n===== 期末净值 =====')
print(nav_df[['baseline', 'research', 'hs300', 'baseline_ideal', 'research_ideal']].iloc[-1].round(4).to_string())
print('\n输出目录:', OUT)
