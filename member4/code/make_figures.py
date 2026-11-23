# -*- coding: utf-8 -*-
"""
组员4 模块4：按 PLAN 5.1 统一视觉系统重绘全组全部图表（report、slide 与 slide_notitle 三套，300 DPI）
上游数据只读，基于 member4/results/ 与上游 quant_project / member2_v2 / member3 结果绘图。
复现命令（在 member4 目录）：
    .venv/bin/python code/make_figures.py
"""
from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import Rectangle

import paths as P
import style as S

ROOT = P.WORKSPACE_ROOT
MEMBER4 = P.MEMBER4_DIR
PROC = P.PROC
M2_RES = P.M2_RES
M3_RES = P.M3_RES
M4_RES = MEMBER4 / "results"
FIG_DIR = MEMBER4 / "figures"

BACKTEST_TICKS = [
    pd.Timestamp("2023-06-01"),
    pd.Timestamp("2024-01-01"),
    pd.Timestamp("2024-07-01"),
    pd.Timestamp("2025-01-01"),
    pd.Timestamp("2025-07-01"),
    pd.Timestamp("2026-01-01"),
    pd.Timestamp("2026-07-01"),
]
FULL_TICKS = [pd.Timestamp(f"{y}-06-01") for y in range(2019, 2027)]


def _fmt_date_axis(ax, full_span: bool = False):
    ticks = FULL_TICKS if full_span else BACKTEST_TICKS
    ax.set_xticks(ticks)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))


def _add_oos_split(ax, p: dict, y_frac: float = 0.96):
    split_dt = pd.Timestamp("2025-01-01")
    ax.axvline(split_dt, color=S.SPINE_GRAY, linestyle=":", linewidth=p["lw_ref"] * 1.1, zorder=1)
    ax.text(
        split_dt, y_frac, " 验证期 | 样本外 ",
        transform=ax.get_xaxis_transform(),
        ha="center", va="top",
        fontsize=p["annot_size"] * 0.9,
        color=S.TEXT_MUTED,
        bbox=dict(boxstyle="round,pad=0.15", facecolor=S.BG_WHITE, edgecolor="none", alpha=0.85),
    )


def _set_title(ax, text: str, show_title: bool):
    if show_title:
        ax.set_title(text, loc="left")


def plot_01_nav_curve(data: dict, mode: str, out_subdir: str, show_title: bool):
    nav = data["nav"]
    fig, ax, p = S.make_figure(mode, aspect=0.52)
    ax.plot(nav.index, nav["hs300"], color=S.GRAY, ls="--", lw=p["lw_sub"], zorder=2)
    ax.plot(nav.index, nav["research"], color=S.TAUPE, ls="-", lw=p["lw_sub"], zorder=3)
    ax.plot(nav.index, nav["baseline"], color=S.NAVY, ls="-", lw=p["lw_main"] * 1.15, zorder=4)

    S.style_axes(ax, grid_axis="y")
    ax.axhline(1.0, color=S.SPINE_GRAY, lw=0.7, ls="-", zorder=1)
    _add_oos_split(ax, p, y_frac=0.97)
    ax.set_ylabel("累计净值（初始 = 1.0）")
    _set_title(ax, "Baseline 计成本净值稳健上行，2023 年以来累计跑赢沪深300 约 45 个百分点", show_title)

    last_d = nav.index[-1]
    b_end, r_end, h_end = nav["baseline"].iloc[-1], nav["research"].iloc[-1], nav["hs300"].iloc[-1]
    S.label_line_ends(ax, [
        {"x": last_d, "y": b_end, "text": f"Baseline  {b_end:.3f} (+{(b_end-1)*100:.1f}%)", "color": S.RED, "weight": "bold"},
        {"x": last_d, "y": h_end, "text": f"沪深300  {h_end:.3f} (+{(h_end-1)*100:.1f}%)", "color": S.TEXT_MUTED},
        {"x": last_d, "y": r_end, "text": f"Research  {r_end:.3f} ({(r_end-1)*100:.1f}%)", "color": S.TAUPE},
    ], mode=mode, right_pad_frac=0.25 if mode == "report" else 0.22)
    _fmt_date_axis(ax)

    S.save_figure(fig, FIG_DIR / out_subdir / "01_nav_curve.png", mode=mode,
                  source_text="来源：member3/results/nav.csv（2023-01-09 至 2026-10-30，含双边佣金、印花税与滑点）")


def plot_02_excess_curve(data: dict, mode: str, out_subdir: str, show_title: bool):
    nav = data["nav"]
    fig, ax, p = S.make_figure(mode, aspect=0.48)
    ax.plot(nav.index, nav["research_excess_hs300"] * 100, color=S.TAUPE, lw=p["lw_sub"], zorder=3)
    ax.plot(nav.index, nav["baseline_excess_hs300"] * 100, color=S.NAVY, lw=p["lw_main"] * 1.15, zorder=4)
    ax.fill_between(nav.index, 0, nav["baseline_excess_hs300"] * 100, color=S.SOFT_NAVY, alpha=0.35, zorder=1)

    S.style_axes(ax, grid_axis="y", zero_line=True)
    _add_oos_split(ax, p, y_frac=0.97)
    ax.set_ylabel("相对沪深300累计净值差（百分点）")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    _set_title(ax, "Baseline 验证期与样本外持续累积正超额，Research 全程为负", show_title)

    last_d = nav.index[-1]
    bx = nav["baseline_excess_hs300"].iloc[-1] * 100
    rx = nav["research_excess_hs300"].iloc[-1] * 100
    S.label_line_ends(ax, [
        {"x": last_d, "y": bx, "text": f"Baseline 超额 +{bx:.1f} pct", "color": S.RED, "weight": "bold"},
        {"x": last_d, "y": rx, "text": f"Research 超额 {rx:.1f} pct", "color": S.TAUPE},
    ], mode=mode, right_pad_frac=0.25 if mode == "report" else 0.22)
    _fmt_date_axis(ax)

    S.save_figure(fig, FIG_DIR / out_subdir / "02_excess_curve.png", mode=mode,
                  source_text="来源：member3/results/nav.csv（净值差 = 组合净值 - 沪深300净值）")


def plot_03_drawdown_underwater(data: dict, mode: str, out_subdir: str, show_title: bool):
    nav = data["nav"]
    fig, ax, p = S.make_figure(mode, aspect=0.50)
    dd_b = (nav["baseline"] / nav["baseline"].cummax() - 1.0) * 100
    dd_r = (nav["research"] / nav["research"].cummax() - 1.0) * 100
    dd_h = (nav["hs300"] / nav["hs300"].cummax() - 1.0) * 100

    ax.plot(dd_h.index, dd_h, color=S.GRAY, ls="--", lw=p["lw_sub"], zorder=2)
    ax.plot(dd_r.index, dd_r, color=S.TAUPE, ls="-", lw=p["lw_sub"], zorder=3)
    ax.fill_between(dd_b.index, dd_b, 0, color=S.SOFT_NAVY, alpha=0.55, zorder=1)
    ax.plot(dd_b.index, dd_b, color=S.NAVY, ls="-", lw=p["lw_main"], zorder=4)

    S.style_axes(ax, grid_axis="y", zero_line=True)
    ax.set_ylim(-32.5, 3.8)
    _add_oos_split(ax, p, y_frac=0.98)
    ax.set_ylabel("动态回撤（%）")
    _set_title(ax, "Baseline 最大回撤 -16.7% 显著浅于指数（-24.8%）与 Research（-27.1%）", show_title)

    tb = dd_b.idxmin()
    tr = dd_r.idxmin()
    th = dd_h.idxmin()
    ax.scatter([tb], [dd_b.loc[tb]], color=S.RED, s=p["marker_size"] ** 2, zorder=5)
    ax.annotate(f"Baseline 谷底 {dd_b.loc[tb]:.1f}%", xy=(tb, dd_b.loc[tb]),
                xytext=(pd.Timestamp("2023-06-15"), -26.5),
                fontsize=p["annot_size"], fontweight="bold", color=S.RED,
                arrowprops=dict(arrowstyle="->", color=S.RED, lw=0.9))
    ax.annotate(f"Research {dd_r.loc[tr]:.1f}%", xy=(tr, dd_r.loc[tr]),
                xytext=(-28, -14), textcoords="offset points",
                fontsize=p["annot_size"], color=S.TAUPE, fontweight="semibold")
    ax.annotate(f"沪深300 {dd_h.loc[th]:.1f}%", xy=(th, dd_h.loc[th]),
                xytext=(12, -4), textcoords="offset points",
                fontsize=p["annot_size"], color=S.TEXT_MUTED)

    last_d = nav.index[-1]
    S.label_line_ends(ax, [
        {"x": last_d, "y": dd_b.iloc[-1], "text": f"Baseline ({dd_b.iloc[-1]:.1f}%)", "color": S.NAVY},
        {"x": last_d, "y": dd_h.iloc[-1], "text": f"沪深300 ({dd_h.iloc[-1]:.1f}%)", "color": S.TEXT_MUTED},
        {"x": last_d, "y": dd_r.iloc[-1], "text": f"Research ({dd_r.iloc[-1]:.1f}%)", "color": S.TAUPE},
    ], mode=mode, right_pad_frac=0.22)
    _fmt_date_axis(ax)

    S.save_figure(fig, FIG_DIR / out_subdir / "03_drawdown_underwater.png", mode=mode,
                  source_text="来源：member3/results/nav.csv")


def plot_04_cost_erosion_waterfall(data: dict, mode: str, out_subdir: str, show_title: bool):
    nav = data["nav"]
    b_ideal = (nav["baseline_ideal"].iloc[-1] - 1.0) * 100
    b_real = (nav["baseline"].iloc[-1] - 1.0) * 100
    b_drag = b_real - b_ideal

    r_ideal = (nav["research_ideal"].iloc[-1] - 1.0) * 100
    r_real = (nav["research"].iloc[-1] - 1.0) * 100
    r_drag = r_real - r_ideal

    fig, ax, p = S.make_figure(mode, aspect=0.52)
    x = np.array([0, 1, 2, 3.6, 4.6, 5.6])
    width = 0.58

    ax.bar(x[0], b_ideal, width, color=S.SLATE, edgecolor="none")
    ax.bar(x[1], abs(b_drag), width, bottom=b_real, color=S.TAUPE, alpha=0.85)
    ax.bar(x[2], b_real, width, color=S.NAVY)

    ax.bar(x[3], r_ideal, width, color=S.SLATE, edgecolor="none")
    ax.bar(x[4], abs(r_drag), width, bottom=r_real, color=S.RED, alpha=0.90)
    ax.bar(x[5], r_real, width, color=S.TAUPE)

    ax.plot([x[0] + width / 2, x[1] - width / 2], [b_ideal, b_ideal], color=S.SPINE_GRAY, lw=0.9, ls="--")
    ax.plot([x[1] + width / 2, x[2] - width / 2], [b_real, b_real], color=S.SPINE_GRAY, lw=0.9, ls="--")
    ax.plot([x[3] + width / 2, x[4] - width / 2], [r_ideal, r_ideal], color=S.SPINE_GRAY, lw=0.9, ls="--")
    ax.plot([x[4] + width / 2, x[5] - width / 2], [r_real, r_real], color=S.SPINE_GRAY, lw=0.9, ls="--")

    S.style_axes(ax, grid_axis="y", zero_line=True)
    ax.axvline(2.8, color=S.GRID_GRAY, lw=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels([
        "Baseline\n无成本理想", "Baseline\n成本侵蚀", "Baseline\n计成本实际",
        "Research\n无成本理想", "Research\n成本侵蚀", "Research\n计成本实际",
    ])
    ax.set_ylabel("全样本累计收益（%）")
    ax.set_ylim(-14, 62)
    _set_title(ax, "Research 高换手（51.2%）被交易成本吞噬 37.2 个百分点，Baseline 仅损 5.5 pct", show_title)

    ax.text(x[0], b_ideal + 1.5, f"+{b_ideal:.1f}%", ha="center", va="bottom", fontsize=p["annot_size"], fontweight="semibold")
    ax.text(x[1], b_ideal + 1.5, f"{b_drag:.1f} pct", ha="center", va="bottom", fontsize=p["annot_size"], color=S.TEXT_MUTED)
    ax.text(x[2], b_real + 1.5, f"+{b_real:.1f}%", ha="center", va="bottom", fontsize=p["annot_size"], fontweight="bold", color=S.NAVY)

    ax.text(x[3], r_ideal + 1.5, f"+{r_ideal:.1f}%", ha="center", va="bottom", fontsize=p["annot_size"], fontweight="semibold")
    ax.text(x[4], r_ideal + 1.5, f"{r_drag:.1f} pct", ha="center", va="bottom", fontsize=p["annot_size"], fontweight="bold", color=S.RED)
    ax.text(x[5], r_real - 1.8, f"{r_real:.1f}%", ha="center", va="top", fontsize=p["annot_size"], fontweight="bold", color=S.TAUPE)

    S.save_figure(fig, FIG_DIR / out_subdir / "04_cost_erosion_waterfall.png", mode=mode,
                  source_text="来源：member3/results/nav.csv 与 turnover.csv（Baseline 单边换手 5.9% vs Research 51.2%）")


def plot_05_attribution_diff_bar(data: dict, mode: str, out_subdir: str, show_title: bool):
    comp = data["decomp_compare"]
    label_map = {
        "贡献_bp": "BP（价值）",
        "贡献_ep": "EP（盈利）",
        "贡献_small": "Small（规模）",
        "贡献_alpha006": "Alpha006",
        "贡献_alpha033": "Alpha033",
        "alpha贡献": "截距 Alpha",
        "特异贡献": "特异残差项",
        "组合毛收益": "合计毛收益差",
    }
    order = ["贡献_bp", "贡献_ep", "贡献_small", "贡献_alpha006", "贡献_alpha033", "alpha贡献", "特异贡献", "组合毛收益"]
    vals_bps = [float(comp.loc[k, "差值(research-baseline)"]) * 10000.0 for k in order]
    labels = [label_map[k] for k in order]

    fig, ax, p = S.make_figure(mode, aspect=0.52)
    y_pos = np.arange(len(labels))[::-1]
    colors = []
    for k, v in zip(order, vals_bps):
        if k == "组合毛收益":
            colors.append(S.RED)
        elif v >= 0:
            colors.append(S.SLATE)
        else:
            colors.append(S.NAVY if k in ("贡献_bp", "贡献_ep", "特异贡献") else S.TAUPE)

    ax.barh(y_pos, vals_bps, height=0.58, color=colors)
    S.style_axes(ax, grid_axis="x")
    ax.axvline(0.0, color=S.SPINE_GRAY, lw=1.0)
    ax.axhline(0.5, color=S.GRID_GRAY, lw=1.2)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel("日均收益差（Research - Baseline，基点 bps / 日）")
    ax.set_xlim(-2.25, 0.55)
    _set_title(ax, "Research 选股毛收益日均落后 1.76 bps：价值暴露被稀释 + 显著负特异项", show_title)

    for y, v, k in zip(y_pos, vals_bps, order):
        ha = "right" if v < 0 else "left"
        dx = -0.04 if v < 0 else 0.04
        col = S.RED if k == "组合毛收益" else S.TEXT_DARK
        fw = "bold" if k == "组合毛收益" else "normal"
        ax.text(v + dx, y, f"{v:+.2f}", va="center", ha=ha, fontsize=p["annot_size"], color=col, fontweight=fw)

    S.save_figure(fig, FIG_DIR / out_subdir / "05_attribution_diff_bar.png", mode=mode,
                  source_text="来源：member3/results/decomp_compare.csv（Fama-MacBeth 逐日横截面归因，开盘调仓权重口径）")


def plot_06_cost_grid_heatmap(data: dict, mode: str, out_subdir: str, show_title: bool):
    cs = data["cost_sensitivity"]
    sub = cs[cs["cost_bp"] == 10].copy()
    weights = [0.0, 0.25, 0.5, 0.75]
    rebals = [5, 10, 20]

    # 与全局配色一致的发散色图：负值 #C23B22 -> 0 为纯白 #FFFFFF -> 正值 #14284B
    cmap = LinearSegmentedColormap.from_list("global_div", [S.RED, S.BG_WHITE, S.NAVY], N=256)
    norm = TwoSlopeNorm(vmin=-10.0, vcenter=0.0, vmax=18.0)

    fig, axes, p = S.make_figure(mode, aspect=0.45, nrows=1, ncols=2, sharey=True)
    for ax, per, title_per in zip(axes, ["validation", "test"], ["验证期（2023–2024）", "样本外（2025–2026.10）"]):
        piv = (
            sub[sub["period"] == per]
            .pivot(index="alpha_weight", columns="rebalance", values="net_annualized")
            .reindex(index=weights, columns=rebals)
            * 100.0
        )
        mat = piv.values
        im = ax.imshow(mat, cmap=cmap, norm=norm, aspect="auto")
        ax.set_xticks(range(len(rebals)))
        ax.set_xticklabels([f"{r}日" for r in rebals])
        ax.set_yticks(range(len(weights)))
        ax.set_yticklabels([f"{int(w*100)}%" for w in weights])
        ax.set_xlabel("调仓周期")
        ax.set_title(title_per, fontsize=p["title_size"] * 0.95, color=S.NAVY)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        for i in range(len(weights)):
            for j in range(len(rebals)):
                val = mat[i, j]
                r_c, g_c, b_c, _ = cmap(norm(val))
                lum = 0.299 * r_c + 0.587 * g_c + 0.114 * b_c
                txt_col = S.BG_WHITE if lum < 0.56 else S.TEXT_DARK
                fw = "bold" if (weights[i] == 0.5 and rebals[j] == 5) or (weights[i] == 0.0 and rebals[j] == 5) else "normal"
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center", color=txt_col, fontsize=p["annot_size"], fontweight=fw)

        ax.add_patch(Rectangle((-0.48, -0.48), 0.96, 0.96, fill=False, edgecolor=S.NAVY, lw=1.8))
        ax.add_patch(Rectangle((-0.48, 2 - 0.48), 0.96, 0.96, fill=False, edgecolor=S.RED, lw=1.8, ls="--"))

    axes[0].set_ylabel("Alpha 量价因子权重")
    if show_title:
        fig.suptitle("10bp 单边成本下净年化收益（%）：降频至 20 日可使 50% Alpha 权重恢复至 10.4%",
                     x=0.02, ha="left", y=0.96, fontsize=p["title_size"], color=S.NAVY, fontweight="bold")
        fig.subplots_adjust(left=0.09, right=0.87, bottom=0.18, top=0.80, wspace=0.10)
        cax = fig.add_axes([0.89, 0.18, 0.018, 0.62])
    else:
        fig.subplots_adjust(left=0.09, right=0.87, bottom=0.18, top=0.88, wspace=0.10)
        cax = fig.add_axes([0.89, 0.18, 0.018, 0.70])

    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label("年化净收益（%）", fontsize=p["tick_size"])
    cbar.ax.tick_params(labelsize=p["tick_size"])

    S.save_figure(fig, FIG_DIR / out_subdir / "06_cost_grid_heatmap.png", mode=mode,
                  source_text="来源：member2_v2/results/cost_sensitivity.csv（10bp 截面；实线框为 Baseline，虚线框为 Research）",
                  use_tight=False)


def plot_07_factor_ic_periods(data: dict, mode: str, out_subdir: str, show_title: bool):
    ft = data["factor_tests"]
    sel = data["selection"]
    selected_set = set(sel[sel["decision"] == "selected"]["factor"])

    sub = ft[(ft["stage"] == "neutral") & (ft["horizon"] == 5)].copy()
    factors = ["alpha006", "alpha033", "alpha014", "alpha012", "alpha101"]
    periods = [("train", "训练期 2019-2022", S.NAVY),
               ("validation", "验证期 2023-2024", S.SLATE),
               ("test", "样本外 2025-2026.10", S.TAUPE)]

    fig, ax, p = S.make_figure(mode, aspect=0.50)
    x = np.arange(len(factors))
    w = 0.25

    for idx, (per, label, col) in enumerate(periods):
        vals = [float(sub[(sub["factor"] == f) & (sub["period"] == per)]["mean"].iloc[0]) for f in factors]
        offset = (idx - 1) * w
        bars = ax.bar(x + offset, vals, w, label=label, color=col, alpha=0.92)
        for bx, v in zip(bars, vals):
            va = "bottom" if v >= 0 else "top"
            dy = 0.0006 if v >= 0 else -0.0006
            ax.text(bx.get_x() + bx.get_width() / 2, v + dy, f"{v:.3f}",
                    ha="center", va=va, fontsize=p["annot_size"] * 0.85, color=S.TEXT_DARK)

    S.style_axes(ax, grid_axis="y", zero_line=True)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{f.upper()}\n(入选)" if f in selected_set else f.upper() for f in factors])
    ax.set_ylabel("5日中性化 RankIC 均值")
    ax.set_ylim(-0.015, 0.025)
    _set_title(ax, "训练期仅 Alpha006 与 Alpha033 通过 Holm 校正且低相关入选，验证期全面回落", show_title)
    ax.legend(frameon=False, ncol=3, loc="upper right", fontsize=p["annot_size"])

    S.save_figure(fig, FIG_DIR / out_subdir / "07_factor_ic_periods.png", mode=mode,
                  source_text="来源：member2_v2/results/factor_tests.csv 与 selection.csv（5日中性化 RankIC）")


def plot_08_new012_vs_alpha012_ic(data: dict, mode: str, out_subdir: str, show_title: bool):
    pic = data["proportional_ic"]
    sub = pic[(pic["horizon"] == 5) & (pic["factor"].isin(["alpha012", "new012_return"]))].copy()
    periods = ["train", "validation", "test"]
    p_labels = ["训练期\n(2019–2022)", "验证期\n(2023–2024)", "样本外\n(2025–2026.10)"]

    v_old = [float(sub[(sub["factor"] == "alpha012") & (sub["period"] == per)]["mean"].iloc[0]) for per in periods]
    v_new = [float(sub[(sub["factor"] == "new012_return") & (sub["period"] == per)]["mean"].iloc[0]) for per in periods]

    fig, ax, p = S.make_figure(mode, aspect=0.48)
    x = np.arange(len(periods))
    w = 0.30
    ax.bar(x - w / 2, v_old, w, color=S.TAUPE, label="原版 Alpha012（价格差分尺度敏感）")
    b2 = ax.bar(x + w / 2, v_new, w, color=S.NAVY, label="比例化改进 new012_return（无量纲）")
    b2[-1].set_color(S.RED)

    for i, (vo, vn) in enumerate(zip(v_old, v_new)):
        ax.text(x[i] - w / 2, vo + 0.0004, f"{vo:.4f}", ha="center", va="bottom",
                fontsize=p["annot_size"], color=S.TAUPE, fontweight="semibold")
        col_n = S.RED if i == len(periods) - 1 else S.NAVY
        ax.text(x[i] + w / 2, vn + 0.0004, f"{vn:.4f}", ha="center", va="bottom",
                fontsize=p["annot_size"], color=col_n, fontweight="bold")

    S.style_axes(ax, grid_axis="y", zero_line=True)
    ax.set_xticks(x)
    ax.set_xticklabels(p_labels)
    ax.set_ylabel("5日中性化 RankIC 均值")
    ax.set_ylim(0, 0.0195)
    _set_title(ax, "比例化改进 new012_return 消除价格尺度偏差，三期 IC 全面超越原版 Alpha012", show_title)
    ax.legend(frameon=False, loc="upper left", fontsize=p["annot_size"])

    S.save_figure(fig, FIG_DIR / out_subdir / "08_new012_vs_alpha012_ic.png", mode=mode,
                  source_text="来源：member2_v2/results/proportional_ic.csv（5日持有期；20日样本外 new012 达 0.0171）")


def plot_09_rolling_volatility(data: dict, mode: str, out_subdir: str, show_title: bool):
    nav = data["nav"]
    fig, ax, p = S.make_figure(mode, aspect=0.46)
    rv_h = nav["hs300"].pct_change().rolling(30).std() * np.sqrt(252) * 100
    rv_r = nav["research"].pct_change().rolling(30).std() * np.sqrt(252) * 100
    rv_b = nav["baseline"].pct_change().rolling(30).std() * np.sqrt(252) * 100

    ax.plot(rv_h.index, rv_h, color=S.GRAY, ls="--", lw=p["lw_sub"])
    ax.plot(rv_r.index, rv_r, color=S.TAUPE, ls="-", lw=p["lw_sub"])
    ax.plot(rv_b.index, rv_b, color=S.NAVY, ls="-", lw=p["lw_main"])

    S.style_axes(ax, grid_axis="y")
    _add_oos_split(ax, p, y_frac=0.96)
    ax.set_ylabel("30日滚动年化波动率（%）")
    _set_title(ax, "三者波动水平接近（13%–19%），Baseline 以相近波动获得更高夏普比率", show_title)

    last_d = rv_b.dropna().index[-1]
    S.label_line_ends(ax, [
        {"x": last_d, "y": rv_b.loc[last_d], "text": "Baseline (全期均值 16.0%)", "color": S.NAVY},
        {"x": last_d, "y": rv_r.loc[last_d], "text": "Research (均值 16.3%)", "color": S.TAUPE},
        {"x": last_d, "y": rv_h.loc[last_d], "text": "沪深300 (均值 17.4%)", "color": S.TEXT_MUTED},
    ], mode=mode, right_pad_frac=0.28 if mode == "report" else 0.24)
    _fmt_date_axis(ax)

    S.save_figure(fig, FIG_DIR / out_subdir / "09_rolling_volatility.png", mode=mode,
                  source_text="来源：member3/results/nav.csv（30个交易日滚动标准差 × √252）")


def plot_10_style_exposure(data: dict, mode: str, out_subdir: str, show_title: bool):
    dec_b = data["decomp_base"]
    dec_r = data["decomp_res"]
    fig, axes, p = S.make_figure(mode, aspect=0.72 if mode == "report" else 0.56, nrows=3, ncols=1, sharex=True)

    specs = [
        ("暴露_bp", "BP（账面市值比）暴露"),
        ("暴露_ep", "EP（盈利收益率）暴露"),
        ("暴露_small", "Small（-ln市值）暴露"),
    ]
    for ax, (col, ylabel) in zip(axes, specs):
        ax.plot(dec_r.index, dec_r[col], color=S.TAUPE, lw=p["lw_sub"])
        ax.plot(dec_b.index, dec_b[col], color=S.NAVY, lw=p["lw_main"])
        S.style_axes(ax, grid_axis="y", zero_line=True)
        ax.set_ylabel(ylabel, fontsize=p["label_size"] * 0.92)
        mb = dec_b[col].mean()
        mr = dec_r[col].mean()
        last_d = dec_b.index[-1]
        S.label_line_ends(ax, [
            {"x": last_d, "y": dec_b[col].iloc[-1], "text": f"Baseline 均值 {mb:.2f}", "color": S.NAVY},
            {"x": last_d, "y": dec_r[col].iloc[-1], "text": f"Research 均值 {mr:.2f}", "color": S.TAUPE},
        ], mode=mode, right_pad_frac=0.25 if mode == "report" else 0.22, min_gap_frac=0.14)

    axes[-1].set_xticks([pd.Timestamp("2023-06-01"), pd.Timestamp("2024-06-01"),
                         pd.Timestamp("2025-06-01"), pd.Timestamp("2026-06-01")])
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    _set_title(axes[0], "Research 将组合 BP/EP 价值暴露由 1.54/1.47 稀释至 1.12/1.10，规模倾斜极小", show_title)

    S.save_figure(fig, FIG_DIR / out_subdir / "10_style_exposure.png", mode=mode,
                  source_text="来源：member3/results/decomp_baseline.csv 与 decomp_research.csv（开盘调仓后持仓 × 信号日因子）")


def plot_11_capacity_curve(data: dict, mode: str, out_subdir: str, show_title: bool):
    curve = data["capacity_curve"]
    summary = data["product_summary"]
    c08 = curve[curve["Y"] == 0.8].sort_values("aum_yi")
    c05 = curve[curve["Y"] == 0.5].sort_values("aum_yi")
    c10 = curve[curve["Y"] == 1.0].sort_values("aum_yi")

    hs_ann = float(c08["hs300_ann"].iloc[0]) * 100.0
    cap_y08 = summary["capacity_impact"]["half_excess_capacities"]["Y_0.8"]["baseline_half_excess_aum_yi"]
    target_ann = summary["capacity_impact"]["half_excess_capacities"]["Y_0.8"]["baseline_target_net_ann"] * 100.0

    fig, ax, p = S.make_figure(mode, aspect=0.52)
    ax.set_xscale("log")

    # 极浅主色带标出「建议管理规模 ≤ 10亿元」区间
    ax.axvspan(0.08, 10.0, color=S.SOFT_NAVY, alpha=0.22, zorder=0)
    ax.axvline(10.0, color=S.SLATE, ls="-.", lw=0.9, alpha=0.65, zorder=1)
    ax.text(0.85, 12.6, "建议管理规模 ≤ 10 亿元（流动性约束）",
            ha="center", va="center", fontsize=p["annot_size"] * 0.92,
            color=S.NAVY, fontweight="semibold")

    ax.fill_between(c08["aum_yi"], c10["baseline_net_ann"] * 100, c05["baseline_net_ann"] * 100,
                    color=S.SOFT_NAVY, alpha=0.45, zorder=1)
    ax.plot(c08["aum_yi"], c08["research_net_ann"] * 100, color=S.TAUPE, lw=p["lw_sub"], zorder=3)
    ax.plot(c08["aum_yi"], c08["baseline_net_ann"] * 100, color=S.NAVY, lw=p["lw_main"] * 1.15, zorder=4)

    ax.axhline(hs_ann, color=S.GRAY, ls="--", lw=p["lw_sub"], zorder=2)
    ax.axhline(target_ann, color=S.SPINE_GRAY, ls=":", lw=1.0, zorder=2)

    # 容量交点（唯一朱砂红强调）
    ax.scatter([cap_y08], [target_ann], color=S.RED, s=p["marker_size"] ** 2 * 1.3, zorder=5)
    ax.vlines(cap_y08, -25, target_ann, color=S.RED, ls=":", lw=1.0, zorder=2)
    ax.annotate(
        f"理论半衰容量 ≈ {cap_y08:.1f} 亿元\n（Y=0.8，敏感性 {summary['capacity_impact']['half_excess_capacities']['Y_1.0']['baseline_half_excess_aum_yi']:.0f}–{summary['capacity_impact']['half_excess_capacities']['Y_0.5']['baseline_half_excess_aum_yi']:.0f} 亿）",
        xy=(cap_y08, target_ann),
        xytext=(cap_y08 * 0.25, target_ann - 10.5),
        fontsize=p["annot_size"], fontweight="bold", color=S.RED,
        arrowprops=dict(arrowstyle="->", color=S.RED, lw=1.0),
    )

    S.style_axes(ax, grid_axis="y")
    ax.set_xlim(0.08, 1200)
    ax.set_ylim(-25, 14.5)
    ax.set_xticks([0.1, 1, 5, 10, 50, 100, 500])
    ax.get_xaxis().set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}亿"))
    ax.set_xlabel("资产管理规模 AUM（对数刻度）")
    ax.set_ylabel("计入交易与冲击成本后年化净收益（%）")
    _set_title(ax, "建议规模 10 亿元以内；冲击成本理论半衰容量约 81 亿元", show_title)

    ax.text(550, c08["baseline_net_ann"].iloc[-1] * 100, "Baseline\n(Y=0.8)",
            color=S.NAVY, fontsize=p["annot_size"], fontweight="semibold", va="center")
    # Research 文字标签置于曲线左上方空白处，避开曲线与 10亿/80.9亿 竖虚线
    ax.text(1.05, -1.5,
            "Research (Y=0.8)\n超额已为负\n10亿即跌至 -16.3%",
            color=S.TAUPE, fontsize=p["annot_size"] * 0.90, va="top", ha="left")
    ax.text(0.10, hs_ann + 0.55, f"沪深300 基准 ({hs_ann:.2f}%)", color=S.TEXT_MUTED, fontsize=p["annot_size"] * 0.88)
    ax.text(0.10, target_ann + 0.55, f"超额半衰阈值 ({target_ann:.2f}%)", color=S.TEXT_MUTED, fontsize=p["annot_size"] * 0.88)

    S.save_figure(fig, FIG_DIR / out_subdir / "11_capacity_curve.png", mode=mode,
                  source_text="来源：member4/results/capacity_curve.csv（阴影带为 Y=0.5 至 Y=1.0 敏感区间；Research 仅绘至 -25% 区间内）")


def plot_12_fee_net_nav(data: dict, mode: str, out_subdir: str, show_title: bool):
    inv = data["investor_nav"]
    fee_df = data["fee_analysis"].set_index("plan_id")

    fig, ax, p = S.make_figure(mode, aspect=0.52)
    ax.plot(inv.index, inv["hs300"], color=S.GRAY, ls="--", lw=p["lw_sub"], zorder=2)
    ax.plot(inv.index, inv["plan_A"], color=S.TAUPE, ls="-", lw=p["lw_sub"], zorder=3)
    ax.plot(inv.index, inv["plan_B"], color=S.AMBER, ls="-.", lw=p["lw_sub"], zorder=3)
    ax.plot(inv.index, inv["plan_C"], color=S.TEAL, ls="-", lw=p["lw_sub"] * 1.1, zorder=4)
    ax.plot(inv.index, inv["plan_D"], color=S.SLATE, ls=":", lw=p["lw_sub"] * 1.1, zorder=4)
    ax.plot(inv.index, inv["baseline_gross"], color=S.NAVY, ls="-", lw=p["lw_main"] * 1.15, zorder=5)

    S.style_axes(ax, grid_axis="y")
    ax.axhline(1.0, color=S.SPINE_GRAY, lw=0.7)
    ax.set_ylabel("净值（初始 = 1.0）")
    _set_title(ax, "扣除管理与业绩报酬后，四档方案投资者到手年化仍达 7.6%–8.9%", show_title)

    last_d = inv.index[-1]
    items = [
        {"x": last_d, "y": inv["baseline_gross"].iloc[-1],
         "text": f"策略净值(未扣费) {inv['baseline_gross'].iloc[-1]:.3f} (10.8%/yr)", "color": S.NAVY, "weight": "bold"},
        {"x": last_d, "y": inv["plan_D"].iloc[-1],
         "text": f"方案D 纯管理费 {inv['plan_D'].iloc[-1]:.3f} ({fee_df.loc['D','ann_return']*100:.1f}%/yr)", "color": S.SLATE},
        {"x": last_d, "y": inv["plan_C"].iloc[-1],
         "text": f"方案C 机构份额 {inv['plan_C'].iloc[-1]:.3f} ({fee_df.loc['C','ann_return']*100:.1f}%/yr)", "color": S.RED, "weight": "bold"},
        {"x": last_d, "y": inv["plan_A"].iloc[-1],
         "text": f"方案A 标准份额 {inv['plan_A'].iloc[-1]:.3f} ({fee_df.loc['A','ann_return']*100:.1f}%/yr)", "color": S.TAUPE},
        {"x": last_d, "y": inv["plan_B"].iloc[-1],
         "text": f"方案B 超额计提 {inv['plan_B'].iloc[-1]:.3f} ({fee_df.loc['B','ann_return']*100:.1f}%/yr)", "color": S.AMBER},
        {"x": last_d, "y": inv["hs300"].iloc[-1],
         "text": f"沪深300基准 {inv['hs300'].iloc[-1]:.3f} (0.0%/yr)", "color": S.TEXT_MUTED},
    ]
    S.label_line_ends(ax, items, mode=mode, right_pad_frac=0.33 if mode == "report" else 0.28, min_gap_frac=0.08)
    _fmt_date_axis(ax)

    S.save_figure(fig, FIG_DIR / out_subdir / "12_fee_net_nav.png", mode=mode,
                  source_text="来源：member4/results/investor_nav.csv 与 fee_analysis.csv（逐日计提管理/托管费，年度高水位计提业绩报酬）")


def plot_13_latest_industry_dist(data: dict, mode: str, out_subdir: str, show_title: bool):
    ind = data["ind_dist"].sort_values("权重合计", ascending=True)
    fig, ax, p = S.make_figure(mode, aspect=0.52)
    y = np.arange(len(ind))
    colors = [S.NAVY if n in ("银行", "非银金融") else S.SLATE for n in ind["申万一级行业"]]

    ax.barh(y, ind["权重合计"], height=0.62, color=colors)
    S.style_axes(ax, grid_axis="x")
    ax.set_yticks(y)
    ax.set_yticklabels(ind["申万一级行业"])
    ax.set_xlabel("最新持仓权重占比（%）")
    ax.set_xlim(0, 39)
    _set_title(ax, "2026-10-30 最新 50 只等权持仓分布：金融与基建价值板块占主导", show_title)

    for yi, (_, r) in enumerate(ind.iterrows()):
        ax.text(r["权重合计"] + 0.5, yi, f"{r['权重合计']:.0f}% ({int(r['持仓只数'])}只)",
                va="center", ha="left", fontsize=p["annot_size"], color=S.TEXT_DARK)

    ax.text(0.97, 0.12, "银行 + 非银金融合计 60%\n（30只，高 BP/EP 价值集中）",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=p["annot_size"], fontweight="bold", color=S.RED,
            bbox=dict(boxstyle="round,pad=0.35", facecolor=S.BG_WHITE, edgecolor=S.RED, lw=0.9))

    S.save_figure(fig, FIG_DIR / out_subdir / "13_latest_industry_dist.png", mode=mode,
                  source_text="来源：member4/xueqiu/最新持仓_2026-10-30.csv（申万一级行业分类，45天快照时效约束）")


def plot_14_data_universe_filtering(panel: pd.DataFrame, mode: str, out_subdir: str, show_title: bool):
    stats = (
        panel.groupby("trade_date")
        .agg(index_members=("in_index_universe", "sum"), tradable=("tradable_mask", "sum"))
        .sort_index()
    )
    fig, ax, p = S.make_figure(mode, aspect=0.45)
    ax.plot(stats.index, stats["index_members"], color=S.SLATE, lw=p["lw_sub"])
    ax.fill_between(stats.index, stats["tradable"], stats["index_members"], color=S.TAUPE, alpha=0.30)
    ax.plot(stats.index, stats["tradable"], color=S.NAVY, lw=p["lw_main"])

    S.style_axes(ax, grid_axis="y")
    ax.set_ylim(245, 315)
    ax.set_ylabel("每日股票数量（只）")
    _set_title(ax, "2019–2026 动态沪深300 成分股与可交易有效样本（均约 299 只有效）", show_title)

    last_d = stats.index[-1]
    n_idx = int(stats["index_members"].iloc[-1])
    n_trd = int(stats["tradable"].iloc[-1])
    S.label_line_ends(ax, [
        {"x": last_d, "y": n_idx, "text": f"成分股 {n_idx}只", "color": S.SLATE},
        {"x": last_d, "y": n_trd, "text": f"有效可交易 {n_trd}只", "color": S.NAVY, "weight": "bold"},
    ], mode=mode, right_pad_frac=0.20, min_gap_frac=0.10)
    _fmt_date_axis(ax, full_span=True)

    ax.text(pd.Timestamp("2020-07-01"), 272, f"日均过滤 { (stats['index_members']-stats['tradable']).mean():.1f} 只\n(停牌/ST/次新/异常)",
            fontsize=p["annot_size"], color=S.TAUPE)

    S.save_figure(fig, FIG_DIR / out_subdir / "14_data_universe_filtering.png", mode=mode,
                  source_text="来源：quant_project_data/processed/clean_daily_panel.parquet（共 1,897 个交易日，568,036 条可交易记录）")


def _kde_curve(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    bw = max(1.06 * np.std(values) * len(values) ** (-0.2), 1e-9)
    return np.exp(-0.5 * ((grid[:, None] - values[None, :]) / bw) ** 2).sum(axis=1) / (
        len(values) * bw * np.sqrt(2.0 * np.pi)
    )


def plot_15_data_preprocess_3stages(panel: pd.DataFrame, mode: str, out_subdir: str, show_title: bool):
    last_dt = panel["trade_date"].max()
    sub = panel[panel["trade_date"] == last_dt]
    fig, axes, p = S.make_figure(mode, aspect=0.38, nrows=1, ncols=3)

    stages = [
        ("raw_alpha_demo_masked", "① 原始可交易因子", S.TAUPE),
        ("raw_alpha_demo_winsorized", "② MAD 去极值", S.SLATE),
        ("raw_alpha_demo_clean", "③ 行业与市值中性化 + Z", S.NAVY),
    ]
    for ax, (col, title_s, color) in zip(axes, stages):
        vals = sub[col].dropna().to_numpy(float)
        ax.hist(vals, bins=25, density=True, color=color, alpha=0.45, edgecolor=S.BG_WHITE, lw=0.4)
        grid = np.linspace(vals.min() - 0.5 * vals.std(), vals.max() + 0.5 * vals.std(), 200)
        ax.plot(grid, _kde_curve(vals, grid), color=color, lw=p["lw_main"])
        S.style_axes(ax, grid_axis="y")
        ax.set_title(title_s, fontsize=p["title_size"] * 0.90, color=S.NAVY)
        ax.set_xlabel("因子值")
        s = pd.Series(vals)
        ax.text(0.96, 0.94, f"均值 {s.mean():.3f}\n中位 {s.median():.3f}\n偏度 {s.skew():.2f}\n峰度 {s.kurt():.2f}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=p["annot_size"] * 0.88, color=S.TEXT_DARK,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=S.BG_WHITE, edgecolor=S.GRID_GRAY, alpha=0.9))

    axes[0].set_ylabel("概率密度")
    if show_title:
        fig.suptitle(f"截面预处理三阶段分布演变（示例断面：{last_dt.date()}）",
                     x=0.02, ha="left", fontsize=p["title_size"], color=S.NAVY, fontweight="bold")
        t_rect = (0.0, 0.04, 1.0, 0.92)
    else:
        t_rect = (0.0, 0.04, 1.0, 1.0)
    S.save_figure(fig, FIG_DIR / out_subdir / "15_data_preprocess_3stages.png", mode=mode,
                  source_text="来源：quant_project_data/processed/clean_daily_panel.parquet（raw_alpha_demo 三阶段字段）",
                  tight_rect=t_rect)


def plot_16_data_coverage_summary(panel: pd.DataFrame, mode: str, out_subdir: str, show_title: bool):
    fields = ["open", "close_hfq", "volume", "amount", "turn", "peTTM", "pbMRQ", "ln_mkt_cap", "sw_l1_name"]
    labels = ["open(开盘价)", "close_hfq(后复权)", "volume(成交量)", "amount(成交额)",
              "turn(换手率)", "peTTM(市盈率)", "pbMRQ(市净率)", "ln_mkt_cap(市值代理)", "sw_l1_name(申万行业)"]
    before = [panel[f"raw_valid_{c}"].mean() if f"raw_valid_{c}" in panel else np.nan for c in fields]
    after = [panel[c].notna().mean() if c != "sw_l1_name" else panel[c].ne("未分类").mean() for c in fields]
    before[-2] = panel["raw_valid_amount"].mean() * panel["raw_valid_turn"].mean()
    before[-1] = after[-1]

    fig, ax, p = S.make_figure(mode, aspect=0.50)
    x = np.arange(len(fields))
    w = 0.35
    ax.bar(x - w / 2, [b * 100 for b in before], w, color=S.TAUPE, label="原始有效覆盖率")
    ax.bar(x + w / 2, [a * 100 for a in after], w, color=S.NAVY, label="清洗后有效覆盖率")

    S.style_axes(ax, grid_axis="y")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=22, ha="right")
    ax.set_ylim(75, 108.5)
    ax.set_ylabel("全样本覆盖率（%）")
    _set_title(ax, "行情与估值字段清洗后覆盖率均达 99%–100%，申万行业纯化保留 19.6% 未分类", show_title)
    ax.legend(frameon=False, loc="upper right", ncol=2, fontsize=p["annot_size"])

    for i, (b, a) in enumerate(zip(before, after)):
        col_a = S.RED if fields[i] == "sw_l1_name" else S.NAVY
        ax.text(i + w / 2, a * 100 + 0.5, f"{a*100:.1f}%", ha="center", va="bottom",
                fontsize=p["annot_size"] * 0.85, color=col_a, fontweight="semibold")

    S.save_figure(fig, FIG_DIR / out_subdir / "16_data_coverage_summary.png", mode=mode,
                  source_text="来源：quant_project_data/processed/clean_daily_panel.parquet（940,696 行，45天行业快照时效限制）")


def main():
    print("加载绘图所需数据 ...")
    data = {
        "nav": pd.read_csv(M3_RES / "nav.csv", index_col=0, parse_dates=True),
        "decomp_compare": pd.read_csv(M3_RES / "decomp_compare.csv", index_col=0),
        "decomp_base": pd.read_csv(M3_RES / "decomp_baseline.csv", index_col=0, parse_dates=True),
        "decomp_res": pd.read_csv(M3_RES / "decomp_research.csv", index_col=0, parse_dates=True),
        "cost_sensitivity": pd.read_csv(M2_RES / "cost_sensitivity.csv"),
        "factor_tests": pd.read_csv(M2_RES / "factor_tests.csv"),
        "selection": pd.read_csv(M2_RES / "selection.csv"),
        "proportional_ic": pd.read_csv(M2_RES / "proportional_ic.csv"),
        "capacity_curve": pd.read_csv(M4_RES / "capacity_curve.csv"),
        "fee_analysis": pd.read_csv(M4_RES / "fee_analysis.csv"),
        "investor_nav": pd.read_csv(M4_RES / "investor_nav.csv", index_col=0, parse_dates=True),
        "ind_dist": pd.read_csv(M4_RES / "latest_industry_distribution.csv"),
    }
    with open(M4_RES / "product_summary.json", "r", encoding="utf-8") as f:
        data["product_summary"] = json.load(f)

    panel_cols = [
        "trade_date", "in_index_universe", "tradable_mask",
        "raw_alpha_demo_masked", "raw_alpha_demo_winsorized", "raw_alpha_demo_clean",
        "open", "close_hfq", "volume", "amount", "turn", "peTTM", "pbMRQ", "ln_mkt_cap", "sw_l1_name",
        "raw_valid_open", "raw_valid_close_hfq", "raw_valid_volume", "raw_valid_amount",
        "raw_valid_turn", "raw_valid_peTTM", "raw_valid_pbMRQ",
    ]
    panel = pd.read_parquet(PROC / "clean_daily_panel.parquet", columns=panel_cols)
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    plot_funcs = [
        ("01_nav_curve", lambda m, sub, st: plot_01_nav_curve(data, m, sub, st)),
        ("02_excess_curve", lambda m, sub, st: plot_02_excess_curve(data, m, sub, st)),
        ("03_drawdown_underwater", lambda m, sub, st: plot_03_drawdown_underwater(data, m, sub, st)),
        ("04_cost_erosion_waterfall", lambda m, sub, st: plot_04_cost_erosion_waterfall(data, m, sub, st)),
        ("05_attribution_diff_bar", lambda m, sub, st: plot_05_attribution_diff_bar(data, m, sub, st)),
        ("06_cost_grid_heatmap", lambda m, sub, st: plot_06_cost_grid_heatmap(data, m, sub, st)),
        ("07_factor_ic_periods", lambda m, sub, st: plot_07_factor_ic_periods(data, m, sub, st)),
        ("08_new012_vs_alpha012_ic", lambda m, sub, st: plot_08_new012_vs_alpha012_ic(data, m, sub, st)),
        ("09_rolling_volatility", lambda m, sub, st: plot_09_rolling_volatility(data, m, sub, st)),
        ("10_style_exposure", lambda m, sub, st: plot_10_style_exposure(data, m, sub, st)),
        ("11_capacity_curve", lambda m, sub, st: plot_11_capacity_curve(data, m, sub, st)),
        ("12_fee_net_nav", lambda m, sub, st: plot_12_fee_net_nav(data, m, sub, st)),
        ("13_latest_industry_dist", lambda m, sub, st: plot_13_latest_industry_dist(data, m, sub, st)),
        ("14_data_universe_filtering", lambda m, sub, st: plot_14_data_universe_filtering(panel, m, sub, st)),
        ("15_data_preprocess_3stages", lambda m, sub, st: plot_15_data_preprocess_3stages(panel, m, sub, st)),
        ("16_data_coverage_summary", lambda m, sub, st: plot_16_data_coverage_summary(panel, m, sub, st)),
    ]

    variants = [
        ("report", "report", True),
        ("slide", "slide", True),
        ("slide", "slide_notitle", False),
    ]
    for mode, out_subdir, show_title in variants:
        print(f"生成 {out_subdir} 预设图表（16 张，mode={mode}, title={show_title}）...")
        for name, fn in plot_funcs:
            fn(mode, out_subdir, show_title)
            print(f"  ✓ {out_subdir}/{name}.png")

    print("全部 48 张图表（report×16 + slide×16 + slide_notitle×16）已生成至:", FIG_DIR)


if __name__ == "__main__":
    main()
