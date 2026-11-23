# -*- coding: utf-8 -*-
"""
组员4 v3.0 图表绘制脚本：动态读取 Tushare 数据 3.0、member2_tushare、member3_v3 与 member4 v3 结果，
一键输出两套 300 DPI 高清图表（共 10 张 × 2 套）：
1. figures/report_v3/ : 学术白底版（供 20-30 页书面技术报告 Word/PDF 嵌入）
2. figures/slide_v3/  : Claude 官网极简暖白底 (#FAF9F5) 无框无缝融合版（供 17 页路演 PPT 嵌入）
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

if not os.environ.get("MPLCONFIGDIR"):
    tmp_mpl = Path(tempfile.gettempdir()) / "member4_v3_mpl"
    tmp_mpl.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(tmp_mpl)

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

import paths as P

M2_HS = P.resolve_member2_tushare_pool("hs300")
M2_ZZ = P.resolve_member2_tushare_pool("zz500")
M3_RES = P.resolve_member3_dir("v3") / "results"
M4_RES = P.MEMBER4_DIR / "results"
M4_XQ = P.MEMBER4_DIR / "xueqiu"
OUT_REP = P.MEMBER4_DIR / "figures" / "report_v3"
OUT_SLD = P.MEMBER4_DIR / "figures" / "slide_v3"
OUT_REP.mkdir(parents=True, exist_ok=True)
OUT_SLD.mkdir(parents=True, exist_ok=True)

# 统一主题色板（暖白极简编辑风 + 学术打印高对比）
TERRA = "#C45A38"   # 主交付 M4 陶土深橙（高辨识、打印锐利）
NAVY = "#1E3A5F"    # M1 / 基准标杆藏青
SAGE = "#3D7A5E"    # 中证500 / M5 / 正增量鼠尾草绿
AMBER = "#C88A2B"   # M3b / 机构C档琥珀金
SLATE = "#6E7681"   # 市场指数 / 辅助线冷灰
MUTED = "#A0A4AB"   # 次级对照浅灰
CRIMSON = "#B43E3E" # M0b / 负对照 / 风险警戒红
INK = "#1C1B19"
GRID = "#E5E2D9"

TICKS = [
    pd.Timestamp("2023-06-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2024-07-01"),
    pd.Timestamp("2025-01-01"), pd.Timestamp("2025-07-01"), pd.Timestamp("2026-01-01"),
    pd.Timestamp("2026-07-01"),
]


def apply_style(is_slide: bool):
    bg = "#FAF9F5" if is_slide else "#FFFFFF"
    plt.rcParams.update({
        "font.sans-serif": ["PingFang SC", "Hiragino Sans GB", "Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": bg,
        "axes.facecolor": bg,
        "savefig.facecolor": bg,
        "axes.edgecolor": GRID,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK,
        "xtick.color": "#4A4843",
        "ytick.color": "#4A4843",
        "text.color": INK,
        "grid.color": GRID,
        "grid.linestyle": "--",
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "font.size": 10 if is_slide else 9.5,
    })
    return bg


def clean_ax(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis=grid_axis, alpha=0.75)


def fmt_dates(ax):
    ax.set_xticks(TICKS)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.axvline(pd.Timestamp("2025-01-01"), color="#8C8980", ls=":", lw=1.0)


def save_both(fig, name: str, is_slide: bool):
    out_dir = OUT_SLD if is_slide else OUT_REP
    fig.savefig(out_dir / name, dpi=300, bbox_inches="tight", pad_inches=0.12)
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


def fig01_hs300_nav(D: dict, is_slide: bool):
    apply_style(is_slide)
    nc, nf = D["nav_hs_clean"], D["nav_hs_full"]
    fig, ax = plt.subplots(figsize=(9.2, 4.6) if is_slide else (8.4, 4.4))
    series = [
        ("M4 主交付（价值+低波+低换手）", nc["M4_net_10bp"], TERRA, 2.4, "-"),
        ("M5（M4+E/B代理对照）", nc["M5_net_10bp"], SAGE, 1.5, "--"),
        ("M3b（M2+15%改造012）", nc["M3b_net_10bp"], AMBER, 1.4, "-"),
        ("M1（3.0基准+前75缓冲）", nc["M1_net_10bp"], NAVY, 1.8, "-"),
        ("M0a（原5日无缓冲锚）", nf["M0a_net_10bp"], SLATE, 1.2, "-."),
        ("沪深300（3.0 intraday）", nc["hs300_intraday"], "#2B2B2B", 1.3, ":"),
        ("M0b（原50%量价高换手）", nf["M0b_net_10bp"], CRIMSON, 1.3, "--"),
    ]
    for label, s, col, lw, ls in series:
        ret_pct = (s.iloc[-1] - 1.0) * 100.0
        ax.plot(s.index, s.values, label=f"{label}  ({ret_pct:+.2f}%)", color=col, lw=lw, ls=ls)
    fmt_dates(ax)
    ax.set_ylim(0.70, 1.72)
    ax.text(pd.Timestamp("2024-12-12"), 0.74, "← 验证期 (23–24)", ha="right", fontsize=8.5, color="#57554F")
    ax.text(pd.Timestamp("2025-01-18"), 0.74, "历史留后区间 (25–26.10) →", ha="left", fontsize=8.5, color="#57554F")
    ax.set_ylabel("累计净值（初始 = 1.0）")
    if not is_slide:
        ax.set_title("沪深300 3.0 干净共同池核心消融净值曲线（net_10bp 压力情景）", fontweight="bold", pad=36)
    clean_ax(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), fontsize=8.2, ncol=2)
    save_both(fig, "01_hs300_ablation_nav.png", is_slide)


def fig02_dual_pool_bars(D: dict, is_slide: bool):
    apply_style(is_slide)
    m = D["metrics"]
    m_all = m[(m["stage"] == "all") & (m["fee_scenario"] == "net_10bp")]
    models = ["M1", "M2", "M3b", "M4", "M5"]
    hs = m_all[m_all["experiment"] == "hs300_clean"].set_index("model").loc[models]
    zz = m_all[m_all["experiment"] == "zz500"].set_index("model").loc[models]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.3) if is_slide else (9.0, 4.1))
    x = np.arange(len(models))
    w = 0.36
    b1 = ax1.bar(x - w / 2, hs["cum_return"] * 100, w, label="沪深300（干净池）", color=TERRA)
    b2 = ax1.bar(x + w / 2, zz["cum_return"] * 100, w, label="中证500", color=NAVY)
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.1, f"{h:.1f}%", ha="center", va="bottom", fontsize=8)
    ax1.set_xticks(x); ax1.set_xticklabels(models)
    ax1.set_ylabel("全期累计净收益（%）")
    ax1.set_ylim(0, 72)
    ax1.set_title("全期扣费累计收益（net_10bp）", fontsize=10, fontweight="bold")
    clean_ax(ax1)
    ax1.legend(loc="upper left", fontsize=8.5)

    b3 = ax2.bar(x - w / 2, hs["sharpe_arith_rf0"], w, label="沪深300（干净池）", color=TERRA)
    b4 = ax2.bar(x + w / 2, zz["sharpe_arith_rf0"], w, label="中证500", color=NAVY)
    for bars in (b3, b4):
        for bar in bars:
            h = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.02, f"{h:.2f}", ha="center", va="bottom", fontsize=8)
    ax2.set_xticks(x); ax2.set_xticklabels(models)
    ax2.set_ylabel("算术年化夏普比率（Rf=0）")
    ax2.set_ylim(0, 1.12)
    ax2.set_title("跨股票池算术夏普比率对比", fontsize=10, fontweight="bold")
    clean_ax(ax2)
    fig.tight_layout()
    save_both(fig, "02_dual_pool_ablation_bars.png", is_slide)


def fig03_015_diagnosis(D: dict, is_slide: bool):
    apply_style(is_slide)
    nc, nf = D["nav_hs_clean"], D["nav_hs_full"]
    tr = D["turn"]
    t_clean = tr[(tr["experiment"] == "hs300_clean") & (tr["model"] == "M1") & (tr["fee_scenario"] == "net_10bp")].set_index("execution_date")["half_turn"] * 100
    t_full = tr[(tr["experiment"] == "hs300_full") & (tr["model"] == "M1") & (tr["fee_scenario"] == "net_10bp")].set_index("execution_date")["half_turn"] * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.0, 5.2) if is_slide else (8.4, 5.0), sharex=True, gridspec_kw={"height_ratios": [1.3, 1.0]})
    ax1.plot(nc.index, nc["M1_net_10bp"], color=NAVY, lw=2.0, label=f"M1 解除015覆盖约束（净收益 {(nc['M1_net_10bp'].iloc[-1]-1)*100:+.2f}%，中位284股）")
    ax1.plot(nf.index, nf["M1_net_10bp"], color=CRIMSON, lw=1.8, label=f"M1 含015共同池（净收益 {(nf['M1_net_10bp'].iloc[-1]-1)*100:+.2f}%，中位152股）")
    ax1.plot(nc.index, nc["hs300_intraday"], color=SLATE, lw=1.2, ls=":", label="沪深300基准（-0.33%）")
    ax1.set_ylabel("净值")
    if not is_slide:
        ax1.set_title("沪深300 Alpha015 低覆盖率陷阱诊断：同一 M1 分数的净值与强制换手对比", fontweight="bold")
    clean_ax(ax1)
    ax1.legend(loc="upper left", fontsize=8.5)

    ax2.plot(t_full.index, t_full.values, color=CRIMSON, lw=1.2, alpha=0.85, label=f"含015共同池单边换手（均值 {t_full.mean():.2f}%）")
    ax2.plot(t_clean.index, t_clean.values, color=NAVY, lw=1.5, label=f"解除015覆盖单边换手（均值 {t_clean.mean():.2f}%）")
    fmt_dates(ax2)
    ax2.set_ylabel("每次调仓单边换手（%）")
    clean_ax(ax2)
    ax2.legend(loc="upper right", fontsize=8.5)
    fig.tight_layout()
    save_both(fig, "03_015_coverage_diagnosis.png", is_slide)


def fig04_drawdown(D: dict, is_slide: bool):
    apply_style(is_slide)
    nc, nf, nz = D["nav_hs_clean"], D["nav_hs_full"], D["nav_zz"]
    fig, ax = plt.subplots(figsize=(9.0, 4.3) if is_slide else (8.4, 4.1))
    items = [
        ("沪深300 M4（主交付）", nc["M4_net_10bp"], TERRA, 2.2, "-"),
        ("沪深300 M1（3.0基准）", nc["M1_net_10bp"], NAVY, 1.5, "-"),
        ("中证500 M4（跨池对照）", nz["M4_net_10bp"], SAGE, 1.5, "--"),
        ("沪深300指数", nc["hs300_intraday"], SLATE, 1.4, ":"),
        ("M0b（50%高换手反例）", nf["M0b_net_10bp"], CRIMSON, 1.2, "-."),
    ]
    for lab, s, col, lw, ls in items:
        dd = (s / s.cummax().clip(lower=1.0) - 1.0) * 100
        ax.plot(dd.index, dd.values, label=f"{lab}（最大 {dd.min():.2f}%）", color=col, lw=lw, ls=ls)
        if col == TERRA:
            ax.fill_between(dd.index, dd.values, 0, color=TERRA, alpha=0.10)
    fmt_dates(ax)
    ax.set_ylabel("水下回撤幅度（%）")
    if not is_slide:
        ax.set_title("策略与市场基准水下回撤曲线对比（2023.01–2026.10）", fontweight="bold")
    clean_ax(ax)
    ax.legend(loc="lower left", fontsize=8.4, ncol=2)
    save_both(fig, "04_drawdown_underwater_v3.png", is_slide)


def fig05_factor_ic(D: dict, is_slide: bool):
    apply_style(is_slide)
    facs = ["bp", "ep", "lowvol_60", "lowturn_20", "new012_amt_ema10", "alpha040", "eb_proxy", "small"]
    labels = ["BP\n价值", "EP\n盈利", "LowVol60\n低波动", "LowTurn20\n低换手", "new012\n改造量价", "Alpha040\n101首选", "E/B代理\n(EP/BP)", "Small\n小市值代理"]
    fhs = D["fic_hs"][D["fic_hs"]["horizon"] == 5].pivot(index="factor", columns="stage", values="mean_ic").loc[facs]
    fzz = D["fic_zz"][D["fic_zz"]["horizon"] == 5].pivot(index="factor", columns="stage", values="mean_ic").loc[facs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 4.2) if is_slide else (9.2, 4.1), sharey=True)
    x = np.arange(len(facs))
    w = 0.26
    for ax, df, title in [(ax1, fhs, "沪深300 核心因子 5日 Rank IC"), (ax2, fzz, "中证500 核心因子 5日 Rank IC")]:
        ax.bar(x - w, df["train"] * 100, w, label="训练期 (19–22)", color=SLATE)
        ax.bar(x, df["validation"] * 100, w, label="验证期 (23–24)", color=NAVY)
        ax.bar(x + w, df["seen"] * 100, w, label="历史后段 (25–26.10)", color=TERRA)
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7.8)
        ax.set_title(title, fontsize=10, fontweight="bold")
        clean_ax(ax)
    ax1.set_ylabel("5日均值 Rank IC（×100）")
    ax1.legend(loc="upper right", fontsize=8.2)
    fig.tight_layout()
    save_both(fig, "05_factor_ic_and_new012.png", is_slide)


def fig06_fm_attribution(D: dict, is_slide: bool):
    apply_style(is_slide)
    dec = D["decomp"]
    comps = [
        "market_intercept", "factor_bp", "factor_ep", "factor_lowvol_60", "factor_lowturn_20",
        "factor_small", "factor_eb_proxy", "factor_new012_amt_ema10",
        "specific_residual_and_timing", "transaction_cost",
    ]
    clabs = ["市场截距", "BP价值", "EP盈利", "LowVol60", "LowTurn20", "Small代理", "E/B代理", "改造012", "特异残差", "交易成本"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.55) if is_slide else (9.2, 4.45), sharey=True)
    y = np.arange(len(comps))
    h = 0.36
    for ax, exp, title in [(ax1, "hs300_clean", "沪深300（干净池）：M4 vs M1 年化收益拆解"), (ax2, "zz500", "中证500：M4 vs M1 年化收益拆解")]:
        sub = dec[(dec["experiment"] == exp) & (dec["model"].isin(["M1", "M4"]))].pivot(index="component", columns="model", values="ann_arith_pct").loc[comps] * 100
        ax.barh(y - h / 2, sub["M4"], h, label="M4（主交付）", color=TERRA)
        ax.barh(y + h / 2, sub["M1"], h, label="M1（3.0基准）", color=NAVY)
        ax.axvline(0, color=INK, lw=0.8)
        ax.set_yticks(y); ax.set_yticklabels(clabs, fontsize=8.8)
        ax.invert_yaxis()
        ax.set_xlabel("算术年化收益贡献（%）")
        ax.set_title(title, fontsize=9.8, fontweight="bold")
        clean_ax(ax, grid_axis="x")
    ax1.legend(loc="upper right", fontsize=8.5)
    fig.tight_layout()
    save_both(fig, "06_fm_attribution_v3.png", is_slide)


def fig07_industry(D: dict, is_slide: bool):
    apply_style(is_slide)
    ind = D["ind"]
    hs_full = ind[(ind["experiment"] == "hs300_clean") & (ind["scope"] == "full_mean")]
    top_inds = hs_full[hs_full["model"] == "M4"].sort_values("weight", ascending=False).head(8)["sw_l1_name"].tolist()
    piv_hs = hs_full[hs_full["model"].isin(["M1", "M2", "M4"])].pivot(index="sw_l1_name", columns="model", values="weight").reindex(top_inds).fillna(0) * 100

    # 右图：沪深300 M4 vs 中证500 M4 金融集中度与前5行业
    zz_full = ind[(ind["experiment"] == "zz500") & (ind["scope"] == "full_mean") & (ind["model"] == "M4")].set_index("sw_l1_name")["weight"] * 100
    hs_m4 = hs_full[hs_full["model"] == "M4"].set_index("sw_l1_name")["weight"] * 100
    comp_cats = ["银行", "非银金融", "交通运输", "建筑装饰", "公用事业", "煤炭", "有色金属"]
    hs_vals = [hs_m4.get(c, 0.0) for c in comp_cats]
    zz_vals = [zz_full.get(c, 0.0) for c in comp_cats]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.3) if is_slide else (9.2, 4.2))
    x = np.arange(len(top_inds))
    w = 0.27
    ax1.bar(x - w, piv_hs["M4"], w, label="M4（金融42.4%）", color=TERRA)
    ax1.bar(x, piv_hs["M2"], w, label="M2（金融48.2%）", color=AMBER)
    ax1.bar(x + w, piv_hs["M1"], w, label="M1（金融38.8%）", color=NAVY)
    ax1.set_xticks(x); ax1.set_xticklabels(top_inds, rotation=28, ha="right", fontsize=8.3)
    ax1.set_ylabel("全期平均持仓权重（%）")
    ax1.set_title("沪深300：M4 vs M2/M1 前8行业暴露", fontsize=9.8, fontweight="bold")
    clean_ax(ax1)
    ax1.legend(loc="upper right", fontsize=8.2)

    x2 = np.arange(len(comp_cats))
    w2 = 0.36
    ax2.bar(x2 - w2 / 2, hs_vals, w2, label="沪深300 M4", color=TERRA)
    ax2.bar(x2 + w2 / 2, zz_vals, w2, label="中证500 M4", color=SAGE)
    ax2.set_xticks(x2); ax2.set_xticklabels(comp_cats, rotation=28, ha="right", fontsize=8.3)
    ax2.set_ylabel("全期平均持仓权重（%）")
    ax2.set_title("双股票池 M4 行业分散度对比（中证500金融仅22.3%）", fontsize=9.8, fontweight="bold")
    clean_ax(ax2)
    ax2.legend(loc="upper right", fontsize=8.2)
    fig.tight_layout()
    save_both(fig, "07_industry_exposure_v3.png", is_slide)


def fig08_capacity(D: dict, is_slide: bool):
    apply_style(is_slide)
    cc = D["cap_c"]
    cv = D["cap_curve"]
    cv08 = cv[cv["Y"] == 0.8].sort_values("aum_yi")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.3) if is_slide else (9.2, 4.2))
    # 左图：5% 参与率硬约束 P10 双池对比
    cats = ["1日调仓\n(5% P10)", "3日拆单\n(5% P10)", "5日清仓\n(5% P10)"]
    def gp(m, ct, win):
        return float(cc[(cc["model"] == m) & (cc["constraint_type"] == ct) & (cc["participation_rate"] == 0.05) & (cc["window_days"] == win)]["p10_yi"].iloc[0])
    v_hs = [gp("hs300_M4_main", "rebalance_participation", 1), gp("hs300_M4_main", "rebalance_participation", 3), gp("hs300_M4_main", "liquidation_5d", 5)]
    v_zz = [gp("zz500_M4_peer", "rebalance_participation", 1), gp("zz500_M4_peer", "rebalance_participation", 3), gp("zz500_M4_peer", "liquidation_5d", 5)]
    v_m0b = [gp("hs300_M0b_highturn", "rebalance_participation", 1), gp("hs300_M0b_highturn", "rebalance_participation", 3), gp("hs300_M0b_highturn", "liquidation_5d", 5)]

    x = np.arange(3); w = 0.26
    b1 = ax1.bar(x - w, v_hs, w, label="沪深300 M4（主交付）", color=TERRA)
    b2 = ax1.bar(x, v_zz, w, label="中证500 M4（跨池）", color=SAGE)
    b3 = ax1.bar(x + w, v_m0b, w, label="沪深300 M0b（高换手）", color=CRIMSON)
    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 0.2, f"{h:.2f}", ha="center", va="bottom", fontsize=7.8)
    ax1.set_xticks(x); ax1.set_xticklabels(cats, fontsize=8.5)
    ax1.set_ylabel("流动性硬约束容量上限（亿元）")
    ax1.set_ylim(0, max(v_hs) * 1.38)
    ax1.set_title("5% 成交参与率硬约束（P10 瓶颈）", fontsize=9.8, fontweight="bold")
    clean_ax(ax1)
    ax1.legend(loc="upper right", fontsize=7.8)

    # 右图：平方根冲击收益衰减曲线
    ax2.plot(cv08["aum_yi"], cv08["hs300_M4_main_net_ann"] * 100, color=TERRA, lw=2.2, label="沪深300 M4（Y=0.8）")
    ax2.plot(cv08["aum_yi"], cv08["zz500_M4_peer_net_ann"] * 100, color=SAGE, lw=1.9, ls="--", label="中证500 M4（Y=0.8）")
    ax2.plot(cv08["aum_yi"], cv08["hs300_M0b_highturn_net_ann"] * 100, color=CRIMSON, lw=1.5, ls="-.", label="沪深300 M0b（高换手）")
    ax2.axvspan(3.0, 6.63, color=NAVY, alpha=0.10, label="稳健区间(3–6.6亿)")
    ax2.axvline(10.0, color=AMBER, ls=":", lw=1.3)
    ax2.text(11.2, 5.8, "压测情景\n10–15亿", fontsize=8.0, color=AMBER, fontweight="bold")
    ax2.axhline(0, color=INK, lw=0.7)
    ax2.set_xscale("log")
    ax2.set_xlabel("产品管理规模 AUM（亿元，对数刻度）")
    ax2.set_ylabel("扣冲击后策略年化收益（%）")
    ax2.set_ylim(-25, 16.5)
    ax2.set_title("平方根市场冲击衰减曲线（Y=0.8）", fontsize=9.8, fontweight="bold")
    clean_ax(ax2)
    ax2.legend(loc="lower left", fontsize=8.0)
    fig.tight_layout()
    save_both(fig, "08_dual_pool_capacity_v3.png", is_slide)


def fig09_fee_nav(D: dict, is_slide: bool):
    apply_style(is_slide)
    inv = D["inv_nav"]
    fig, ax = plt.subplots(figsize=(9.0, 4.4) if is_slide else (8.4, 4.2))
    lines = [
        ("M4 策略净值（未扣产品费）", "M4_strategy_net10bp", TERRA, 2.3, "-"),
        ("方案D 纯管理费（1.5%+0.2%）", "plan_D", SAGE, 1.7, "-"),
        ("方案C 机构份额（0.6%+0.15%+超额15%）", "plan_C", NAVY, 1.9, "-"),
        ("方案A 标准份额（1.0%+0.2%+绝对20%）", "plan_A", AMBER, 1.4, "--"),
        ("方案B 超额计提（1.0%+0.2%+超额20%）", "plan_B", "#7E57C2", 1.3, "-."),
        ("沪深300基准（3.0 intraday）", "hs300_intraday", SLATE, 1.3, ":"),
    ]
    for lab, col_name, col, lw, ls in lines:
        s = inv[col_name]
        ax.plot(s.index, s.values, label=f"{lab}（{(s.iloc[-1]-1)*100:+.2f}%）", color=col, lw=lw, ls=ls)
    fmt_dates(ax)
    ax.set_ylabel("投资者到手净值（初始 = 1.0）")
    if not is_slide:
        ax.set_title("沪深300 M4 四档高水位法产品费率下投资者到手净值对比", fontweight="bold")
    clean_ax(ax)
    ax.legend(loc="upper left", fontsize=8.3)
    save_both(fig, "09_fee_net_nav_v3.png", is_slide)


def fig10_xueqiu_tracking(D: dict, is_slide: bool):
    apply_style(is_slide)
    xn = D["xq_nav"]
    xb = D["xq_bt"]
    sub = xb[(xb["base_model"] == "hs300_M4_clean") & (xb["stage"] == "all") & (xb["fee_scenario"] == "net_10bp")].set_index("mapping_scheme")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.2) if is_slide else (9.2, 4.1), gridspec_kw={"width_ratios": [1.5, 1.0]})
    ax1.plot(xn.index, xn["hs300_M4_clean_top50_ew_net_10bp"], color=NAVY, lw=2.0, label=f"M4 原策略 50只等权（{sub.loc['top50_ew','cum_return']*100:+.2f}%）")
    ax1.plot(xn.index, xn["hs300_M4_clean_xq30_buf45_tiered_net_10bp"], color=TERRA, lw=2.0, label=f"雪球30只分层+前45缓冲（{sub.loc['xq30_buf45_tiered','cum_return']*100:+.2f}%）")
    ax1.plot(xn.index, xn["hs300_M4_clean_xq30_trunc_tiered_net_10bp"], color=AMBER, lw=1.4, ls="--", label=f"直接硬截断30只分层（{sub.loc['xq30_trunc_tiered','cum_return']*100:+.2f}%）")
    ax1.plot(xn.index, xn["hs300_intraday"], color=SLATE, lw=1.2, ls=":", label="沪深300基准（-0.33%）")
    fmt_dates(ax1)
    ax1.set_ylabel("累计净值")
    ax1.set_title("M4 50只原策略 vs 雪球30只映射净值", fontsize=9.8, fontweight="bold")
    clean_ax(ax1)
    ax1.legend(loc="upper left", fontsize=8.0)

    # 右图：单边换手与跟踪误差对比
    schemes = ["top50_ew", "xq30_buf45_tiered", "xq30_trunc_tiered"]
    slabs = ["M4 原策略\n50只等权", "雪球30只分层\n(独立前45缓冲)", "直接硬截断\n30只分层"]
    turns = [sub.loc[s, "mean_half_turn"] * 100 for s in schemes]
    tes = [sub.loc[s, "tracking_error_vs_top50"] * 100 for s in schemes]
    x = np.arange(3); w = 0.34
    b1 = ax2.bar(x - w / 2, turns, w, label="每次单边换手(%)", color=TERRA)
    b2 = ax2.bar(x + w / 2, tes, w, label="相对50只年化TE(%)", color=NAVY)
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.15, f"{h:.2f}%", ha="center", va="bottom", fontsize=7.8)
    ax2.set_xticks(x); ax2.set_xticklabels(slabs, fontsize=8.0)
    ax2.set_ylabel("百分比（%）")
    ax2.set_ylim(0, max(turns) * 1.25)
    ax2.set_title("独立前45缓冲将换手压缩超一半", fontsize=9.8, fontweight="bold")
    clean_ax(ax2)
    ax2.legend(loc="upper left", fontsize=8.0)
    fig.tight_layout()
    save_both(fig, "10_xueqiu_30_tracking_v3.png", is_slide)


def main():
    D = load_all()
    funcs = [
        fig01_hs300_nav, fig02_dual_pool_bars, fig03_015_diagnosis,
        fig04_drawdown, fig05_factor_ic, fig06_fm_attribution,
        fig07_industry, fig08_capacity, fig09_fee_nav, fig10_xueqiu_tracking,
    ]
    for is_slide in (False, True):
        tag = "slide_v3" if is_slide else "report_v3"
        print(f"绘制 {tag} 全部 10 张 300 DPI 图表 ...")
        for fn in funcs:
            fn(D, is_slide)
    print(f"完成！\n  报告图: {OUT_REP}\n  PPT图 : {OUT_SLD}")


if __name__ == "__main__":
    main()
