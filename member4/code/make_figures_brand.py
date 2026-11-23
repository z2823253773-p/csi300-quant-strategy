# -*- coding: utf-8 -*-
"""
组员4：Anthropic brand-guidelines + competitive-analysis 双技能版 PPT 图表脚本
严格遵循 Anthropic 官方三强调色系统：
- Main: Dark #141413, Light #FAF9F5, Mid Gray #B0AEA5, Light Gray #E8E6DC
- Accents: Orange #D97757, Blue #6A9BCC, Green #788C5D
输出 8 张 300 DPI 无框纸面底色图表至 member4/figures/slide_brand/。
复现命令（在 member4 目录）：
    .venv/bin/python code/make_figures_brand.py
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

if not os.environ.get("MPLCONFIGDIR"):
    default_mpl = Path.home() / ".matplotlib"
    try:
        default_mpl.mkdir(parents=True, exist_ok=True)
        test_file = default_mpl / ".write_test"
        test_file.touch()
        test_file.unlink()
    except OSError:
        tmp_mpl = Path(tempfile.gettempdir()) / "member4_mpl_cache"
        tmp_mpl.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(tmp_mpl)

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from paths import M2_RES, M3_RES, MEMBER4_DIR

M4_RES = MEMBER4_DIR / "results"
OUT_DIR = MEMBER4_DIR / "figures" / "slide_brand"

# ---------------------------------------------------------------------------
# Anthropic Official brand-guidelines Color System
# ---------------------------------------------------------------------------
DARK = "#141413"        # Main Dark
LIGHT = "#FAF9F5"       # Main Light (Slide Canvas)
MID_GRAY = "#B0AEA5"    # Main Mid Gray
LIGHT_GRAY = "#E8E6DC"  # Main Light Gray

ORANGE = "#D97757"      # Primary Accent
ORANGE_DEEP = "#C05E3D" # High-contrast Orange text
BLUE = "#6A9BCC"        # Secondary Accent
BLUE_DEEP = "#4879AA"   # High-contrast Blue text
GREEN = "#788C5D"       # Tertiary Accent
GREEN_DEEP = "#596D42"  # High-contrast Green text

TEXT_SUB = "#595751"
GRID = "#EAE7DE"
SPINE = "#D2CFC5"
ORANGE_TINT = "#F5E4DC"
GREEN_TINT = "#EBF0E4"
BLUE_TINT = "#E6EFF7"

FONT_LIST = ["PingFang SC", "Heiti SC", "Arial", "Songti SC", "Georgia", "DejaVu Sans"]

BACKTEST_TICKS = [
    pd.Timestamp("2023-06-01"),
    pd.Timestamp("2024-06-01"),
    pd.Timestamp("2025-06-01"),
    pd.Timestamp("2026-06-01"),
]


def apply_brand_style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": FONT_LIST,
        "axes.unicode_minus": False,
        "figure.facecolor": LIGHT,
        "axes.facecolor": LIGHT,
        "savefig.facecolor": LIGHT,
        "savefig.edgecolor": "none",
        "axes.edgecolor": SPINE,
        "axes.linewidth": 0.8,
        "axes.labelsize": 11.0,
        "axes.labelcolor": TEXT_SUB,
        "xtick.labelsize": 10.0,
        "ytick.labelsize": 10.0,
        "xtick.color": TEXT_SUB,
        "ytick.color": TEXT_SUB,
        "xtick.major.size": 3.0,
        "ytick.major.size": 0.0,
        "grid.color": GRID,
        "grid.linewidth": 0.65,
        "grid.linestyle": "-",
        "text.color": DARK,
    })


def style_axes(ax, grid_axis: str = "y", zero_line: bool = False):
    ax.set_facecolor(LIGHT)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SPINE)
    ax.spines["bottom"].set_color(SPINE)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.set_axisbelow(True)
    if grid_axis in ("y", "x", "both"):
        ax.grid(True, axis=grid_axis, color=GRID, linewidth=0.65)
    else:
        ax.grid(False)
    if zero_line:
        ax.axhline(0.0, color=MID_GRAY, linewidth=0.9, linestyle="-", zorder=1)


def _fmt_date_axis(ax):
    ax.set_xticks(BACKTEST_TICKS)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))


def _add_oos_split(ax, y_frac: float = 0.97):
    split_dt = pd.Timestamp("2025-01-01")
    ax.axvline(split_dt, color=MID_GRAY, linestyle=":", linewidth=1.15, zorder=1)
    ax.text(
        split_dt, y_frac, " 验证期 | 样本外 ",
        transform=ax.get_xaxis_transform(),
        ha="center", va="top",
        fontsize=9.5,
        color=TEXT_SUB,
        bbox=dict(boxstyle="round,pad=0.18", facecolor=LIGHT, edgecolor="none", alpha=0.92),
    )


def label_line_ends(ax, items: list[dict], right_pad_frac: float = 0.28, min_gap_frac: float = 0.088):
    if not items:
        return
    x0, x1 = ax.get_xlim()
    dx = x1 - x0
    if dx > 0:
        ax.set_xlim(x0, x1 + dx * right_pad_frac)

    y0, y1 = ax.get_ylim()
    yr = y1 - y0 if (y1 - y0) > 0 else 1.0

    parsed = sorted(
        [{
            "x": it["x"],
            "y": float(it["y"]),
            "text": it["text"],
            "color": it["color"],
            "weight": it.get("weight", "semibold"),
            "fontsize": it.get("fontsize", 10.2),
        } for it in items],
        key=lambda d: d["y"],
    )

    min_gap = yr * min_gap_frac
    ys = [d["y"] for d in parsed]
    for i in range(1, len(ys)):
        if ys[i] - ys[i - 1] < min_gap:
            ys[i] = ys[i - 1] + min_gap
    if ys[-1] > y1 - 0.03 * yr:
        shift = ys[-1] - (y1 - 0.03 * yr)
        ys = [y - shift for y in ys]
        for i in range(len(ys) - 2, -1, -1):
            if ys[i + 1] - ys[i] < min_gap:
                ys[i] = ys[i + 1] - min_gap

    x_end = parsed[0]["x"]
    for d, y_adj in zip(parsed, ys):
        ax.annotate(
            d["text"],
            xy=(x_end, d["y"]),
            xytext=(8, 0) if abs(y_adj - d["y"]) < 0.015 * yr else (10, (y_adj - d["y"]) / yr * 180),
            textcoords="offset points",
            va="center", ha="left",
            fontsize=d["fontsize"],
            fontweight=d["weight"],
            color=d["color"],
            clip_on=False,
        )


def save_brand_fig(fig, filename: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / filename
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.14, facecolor=LIGHT)
    plt.close(fig)
    print(f"[brand fig] saved {out.name}")


def load_all_data() -> dict:
    nav = pd.read_csv(M3_RES / "nav.csv", index_col=0, parse_dates=True)
    metrics = pd.read_csv(M3_RES / "metrics.csv")
    turn = pd.read_csv(M3_RES / "turnover.csv", index_col=0, parse_dates=True)
    pic = pd.read_csv(M2_RES / "proportional_ic.csv")
    cap_curve = pd.read_csv(M4_RES / "capacity_curve.csv")
    inv_nav = pd.read_csv(M4_RES / "investor_nav.csv", index_col=0, parse_dates=True)
    fee_df = pd.read_csv(M4_RES / "fee_analysis.csv")
    ind_df = pd.read_csv(M4_RES / "latest_industry_distribution.csv")
    with open(M4_RES / "product_summary.json", "r", encoding="utf-8") as f:
        prod = json.load(f)
    return {
        "nav": nav,
        "metrics": metrics,
        "turn": turn,
        "proportional_ic": pic,
        "cap_curve": cap_curve,
        "inv_nav": inv_nav,
        "fee_df": fee_df,
        "ind_df": ind_df,
        "prod": prod,
    }


def plot_01_nav_curve(data: dict):
    apply_brand_style()
    nav = data["nav"]
    fig, ax = plt.subplots(figsize=(6.3, 4.3), facecolor=LIGHT)

    ax.axhline(1.0, color=LIGHT_GRAY, lw=1.1, ls="-", zorder=1)
    ax.plot(nav.index, nav["hs300"], color=BLUE, ls="--", lw=1.8, zorder=2)
    ax.plot(nav.index, nav["research"], color=MID_GRAY, ls="-", lw=1.8, zorder=3)
    ax.plot(nav.index, nav["baseline"], color=ORANGE, ls="-", lw=2.6, zorder=4)

    style_axes(ax, grid_axis="y")
    ax.set_ylim(0.76, 1.56)
    _add_oos_split(ax, y_frac=0.97)
    ax.set_ylabel("累计单位净值")

    last_d = nav.index[-1]
    label_line_ends(ax, [
        {"x": last_d, "y": nav["baseline"].iloc[-1], "text": f"Baseline  {nav['baseline'].iloc[-1]:.3f}", "color": ORANGE_DEEP, "weight": "bold", "fontsize": 10.2},
        {"x": last_d, "y": nav["hs300"].iloc[-1], "text": f"沪深300  {nav['hs300'].iloc[-1]:.3f}", "color": BLUE_DEEP, "fontsize": 9.8},
        {"x": last_d, "y": nav["research"].iloc[-1], "text": f"Research  {nav['research'].iloc[-1]:.3f}", "color": TEXT_SUB, "fontsize": 9.8},
    ], right_pad_frac=0.31, min_gap_frac=0.09)
    _fmt_date_axis(ax)

    save_brand_fig(fig, "01_nav_curve.png")


def plot_02_positioning_2x2(data: dict):
    """competitive-analysis Step 5: 2x2 Competitive Positioning Matrix."""
    apply_brand_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.9), facecolor=LIGHT)

    # X: Cost & Turnover Efficiency = 100 - avg one-way turnover (%)  -> higher right = lower turnover
    # Y: Net Risk-Adjusted Performance (Sharpe Ratio)
    # Quadrants divided at x=72 (28% turnover) and y=0.25 (Sharpe 0.25)
    x_mid, y_mid = 72.0, 0.25

    # Highlight top-right golden quadrant (Low Turnover x High Sharpe)
    rect = mpatches.Rectangle((x_mid, y_mid), 106 - x_mid, 0.96 - y_mid,
                              facecolor=GREEN_TINT, edgecolor="none", alpha=0.65, zorder=0)
    ax.add_patch(rect)
    # Subtle warning tint for bottom-left (High Turnover x Negative Sharpe)
    rect_bl = mpatches.Rectangle((36, -0.34), x_mid - 36, y_mid - (-0.34),
                                 facecolor=LIGHT_GRAY, edgecolor="none", alpha=0.55, zorder=0)
    ax.add_patch(rect_bl)

    ax.axvline(x_mid, color=MID_GRAY, ls="--", lw=1.0, zorder=1)
    ax.axhline(y_mid, color=MID_GRAY, ls="--", lw=1.0, zorder=1)
    ax.axhline(0.0, color=SPINE, ls=":", lw=0.9, zorder=1)

    # Quadrant corner labels
    ax.text(104.2, 0.91, "黄金稀缺象限\n低换手 · 高风险收益比", ha="right", va="top",
            fontsize=9.8, fontweight="bold", color=GREEN_DEEP)
    ax.text(37.8, -0.30, "摩擦损耗象限 · 高换手成本侵蚀", ha="left", va="bottom",
            fontsize=9.3, color=TEXT_SUB)
    ax.text(37.8, 0.91, "高换手高频区 · 依赖极低冲击基础设施", ha="left", va="top",
            fontsize=9.0, color=MID_GRAY)
    ax.text(104.2, -0.30, "被动跟踪区 · 零超额收益", ha="right", va="bottom",
            fontsize=9.0, color=BLUE_DEEP)

    # Plot empirical strategy points (all 4 markers clearly visible!)
    # 1. Baseline: turnover 5.9% -> x=94.1, Sharpe 0.67
    ax.scatter([94.1], [0.67], s=320, color=ORANGE, edgecolors=LIGHT, linewidths=2.2, zorder=6)
    ax.annotate(
        "Baseline 主策略\n单边换手 5.9% | 夏普 0.67\n计成本年化 +10.78%",
        xy=(93.0, 0.63), xytext=(75.5, 0.30),
        fontsize=9.6, fontweight="bold", color=ORANGE_DEEP,
        bbox=dict(boxstyle="round,pad=0.34", facecolor=LIGHT, edgecolor=ORANGE, lw=1.2),
        arrowprops=dict(arrowstyle="->", color=ORANGE_DEEP, lw=1.25),
        zorder=7,
    )

    # 2. HS300 Benchmark: turnover ~0% -> x=100, Sharpe 0.00
    ax.scatter([100.0], [0.00], s=180, color=BLUE, edgecolors=LIGHT, linewidths=1.8, zorder=6)
    ax.annotate(
        "沪深300 基准指数\n被动跟踪 | 夏普 0.00 | 年化 +0.03%",
        xy=(98.8, -0.02), xytext=(73.2, -0.18),
        fontsize=9.1, fontweight="semibold", color=BLUE_DEEP,
        bbox=dict(boxstyle="round,pad=0.26", facecolor=LIGHT, edgecolor=BLUE, lw=0.95),
        arrowprops=dict(arrowstyle="->", color=BLUE_DEEP, lw=1.05),
        zorder=7,
    )

    # 3. Research (5d high turnover): turnover 51.2% -> x=48.8, Sharpe -0.11
    ax.scatter([48.8], [-0.11], s=210, color=MID_GRAY, edgecolors=DARK, linewidths=1.3, zorder=6)
    ax.annotate(
        "Research 量价对照 (5日)\n单边换手 51.2% | 夏普 -0.11\n年化 -1.83% (成本吞噬 37.2 pct)",
        xy=(48.8, -0.07), xytext=(38.2, 0.06),
        fontsize=9.1, fontweight="semibold", color=DARK,
        bbox=dict(boxstyle="round,pad=0.28", facecolor=LIGHT, edgecolor=MID_GRAY, lw=1.0),
        arrowprops=dict(arrowstyle="->", color=TEXT_SUB, lw=1.05),
        zorder=7,
    )

    # 4. 20-day De-frequencied Research (diagnostic)
    ax.scatter([77.5], [0.58], s=175, facecolors=LIGHT, edgecolors=GREEN, linewidths=2.4, zorder=6)
    ax.annotate(
        "Research 20日降频情景 (诊断)\n年成交降至 14× | 样本外 10bp 净年化 10.4%",
        xy=(75.8, 0.58), xytext=(38.2, 0.65),
        fontsize=9.0, fontweight="semibold", color=GREEN_DEEP,
        bbox=dict(boxstyle="round,pad=0.28", facecolor=LIGHT, edgecolor=GREEN, lw=1.0),
        arrowprops=dict(arrowstyle="->", color=GREEN_DEEP, lw=1.05, ls="--"),
        zorder=7,
    )

    # Trajectory arrow from Research 5d -> 20d diagnostic
    ax.annotate(
        "", xy=(76.2, 0.54), xytext=(50.6, -0.07),
        arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.35, ls=":", connectionstyle="arc3,rad=-0.16"),
        zorder=4,
    )
    ax.text(63.2, 0.34, "降频缓释路径", fontsize=8.8, color=GREEN_DEEP, rotation=36, ha="center")

    style_axes(ax, grid_axis="none")
    ax.set_xlim(36, 106)
    ax.set_ylim(-0.34, 0.96)
    ax.set_xticks([45, 60, 75, 90, 100])
    ax.set_xticklabels(["高换手\n55%", "40%", "25%", "低换手\n10%", "极低\n0%"])
    ax.set_xlabel("换手率与成本效率（单边换手率越低越靠右）", labelpad=8)
    ax.set_ylabel("全样本计成本夏普比率")

    save_brand_fig(fig, "02_positioning_2x2.png")


def plot_03_drawdown_underwater(data: dict):
    apply_brand_style()
    nav = data["nav"]
    fig, ax = plt.subplots(figsize=(6.3, 4.3), facecolor=LIGHT)

    dd_b = (nav["baseline"] / nav["baseline"].cummax() - 1.0) * 100
    dd_r = (nav["research"] / nav["research"].cummax() - 1.0) * 100
    dd_h = (nav["hs300"] / nav["hs300"].cummax() - 1.0) * 100

    ax.plot(dd_h.index, dd_h, color=BLUE, ls="--", lw=1.6, zorder=2)
    ax.plot(dd_r.index, dd_r, color=MID_GRAY, ls="-", lw=1.6, zorder=3)
    ax.fill_between(dd_b.index, dd_b, 0, color=ORANGE_TINT, alpha=0.82, zorder=1)
    ax.plot(dd_b.index, dd_b, color=ORANGE, ls="-", lw=2.3, zorder=4)

    # Green horizontal product warning line (-18% HWM)
    ax.axhline(-18.0, color=GREEN, ls=":", lw=1.2, zorder=2)
    ax.text(pd.Timestamp("2025-02-01"), -19.8, "产品高水位预警 -18%",
            fontsize=8.8, color=GREEN_DEEP, fontweight="semibold",
            bbox=dict(boxstyle="round,pad=0.14", facecolor=LIGHT, edgecolor="none", alpha=0.88))

    style_axes(ax, grid_axis="y", zero_line=True)
    ax.set_ylim(-31.5, 3.8)
    _add_oos_split(ax, y_frac=0.97)
    ax.set_ylabel("动态回撤  %")

    tb = dd_b.idxmin()
    th = dd_h.idxmin()
    ax.scatter([tb], [dd_b.loc[tb]], color=ORANGE_DEEP, s=42, zorder=5)
    ax.annotate(
        f"Baseline 谷底 {dd_b.loc[tb]:.1f}%",
        xy=(tb, dd_b.loc[tb]),
        xytext=(pd.Timestamp("2023-04-15"), -26.5),
        fontsize=9.6, fontweight="bold", color=ORANGE_DEEP,
        arrowprops=dict(arrowstyle="->", color=ORANGE_DEEP, lw=1.0),
    )
    ax.annotate(
        f"沪深300 {dd_h.loc[th]:.1f}%",
        xy=(th, dd_h.loc[th]),
        xytext=(8, -5), textcoords="offset points",
        fontsize=9.3, color=BLUE_DEEP,
    )

    last_d = nav.index[-1]
    label_line_ends(ax, [
        {"x": last_d, "y": dd_b.iloc[-1], "text": f"Baseline {dd_b.iloc[-1]:.1f}%", "color": ORANGE_DEEP, "weight": "bold", "fontsize": 9.6},
        {"x": last_d, "y": dd_h.iloc[-1], "text": f"沪深300 {dd_h.iloc[-1]:.1f}%", "color": BLUE_DEEP, "fontsize": 9.3},
        {"x": last_d, "y": dd_r.iloc[-1], "text": f"Research {dd_r.iloc[-1]:.1f}%", "color": TEXT_SUB, "fontsize": 9.3},
    ], right_pad_frac=0.31, min_gap_frac=0.095)
    _fmt_date_axis(ax)

    save_brand_fig(fig, "03_drawdown_underwater.png")


def plot_04_cost_erosion_waterfall(data: dict):
    apply_brand_style()
    nav = data["nav"]
    b_ideal = (nav["baseline_ideal"].iloc[-1] - 1.0) * 100
    b_real = (nav["baseline"].iloc[-1] - 1.0) * 100
    b_drag = b_real - b_ideal

    r_ideal = (nav["research_ideal"].iloc[-1] - 1.0) * 100
    r_real = (nav["research"].iloc[-1] - 1.0) * 100
    r_drag = r_real - r_ideal

    fig, ax = plt.subplots(figsize=(6.8, 4.8), facecolor=LIGHT)
    x = np.array([0, 1, 2, 3.55, 4.55, 5.55])
    width = 0.56

    ax.bar(x[0], b_ideal, width, color=BLUE, edgecolor="none")
    ax.bar(x[1], abs(b_drag), width, bottom=b_real, color=MID_GRAY, alpha=0.9)
    ax.bar(x[2], b_real, width, color=ORANGE)

    ax.bar(x[3], r_ideal, width, color=BLUE, edgecolor="none")
    ax.bar(x[4], abs(r_drag), width, bottom=r_real, color=DARK, alpha=0.88)
    ax.bar(x[5], r_real, width, color=MID_GRAY)

    ax.plot([x[0] + width / 2, x[1] - width / 2], [b_ideal, b_ideal], color=SPINE, lw=0.9, ls="--")
    ax.plot([x[1] + width / 2, x[2] - width / 2], [b_real, b_real], color=SPINE, lw=0.9, ls="--")
    ax.plot([x[3] + width / 2, x[4] - width / 2], [r_ideal, r_ideal], color=SPINE, lw=0.9, ls="--")
    ax.plot([x[4] + width / 2, x[5] - width / 2], [r_real, r_real], color=SPINE, lw=0.9, ls="--")

    style_axes(ax, grid_axis="y", zero_line=True)
    ax.axvline(2.775, color=LIGHT_GRAY, lw=1.4)
    ax.set_xticks(x)
    ax.set_xticklabels([
        "Baseline\n无成本理想", "Baseline\n成本侵蚀", "Baseline\n计成本实际",
        "Research\n无成本理想", "Research\n成本侵蚀", "Research\n计成本实际",
    ], fontsize=9.8)
    ax.set_ylabel("全样本累计收益  %")
    ax.set_ylim(-14, 61)

    ax.text(x[0], b_ideal + 1.4, f"+{b_ideal:.1f}%", ha="center", va="bottom", fontsize=10.2, fontweight="semibold", color=BLUE_DEEP)
    ax.text(x[1], b_ideal + 1.4, f"{b_drag:.1f} pct", ha="center", va="bottom", fontsize=10.0, color=TEXT_SUB)
    ax.text(x[2], b_real + 1.4, f"+{b_real:.1f}%", ha="center", va="bottom", fontsize=10.8, fontweight="bold", color=ORANGE_DEEP)

    ax.text(x[3], r_ideal + 1.4, f"+{r_ideal:.1f}%", ha="center", va="bottom", fontsize=10.2, fontweight="semibold", color=BLUE_DEEP)
    ax.text(x[4], r_ideal + 1.4, f"{r_drag:.1f} pct", ha="center", va="bottom", fontsize=10.6, fontweight="bold", color=DARK)
    ax.text(x[5], r_real - 1.6, f"{r_real:.1f}%", ha="center", va="top", fontsize=10.2, fontweight="bold", color=TEXT_SUB)

    save_brand_fig(fig, "04_cost_erosion_waterfall.png")


def plot_08_new012_vs_alpha012_ic(data: dict):
    apply_brand_style()
    pic = data["proportional_ic"]
    sub = pic[(pic["horizon"] == 5) & (pic["factor"].isin(["alpha012", "new012_return"]))].copy()
    periods = ["train", "validation", "test"]
    p_labels = ["训练期\n2019–2022", "验证期\n2023–2024", "样本外\n2025–2026.10"]

    v_old = [float(sub[(sub["factor"] == "alpha012") & (sub["period"] == per)]["mean"].iloc[0]) for per in periods]
    v_new = [float(sub[(sub["factor"] == "new012_return") & (sub["period"] == per)]["mean"].iloc[0]) for per in periods]

    fig, ax = plt.subplots(figsize=(6.2, 4.7), facecolor=LIGHT)
    x = np.arange(len(periods))
    w = 0.30
    ax.bar(x - w / 2, v_old, w, color=MID_GRAY, label="原版 Alpha012（价格差分尺度敏感）")
    b2 = ax.bar(x + w / 2, v_new, w, color=BLUE, label="比例化改进 new012_return（无量纲）")
    b2[-1].set_color(ORANGE)

    for i, (vo, vn) in enumerate(zip(v_old, v_new)):
        ax.text(x[i] - w / 2, vo + 0.0004, f"{vo:.4f}", ha="center", va="bottom",
                fontsize=10.2, color=TEXT_SUB, fontweight="semibold")
        col_n = ORANGE_DEEP if i == len(periods) - 1 else BLUE_DEEP
        ax.text(x[i] + w / 2, vn + 0.0004, f"{vn:.4f}", ha="center", va="bottom",
                fontsize=10.6, color=col_n, fontweight="bold")

    style_axes(ax, grid_axis="y", zero_line=True)
    ax.set_xticks(x)
    ax.set_xticklabels(p_labels, fontsize=10.4)
    ax.set_ylabel("5日中性化 RankIC 均值")
    ax.set_ylim(0, 0.0205)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    ax.legend(frameon=False, loc="upper left", fontsize=9.8)

    save_brand_fig(fig, "08_new012_vs_alpha012_ic.png")


def plot_11_capacity_curve(data: dict):
    apply_brand_style()
    cc = data["cap_curve"]
    prod = data["prod"]
    c08 = cc[cc["Y"] == 0.8].sort_values("aum_yi")
    c05 = cc[cc["Y"] == 0.5].sort_values("aum_yi")
    c10 = cc[cc["Y"] == 1.0].sort_values("aum_yi")

    hs_ann = float(c08["hs300_ann"].iloc[0]) * 100.0
    cap_main = prod["capacity_impact"]["half_excess_capacities"]["Y_0.8"]["baseline_half_excess_aum_yi"]
    cap_y10 = prod["capacity_impact"]["half_excess_capacities"]["Y_1.0"]["baseline_half_excess_aum_yi"]
    cap_y05 = prod["capacity_impact"]["half_excess_capacities"]["Y_0.5"]["baseline_half_excess_aum_yi"]
    half_target = prod["capacity_impact"]["half_excess_capacities"]["Y_0.8"]["baseline_target_net_ann"] * 100.0

    fig, ax = plt.subplots(figsize=(7.0, 4.8), facecolor=LIGHT)

    # Green safe liquidity zone (up to 10B assumption)
    ax.axvspan(0.08, 10.0, color=GREEN_TINT, alpha=0.65, zorder=0)
    ax.axvline(10.0, color=BLUE, ls="-.", lw=1.35, zorder=2)
    ax.text(0.95, 13.0, "10 亿元假设情景 · 流动性约束参考", fontsize=9.6, fontweight="bold",
            color=BLUE_DEEP, ha="center", va="top")

    ax.fill_between(c08["aum_yi"], c10["baseline_net_ann"] * 100, c05["baseline_net_ann"] * 100,
                    color=ORANGE_TINT, alpha=0.72, zorder=1)
    ax.plot(c08["aum_yi"], c08["baseline_net_ann"] * 100, color=ORANGE, lw=2.8, zorder=4)
    ax.plot(c08["aum_yi"], c08["research_net_ann"] * 100, color=MID_GRAY, lw=2.0, zorder=3)

    ax.axhline(hs_ann, color=BLUE, ls="--", lw=1.1, zorder=1)
    ax.text(0.10, hs_ann + 0.55, f"沪深300 基准 {hs_ann:.2f}%", fontsize=9.2, color=BLUE_DEEP)

    ax.axhline(half_target, color=GREEN, ls=":", lw=1.1, zorder=1)
    ax.text(0.10, half_target + 0.55, f"超额半衰阈值 {half_target:.2f}%", fontsize=9.2, color=GREEN_DEEP)

    ax.scatter([cap_main], [half_target], color=ORANGE_DEEP, s=62, zorder=6)
    ax.plot([cap_main, cap_main], [-25, half_target], color=ORANGE_DEEP, ls=":", lw=1.15, zorder=3)
    ax.annotate(
        f"理论半衰容量 ≈ {cap_main:.1f} 亿元\nY=0.8 | 敏感区间 {cap_y10:.0f}–{cap_y05:.0f} 亿",
        xy=(cap_main, half_target), xytext=(15.0, -5.2),
        fontsize=9.8, fontweight="bold", color=ORANGE_DEEP, ha="center",
        bbox=dict(boxstyle="round,pad=0.30", facecolor=LIGHT, edgecolor=ORANGE, lw=0.9),
        arrowprops=dict(arrowstyle="->", color=ORANGE_DEEP, lw=1.1),
    )

    ax.text(0.14, -15.2, "Research Y=0.8\n超额已为负\n10亿跌至 -16.3%",
            fontsize=9.3, color=TEXT_SUB, ha="left", va="center")

    style_axes(ax, grid_axis="y")
    ax.set_xscale("log")
    ax.set_xlim(0.08, 1250)
    ax.set_ylim(-25, 14.5)
    ax.set_xticks([0.1, 1, 5, 10, 50, 100, 500])
    ax.set_xticklabels(["0.1亿", "1亿", "5亿", "10亿", "50亿", "100亿", "500亿"])
    ax.set_xlabel("资产管理规模 AUM  对数刻度")
    ax.set_ylabel("计入交易与冲击成本后年化净收益  %")

    ax.text(460, c08["baseline_net_ann"].iloc[-1] * 100 + 2.5, "Baseline\nY=0.8",
            fontsize=9.8, fontweight="bold", color=ORANGE_DEEP, ha="left", va="center")

    save_brand_fig(fig, "11_capacity_curve.png")


def plot_12_fee_net_nav(data: dict):
    apply_brand_style()
    inv = data["inv_nav"]
    fee_df = data["fee_df"].set_index("plan_id")
    fig, ax = plt.subplots(figsize=(6.4, 4.7), facecolor=LIGHT)

    ax.axhline(1.0, color=LIGHT_GRAY, lw=1.0, zorder=1)
    ax.plot(inv.index, inv["hs300"], color=MID_GRAY, ls="--", lw=1.5, zorder=2)
    ax.plot(inv.index, inv["plan_B"], color=MID_GRAY, ls=":", lw=1.5, zorder=2)
    ax.plot(inv.index, inv["plan_A"], color=TEXT_SUB, ls="-.", lw=1.6, zorder=3)
    ax.plot(inv.index, inv["plan_D"], color=GREEN, ls="-", lw=2.0, zorder=4)
    ax.plot(inv.index, inv["plan_C"], color=BLUE, ls="-", lw=2.6, zorder=5)
    ax.plot(inv.index, inv["baseline_gross"], color=ORANGE, ls="-", lw=2.4, zorder=6)

    style_axes(ax, grid_axis="y")
    ax.set_ylim(0.82, 1.54)
    _add_oos_split(ax, y_frac=0.97)
    ax.set_ylabel("投资者扣费后单位净值")

    last_d = inv.index[-1]
    label_line_ends(ax, [
        {"x": last_d, "y": inv["baseline_gross"].iloc[-1],
         "text": f"策略毛净值 {fee_df.loc['Gross', 'ann_return']*100:.2f}%", "color": ORANGE_DEEP, "weight": "bold", "fontsize": 9.8},
        {"x": last_d, "y": inv["plan_D"].iloc[-1],
         "text": f"D 纯管理费 {fee_df.loc['D', 'ann_return']*100:.2f}%", "color": GREEN_DEEP, "fontsize": 9.5},
        {"x": last_d, "y": inv["plan_C"].iloc[-1],
         "text": f"C 机构主推 {fee_df.loc['C', 'ann_return']*100:.2f}%", "color": BLUE_DEEP, "weight": "bold", "fontsize": 9.9},
        {"x": last_d, "y": inv["plan_A"].iloc[-1],
         "text": f"A/B 标准超额 {fee_df.loc['A', 'ann_return']*100:.2f}%", "color": TEXT_SUB, "fontsize": 9.2},
        {"x": last_d, "y": inv["hs300"].iloc[-1],
         "text": "沪深300 0.03%", "color": MID_GRAY, "fontsize": 9.2},
    ], right_pad_frac=0.42, min_gap_frac=0.095)
    _fmt_date_axis(ax)

    save_brand_fig(fig, "12_fee_net_nav.png")


def plot_13_latest_industry_dist(data: dict):
    apply_brand_style()
    ind = data["ind_df"].sort_values("权重合计", ascending=True)
    fig, ax = plt.subplots(figsize=(6.5, 4.7), facecolor=LIGHT)

    y = np.arange(len(ind))
    colors = []
    for name in ind["申万一级行业"]:
        if name in ("银行", "非银金融", "建筑装饰"):
            colors.append(ORANGE)
        elif name in ("有色金属", "汽车", "机械设备"):
            colors.append(BLUE)
        else:
            colors.append(GREEN)

    ax.barh(y, ind["权重合计"], height=0.62, color=colors, edgecolor="none")
    for idx, (_, row) in enumerate(ind.iterrows()):
        is_top = row["申万一级行业"] in ("银行", "非银金融", "建筑装饰")
        ax.text(
            row["权重合计"] + 0.65, idx,
            f"{row['权重合计']:.0f}% · {int(row['持仓只数'])}只",
            va="center", ha="left",
            fontsize=9.8,
            fontweight="bold" if is_top else "normal",
            color=ORANGE_DEEP if is_top else TEXT_SUB,
        )

    style_axes(ax, grid_axis="x")
    ax.set_yticks(y)
    ax.set_yticklabels(ind["申万一级行业"], fontsize=10.4)
    ax.set_xlim(0, 41.5)
    ax.set_xlabel("组合权重占比  %（50只完整策略基准口径）")
    ax.spines["left"].set_visible(False)

    # Compact 3-accent legend in lower right
    legend_handles = [
        mpatches.Patch(color=ORANGE, label="金融基建主仓 74%"),
        mpatches.Patch(color=BLUE, label="周期制造 16%"),
        mpatches.Patch(color=GREEN, label="其余分散板块 10%"),
    ]
    ax.legend(handles=legend_handles, frameon=False, loc="lower right", fontsize=9.2)

    save_brand_fig(fig, "13_latest_industry_dist.png")


def main():
    data = load_all_data()
    plot_01_nav_curve(data)
    plot_02_positioning_2x2(data)
    plot_03_drawdown_underwater(data)
    plot_04_cost_erosion_waterfall(data)
    plot_08_new012_vs_alpha012_ic(data)
    plot_11_capacity_curve(data)
    plot_12_fee_net_nav(data)
    plot_13_latest_industry_dist(data)
    print(f"[brand fig] all 8 figures written to {OUT_DIR}")


if __name__ == "__main__":
    main()
