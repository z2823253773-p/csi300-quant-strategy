# -*- coding: utf-8 -*-
"""
组员4：Claude 官网极简编辑风 PPT 专用图表重绘脚本
输出 7 张无框、#FAF9F5 底色无缝融合图表至 member4/figures/slide_claude/（300 DPI）。
复现命令（在 member4 目录）：
    .venv/bin/python code/make_figures_claude.py
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
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

import paths as P

ROOT = P.WORKSPACE_ROOT
MEMBER4 = P.MEMBER4_DIR
M2_RES = P.M2_RES
M3_RES = P.M3_RES
M4_RES = MEMBER4 / "results"
OUT_DIR = MEMBER4 / "figures" / "slide_claude"

# ---------------------------------------------------------------------------
# Claude 官网极简编辑风色板
# ---------------------------------------------------------------------------
BG = "#FAF9F5"          # 画布与坐标区背景，与 PPT 完全一致
OAT = "#F0EEE6"         # 轻燕麦底带
TINT = "#F5E6DF"        # 浅陶土底带/徽章
INK = "#141413"         # 主墨黑
STONE = "#57554F"       # 次墨灰
MUTED = "#8C8980"       # 浅墨灰
SPINE = "#D8D3C8"       # 极细轴线
GRID = "#EAE6DC"        # 横向网格线
TERRA = "#C96442"       # Baseline 主角陶土橙
CLAY = "#C45A38"        # 高亮深陶土
SAND = "#C7BEB0"        # Research 暖沙
STONE_DASH = "#9C978D"  # 沪深300 暖石虚线
SAGE = "#5F7A6A"        # D 档鼠尾草绿
SAND_TEXT = "#857D70"   # 暖沙线在米白底上的高可读文字色

FONT_LIST = ["PingFang SC", "Heiti SC", "Helvetica Neue", "Arial Unicode MS", "DejaVu Sans"]

BACKTEST_TICKS = [
    pd.Timestamp("2023-06-01"),
    pd.Timestamp("2024-01-01"),
    pd.Timestamp("2024-07-01"),
    pd.Timestamp("2025-01-01"),
    pd.Timestamp("2025-07-01"),
    pd.Timestamp("2026-01-01"),
    pd.Timestamp("2026-07-01"),
]


def apply_claude_style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": FONT_LIST,
        "axes.unicode_minus": False,
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "savefig.edgecolor": "none",
        "axes.edgecolor": SPINE,
        "axes.linewidth": 0.75,
        "axes.labelsize": 11.0,
        "axes.labelcolor": STONE,
        "xtick.labelsize": 10.0,
        "ytick.labelsize": 10.0,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.major.size": 3.0,
        "ytick.major.size": 0.0,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",
        "text.color": INK,
    })


def style_axes(ax, grid_axis: str = "y", zero_line: bool = False):
    ax.set_facecolor(BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SPINE)
    ax.spines["bottom"].set_color(SPINE)
    ax.spines["left"].set_linewidth(0.75)
    ax.spines["bottom"].set_linewidth(0.75)
    ax.set_axisbelow(True)
    if grid_axis in ("y", "x", "both"):
        ax.grid(True, axis=grid_axis, color=GRID, linewidth=0.6)
    else:
        ax.grid(False)
    if zero_line:
        ax.axhline(0.0, color=SPINE, linewidth=0.85, linestyle="-", zorder=1)


def _fmt_date_axis(ax):
    ax.set_xticks(BACKTEST_TICKS)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))


def _add_oos_split(ax, y_frac: float = 0.97):
    split_dt = pd.Timestamp("2025-01-01")
    ax.axvline(split_dt, color=SPINE, linestyle=":", linewidth=1.1, zorder=1)
    ax.text(
        split_dt, y_frac, " 验证期 ｜ 样本外 ",
        transform=ax.get_xaxis_transform(),
        ha="center", va="top",
        fontsize=9.5,
        color=MUTED,
        bbox=dict(boxstyle="round,pad=0.18", facecolor=BG, edgecolor="none", alpha=0.92),
    )


def label_line_ends(ax, items: list[dict], right_pad_frac: float = 0.28, min_gap_frac: float = 0.085):
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
    if ys[-1] > y1 - 0.03 * yr and len(ys) > 1:
        shift = ys[-1] - (y1 - 0.03 * yr)
        ys[-1] -= shift
        for i in range(len(ys) - 2, -1, -1):
            if ys[i + 1] - ys[i] < min_gap:
                ys[i] = ys[i + 1] - min_gap

    new_y0 = min(y0, min(ys) - 0.04 * yr)
    new_y1 = max(y1, max(ys) + 0.04 * yr)
    ax.set_ylim(new_y0, new_y1)

    x_offset = (dx * 0.015) if dx > 0 else 0
    for d, y_pos in zip(parsed, ys):
        x_val = d["x"]
        if hasattr(x_val, "toordinal") or hasattr(x_val, "timestamp"):
            x_num = mdates.date2num(x_val) + x_offset
        else:
            x_num = float(x_val) + x_offset
        ax.text(
            x_num, y_pos, d["text"],
            color=d["color"], fontsize=d["fontsize"], fontweight=d["weight"],
            va="center", ha="left", clip_on=False,
        )


def save_claude_fig(fig, filename: str, use_tight: bool = True):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if use_tight:
        fig.tight_layout(pad=0.35)
    fig.savefig(
        OUT_DIR / filename,
        dpi=300,
        facecolor=BG,
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.06,
    )
    plt.close(fig)


def plot_01_nav_curve(data: dict):
    apply_claude_style()
    nav = data["nav"]
    fig, ax = plt.subplots(figsize=(7.6, 4.9), facecolor=BG)

    ax.plot(nav.index, nav["hs300"], color=STONE_DASH, ls="--", lw=1.7, zorder=2)
    ax.plot(nav.index, nav["research"], color=SAND, ls="-", lw=1.9, zorder=3)
    ax.plot(nav.index, nav["baseline"], color=TERRA, ls="-", lw=2.6, zorder=4)

    style_axes(ax, grid_axis="y")
    ax.axhline(1.0, color=SPINE, lw=0.75, ls="-", zorder=1)
    _add_oos_split(ax, y_frac=0.97)
    ax.set_ylabel("累计净值  初始 = 1.0")

    last_d = nav.index[-1]
    b_end, r_end, h_end = nav["baseline"].iloc[-1], nav["research"].iloc[-1], nav["hs300"].iloc[-1]
    label_line_ends(ax, [
        {"x": last_d, "y": b_end, "text": f"Baseline  {b_end:.3f} (+{(b_end-1)*100:.1f}%)", "color": CLAY, "weight": "bold", "fontsize": 10.5},
        {"x": last_d, "y": h_end, "text": f"沪深300  {h_end:.3f} (+{(h_end-1)*100:.1f}%)", "color": STONE, "fontsize": 10.0},
        {"x": last_d, "y": r_end, "text": f"Research  {r_end:.3f} ({(r_end-1)*100:.1f}%)", "color": SAND_TEXT, "fontsize": 10.0},
    ], right_pad_frac=0.34, min_gap_frac=0.10)
    _fmt_date_axis(ax)

    save_claude_fig(fig, "01_nav_curve.png")


def plot_03_drawdown_underwater(data: dict):
    apply_claude_style()
    nav = data["nav"]
    fig, ax = plt.subplots(figsize=(7.1, 4.5), facecolor=BG)

    dd_b = (nav["baseline"] / nav["baseline"].cummax() - 1.0) * 100
    dd_r = (nav["research"] / nav["research"].cummax() - 1.0) * 100
    dd_h = (nav["hs300"] / nav["hs300"].cummax() - 1.0) * 100

    ax.plot(dd_h.index, dd_h, color=STONE_DASH, ls="--", lw=1.6, zorder=2)
    ax.plot(dd_r.index, dd_r, color=SAND, ls="-", lw=1.8, zorder=3)
    ax.fill_between(dd_b.index, dd_b, 0, color=TINT, alpha=0.80, zorder=1)
    ax.plot(dd_b.index, dd_b, color=TERRA, ls="-", lw=2.3, zorder=4)

    style_axes(ax, grid_axis="y", zero_line=True)
    ax.set_ylim(-31.5, 3.8)
    _add_oos_split(ax, y_frac=0.98)
    ax.set_ylabel("动态回撤  %")

    tb = dd_b.idxmin()
    tr = dd_r.idxmin()
    th = dd_h.idxmin()
    ax.scatter([tb], [dd_b.loc[tb]], color=CLAY, s=42, zorder=5)
    ax.annotate(
        f"Baseline 谷底 {dd_b.loc[tb]:.1f}%",
        xy=(tb, dd_b.loc[tb]),
        xytext=(pd.Timestamp("2023-06-10"), -26.2),
        fontsize=10.2, fontweight="bold", color=CLAY,
        arrowprops=dict(arrowstyle="->", color=CLAY, lw=1.0),
    )
    ax.annotate(
        f"Research {dd_r.loc[tr]:.1f}%",
        xy=(tr, dd_r.loc[tr]),
        xytext=(-32, -13), textcoords="offset points",
        fontsize=9.8, color=SAND_TEXT, fontweight="semibold",
    )
    ax.annotate(
        f"沪深300 {dd_h.loc[th]:.1f}%",
        xy=(th, dd_h.loc[th]),
        xytext=(10, -4), textcoords="offset points",
        fontsize=9.8, color=STONE,
    )

    last_d = nav.index[-1]
    label_line_ends(ax, [
        {"x": last_d, "y": dd_b.iloc[-1], "text": f"Baseline {dd_b.iloc[-1]:.1f}%", "color": CLAY, "weight": "bold", "fontsize": 10.0},
        {"x": last_d, "y": dd_h.iloc[-1], "text": f"沪深300 {dd_h.iloc[-1]:.1f}%", "color": STONE, "fontsize": 9.8},
        {"x": last_d, "y": dd_r.iloc[-1], "text": f"Research {dd_r.iloc[-1]:.1f}%", "color": SAND_TEXT, "fontsize": 9.8},
    ], right_pad_frac=0.28, min_gap_frac=0.095)
    _fmt_date_axis(ax)

    save_claude_fig(fig, "03_drawdown_underwater.png")


def plot_04_cost_erosion_waterfall(data: dict):
    apply_claude_style()
    nav = data["nav"]
    b_ideal = (nav["baseline_ideal"].iloc[-1] - 1.0) * 100
    b_real = (nav["baseline"].iloc[-1] - 1.0) * 100
    b_drag = b_real - b_ideal

    r_ideal = (nav["research_ideal"].iloc[-1] - 1.0) * 100
    r_real = (nav["research"].iloc[-1] - 1.0) * 100
    r_drag = r_real - r_ideal

    fig, ax = plt.subplots(figsize=(6.9, 4.9), facecolor=BG)
    x = np.array([0, 1, 2, 3.55, 4.55, 5.55])
    width = 0.58

    ax.bar(x[0], b_ideal, width, color=STONE, edgecolor="none")
    ax.bar(x[1], abs(b_drag), width, bottom=b_real, color=SAND, alpha=0.95)
    ax.bar(x[2], b_real, width, color=TERRA)

    ax.bar(x[3], r_ideal, width, color=STONE, edgecolor="none")
    ax.bar(x[4], abs(r_drag), width, bottom=r_real, color=CLAY, alpha=0.95)
    ax.bar(x[5], r_real, width, color=SAND)

    ax.plot([x[0] + width / 2, x[1] - width / 2], [b_ideal, b_ideal], color=SPINE, lw=0.9, ls="--")
    ax.plot([x[1] + width / 2, x[2] - width / 2], [b_real, b_real], color=SPINE, lw=0.9, ls="--")
    ax.plot([x[3] + width / 2, x[4] - width / 2], [r_ideal, r_ideal], color=SPINE, lw=0.9, ls="--")
    ax.plot([x[4] + width / 2, x[5] - width / 2], [r_real, r_real], color=SPINE, lw=0.9, ls="--")

    style_axes(ax, grid_axis="y", zero_line=True)
    ax.axvline(2.775, color=GRID, lw=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels([
        "Baseline\n无成本理想", "Baseline\n成本侵蚀", "Baseline\n计成本实际",
        "Research\n无成本理想", "Research\n成本侵蚀", "Research\n计成本实际",
    ], fontsize=9.8)
    ax.set_ylabel("全样本累计收益  %")
    ax.set_ylim(-14, 61)

    ax.text(x[0], b_ideal + 1.4, f"+{b_ideal:.1f}%", ha="center", va="bottom", fontsize=10.2, fontweight="semibold", color=INK)
    ax.text(x[1], b_ideal + 1.4, f"{b_drag:.1f} pct", ha="center", va="bottom", fontsize=10.0, color=MUTED)
    ax.text(x[2], b_real + 1.4, f"+{b_real:.1f}%", ha="center", va="bottom", fontsize=10.6, fontweight="bold", color=CLAY)

    ax.text(x[3], r_ideal + 1.4, f"+{r_ideal:.1f}%", ha="center", va="bottom", fontsize=10.2, fontweight="semibold", color=INK)
    ax.text(x[4], r_ideal + 1.4, f"{r_drag:.1f} pct", ha="center", va="bottom", fontsize=10.6, fontweight="bold", color=CLAY)
    ax.text(x[5], r_real - 1.6, f"{r_real:.1f}%", ha="center", va="top", fontsize=10.2, fontweight="bold", color=SAND_TEXT)

    save_claude_fig(fig, "04_cost_erosion_waterfall.png")


def plot_08_new012_vs_alpha012_ic(data: dict):
    apply_claude_style()
    pic = data["proportional_ic"]
    sub = pic[(pic["horizon"] == 5) & (pic["factor"].isin(["alpha012", "new012_return"]))].copy()
    periods = ["train", "validation", "test"]
    p_labels = ["训练期\n2019–2022", "验证期\n2023–2024", "样本外\n2025–2026.10"]

    v_old = [float(sub[(sub["factor"] == "alpha012") & (sub["period"] == per)]["mean"].iloc[0]) for per in periods]
    v_new = [float(sub[(sub["factor"] == "new012_return") & (sub["period"] == per)]["mean"].iloc[0]) for per in periods]

    fig, ax = plt.subplots(figsize=(6.2, 4.9), facecolor=BG)
    x = np.arange(len(periods))
    w = 0.30
    ax.bar(x - w / 2, v_old, w, color=SAND, label="原版 Alpha012 · 价格差分尺度敏感")
    b2 = ax.bar(x + w / 2, v_new, w, color=INK, label="比例化改进 new012_return · 无量纲")
    b2[-1].set_color(CLAY)

    for i, (vo, vn) in enumerate(zip(v_old, v_new)):
        ax.text(x[i] - w / 2, vo + 0.0004, f"{vo:.4f}", ha="center", va="bottom",
                fontsize=10.2, color=SAND_TEXT, fontweight="semibold")
        col_n = CLAY if i == len(periods) - 1 else INK
        ax.text(x[i] + w / 2, vn + 0.0004, f"{vn:.4f}", ha="center", va="bottom",
                fontsize=10.6, color=col_n, fontweight="bold")

    style_axes(ax, grid_axis="y", zero_line=True)
    ax.set_xticks(x)
    ax.set_xticklabels(p_labels, fontsize=10.5)
    ax.set_ylabel("5日中性化 RankIC 均值")
    ax.set_ylim(0, 0.0195)
    ax.legend(frameon=False, loc="upper left", fontsize=10.2)

    save_claude_fig(fig, "08_new012_vs_alpha012_ic.png")


def plot_11_capacity_curve(data: dict):
    apply_claude_style()
    curve = data["capacity_curve"]
    summary = data["product_summary"]
    c08 = curve[curve["Y"] == 0.8].sort_values("aum_yi")
    c05 = curve[curve["Y"] == 0.5].sort_values("aum_yi")
    c10 = curve[curve["Y"] == 1.0].sort_values("aum_yi")

    hs_ann = float(c08["hs300_ann"].iloc[0]) * 100.0
    cap_y08 = summary["capacity_impact"]["half_excess_capacities"]["Y_0.8"]["baseline_half_excess_aum_yi"]
    cap_y10 = summary["capacity_impact"]["half_excess_capacities"]["Y_1.0"]["baseline_half_excess_aum_yi"]
    cap_y05 = summary["capacity_impact"]["half_excess_capacities"]["Y_0.5"]["baseline_half_excess_aum_yi"]
    target_ann = summary["capacity_impact"]["half_excess_capacities"]["Y_0.8"]["baseline_target_net_ann"] * 100.0

    fig, ax = plt.subplots(figsize=(7.3, 4.9), facecolor=BG)
    ax.set_xscale("log")

    ax.axvspan(0.08, 10.0, color=OAT, alpha=0.90, zorder=0)
    ax.axvline(10.0, color=STONE, ls="-.", lw=0.95, alpha=0.75, zorder=1)
    ax.text(0.88, 12.6, "10 亿元假设情景 · 流动性约束参考",
            ha="center", va="center", fontsize=9.8, color=INK, fontweight="semibold")

    ax.fill_between(c08["aum_yi"], c10["baseline_net_ann"] * 100, c05["baseline_net_ann"] * 100,
                    color=TINT, alpha=0.70, zorder=1)
    ax.plot(c08["aum_yi"], c08["research_net_ann"] * 100, color=SAND, lw=1.9, zorder=3)
    ax.plot(c08["aum_yi"], c08["baseline_net_ann"] * 100, color=TERRA, lw=2.6, zorder=4)

    ax.axhline(hs_ann, color=STONE_DASH, ls="--", lw=1.5, zorder=2)
    ax.axhline(target_ann, color=SPINE, ls=":", lw=1.0, zorder=2)

    ax.scatter([cap_y08], [target_ann], color=CLAY, s=54, zorder=5)
    ax.vlines(cap_y08, -25, target_ann, color=CLAY, ls=":", lw=1.1, zorder=2)
    ax.annotate(
        f"理论半衰容量 ≈ {cap_y08:.1f} 亿元\nY=0.8 ｜ 敏感区间 {cap_y10:.0f}–{cap_y05:.0f} 亿",
        xy=(cap_y08, target_ann),
        xytext=(cap_y08 * 0.72, target_ann - 10.5),
        ha="right",
        fontsize=10.2, fontweight="bold", color=CLAY,
        arrowprops=dict(arrowstyle="->", color=CLAY, lw=1.1),
    )

    style_axes(ax, grid_axis="y")
    ax.set_xlim(0.08, 1300)
    ax.set_ylim(-25, 14.5)
    ax.set_xticks([0.1, 1, 5, 10, 50, 100, 500])
    ax.get_xaxis().set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}亿"))
    ax.set_xlabel("资产管理规模 AUM  对数刻度")
    ax.set_ylabel("计入交易与冲击成本后年化净收益  %")

    ax.text(530, c08["baseline_net_ann"].iloc[-1] * 100, "Baseline\nY=0.8",
            color=CLAY, fontsize=10.0, fontweight="bold", va="center")
    ax.text(0.14, -14.0,
            "Research Y=0.8\n超额已为负\n10亿跌至 -16.3%",
            color=SAND_TEXT, fontsize=9.6, va="top", ha="left")
    ax.text(0.10, hs_ann + 0.55, f"沪深300 基准 {hs_ann:.2f}%", color=MUTED, fontsize=9.2)
    ax.text(0.10, target_ann + 0.55, f"超额半衰阈值 {target_ann:.2f}%", color=MUTED, fontsize=9.2)

    save_claude_fig(fig, "11_capacity_curve.png")


def plot_12_fee_net_nav(data: dict):
    apply_claude_style()
    inv = data["investor_nav"]
    fee_df = data["fee_analysis"].set_index("plan_id")

    fig, ax = plt.subplots(figsize=(6.3, 4.9), facecolor=BG)
    ax.plot(inv.index, inv["hs300"], color=STONE_DASH, ls="--", lw=1.6, zorder=2)
    ax.plot(inv.index, inv["plan_B"], color=SAND, ls="-.", lw=1.6, zorder=3)
    ax.plot(inv.index, inv["plan_A"], color=STONE_DASH, ls="-", lw=1.6, zorder=3)
    ax.plot(inv.index, inv["plan_C"], color=CLAY, ls="-", lw=2.3, zorder=5)
    ax.plot(inv.index, inv["plan_D"], color=SAGE, ls="-", lw=1.9, zorder=4)
    ax.plot(inv.index, inv["baseline_gross"], color=INK, ls="-", lw=2.4, zorder=6)

    style_axes(ax, grid_axis="y")
    ax.axhline(1.0, color=SPINE, lw=0.75)
    ax.set_ylabel("净值  初始 = 1.0")

    last_d = inv.index[-1]
    items = [
        {"x": last_d, "y": inv["baseline_gross"].iloc[-1],
         "text": f"策略未扣费  {inv['baseline_gross'].iloc[-1]:.3f} · 10.8%", "color": INK, "weight": "bold", "fontsize": 9.8},
        {"x": last_d, "y": inv["plan_D"].iloc[-1],
         "text": f"D档 纯管理费  {inv['plan_D'].iloc[-1]:.3f} · {fee_df.loc['D','ann_return']*100:.1f}%", "color": SAGE, "weight": "semibold", "fontsize": 9.6},
        {"x": last_d, "y": inv["plan_C"].iloc[-1],
         "text": f"C档 机构份额  {inv['plan_C'].iloc[-1]:.3f} · {fee_df.loc['C','ann_return']*100:.1f}%", "color": CLAY, "weight": "bold", "fontsize": 9.8},
        {"x": last_d, "y": inv["plan_A"].iloc[-1],
         "text": f"A档 标准份额  {inv['plan_A'].iloc[-1]:.3f} · {fee_df.loc['A','ann_return']*100:.1f}%", "color": STONE, "fontsize": 9.4},
        {"x": last_d, "y": inv["plan_B"].iloc[-1],
         "text": f"B档 超额计提  {inv['plan_B'].iloc[-1]:.3f} · {fee_df.loc['B','ann_return']*100:.1f}%", "color": SAND_TEXT, "fontsize": 9.4},
        {"x": last_d, "y": inv["hs300"].iloc[-1],
         "text": f"沪深300基准  {inv['hs300'].iloc[-1]:.3f} · 0.0%", "color": MUTED, "fontsize": 9.4},
    ]
    label_line_ends(ax, items, right_pad_frac=0.45, min_gap_frac=0.095)
    ax.set_xticks([
        pd.Timestamp("2023-07-01"),
        pd.Timestamp("2024-07-01"),
        pd.Timestamp("2025-07-01"),
        pd.Timestamp("2026-07-01"),
    ])
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    save_claude_fig(fig, "12_fee_net_nav.png")


def plot_13_latest_industry_dist(data: dict):
    apply_claude_style()
    ind = data["ind_dist"].sort_values("权重合计", ascending=True)
    fig, ax = plt.subplots(figsize=(6.4, 3.8), facecolor=BG)
    y = np.arange(len(ind))
    colors = [TERRA if n in ("银行", "非银金融") else "#B8B0A2" for n in ind["申万一级行业"]]

    ax.barh(y, ind["权重合计"], height=0.62, color=colors)
    style_axes(ax, grid_axis="x")
    ax.set_yticks(y)
    ax.set_yticklabels(ind["申万一级行业"], fontsize=10.0)
    ax.set_xlabel("最新持仓权重占比  %")
    ax.set_xlim(0, 41)

    for yi, (_, r) in enumerate(ind.iterrows()):
        ax.text(r["权重合计"] + 0.5, yi, f"{r['权重合计']:.0f}% · {int(r['持仓只数'])}只",
                va="center", ha="left", fontsize=9.8, color=INK)

    ax.text(0.97, 0.12, "银行 + 非银金融合计 60%\n30 只 ｜ 高 BP/EP 价值集中",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=9.8, fontweight="bold", color=CLAY,
            bbox=dict(boxstyle="round,pad=0.38", facecolor=TINT, edgecolor=CLAY, lw=0.85))

    save_claude_fig(fig, "13_latest_industry_dist.png")


def main():
    print("加载数据并绘制 Claude 极简编辑风 PPT 专用图表 ...")
    data = {
        "nav": pd.read_csv(M3_RES / "nav.csv", index_col=0, parse_dates=True),
        "proportional_ic": pd.read_csv(M2_RES / "proportional_ic.csv"),
        "capacity_curve": pd.read_csv(M4_RES / "capacity_curve.csv"),
        "fee_analysis": pd.read_csv(M4_RES / "fee_analysis.csv"),
        "investor_nav": pd.read_csv(M4_RES / "investor_nav.csv", index_col=0, parse_dates=True),
        "ind_dist": pd.read_csv(M4_RES / "latest_industry_distribution.csv"),
    }
    with open(M4_RES / "product_summary.json", "r", encoding="utf-8") as f:
        data["product_summary"] = json.load(f)

    plot_01_nav_curve(data)
    plot_03_drawdown_underwater(data)
    plot_04_cost_erosion_waterfall(data)
    plot_08_new012_vs_alpha012_ic(data)
    plot_11_capacity_curve(data)
    plot_12_fee_net_nav(data)
    plot_13_latest_industry_dist(data)

    print("全部 7 张 Claude 风格图表已生成至:", OUT_DIR)


if __name__ == "__main__":
    main()
