# -*- coding: utf-8 -*-
"""
组员4 路演 PPT 暖大地配色图表脚本（v3.2 联审修订版）
- 100% 动态读取 member2_tushare / member3_v3 / member4 v3 结果
- 纯正 Anthropic 暖大地三色（零冷蓝/藏青/紫）：
  * 主色（主策略 M4）：陶土橙 #D97757 / 深陶土 #BE5A39
  * 辅色（中证500 / M5 / 防御）：鼠尾草绿 #6B8058 / 深橄榄 #4F623E
  * 第三色（基准 M1 / 周期对照）：暖赭石 #B4844C / 深古铜 #8C6231
  * 风险警示（M0b / 015 陷阱）：砖红 #A63D33
- 针对答辩评审意见定向修复：
  * fig03: 区分 M1(含015) 与 M1(干净)
  * fig04: 图例移至图上方，避免遮挡回撤曲线
  * fig06: 加入 M5（M4 vs M5 vs M1 三柱对比），图上直接呈现 E/B 代理贡献
  * fig07: 标注“未分类*”系申万45天时效约束下缺失行业标签股
- 输出至 member4/figures/slide_v3_brand/（不覆盖报告用图 report_v3/）
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

if not os.environ.get("MPLCONFIGDIR"):
    tmp_mpl = Path(tempfile.gettempdir()) / "member4_v3_brand_mpl"
    tmp_mpl.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(tmp_mpl)

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import paths as P

M2_HS = P.resolve_member2_tushare_pool("hs300")
M2_ZZ = P.resolve_member2_tushare_pool("zz500")
M3_RES = P.resolve_member3_dir("v3") / "results"
M4_RES = P.MEMBER4_DIR / "results"
M4_XQ = P.MEMBER4_DIR / "xueqiu"
OUT_SLD = P.MEMBER4_DIR / "figures" / "slide_v3_brand"
OUT_SLD.mkdir(parents=True, exist_ok=True)

# Anthropic 暖大地色板（零冷蓝）
BG = "#FAF9F5"
INK = "#141413"
TEXT_SUB = "#57554F"
GRID = "#E6E3DA"
SPINE = "#D2CFC5"

TERRA = "#D97757"       # 主色：陶土橙（M4 主交付）
TERRA_DEEP = "#BE5A39"  # 深陶土
SAGE = "#6B8058"        # 辅色：鼠尾草绿（中证500 / M5 / 机构C档）
SAGE_DEEP = "#4F623E"   # 深橄榄
OCHRE = "#B4844C"       # 第三色：暖赭石（M1 / M2 / 基准对照）
OCHRE_DEEP = "#8C6231"  # 深古铜
WARM_GRAY = "#8C877E"   # 市场指数 / 中性暖灰
LIGHT_GRAY = "#B8B3A8"  # 次级对照浅暖灰
BRICK = "#A63D33"       # 砖红（高换手反例 / 015 覆盖陷阱）

TICKS = [
    pd.Timestamp("2023-06-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2024-07-01"),
    pd.Timestamp("2025-01-01"), pd.Timestamp("2025-07-01"), pd.Timestamp("2026-01-01"),
    pd.Timestamp("2026-07-01"),
]


def apply_style():
    plt.rcParams.update({
        "font.sans-serif": ["PingFang SC", "Hiragino Sans GB", "Heiti SC", "STHeiti", "Arial", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "axes.edgecolor": SPINE,
        "axes.linewidth": 0.8,
        "axes.labelcolor": TEXT_SUB,
        "xtick.color": TEXT_SUB,
        "ytick.color": TEXT_SUB,
        "text.color": INK,
        "grid.color": GRID,
        "grid.linestyle": "--",
        "grid.linewidth": 0.65,
        "legend.frameon": False,
        "font.size": 10.0,
    })


def clean_ax(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis=grid_axis, alpha=0.8)


def fmt_dates(ax):
    ax.set_xticks(TICKS)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.axvline(pd.Timestamp("2025-01-01"), color="#9B968D", ls=":", lw=1.0)


def save_fig(fig, name: str):
    fig.savefig(OUT_SLD / name, dpi=300, bbox_inches="tight", pad_inches=0.10)
    plt.close(fig)


def load_all() -> dict:
    return {
        "nav_hs_clean": pd.read_csv(M3_RES / "daily_nav_hs300_clean.csv", parse_dates=["date"]).set_index("date"),
        "nav_hs_full": pd.read_csv(M3_RES / "daily_nav_hs300_full.csv", parse_dates=["date"]).set_index("date"),
        "nav_zz": pd.read_csv(M3_RES / "daily_nav_zz500.csv", parse_dates=["date"]).set_index("date"),
        "metrics": pd.read_csv(M3_RES / "metrics_v3.csv"),
        "turn": pd.read_csv(M3_RES / "turnover_v3.csv", parse_dates=["execution_date"]),
        "ind": pd.read_csv(M3_RES / "industry_exposure_v3.csv"),
        "decomp": pd.read_csv(M3_RES / "decomp_v3.csv"),
        "fic_hs": pd.read_csv(M2_HS / "results" / "factor_ic_v3.csv"),
        "fic_zz": pd.read_csv(M2_ZZ / "results" / "factor_ic_v3.csv"),
        "cap_c": pd.read_csv(M4_RES / "capacity_constraints_v3.csv"),
        "cap_curve": pd.read_csv(M4_RES / "capacity_curve_v3.csv"),
        "inv_nav": pd.read_csv(M4_RES / "investor_nav_v3.csv", parse_dates=["date"]).set_index("date"),
        "fee_df": pd.read_csv(M4_RES / "fee_analysis_v3.csv"),
        "xq_bt": pd.read_csv(M4_XQ / "xueqiu_30_tracking_backtest.csv"),
        "xq_nav": pd.read_csv(M4_XQ / "xueqiu_30_tracking_nav.csv", parse_dates=["date"]).set_index("date"),
        "prod": json.loads((M4_RES / "product_summary_v3.json").read_text(encoding="utf-8")),
    }


def fig01_hs300_nav(D: dict):
    apply_style()
    nc, nf = D["nav_hs_clean"], D["nav_hs_full"]
    fig, ax = plt.subplots(figsize=(9.0, 4.7))
    series = [
        ("M4 主交付（价值+低波+低换手）", nc["M4_net_10bp"], TERRA_DEEP, 2.5, "-"),
        ("M5（M4+E/B代理）", nc["M5_net_10bp"], SAGE, 1.5, "--"),
        ("M3b（M2+15%改造012）", nc["M3b_net_10bp"], OCHRE, 1.35, "-"),
        ("M1(干净)（缓冲基准）", nc["M1_net_10bp"], OCHRE_DEEP, 1.5, "-."),
        ("原始基准 M0a（无缓冲）", nf["M0a_net_10bp"], WARM_GRAY, 1.55, "--"),
        ("沪深300价格指数", nc["hs300_intraday"], INK, 1.25, ":"),
        ("M0b（原50%高频量价）", nf["M0b_net_10bp"], BRICK, 1.35, "--"),
    ]
    for label, s, col, lw, ls in series:
        ret_pct = (s.iloc[-1] - 1.0) * 100.0
        ax.plot(s.index, s.values, label=f"{label} ({ret_pct:+.2f}%)", color=col, lw=lw, ls=ls)
    fmt_dates(ax)
    ax.set_ylim(0.70, 1.72)
    ax.text(pd.Timestamp("2024-12-10"), 0.74, "← 验证期 (23–24)", ha="right", fontsize=8.8, color=TEXT_SUB)
    ax.text(pd.Timestamp("2025-01-20"), 0.74, "历史留后区间 (25–26.10) →", ha="left", fontsize=8.8, color=TEXT_SUB)
    ax.set_ylabel("累计净值（初始 = 1.0）")
    clean_ax(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), fontsize=8.4, ncol=2, columnspacing=1.2)
    save_fig(fig, "01_hs300_ablation_nav.png")


def fig02_dual_pool_bars(D: dict):
    apply_style()
    m = D["metrics"]
    m_all = m[(m["stage"] == "all") & (m["fee_scenario"] == "net_10bp")]
    models = ["M1", "M2", "M3b", "M4", "M5"]
    hs = m_all[m_all["experiment"] == "hs300_clean"].set_index("model").loc[models]
    zz = m_all[m_all["experiment"] == "zz500"].set_index("model").loc[models]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 4.2))
    x = np.arange(len(models))
    w = 0.36
    b1 = ax1.bar(x - w / 2, hs["cum_return"] * 100, w, label="沪深300（干净池）", color=TERRA)
    b2 = ax1.bar(x + w / 2, zz["cum_return"] * 100, w, label="中证500", color=SAGE)
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.1, f"{h:.1f}%", ha="center", va="bottom", fontsize=7.6)
    ax1.set_xticks(x); ax1.set_xticklabels(models)
    ax1.set_ylabel("全期累计净收益（%）")
    ax1.set_ylim(0, 72)
    ax1.set_title("全期扣费累计收益（net_10bp）", fontsize=10.5, fontweight="bold", color=INK)
    clean_ax(ax1)
    ax1.legend(loc="upper left", fontsize=8.8)

    b3 = ax2.bar(x - w / 2, hs["sharpe_arith_rf0"], w, label="沪深300（干净池）", color=TERRA)
    b4 = ax2.bar(x + w / 2, zz["sharpe_arith_rf0"], w, label="中证500", color=SAGE)
    for bars in (b3, b4):
        for bar in bars:
            h = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.02, f"{h:.2f}", ha="center", va="bottom", fontsize=8.3)
    ax2.set_xticks(x); ax2.set_xticklabels(models)
    ax2.set_ylabel("算术年化夏普比率（Rf=0）")
    ax2.set_ylim(0, 1.12)
    ax2.set_title("跨股票池算术夏普比率对比", fontsize=10.5, fontweight="bold", color=INK)
    clean_ax(ax2)
    fig.tight_layout(w_pad=2.2)
    save_fig(fig, "02_dual_pool_ablation_bars.png")


def fig03_015_diagnosis(D: dict):
    apply_style()
    nc, nf = D["nav_hs_clean"], D["nav_hs_full"]
    tr = D["turn"]
    t_clean = tr[(tr["experiment"] == "hs300_clean") & (tr["model"] == "M1") & (tr["fee_scenario"] == "net_10bp")].set_index("execution_date")["half_turn"] * 100
    t_full = tr[(tr["experiment"] == "hs300_full") & (tr["model"] == "M1") & (tr["fee_scenario"] == "net_10bp")].set_index("execution_date")["half_turn"] * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.0, 5.2), sharex=True, gridspec_kw={"height_ratios": [1.3, 1.0]})
    ax1.plot(nc.index, nc["M1_net_10bp"], color=SAGE_DEEP, lw=2.1, label=f"M1(干净) 解除015约束（{(nc['M1_net_10bp'].iloc[-1]-1)*100:+.2f}%，中位284股）")
    ax1.plot(nf.index, nf["M1_net_10bp"], color=BRICK, lw=1.9, label=f"M1(含015) 共同池（{(nf['M1_net_10bp'].iloc[-1]-1)*100:+.2f}%，中位152股）")
    ax1.plot(nc.index, nc["hs300_intraday"], color=WARM_GRAY, lw=1.2, ls=":", label="沪深300价格指数（-0.33%）")
    ax1.set_ylabel("累计净值")
    clean_ax(ax1)
    ax1.legend(loc="upper left", fontsize=8.6)

    ax2.plot(t_full.index, t_full.values, color=BRICK, lw=1.25, alpha=0.85, label=f"M1(含015) 单次单边换手（均值 {t_full.mean():.2f}%）")
    ax2.plot(t_clean.index, t_clean.values, color=SAGE_DEEP, lw=1.6, label=f"M1(干净) 单次单边换手（均值 {t_clean.mean():.2f}%）")
    fmt_dates(ax2)
    ax2.set_ylabel("每次调仓单边换手（%）")
    clean_ax(ax2)
    ax2.legend(loc="upper right", fontsize=8.6)
    fig.tight_layout()
    save_fig(fig, "03_015_coverage_diagnosis.png")


def fig04_drawdown(D: dict):
    apply_style()
    nc, nf, nz = D["nav_hs_clean"], D["nav_hs_full"], D["nav_zz"]
    fig, ax = plt.subplots(figsize=(8.8, 4.7))
    items = [
        ("沪深300 M4（主交付）", nc["M4_net_10bp"], TERRA_DEEP, 2.3, "-"),
        ("沪深300 原始基准 M0a", nf["M0a_net_10bp"], OCHRE, 1.55, "-"),
        ("中证500 M4", nz["M4_net_10bp"], SAGE, 1.55, "--"),
        ("沪深300价格指数", nc["hs300_intraday"], WARM_GRAY, 1.4, ":"),
        ("M0b（50%高换手反例）", nf["M0b_net_10bp"], BRICK, 1.25, "-."),
    ]
    for lab, s, col, lw, ls in items:
        dd = (s / s.cummax().clip(lower=1.0) - 1.0) * 100
        ax.plot(dd.index, dd.values, label=f"{lab}（最大 {dd.min():.2f}%）", color=col, lw=lw, ls=ls)
        if col == TERRA_DEEP:
            ax.fill_between(dd.index, dd.values, 0, color=TERRA, alpha=0.12)
    fmt_dates(ax)
    ax.set_ylabel("高水位相对回撤（%）")
    clean_ax(ax)
    # 图例放在图上方，彻底避免遮挡任何回撤曲线
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), fontsize=8.4, ncol=2, columnspacing=1.1)
    save_fig(fig, "04_drawdown_underwater_v3.png")


def fig05_factor_ic(D: dict):
    apply_style()
    facs = ["bp", "ep", "lowvol_60", "lowturn_20", "new012_amt_ema10", "alpha040", "eb_proxy", "small"]
    labels = ["BP\n价值", "EP\n盈利", "LowVol60\n低波动", "LowTurn20\n低换手", "new012\n改造量价", "Alpha040\n101首选", "E/B代理\n(EP/BP)", "Small\n小市值代理"]
    fhs = D["fic_hs"][D["fic_hs"]["horizon"] == 5].pivot(index="factor", columns="stage", values="mean_ic").loc[facs]
    fzz = D["fic_zz"][D["fic_zz"]["horizon"] == 5].pivot(index="factor", columns="stage", values="mean_ic").loc[facs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.15), sharey=True)
    x = np.arange(len(facs))
    w = 0.26
    for ax, df, title in [(ax1, fhs, "沪深300 核心因子 5日 Rank IC"), (ax2, fzz, "中证500 核心因子 5日 Rank IC")]:
        ax.bar(x - w, df["train"] * 100, w, label="训练期 (19–22)", color=LIGHT_GRAY)
        ax.bar(x, df["validation"] * 100, w, label="验证期 (23–24)", color=SAGE)
        ax.bar(x + w, df["seen"] * 100, w, label="历史后段 (25–26.10)", color=TERRA)
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.0)
        ax.set_title(title, fontsize=10.5, fontweight="bold", color=INK)
        clean_ax(ax)
    ax1.set_ylabel("5日均值 Rank IC（×100）")
    ax1.legend(loc="upper right", fontsize=8.4)
    fig.tight_layout(w_pad=1.8)
    save_fig(fig, "05_factor_ic_and_new012.png")


def fig06_fm_attribution(D: dict):
    apply_style()
    dec = D["decomp"]
    comps = [
        "market_intercept", "factor_bp", "factor_ep", "factor_lowvol_60", "factor_lowturn_20",
        "factor_small", "factor_eb_proxy", "factor_new012_amt_ema10",
        "specific_residual_and_timing", "transaction_cost",
    ]
    clabs = ["市场截距(等权)", "BP价值", "EP盈利", "LowVol60", "LowTurn20", "Small代理", "E/B代理", "改造012", "特异残差", "交易成本"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.55), sharey=True)
    y = np.arange(len(comps))
    h = 0.26
    for ax, exp, title in [
        (ax1, "hs300_clean", "沪深300（干净池）：M4 / M5 / M1 年化归因"),
        (ax2, "zz500", "中证500：M4 / M5 / M1 年化归因"),
    ]:
        sub = dec[(dec["experiment"] == exp) & (dec["model"].isin(["M1", "M4", "M5"]))].pivot(
            index="component", columns="model", values="ann_arith_pct"
        ).loc[comps] * 100
        ax.barh(y - h, sub["M4"], h, label="M4（主交付）", color=TERRA)
        ax.barh(y, sub["M5"], h, label="M5（+E/B代理）", color=SAGE)
        ax.barh(y + h, sub["M1"], h, label="M1(干净)", color=OCHRE)
        ax.axvline(0, color=INK, lw=0.8)
        # 在 E/B 代理行标注 M5 的关键数值
        eb_idx = comps.index("factor_eb_proxy")
        eb_m5 = sub.loc["factor_eb_proxy", "M5"]
        if eb_m5 >= 0:
            ax.text(eb_m5 + 0.18, eb_idx, f"M5 {eb_m5:+.2f}%", va="center", ha="left", fontsize=8.0, fontweight="bold", color=SAGE_DEEP)
        else:
            ax.text(eb_m5 - 0.18, eb_idx, f"M5 {eb_m5:+.2f}%", va="center", ha="right", fontsize=8.0, fontweight="bold", color=BRICK)
        ax.set_yticks(y); ax.set_yticklabels(clabs, fontsize=8.8)
        ax.invert_yaxis()
        ax.set_xlabel("算术年化收益贡献（%）")
        ax.set_title(title, fontsize=10.2, fontweight="bold", color=INK)
        clean_ax(ax, grid_axis="x")
    ax1.set_xlim(-2.2, 6.2)
    ax2.set_xlim(-5.2, 8.2)
    ax1.legend(loc="upper right", fontsize=8.3)
    fig.tight_layout(w_pad=1.8)
    save_fig(fig, "06_fm_attribution_v3.png")


def fig07_industry(D: dict):
    apply_style()
    ind = D["ind"]
    hs_full = ind[(ind["experiment"] == "hs300_clean") & (ind["scope"] == "full_mean")]
    top_inds = hs_full[hs_full["model"] == "M4"].sort_values("weight", ascending=False).head(8)["sw_l1_name"].tolist()
    piv_hs = hs_full[hs_full["model"].isin(["M1", "M2", "M4"])].pivot(index="sw_l1_name", columns="model", values="weight").reindex(top_inds).fillna(0) * 100
    top_labels = ["未分类*" if x == "未分类" else x for x in top_inds]

    zz_full = ind[(ind["experiment"] == "zz500") & (ind["scope"] == "full_mean") & (ind["model"] == "M4")].set_index("sw_l1_name")["weight"] * 100
    hs_m4 = hs_full[hs_full["model"] == "M4"].set_index("sw_l1_name")["weight"] * 100
    comp_cats = ["银行", "非银金融", "建筑装饰", "交通运输", "机械设备", "公用事业", "医药生物"]
    hs_vals = [hs_m4.get(c, 0.0) for c in comp_cats]
    zz_vals = [zz_full.get(c, 0.0) for c in comp_cats]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.25))
    x = np.arange(len(top_inds))
    w = 0.27
    ax1.bar(x - w, piv_hs["M4"], w, label="M4（金融42.4%）", color=TERRA)
    ax1.bar(x, piv_hs["M2"], w, label="M2 纯价值（金融48.2%）", color=OCHRE)
    ax1.bar(x + w, piv_hs["M1"], w, label="M1(干净)（金融38.8%）", color=SAGE)
    ax1.set_xticks(x); ax1.set_xticklabels(top_labels, rotation=26, ha="right", fontsize=8.4)
    ax1.set_ylabel("全期平均持仓权重（%）")
    ax1.set_title("沪深300：M4 vs M2 / M1 前8行业暴露", fontsize=10.2, fontweight="bold", color=INK)
    ax1.text(0.01, -0.26, "*未分类（约11.8%）系申万45天时效约束剔除回填后的缺失标签股", transform=ax1.transAxes, fontsize=7.8, color=TEXT_SUB)
    clean_ax(ax1)
    ax1.legend(loc="upper right", fontsize=8.2)

    x2 = np.arange(len(comp_cats))
    w2 = 0.36
    ax2.bar(x2 - w2 / 2, hs_vals, w2, label="沪深300 M4（金融42.4%）", color=TERRA)
    ax2.bar(x2 + w2 / 2, zz_vals, w2, label="中证500 M4（金融22.3%）", color=SAGE)
    ax2.set_xticks(x2); ax2.set_xticklabels(comp_cats, rotation=26, ha="right", fontsize=8.4)
    ax2.set_ylabel("全期平均持仓权重（%）")
    ax2.set_title("双股票池 M4 行业分布对比", fontsize=10.2, fontweight="bold", color=INK)
    clean_ax(ax2)
    ax2.legend(loc="upper right", fontsize=8.2)
    fig.tight_layout(w_pad=2.0)
    save_fig(fig, "07_industry_exposure_v3.png")


def fig08_capacity(D: dict):
    apply_style()
    cc = D["cap_c"]
    cv = D["cap_curve"]
    cv08 = cv[cv["Y"] == 0.8].sort_values("aum_yi")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.2))
    cats = ["1日调仓\n(5% P10)", "3日拆单\n(5% P10)", "5日清仓\n(5% P10)"]

    def gp(m, ct, win):
        return float(cc[(cc["model"] == m) & (cc["constraint_type"] == ct) & (cc["participation_rate"] == 0.05) & (cc["window_days"] == win)]["p10_yi"].iloc[0])

    v_hs = [gp("hs300_M4_main", "rebalance_participation", 1), gp("hs300_M4_main", "rebalance_participation", 3), gp("hs300_M4_main", "liquidation_5d", 5)]
    v_zz = [gp("zz500_M4_peer", "rebalance_participation", 1), gp("zz500_M4_peer", "rebalance_participation", 3), gp("zz500_M4_peer", "liquidation_5d", 5)]
    v_m0b = [gp("hs300_M0b_highturn", "rebalance_participation", 1), gp("hs300_M0b_highturn", "rebalance_participation", 3), gp("hs300_M0b_highturn", "liquidation_5d", 5)]

    x = np.arange(3); w = 0.26
    b1 = ax1.bar(x - w, v_hs, w, label="沪深300 M4（主交付）", color=TERRA)
    b2 = ax1.bar(x, v_zz, w, label="中证500 M4", color=SAGE)
    b3 = ax1.bar(x + w, v_m0b, w, label="沪深300 M0b（高换手）", color=BRICK)
    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 0.2, f"{h:.2f}", ha="center", va="bottom", fontsize=8.0)
    ax1.set_xticks(x); ax1.set_xticklabels(cats, fontsize=8.6)
    ax1.set_ylabel("流动性硬约束容量上限（亿元）")
    ax1.set_ylim(0, max(v_hs) * 1.38)
    ax1.set_title("5% 成交参与率硬约束（P10 瓶颈）", fontsize=10.2, fontweight="bold", color=INK)
    clean_ax(ax1)
    ax1.legend(loc="upper right", fontsize=8.0)

    ax2.plot(cv08["aum_yi"], cv08["hs300_M4_main_net_ann"] * 100, color=TERRA_DEEP, lw=2.3, label="沪深300 M4（Y=0.8）")
    ax2.plot(cv08["aum_yi"], cv08["zz500_M4_peer_net_ann"] * 100, color=SAGE, lw=1.9, ls="--", label="中证500 M4（Y=0.8）")
    ax2.plot(cv08["aum_yi"], cv08["hs300_M0b_highturn_net_ann"] * 100, color=BRICK, lw=1.5, ls="-.", label="沪深300 M0b（高换手）")
    ax2.axvspan(3.0, 5.0, color=SAGE, alpha=0.18, label="低超限可行区间(3–5亿)")
    ax2.axvline(6.63, color=OCHRE, ls="--", lw=1.1)
    ax2.text(6.0, -5.5, "6.63亿\n5日清仓P10", fontsize=7.5, color=OCHRE_DEEP, ha="right")
    ax2.axvline(10.0, color=BRICK, ls=":", lw=1.2)
    ax2.text(11.2, 5.8, "扩张压测\n10–15亿", fontsize=8.0, color=BRICK, fontweight="bold")
    ax2.axhline(0, color=INK, lw=0.7)
    ax2.set_xscale("log")
    ax2.set_xlabel("产品管理规模 AUM（亿元，对数刻度）")
    ax2.set_ylabel("扣冲击后策略年化收益（%）")
    ax2.set_ylim(-25, 16.5)
    ax2.set_title("平方根市场冲击衰减曲线（Y=0.8）", fontsize=10.2, fontweight="bold", color=INK)
    clean_ax(ax2)
    ax2.legend(loc="lower left", fontsize=8.1)
    fig.tight_layout(w_pad=2.0)
    save_fig(fig, "08_dual_pool_capacity_v3.png")


def fig09_fee_nav(D: dict):
    apply_style()
    inv = D["inv_nav"]
    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    lines = [
        ("M4 策略净值（未扣产品费）", "M4_strategy_net10bp", TERRA_DEEP, 2.3, "-"),
        ("方案D 纯管理费（1.5%+0.2%）", "plan_D", SAGE, 1.75, "-"),
        ("方案C 机构份额（0.6%+0.15%+超额15%）", "plan_C", OCHRE_DEEP, 1.95, "-"),
        ("方案A 标准份额（1.0%+0.2%+绝对20%）", "plan_A", OCHRE, 1.4, "--"),
        ("方案B 超额计提（1.0%+0.2%+超额20%）", "plan_B", WARM_GRAY, 1.35, "-."),
        ("沪深300价格指数", "hs300_intraday", INK, 1.25, ":"),
    ]
    for lab, col_name, col, lw, ls in lines:
        s = inv[col_name]
        ax.plot(s.index, s.values, label=f"{lab}（{(s.iloc[-1]-1)*100:+.2f}%）", color=col, lw=lw, ls=ls)
    fmt_dates(ax)
    ax.set_ylabel("投资者到手净值（初始 = 1.0）")
    clean_ax(ax)
    ax.legend(loc="upper left", fontsize=8.4)
    save_fig(fig, "09_fee_net_nav_v3.png")


def fig10_xueqiu_tracking(D: dict):
    apply_style()
    xn = D["xq_nav"]
    xb = D["xq_bt"]
    sub = xb[(xb["base_model"] == "hs300_M4_clean") & (xb["stage"] == "all") & (xb["fee_scenario"] == "net_10bp")].set_index("mapping_scheme")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.2), gridspec_kw={"width_ratios": [1.5, 1.0]})
    ax1.plot(xn.index, xn["hs300_M4_clean_top50_ew_net_10bp"], color=SAGE_DEEP, lw=2.0, label=f"M4 原策略 50只等权（{sub.loc['top50_ew','cum_return']*100:+.2f}%）")
    ax1.plot(xn.index, xn["hs300_M4_clean_xq30_buf45_tiered_net_10bp"], color=TERRA_DEEP, lw=2.1, label=f"雪球30只分层+前45缓冲（{sub.loc['xq30_buf45_tiered','cum_return']*100:+.2f}%）")
    ax1.plot(xn.index, xn["hs300_M4_clean_xq30_trunc_tiered_net_10bp"], color=OCHRE, lw=1.5, ls="--", label=f"直接硬截断30只分层（{sub.loc['xq30_trunc_tiered','cum_return']*100:+.2f}%）")
    ax1.plot(xn.index, xn["hs300_intraday"], color=WARM_GRAY, lw=1.2, ls=":", label="沪深300价格指数（-0.33%）")
    fmt_dates(ax1)
    ax1.set_ylabel("累计净值")
    ax1.set_title("M4 50只原策略 vs 雪球30只历史映射", fontsize=10.2, fontweight="bold", color=INK)
    clean_ax(ax1)
    ax1.legend(loc="upper left", fontsize=8.1)

    schemes = ["top50_ew", "xq30_buf45_tiered", "xq30_trunc_tiered"]
    slabs = ["M4 原策略\n50只等权", "雪球30只分层\n(独立前45缓冲)", "直接硬截断\n30只分层"]
    turns = [sub.loc[s, "mean_half_turn"] * 100 for s in schemes]
    tes = [sub.loc[s, "tracking_error_vs_top50"] * 100 for s in schemes]
    x = np.arange(3); w = 0.34
    b1 = ax2.bar(x - w / 2, turns, w, label="单次单边换手(%)", color=TERRA)
    b2 = ax2.bar(x + w / 2, tes, w, label="相对50只年化TE(%)", color=SAGE)
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.15, f"{h:.2f}%", ha="center", va="bottom", fontsize=8.0)
    ax2.set_xticks(x); ax2.set_xticklabels(slabs, fontsize=8.2)
    ax2.set_ylabel("百分比（%）")
    ax2.set_ylim(0, max(turns) * 1.28)
    ax2.set_title("独立前45缓冲将单次换手压降超一半", fontsize=10.2, fontweight="bold", color=INK)
    clean_ax(ax2)
    ax2.legend(loc="upper left", fontsize=8.2)
    fig.tight_layout(w_pad=1.8)
    save_fig(fig, "10_xueqiu_30_tracking_v3.png")


def fig11_dual_pool_nav(D: dict):
    """P09 专用：沪深300旗舰 M4 与 中证500卫星 M4 对比各自原始基准 M0a 及价格指数"""
    apply_style()
    nc, nf, nz = D["nav_hs_clean"], D["nav_hs_full"], D["nav_zz"]
    fig, ax = plt.subplots(figsize=(7.8, 4.7))
    series = [
        ("沪深300 M4（旗舰）", nc["M4_net_10bp"], TERRA_DEEP, 2.5, "-"),
        ("中证500 M4（卫星）", nz["M4_net_10bp"], SAGE_DEEP, 2.1, "-"),
        ("沪深300 原始基准 M0a", nf["M0a_net_10bp"], TERRA, 1.25, "--"),
        ("中证500 原始基准 M0a", nz["M0a_net_10bp"], SAGE, 1.25, "--"),
        ("中证500 价格指数", nz["benchmark_intraday"], OCHRE, 1.15, ":"),
        ("沪深300 价格指数", nc["hs300_intraday"], WARM_GRAY, 1.2, ":"),
    ]
    for label, s, col, lw, ls in series:
        ret_pct = (s.iloc[-1] - 1.0) * 100.0
        ax.plot(s.index, s.values, label=f"{label} ({ret_pct:+.2f}%)", color=col, lw=lw, ls=ls, alpha=(0.82 if ls == "--" else 1.0))
    fmt_dates(ax)
    ax.set_ylim(0.68, 1.76)
    ax.text(pd.Timestamp("2024-12-10"), 1.67, "← 验证期 (23–24)", ha="right", fontsize=8.6, color=TEXT_SUB)
    ax.text(pd.Timestamp("2025-01-20"), 1.67, "历史留后区间 (25–26.10) →", ha="left", fontsize=8.6, color=TEXT_SUB)
    ax.set_ylabel("累计净值（初始 = 1.0）")
    clean_ax(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), fontsize=8.2, ncol=2, columnspacing=1.0)
    save_fig(fig, "11_dual_pool_product_nav.png")


def fig12_peer_matrix(D: dict):
    """P09 专用：2×2 市场竞争定位矩阵（现实三类对家 vs 本产品双池 M4）"""
    apply_style()
    fig, ax = plt.subplots(figsize=(6.2, 4.9))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

    # 象限背景淡色（右上甜点区柔和暖绿，其余极淡）
    ax.axvspan(5.0, 10.0, ymin=0.5, ymax=1.0, color="#EBF0E4", alpha=0.65, zorder=0)
    ax.axhline(5.0, color=SPINE, ls="--", lw=1.0, zorder=1)
    ax.axvline(5.0, color=SPINE, ls="--", lw=1.0, zorder=1)

    # 象限角标
    ax.text(9.7, 9.55, "甜点区：低换手 × 强防御", ha="right", va="top", fontsize=9.0, fontweight="bold", color=SAGE_DEEP)
    ax.text(0.3, 9.55, "高换手 · 算力与容量博弈区", ha="left", va="top", fontsize=8.4, color=TEXT_SUB)
    ax.text(9.7, 0.45, "低换手 · 被动敞口区", ha="right", va="bottom", fontsize=8.4, color=TEXT_SUB)
    ax.text(0.3, 0.45, "高磨损 · 负摩擦风险区", ha="left", va="bottom", fontsize=8.4, color=TEXT_SUB)

    # 点位：(x=低换手与成本控制力, y=规则化防御与风险收益比)
    pts = [
        # (x, y, size, color, label, dx, dy, ha)
        (8.5, 8.35, 320, TERRA_DEEP, "本产品 · 沪深300 M4（主回测）\n单次换手 2.74% | 回撤 -15.88%\n几何年化 +13.05% (C档费后 +10.39%)", -0.45, -0.05, "right"),
        (6.7, 6.35, 190, SAGE_DEEP, "中证500 M4（跨池同规格对照）\n单次换手 4.37% | 金融均值 22.3%", 0.38, -0.10, "left"),
        (9.0, 2.35, 170, WARM_GRAY, "被动沪深300指数 ETF\n管理+托管约 0.20% · 换手极低\n无主动防御 · 承受完整指数回撤(-24.8%)", -0.35, 0.72, "right"),
        (6.0, 4.15, 170, OCHRE_DEEP, "主动价值红利公募基金\n固定费约 1.40% · 换手偏低\n风格稳定度依赖基金经理个人判断", 0.32, 0.05, "left"),
        (2.5, 6.45, 190, OCHRE, "中高频量价指增私募/公募\n换手较高 · 依赖算力与高频因子\n大资金受盘口流动性与冲击成本约束", 0.15, 0.98, "center"),
        (1.6, 2.35, 150, BRICK, "本组实测高频量价对照 M0b\n单次换手 51.70% · 扣费净收益 -8.88%", 0.35, 0.05, "left"),
    ]
    for x, y, sz, col, txt, dx, dy, ha in pts:
        ax.scatter([x], [y], s=sz, color=col, edgecolors=BG, linewidth=1.8, zorder=4)
        ax.text(x + dx, y + dy, txt, fontsize=8.0, fontweight=("bold" if col == TERRA_DEEP else "normal"),
                color=(TERRA_DEEP if col == TERRA_DEEP else INK), ha=ha, va="center", linespacing=1.28, zorder=5)

    ax.set_xlabel("低换手与交易成本控制力（高换手高摩擦  ←   →  低换手低磨损）", fontsize=9.2, labelpad=8)
    ax.set_ylabel("弱市回撤防御与规则纪律性", fontsize=9.2, labelpad=8)
    ax.set_xticks([]); ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SPINE)
    ax.spines["bottom"].set_color(SPINE)
    fig.tight_layout()
    save_fig(fig, "12_peer_positioning_2x2.png")


def main():
    D = load_all()
    funcs = [
        fig01_hs300_nav, fig02_dual_pool_bars, fig03_015_diagnosis,
        fig04_drawdown, fig05_factor_ic, fig06_fm_attribution,
        fig07_industry, fig08_capacity, fig09_fee_nav, fig10_xueqiu_tracking,
        fig11_dual_pool_nav, fig12_peer_matrix,
    ]
    print("绘制暖大地配色 PPT 图表（12 张 300 DPI）...")
    for fn in funcs:
        fn(D)
    print(f"完成！已输出至: {OUT_SLD}")


if __name__ == "__main__":
    main()
