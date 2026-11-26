#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机构级研究报告矢量图表生成器（XeLaTeX 专用版）：
动态读取 member2_signals/member2_tushare、member3_backtest/member3_v3 与 member4 结果，
输出全套深酒红（Burgundy #8B1E24）主题、黑白打印友好的矢量 PDF 图表至 figures/report_tex/。
所有图表内部均不设重复大标题（统一由 XeLaTeX 图表题注呈现），严格对齐国内头部券商金工研报规范。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

if not os.environ.get("MPLCONFIGDIR"):
    tmp_mpl = Path(tempfile.gettempdir()) / "member4_report_tex_mpl"
    tmp_mpl.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(tmp_mpl)

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import paths as P

M2_HS = P.resolve_member2_tushare_pool("hs300")
M2_ZZ = P.resolve_member2_tushare_pool("zz500")
M3_RES = P.resolve_member3_dir("v3") / "results"
M4_RES = P.MEMBER4_DIR / "results"
M4_XQ = P.MEMBER4_DIR / "xueqiu"
OUT_DIR = P.MEMBER4_DIR / "figures" / "report_tex"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 统一深酒红机构色板（兼顾灰度打印明度梯度与线型区分）
BURGUNDY = "#8B1E24"     # 主交付 M4（深酒红，最醒目实线）
BRONZE = "#9A7B4F"       # 基准 M1 / 对照（暖古铜金）
PINE = "#3B6E5C"         # 五因子 M5 / 跨池中证500（松石深绿）
SLATE_BLUE = "#3D5A73"   # 改造动量 M3b / 机构C档（钢蓝灰）
CHARCOAL = "#2E2E2E"     # 市场价格指数（炭黑点线）
MUTED_RED = "#B04A4A"    # 高换手反例 M0b / 覆盖受限组（暗砖红）
WARM_GRAY = "#8C857E"    # 辅助分界与次级序列
LIGHT_FILL = "#F6F2F0"   # 历史留后区间底纹
GRID_COL = "#E8E4DF"
INK = "#1E1E1E"

DATE_TICKS = [
    pd.Timestamp("2023-01-09"),
    pd.Timestamp("2023-07-03"),
    pd.Timestamp("2024-01-02"),
    pd.Timestamp("2024-07-01"),
    pd.Timestamp("2025-01-02"),
    pd.Timestamp("2025-07-01"),
    pd.Timestamp("2026-01-05"),
    pd.Timestamp("2026-10-30"),
]


def set_rc() -> None:
    plt.rcParams.update({
        "font.sans-serif": ["STHeiti", "Heiti SC", "PingFang SC", "Songti SC", "Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.facecolor": "#FFFFFF",
        "axes.facecolor": "#FFFFFF",
        "savefig.facecolor": "#FFFFFF",
        "axes.edgecolor": "#BFBAB3",
        "axes.linewidth": 0.75,
        "axes.labelcolor": INK,
        "xtick.color": "#3A3A3A",
        "ytick.color": "#3A3A3A",
        "text.color": INK,
        "grid.color": GRID_COL,
        "grid.linestyle": "-",
        "grid.linewidth": 0.55,
        "font.size": 8.2,
    })


def style_ax(ax, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid_axis in ("x", "y", "both"):
        ax.grid(True, axis=grid_axis, zorder=0)


def add_holdout_band(ax, idx: pd.DatetimeIndex, split_str: str = "2025-01-02", label_y: float | None = None) -> None:
    split_dt = pd.Timestamp(split_str)
    ax.axvspan(split_dt, idx.max(), color=LIGHT_FILL, alpha=0.85, zorder=0)
    ax.axvline(split_dt, color=WARM_GRAY, ls="--", lw=0.8, zorder=1)
    ax.set_xlim(idx.min(), idx.max())
    ax.set_xticks(DATE_TICKS)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    if label_y is not None:
        bbox_kw = dict(boxstyle=" square,pad=0.12", facecolor="#FFFFFF", edgecolor="none", alpha=0.82)
        ax.text(pd.Timestamp("2024-12-08"), label_y, "← 验证期 (2023–2024)", ha="right", fontsize=6.9, color="#555555", bbox=bbox_kw, zorder=4)
        ax.text(pd.Timestamp("2025-01-22"), label_y, "历史留后区间 (2025–2026.10) →", ha="left", fontsize=6.9, color="#555555", bbox=bbox_kw, zorder=4)


def save_pdf(fig, filename: str, pad: float = 0.10) -> None:
    fig.tight_layout(pad=pad)
    fig.savefig(OUT_DIR / filename, format="pdf", dpi=300, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def load_data() -> dict:
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


def fig01_cover_nav(D: dict) -> None:
    """图表 1：首页全宽沪深300核心消融组合与价格指数净值走势"""
    set_rc()
    nc, nf = D["nav_hs_clean"], D["nav_hs_full"]
    fig, ax = plt.subplots(figsize=(6.25, 1.72))
    add_holdout_band(ax, nc.index, "2025-01-02", label_y=0.665)

    series = [
        (f"M4 主交付 ({(nc['M4_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nc["M4_net_10bp"], BURGUNDY, 2.2, "-"),
        (f"M5 五因子对照 ({(nc['M5_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nc["M5_net_10bp"], PINE, 1.35, "-."),
        (f"M1 基准组合 ({(nc['M1_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nc["M1_net_10bp"], BRONZE, 1.45, "--"),
        (f"沪深300价格指数 ({(nc['hs300_intraday'].iloc[-1]-1)*100:+.2f}%)", nc["hs300_intraday"], CHARCOAL, 1.25, ":"),
        (f"M0b 高换手量价对照 ({(nf['M0b_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nf["M0b_net_10bp"], MUTED_RED, 1.05, (0, (3, 2))),
    ]
    for label, s, col, lw, ls in series:
        ax.plot(s.index, s.values, label=label, color=col, lw=lw, ls=ls, zorder=3)

    ax.axhline(1.0, color="#CCCCCC", lw=0.55, zorder=1)
    ax.set_ylim(0.63, 1.70)
    ax.set_ylabel("累计单位净值", fontsize=7.8)
    style_ax(ax, "y")
    ax.legend(
        loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="none",
        framealpha=0.88, fontsize=6.9, ncol=2, handlelength=2.1, columnspacing=0.9, labelspacing=0.18
    )
    save_pdf(fig, "fig01_cover_nav.pdf", pad=0.10)


def fig02_framework_flow(D: dict) -> None:
    """第一章：四阶段研究与组合构建流水线架构图"""
    set_rc()
    fig, ax = plt.subplots(figsize=(6.80, 2.02))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 31)
    ax.axis("off")

    stages = [
        (
            "阶段 I：双池时点数据治理",
            [
                "• 2019.01–2026.10 共1,897交易日",
                "• 沪深300(520股)/中证500(1,107股)",
                "• 94期月度成分消除幸存者偏差",
                "• 逐日ST、45天行业与90天估值上限",
                "• 18张对齐宽表与21文件哈希锁定",
            ],
            BURGUNDY,
        ),
        (
            "阶段 II：截面因子重筛与清洗",
            [
                "• 有效掩码前置，防停牌伪造低波",
                "• 101公式重筛与Holm多重检验校正",
                "• 价值双锚(BP/EP)保留行业配置溢价",
                "• 低波与低换手行业市值OLS中性化",
                "• 无量纲成交额平滑改造012检验",
            ],
            BRONZE,
        ),
        (
            "阶段 III：低换手组合与归因",
            [
                "• M0a–M5 控制变量等权消融序列",
                "• Top 50 等权与前75名保留缓冲带",
                "• 次日开盘报价与涨跌停触限过滤",
                "• 固定千1与历史减半双印花税情景",
                "• 滞后持仓7因子横截面回归归因",
            ],
            PINE,
        ),
        (
            "阶段 IV：产品设计与模拟跟踪",
            [
                "• 5%参与率P10与5日清仓边界测算",
                "• 平方根市场冲击模型多参数压测",
                "• A/B/C/D 四档年度高水位费后模拟",
                "• 雪球30股独立前45缓冲跟踪回测",
                "• ZH3689205 平台归档凭证分列披露",
            ],
            SLATE_BLUE,
        ),
    ]

    box_w = 23.3
    gap = 1.8
    x0 = 0.7
    for i, (title, bullets, accent) in enumerate(stages):
        x = x0 + i * (box_w + gap)
        card = FancyBboxPatch(
            (x, 1.2), box_w, 28.2,
            boxstyle="round,pad=0.25,rounding_size=0.55",
            linewidth=0.8, edgecolor="#D5CFC7", facecolor="#FAF8F6", zorder=1
        )
        ax.add_patch(card)
        hdr = FancyBboxPatch(
            (x, 24.5), box_w, 4.9,
            boxstyle="round,pad=0.2,rounding_size=0.45",
            linewidth=0, facecolor=accent, zorder=2
        )
        ax.add_patch(hdr)
        ax.text(x + box_w / 2, 26.95, title, ha="center", va="center", color="#FFFFFF", fontsize=6.9, fontweight="bold", zorder=3)

        for j, line in enumerate(bullets):
            ax.text(x + 0.70, 21.6 - j * 4.35, line, ha="left", va="center", color="#242424", fontsize=5.95, zorder=3)

        if i < 3:
            ax.annotate(
                "", xy=(x + box_w + gap - 0.15, 15.2), xytext=(x + box_w + 0.25, 15.2),
                arrowprops=dict(arrowstyle="-|>,head_length=0.40,head_width=0.24", lw=1.1, color=BURGUNDY),
                zorder=4,
            )

    save_pdf(fig, "fig02_framework_flow.pdf", pad=0.02)


def fig03_factor_ic_dual_pool(D: dict) -> None:
    """第三章 3.1：双股票池核心与对照因子三阶段 5日 Rank IC 均值对比"""
    set_rc()
    facs = ["bp", "ep", "lowvol_60", "lowturn_20", "new012_amt_ema10", "alpha040", "eb_proxy", "small"]
    labels = ["BP\n账面比", "EP\n盈利比", "60日\n低波动", "20日\n低换手", "改造012\n额平滑", "Alpha040\n重筛首选", "EP/BP\n比率代理", "Small\n小市值"]
    fhs = D["fic_hs"][D["fic_hs"]["horizon"] == 5].pivot(index="factor", columns="stage", values="mean_ic").loc[facs] * 100
    fzz = D["fic_zz"][D["fic_zz"]["horizon"] == 5].pivot(index="factor", columns="stage", values="mean_ic").loc[facs] * 100

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.80, 2.65), sharey=True)
    x = np.arange(len(facs))
    w = 0.25
    for ax, df, sub_title in [
        (ax1, fhs, "（a）沪深300股票池（5日 Rank IC 均值，×100）"),
        (ax2, fzz, "（b）中证500股票池（5日 Rank IC 均值，×100）"),
    ]:
        ax.bar(x - w, df["train"], w, label="训练期 (2019–2022)", color="#B8B2AA", edgecolor="#6E6A64", lw=0.45)
        ax.bar(x, df["validation"], w, label="验证期 (2023–2024)", color=BURGUNDY, edgecolor=BURGUNDY, lw=0.45)
        ax.bar(x + w, df["seen"], w, label="历史留后 (2025–2026.10)", color=PINE, edgecolor=PINE, lw=0.45, hatch="//")
        ax.axhline(0, color=INK, lw=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=6.2)
        ax.set_title(sub_title, fontsize=8.2, fontweight="bold", loc="left", pad=5, color=INK)
        style_ax(ax, "y")

    ax1.set_ylabel("5日截面 Rank IC 均值（%）", fontsize=7.8)
    ax1.set_ylim(-5.5, 9.2)
    ax1.legend(loc="upper right", frameon=True, facecolor="#FFFFFF", edgecolor="none", fontsize=6.8)
    save_pdf(fig, "fig03_factor_ic_dual_pool.pdf", pad=0.15)


def fig04_dual_pool_nav_and_bars(D: dict) -> None:
    """第三章 3.3：中证500同规格消融净值走势与双池算术夏普比率对比"""
    set_rc()
    nz = D["nav_zz"]
    m = D["metrics"]
    m_all = m[(m["stage"] == "all") & (m["fee_scenario"] == "net_10bp")]
    models = ["M0a", "M0b", "M1", "M2", "M3b", "M4", "M5"]

    hs_rows = []
    for mod in models:
        exp = "hs300_full" if mod in ("M0a", "M0b") else "hs300_clean"
        hs_rows.append(float(m_all[(m_all["experiment"] == exp) & (m_all["model"] == mod)]["sharpe_arith_rf0"].iloc[0]))
    zz_rows = [
        float(m_all[(m_all["experiment"] == "zz500") & (m_all["model"] == mod)]["sharpe_arith_rf0"].iloc[0])
        for mod in models
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.80, 2.65), gridspec_kw={"width_ratios": [1.08, 1.0]})

    # 左：中证500净值曲线
    split_dt = pd.Timestamp("2025-01-02")
    ax1.axvspan(split_dt, nz.index.max(), color=LIGHT_FILL, alpha=0.85, zorder=0)
    ax1.axvline(split_dt, color=WARM_GRAY, ls="--", lw=0.75, zorder=1)
    zz_series = [
        (f"M4 跨池对照 ({(nz['M4_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nz["M4_net_10bp"], BURGUNDY, 2.0, "-"),
        (f"M5 五因子对照 ({(nz['M5_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nz["M5_net_10bp"], PINE, 1.3, "-."),
        (f"M2 纯价值 ({(nz['M2_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nz["M2_net_10bp"], SLATE_BLUE, 1.2, (0, (5, 2))),
        (f"M1 基准组合 ({(nz['M1_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nz["M1_net_10bp"], BRONZE, 1.35, "--"),
        (f"中证500价格指数 ({(nz['benchmark_intraday'].iloc[-1]-1)*100:+.2f}%)", nz["benchmark_intraday"], CHARCOAL, 1.15, ":"),
        (f"M0b 高换手对照 ({(nz['M0b_net_10bp'].iloc[-1]-1)*100:+.2f}%)", nz["M0b_net_10bp"], MUTED_RED, 1.0, (0, (3, 2))),
    ]
    for lab, s, col, lw, ls in zz_series:
        ax1.plot(s.index, s.values, label=lab, color=col, lw=lw, ls=ls)
    ax1.axhline(1.0, color="#CCCCCC", lw=0.5)
    ax1.set_xlim(nz.index.min(), nz.index.max())
    ax1.set_xticks([pd.Timestamp("2023-01-09"), pd.Timestamp("2024-01-02"), pd.Timestamp("2025-01-02"), pd.Timestamp("2026-01-05"), pd.Timestamp("2026-10-30")])
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.set_ylim(0.65, 1.72)
    ax1.set_ylabel("累计单位净值", fontsize=7.8)
    ax1.set_title("（a）中证500同规格模型累计净值走势", fontsize=8.2, fontweight="bold", loc="left", pad=5)
    style_ax(ax1, "y")
    ax1.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="none", framealpha=0.88, fontsize=6.3)

    # 右：双池夏普对比
    x = np.arange(len(models))
    w = 0.36
    b1 = ax2.bar(x - w / 2, hs_rows, w, label="沪深300", color=BURGUNDY, edgecolor=BURGUNDY, lw=0.4)
    b2 = ax2.bar(x + w / 2, zz_rows, w, label="中证500", color=PINE, edgecolor=PINE, lw=0.4, hatch="//")
    ax2.axhline(0, color=INK, lw=0.65)
    for bar, dx in [(b, -0.06) for b in b1] + [(b, 0.06) for b in b2]:
        h = bar.get_height()
        va = "bottom" if h >= 0 else "top"
        dy = 0.022 if h >= 0 else -0.028
        ax2.text(bar.get_x() + bar.get_width() / 2 + dx, h + dy, f"{h:.2f}", ha="center", va=va, fontsize=5.2)
    ax2.set_xticks(x)
    ax2.set_xticklabels(models, fontsize=7.2)
    ax2.set_ylim(-0.34, 1.14)
    ax2.set_ylabel("算术年化夏普比率 ($r_f=0$)", fontsize=7.8)
    ax2.set_title("（b）双股票池各模型算术夏普比率对比", fontsize=8.2, fontweight="bold", loc="left", pad=5)
    style_ax(ax2, "y")
    ax2.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="none", fontsize=6.8)

    save_pdf(fig, "fig04_dual_pool_nav_and_bars.pdf", pad=0.15)


def fig05_alpha015_coverage_diag(D: dict) -> None:
    """第三章 3.4：沪深300 Alpha015 低覆盖约束对 M1 净值与单边换手的传导诊断"""
    set_rc()
    nc, nf = D["nav_hs_clean"], D["nav_hs_full"]
    tr = D["turn"]
    t_clean = tr[(tr["experiment"] == "hs300_clean") & (tr["model"] == "M1") & (tr["fee_scenario"] == "net_10bp")].set_index("execution_date")["half_turn"] * 100
    t_full = tr[(tr["experiment"] == "hs300_full") & (tr["model"] == "M1") & (tr["fee_scenario"] == "net_10bp")].set_index("execution_date")["half_turn"] * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.30, 3.05), sharex=True, gridspec_kw={"height_ratios": [1.35, 1.0]})

    add_holdout_band(ax1, nc.index, "2025-01-02")
    ax1.plot(nc.index, nc["M1_net_10bp"], color=BURGUNDY, lw=2.0, ls="-",
             label=f"解除Alpha015约束 干净共同池 M1 ({(nc['M1_net_10bp'].iloc[-1]-1)*100:+.2f}%，中位284股)")
    ax1.plot(nf.index, nf["M3a_net_10bp"], color=BRONZE, lw=1.35, ls="-.",
             label=f"原含Alpha015共同池 M3a ({(nf['M3a_net_10bp'].iloc[-1]-1)*100:+.2f}%，中位152股)")
    ax1.plot(nf.index, nf["M1_net_10bp"], color=MUTED_RED, lw=1.55, ls="--",
             label=f"原含Alpha015共同池 M1 ({(nf['M1_net_10bp'].iloc[-1]-1)*100:+.2f}%，中位152股)")
    ax1.plot(nc.index, nc["hs300_intraday"], color=CHARCOAL, lw=1.15, ls=":",
             label=f"沪深300价格指数 ({(nc['hs300_intraday'].iloc[-1]-1)*100:+.2f}%)")
    ax1.axhline(1.0, color="#CCCCCC", lw=0.5)
    ax1.set_ylabel("累计单位净值", fontsize=7.8)
    ax1.set_title("（a）同一 M1 评分公式在不同共同池约束下的扣费净值与同池 M3a 对照", fontsize=8.1, fontweight="bold", loc="left", pad=4)
    style_ax(ax1, "y")
    ax1.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="none", framealpha=0.88, fontsize=6.7, ncol=2)

    add_holdout_band(ax2, nc.index, "2025-01-02")
    ax2.plot(t_full.iloc[1:].index, t_full.iloc[1:].values, color=MUTED_RED, lw=1.05, ls="-", alpha=0.88,
             label=f"原含Alpha015共同池 M1 每次单边换手（全期均值 {t_full.mean():.2f}%）")
    ax2.plot(t_clean.iloc[1:].index, t_clean.iloc[1:].values, color=BURGUNDY, lw=1.6, ls="-",
             label=f"解除Alpha015约束 干净共同池 M1 每次单边换手（全期均值 {t_clean.mean():.2f}%）")
    ax2.set_ylabel("单次单边换手（%）", fontsize=7.8)
    ax2.set_ylim(0, 72)
    ax2.set_title("（b）常规调仓日账户实际单边换手率序列（不含首期建仓日）", fontsize=8.1, fontweight="bold", loc="left", pad=4)
    style_ax(ax2, "y")
    ax2.legend(loc="upper right", frameon=True, facecolor="#FFFFFF", edgecolor="none", framealpha=0.88, fontsize=6.8)

    save_pdf(fig, "fig05_alpha015_coverage_diag.pdf", pad=0.14)


def fig06_fm_attribution_dual_pool(D: dict) -> None:
    """第四章 4.1：双股票池 M4 对照 M1 / M5 的滞后持仓 7因子 Fama-MacBeth 收益归因图"""
    set_rc()
    dec = D["decomp"]
    comps = [
        "market_intercept", "factor_bp", "factor_ep", "factor_lowvol_60", "factor_lowturn_20",
        "factor_small", "factor_eb_proxy", "factor_new012_amt_ema10",
        "specific_residual_and_timing", "transaction_cost",
    ]
    clabs = ["市场截距项", "BP 价值暴露", "EP 盈利暴露", "60日低波暴露", "20日低换手暴露", "规模代理暴露", "E/B 代理暴露", "改造012暴露", "特异残差与择时", "交易成本拖累"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.30, 2.95), sharey=True)
    y = np.arange(len(comps))
    h = 0.25
    for ax, exp, sub_title in [
        (ax1, "hs300_clean", "（a）沪深300（干净共同池）算术年化归因（%）"),
        (ax2, "zz500", "（b）中证500（共同池）算术年化归因（%）"),
    ]:
        sub = dec[(dec["experiment"] == exp) & (dec["model"].isin(["M1", "M4", "M5"]))].pivot(index="component", columns="model", values="ann_arith_pct").loc[comps] * 100
        ax.barh(y - h, sub["M4"], h, label="M4（主交付四因子）", color=BURGUNDY, edgecolor=BURGUNDY, lw=0.35)
        ax.barh(y, sub["M5"], h, label="M5（五因子含E/B代理）", color=PINE, edgecolor=PINE, lw=0.35, hatch="//")
        ax.barh(y + h, sub["M1"], h, label="M1（三因子基准）", color=BRONZE, edgecolor=BRONZE, lw=0.35)
        ax.axvline(0, color=INK, lw=0.7)
        ax.set_yticks(y)
        ax.set_yticklabels(clabs, fontsize=7.2)
        ax.invert_yaxis()
        ax.set_xlabel("算术年化收益贡献（百分点/年）", fontsize=7.6)
        ax.set_title(sub_title, fontsize=8.1, fontweight="bold", loc="left", pad=5)
        style_ax(ax, "x")

    ax1.legend(loc="lower right", frameon=True, facecolor="#FFFFFF", edgecolor="none", framealpha=0.9, fontsize=6.7)
    save_pdf(fig, "fig06_fm_attribution_dual_pool.pdf", pad=0.14)


def fig07_industry_exposure(D: dict) -> None:
    """第四章 4.2：申万一级行业暴露结构与双池金融板块集中度对比"""
    set_rc()
    ind = D["ind"]
    hs_full = ind[(ind["experiment"] == "hs300_clean") & (ind["scope"] == "full_mean")]
    top_inds = hs_full[hs_full["model"] == "M4"].sort_values("weight", ascending=False).head(8)["sw_l1_name"].tolist()
    piv_hs = hs_full[hs_full["model"].isin(["M1", "M2", "M4"])].pivot(index="sw_l1_name", columns="model", values="weight").reindex(top_inds).fillna(0) * 100

    zz_full = ind[(ind["experiment"] == "zz500") & (ind["scope"] == "full_mean") & (ind["model"] == "M4")].set_index("sw_l1_name")["weight"] * 100
    hs_m4 = hs_full[hs_full["model"] == "M4"].set_index("sw_l1_name")["weight"] * 100
    comp_cats = ["银行", "非银金融", "交通运输", "建筑装饰", "公用事业", "煤炭", "机械设备", "汽车"]
    hs_vals = [hs_m4.get(c, 0.0) for c in comp_cats]
    zz_vals = [zz_full.get(c, 0.0) for c in comp_cats]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.30, 2.50))
    x = np.arange(len(top_inds))
    w = 0.26
    ax1.bar(x - w, piv_hs["M4"], w, label="M4（金融均值 42.4%）", color=BURGUNDY)
    ax1.bar(x, piv_hs["M2"], w, label="M2 纯价值（金融均值 48.2%）", color=MUTED_RED, hatch="//")
    ax1.bar(x + w, piv_hs["M1"], w, label="M1 基准（金融均值 38.8%）", color=BRONZE)
    ax1.set_xticks(x)
    ax1.set_xticklabels(top_inds, rotation=28, ha="right", fontsize=7.0)
    ax1.set_ylabel("全期平均开盘持仓权重（%）", fontsize=7.6)
    ax1.set_title("（a）沪深300：M4 对照 M2 / M1 前8大重仓行业", fontsize=8.0, fontweight="bold", loc="left", pad=5)
    style_ax(ax1, "y")
    ax1.legend(loc="upper right", frameon=True, facecolor="#FFFFFF", edgecolor="none", fontsize=6.6)

    x2 = np.arange(len(comp_cats))
    w2 = 0.35
    ax2.bar(x2 - w2 / 2, hs_vals, w2, label="沪深300 M4（金融均值 42.4%）", color=BURGUNDY)
    ax2.bar(x2 + w2 / 2, zz_vals, w2, label="中证500 M4（金融均值 22.3%）", color=PINE, hatch="//")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(comp_cats, rotation=28, ha="right", fontsize=7.0)
    ax2.set_ylabel("全期平均开盘持仓权重（%）", fontsize=7.6)
    ax2.set_title("（b）沪深300 M4 与中证500 M4 行业分散度对比", fontsize=8.0, fontweight="bold", loc="left", pad=5)
    style_ax(ax2, "y")
    ax2.legend(loc="upper right", frameon=True, facecolor="#FFFFFF", edgecolor="none", fontsize=6.6)

    save_pdf(fig, "fig07_industry_exposure.pdf", pad=0.14)


def fig08_underwater_drawdown(D: dict) -> None:
    """第四章 4.2：核心组合与市场价格指数动态水下回撤曲线"""
    set_rc()
    nc, nf, nz = D["nav_hs_clean"], D["nav_hs_full"], D["nav_zz"]
    fig, ax = plt.subplots(figsize=(6.30, 2.25))
    add_holdout_band(ax, nc.index, "2025-01-02")

    items = [
        ("沪深300 M4 主交付", nc["M4_net_10bp"], BURGUNDY, 2.0, "-"),
        ("沪深300 M1 基准组合", nc["M1_net_10bp"], BRONZE, 1.35, "--"),
        ("中证500 M4 跨池对照", nz["M4_net_10bp"], PINE, 1.35, "-."),
        ("沪深300价格指数", nc["hs300_intraday"], CHARCOAL, 1.2, ":"),
        ("沪深300 M0b 高换手对照", nf["M0b_net_10bp"], MUTED_RED, 1.05, (0, (3, 2))),
    ]
    for lab, s, col, lw, ls in items:
        dd = (s / s.cummax().clip(lower=1.0) - 1.0) * 100
        ax.plot(dd.index, dd.values, label=f"{lab}（最大回撤 {dd.min():.2f}%）", color=col, lw=lw, ls=ls, zorder=3)
        if col == BURGUNDY:
            ax.fill_between(dd.index, dd.values, 0, color=BURGUNDY, alpha=0.09, zorder=2)
            trough_dt = dd.idxmin()
            trough_dd = float(dd.min())
            ax.scatter([trough_dt], [trough_dd], color=BURGUNDY, s=18, zorder=4)
            ax.annotate(
                f"M4最大回撤谷底\n2026-06-30 ({trough_dd:.2f}%)",
                xy=(trough_dt, trough_dd),
                xytext=(pd.Timestamp("2025-04-15"), -17.5),
                fontsize=6.5, color=BURGUNDY,
                bbox=dict(boxstyle="square,pad=0.15", facecolor="#FFFFFF", edgecolor="none", alpha=0.85),
                arrowprops=dict(arrowstyle="->", lw=0.75, color=BURGUNDY),
                zorder=5,
            )

    ax.axhline(0, color="#999999", lw=0.6)
    ax.set_ylim(-31.0, 1.5)
    ax.set_ylabel("动态水下回撤（%）", fontsize=7.8)
    style_ax(ax, "y")
    ax.legend(loc="lower left", frameon=True, facecolor="#FFFFFF", edgecolor="none", framealpha=0.9, fontsize=6.7, ncol=2)
    save_pdf(fig, "fig08_underwater_drawdown.pdf", pad=0.12)


def fig09_fee_hwm_nav(D: dict) -> None:
    """第五章 5.2：四档高水位法产品费率方案下投资者历史模拟净值曲线"""
    set_rc()
    inv = D["inv_nav"]
    fig, ax = plt.subplots(figsize=(6.30, 2.35))
    add_holdout_band(ax, inv.index, "2025-01-02")

    lines = [
        ("策略净值（未扣产品费，已含交易费）", "M4_strategy_net10bp", BURGUNDY, 2.1, "-"),
        ("方案 D（纯管理费：1.50%+0.20%）", "plan_D", PINE, 1.5, "-."),
        ("方案 C（机构份额：0.60%+0.15%+超额15%）", "plan_C", SLATE_BLUE, 1.85, "-"),
        ("方案 A（标准份额：1.00%+0.20%+绝对20%）", "plan_A", BRONZE, 1.35, "--"),
        ("方案 B（超额计提：1.00%+0.20%+超额20%）", "plan_B", MUTED_RED, 1.2, (0, (3, 2))),
        ("沪深300价格指数（计提对比基准）", "hs300_intraday", CHARCOAL, 1.15, ":"),
    ]
    for lab, col_name, col, lw, ls in lines:
        s = inv[col_name]
        ax.plot(s.index, s.values, label=f"{lab} ({(s.iloc[-1]-1)*100:+.2f}%)", color=col, lw=lw, ls=ls)

    for dt_str in ["2023-12-29", "2024-12-31", "2025-12-31"]:
        ax.axvline(pd.Timestamp(dt_str), color="#D0C9C0", ls=":", lw=0.65, zorder=1)

    ax.axhline(1.0, color="#CCCCCC", lw=0.5)
    ax.set_ylim(0.76, 1.68)
    ax.set_ylabel("历史模拟单位净值", fontsize=7.8)
    style_ax(ax, "y")
    ax.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="none", framealpha=0.9, fontsize=6.6, ncol=2)
    save_pdf(fig, "fig09_fee_hwm_nav.pdf", pad=0.12)


def fig10_capacity_impact(D: dict) -> None:
    """第五章 5.3：双股票池 5% 参与率 P10 容量边界与平方根冲击衰减曲线"""
    set_rc()
    cc = D["cap_c"]
    cv = D["cap_curve"]
    cv05 = cv[cv["Y"] == 0.5].sort_values("aum_yi")
    cv08 = cv[cv["Y"] == 0.8].sort_values("aum_yi")
    cv10 = cv[cv["Y"] == 1.0].sort_values("aum_yi")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.30, 2.50))

    cats = ["单日调仓\n(5%参与率 P10)", "假设3日拆单\n(5%参与率 P10)", "5日清仓变现\n(5%参与率 P10)"]

    def gp(m: str, ct: str, win: int) -> float:
        return float(cc[(cc["model"] == m) & (cc["constraint_type"] == ct) & (cc["participation_rate"] == 0.05) & (cc["window_days"] == win)]["p10_yi"].iloc[0])

    v_hs = [gp("hs300_M4_main", "rebalance_participation", 1), gp("hs300_M4_main", "rebalance_participation", 3), gp("hs300_M4_main", "liquidation_5d", 5)]
    v_zz = [gp("zz500_M4_peer", "rebalance_participation", 1), gp("zz500_M4_peer", "rebalance_participation", 3), gp("zz500_M4_peer", "liquidation_5d", 5)]
    v_m0b = [gp("hs300_M0b_highturn", "rebalance_participation", 1), gp("hs300_M0b_highturn", "rebalance_participation", 3), gp("hs300_M0b_highturn", "liquidation_5d", 5)]

    x = np.arange(3)
    w = 0.25
    b1 = ax1.bar(x - w, v_hs, w, label="沪深300 M4", color=BURGUNDY)
    b2 = ax1.bar(x, v_zz, w, label="中证500 M4", color=PINE, hatch="//")
    b3 = ax1.bar(x + w, v_m0b, w, label="沪深300 M0b", color=BRONZE)
    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 0.22, f"{h:.2f}", ha="center", va="bottom", fontsize=6.4)
    ax1.set_xticks(x)
    ax1.set_xticklabels(cats, fontsize=6.8)
    ax1.set_ylim(0, 12.6)
    ax1.set_ylabel("P10 瓶颈资金规模（亿元）", fontsize=7.6)
    ax1.set_title("（a）5%成交参与率下 P10 容量指标对比", fontsize=8.0, fontweight="bold", loc="left", pad=5)
    style_ax(ax1, "y")
    ax1.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="none", fontsize=6.7)

    # 右图：平方根冲击模型衰减曲线（含 Y=0.5~1.0 敏感性带）
    ax2.fill_between(
        cv08["aum_yi"],
        cv10["hs300_M4_main_net_ann"] * 100,
        cv05["hs300_M4_main_net_ann"] * 100,
        color=BURGUNDY, alpha=0.12, label="沪深300 M4 (Y=0.5–1.0 敏感带)"
    )
    ax2.plot(cv08["aum_yi"], cv08["hs300_M4_main_net_ann"] * 100, color=BURGUNDY, lw=2.0, ls="-", label="沪深300 M4 (Y=0.8)")
    ax2.plot(cv08["aum_yi"], cv08["zz500_M4_peer_net_ann"] * 100, color=PINE, lw=1.6, ls="--", label="中证500 M4 (Y=0.8)")
    ax2.plot(cv08["aum_yi"], cv08["hs300_M0b_highturn_net_ann"] * 100, color=MUTED_RED, lw=1.25, ls="-.", label="沪深300 M0b (Y=0.8)")
    ax2.axvspan(3.0, 6.0, color=BRONZE, alpha=0.14, label="3–6亿元低超限募资情景")
    ax2.axvline(10.0, color=SLATE_BLUE, ls=":", lw=0.9)
    ax2.axvline(15.0, color=SLATE_BLUE, ls=":", lw=0.9)
    ax2.axhline(0, color=INK, lw=0.6)
    ax2.set_xscale("log")
    ax2.set_xlabel("资产管理规模（亿元，对数坐标）", fontsize=7.6)
    ax2.set_ylabel("扣除冲击成本后几何年化（%）", fontsize=7.6)
    ax2.set_ylim(-24, 16.5)
    ax2.set_title("（b）平方根市场冲击模型下年化净收益衰减", fontsize=8.0, fontweight="bold", loc="left", pad=5)
    style_ax(ax2, "y")
    ax2.legend(loc="lower left", frameon=True, facecolor="#FFFFFF", edgecolor="none", framealpha=0.9, fontsize=6.2)

    save_pdf(fig, "fig10_capacity_impact.pdf", pad=0.14)


def fig11_xueqiu_tracking(D: dict) -> None:
    """第五章 5.4：50股主回测与雪球30股分层映射的历史净值及换手跟踪误差对比"""
    set_rc()
    xn = D["xq_nav"]
    xb = D["xq_bt"]
    sub = xb[(xb["base_model"] == "hs300_M4_clean") & (xb["stage"] == "all") & (xb["fee_scenario"] == "net_10bp")].set_index("mapping_scheme")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.30, 2.45), gridspec_kw={"width_ratios": [1.45, 1.0]})

    split_dt = pd.Timestamp("2025-01-02")
    ax1.axvspan(split_dt, xn.index.max(), color=LIGHT_FILL, alpha=0.85, zorder=0)
    ax1.axvline(split_dt, color=WARM_GRAY, ls="--", lw=0.75, zorder=1)
    ax1.plot(xn.index, xn["hs300_M4_clean_top50_ew_net_10bp"], color=BURGUNDY, lw=2.0, ls="-",
             label=f"M4 50股等权主回测 ({sub.loc['top50_ew','cum_return']*100:+.2f}%)")
    ax1.plot(xn.index, xn["hs300_M4_clean_xq30_buf45_tiered_net_10bp"], color=PINE, lw=1.6, ls="--",
             label=f"M4 30股分层+前45缓冲 ({sub.loc['xq30_buf45_tiered','cum_return']*100:+.2f}%)")
    ax1.plot(xn.index, xn["hs300_M4_clean_xq30_trunc_tiered_net_10bp"], color=BRONZE, lw=1.25, ls="-.",
             label=f"M4 30股无缓冲截断 ({sub.loc['xq30_trunc_tiered','cum_return']*100:+.2f}%)")
    ax1.plot(xn.index, xn["hs300_intraday"], color=CHARCOAL, lw=1.1, ls=":",
             label=f"沪深300价格指数 ({(xn['hs300_intraday'].iloc[-1]-1)*100:+.2f}%)")
    ax1.set_xlim(xn.index.min(), xn.index.max())
    ax1.set_xticks([pd.Timestamp("2023-01-09"), pd.Timestamp("2024-01-02"), pd.Timestamp("2025-01-02"), pd.Timestamp("2026-01-05"), pd.Timestamp("2026-10-30")])
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.set_ylabel("累计单位净值", fontsize=7.8)
    ax1.set_title("（a）M4 50股原策略与30股历史映射净值走势", fontsize=8.0, fontweight="bold", loc="left", pad=5)
    style_ax(ax1, "y")
    ax1.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="none", framealpha=0.9, fontsize=6.4)

    schemes = ["top50_ew", "xq30_buf45_tiered", "xq30_trunc_tiered"]
    slabs = ["50股原策略\n(前75缓冲)", "30股映射\n(前45缓冲)", "30股截断\n(无独立缓冲)"]
    turns = [sub.loc[s, "mean_half_turn"] * 100 for s in schemes]
    tes = [sub.loc[s, "tracking_error_vs_top50"] * 100 for s in schemes]
    x = np.arange(3)
    w = 0.34
    b1 = ax2.bar(x - w / 2, turns, w, label="单次单边换手(%)", color=BURGUNDY)
    b2 = ax2.bar(x + w / 2, tes, w, label="相对50股年化TE(%)", color=SLATE_BLUE, hatch="//")
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.16, f"{h:.2f}", ha="center", va="bottom", fontsize=6.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels(slabs, fontsize=6.8)
    ax2.set_ylim(0, 9.4)
    ax2.set_ylabel("百分比（%）", fontsize=7.6)
    ax2.set_title("（b）独立前45缓冲对换手率的压降效果", fontsize=8.0, fontweight="bold", loc="left", pad=5)
    style_ax(ax2, "y")
    ax2.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="none", fontsize=6.6)

    save_pdf(fig, "fig11_xueqiu_tracking.pdf", pad=0.14)


def main() -> None:
    D = load_data()
    builders = [
        fig01_cover_nav,
        fig02_framework_flow,
        fig03_factor_ic_dual_pool,
        fig04_dual_pool_nav_and_bars,
        fig05_alpha015_coverage_diag,
        fig06_fm_attribution_dual_pool,
        fig07_industry_exposure,
        fig08_underwater_drawdown,
        fig09_fee_hwm_nav,
        fig10_capacity_impact,
        fig11_xueqiu_tracking,
    ]
    for fn in builders:
        fn(D)
    print(f"成功生成 {len(builders)} 张机构级矢量 PDF 图表 -> {OUT_DIR}")


if __name__ == "__main__":
    main()
