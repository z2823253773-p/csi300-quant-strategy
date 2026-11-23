# -*- coding: utf-8 -*-
"""
组员3：模型 3.0 行业暴露、decomp 归因与风险图表（PRD 接口3）

遍历三个实验目录，输出：
- industry_exposure_v3.csv：申万一级暴露全期均值与最新，金融集中度。
- decomp_v3.csv：隔夜/盘中/费用累计分解（复利加权，加总闭合）。
- 图表：净值、超额、回撤、滚动波动、行业，以及跨实验015覆盖诊断。
"""
import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--data", default=str(ROOT / "Tushare_双股票池完整数据与代码" / "tushare_data"))
ap.add_argument("--out", default=str(ROOT / "member3_v3"))
args = ap.parse_args()
DATA, OUT = Path(args.data), Path(args.out)
RES, FIG = OUT / "results", OUT / "figures"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

EXPERIMENTS = {
    "hs300_clean": ("hs300", ["M1", "M2", "M3b", "M4", "M5"]),
    "hs300_alpha": ("hs300", ["M1", "M3a"]),
    "zz500": ("zz500", ["M0a", "M0b", "M1", "M2", "M3a", "M3b", "M4", "M5"]),
}
FINANCE = ["银行", "非银金融"]


def load_ind(pool):
    proc = DATA / pool / "processed"
    panel = pd.read_parquet(proc / "clean_daily_panel.parquet",
                           columns=["trade_date", "stock_code", "sw_l1_name"])
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])
    return panel.pivot(index="trade_date", columns="stock_code", values="sw_l1_name")


def industry_exposure(exp, pool, models, ind_map):
    res_dir = RES / exp
    rows = []
    for model in models:
        ow = pd.read_parquet(res_dir / f"open_weights_{model}.parquet")
        ow.index = pd.to_datetime(ow.index)
        daily = {}
        for d in ow.index:
            w = ow.loc[d]
            w = w[w > 0]
            im = ind_map.loc[d].reindex(w.index)
            daily[d] = w.groupby(im).sum()
        idf = pd.DataFrame(daily).T.sort_index().fillna(0.0)
        cash_w = 1.0 - ow.sum(axis=1).mean()
        for scope, ser in [("full_mean", idf.mean()), ("latest", idf.iloc[-1])]:
            for ind, val in ser.items():
                rows.append(dict(model=model, scope=scope, sw_l1_name=ind,
                                 weight=val, cash_weight=cash_w))
        fin = idf[[c for c in FINANCE if c in idf.columns]].sum(axis=1)
        print(f"  {exp} {model}: 银行+非银 均值 {fin.mean():.4f} 最新 {fin.iloc[-1]:.4f}")
    pd.DataFrame(rows).to_csv(res_dir / "industry_exposure_v3.csv", index=False,
                              encoding="utf-8-sig")


def decomp(exp, models):
    res_dir = RES / exp
    rows = []
    for model in models:
        led = pd.read_csv(res_dir / f"ledger_{model}.csv", index_col=0, parse_dates=True)
        pa = led.prev_close_asset
        on = led.overnight_pnl / pa
        inn = led.intraday_pnl / pa
        cost = led.cost / pa
        total = led.close_asset / pa - 1.0
        nav_growth = (1 + total).cumprod()
        prev_nav = nav_growth.shift(1).fillna(1.0)
        c_on = (on * prev_nav).sum()
        c_in = (inn * prev_nav).sum()
        c_cost = (cost * prev_nav).sum()
        c_total = nav_growth.iloc[-1] - 1
        closure = abs(c_on + c_in - c_cost - c_total)
        rows.append(dict(model=model, n_days=len(led), cum_overnight=c_on,
                         cum_intraday=c_in, cum_cost=c_cost, cum_total=c_total,
                         closure_max=closure))
    out = pd.DataFrame(rows)
    out.to_csv(res_dir / "decomp_v3.csv", index=False, encoding="utf-8-sig")
    return out


def figures(exp, models):
    res_dir = RES / exp
    nav = pd.read_csv(res_dir / "daily_nav_v3.csv", index_col=0, parse_dates=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    for m in models:
        ax.plot(nav.index, nav[f"{m}_net_10bp"], label=m, lw=1.3)
    ax.plot(nav.index, nav.benchmark, label="benchmark", lw=1.3, ls="--", color="k")
    ax.set_title(f"{exp} 计费净值 net_10bp"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(FIG / f"nav_{exp}.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6))
    for m in models:
        ax.plot(nav.index, nav[f"{m}_net_10bp"] / nav.benchmark - 1, label=m, lw=1.3)
    ax.axhline(0, color="k", lw=0.7)
    ax.set_title(f"{exp} 相对基准累计超额"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(FIG / f"excess_{exp}.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6))
    for m in models:
        s = nav[f"{m}_net_10bp"]
        ax.plot(s.index, s / s.cummax() - 1, label=m, lw=1.2)
    ax.set_title(f"{exp} 回撤曲线"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(FIG / f"drawdown_{exp}.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6))
    for m in models:
        r = nav[f"{m}_net_10bp"].pct_change()
        ax.plot(r.index, r.rolling(30).std() * np.sqrt(252), label=m, lw=1.2)
    ax.set_title(f"{exp} 滚动30日年化波动"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(FIG / f"rolling_vol_{exp}.png", dpi=150); plt.close(fig)

    ie = pd.read_csv(res_dir / "industry_exposure_v3.csv")
    ie = ie[ie.scope == "full_mean"]
    inds = ie.groupby("sw_l1_name").weight.mean().sort_values(ascending=False).index
    x = np.arange(len(inds))
    width = 0.8 / len(models)
    fig, ax = plt.subplots(figsize=(13, 6))
    for k, m in enumerate(models):
        sub = (ie[ie.model == m].set_index("sw_l1_name")[["weight"]]
               .reindex(inds).fillna(0.0))
        ax.bar(x + k * width, sub.weight, width, label=m)
    ax.set_xticks(x); ax.set_xticklabels(inds, rotation=60, ha="right", fontsize=8)
    ax.set_title(f"{exp} 全期平均行业暴露"); ax.legend(fontsize=8); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(FIG / f"industry_{exp}.png", dpi=150); plt.close(fig)


def diagnostic_figure():
    clean = pd.read_csv(RES / "hs300_clean" / "daily_nav_v3.csv",
                        index_col=0, parse_dates=True)
    alpha = pd.read_csv(RES / "hs300_alpha" / "daily_nav_v3.csv",
                        index_col=0, parse_dates=True)
    tc = pd.read_csv(RES / "hs300_clean" / "turnover_v3.csv",
                     parse_dates=["execution_date"])
    ta = pd.read_csv(RES / "hs300_alpha" / "turnover_v3.csv",
                     parse_dates=["execution_date"])
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    axes[0].plot(alpha.index, alpha.M1_net_10bp, label="M1 含015共同池", lw=1.4)
    axes[0].plot(clean.index, clean.M1_net_10bp, label="M1 干净共同池", lw=1.4)
    axes[0].plot(clean.index, clean.benchmark, label="benchmark", lw=1.2, ls="--", color="k")
    axes[0].set_title("015 覆盖条件诊断：净值"); axes[0].legend(fontsize=9); axes[0].grid(alpha=0.3)
    sc = tc[(tc.model == "M1") & (tc.fee_scenario == "net_10bp")]
    sa = ta[(ta.model == "M1") & (ta.fee_scenario == "net_10bp")]
    axes[1].plot(sa.execution_date, sa.half_turn, label="含015", lw=1.3)
    axes[1].plot(sc.execution_date, sc.half_turn, label="不含015", lw=1.3)
    axes[1].set_title("015 覆盖条件诊断：单边换手"); axes[1].legend(fontsize=9); axes[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(FIG / "diagnostic_015_v3.png", dpi=150); plt.close(fig)


def main():
    ind_cache = {}
    for exp, (pool, models) in EXPERIMENTS.items():
        print("="*70, exp)
        if pool not in ind_cache:
            ind_cache[pool] = load_ind(pool)
        industry_exposure(exp, pool, models, ind_cache[pool])
        d = decomp(exp, models)
        print(d.round(4).to_string(index=False))
        figures(exp, models)
    diagnostic_figure()
    print("\n输出:", OUT)


if __name__ == "__main__":
    main()
