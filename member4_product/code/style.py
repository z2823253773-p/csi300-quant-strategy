# -*- coding: utf-8 -*-
"""
组员4：统一视觉系统（PLAN 5.1 规范）
所有 report 与 slide 图表共用本模块。
"""
import os
import tempfile
from pathlib import Path

# 确保沙箱或只读 HOME 下 matplotlib 缓存可写
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
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# PLAN 5.1 调色板
# ---------------------------------------------------------------------------
NAVY = "#14284B"        # 主色：标题、Baseline 曲线
TAUPE = "#A38F6E"       # 对照色：Research（刻意弱化，不抢戏）
GRAY = "#9AA0A6"        # 基准色：沪深300（虚线）
RED = "#C23B22"         # 强调色：每图最多一处，只用于标关键数字
BG_WHITE = "#FFFFFF"    # 纯白背景
GRID_GRAY = "#ECEEF1"   # 极浅灰横网格
SPINE_GRAY = "#CBD2D9"  # 浅灰坐标轴
TEXT_DARK = "#1F2933"   # 正文深灰
TEXT_MUTED = "#52606D"  # 辅助说明灰

# 辅助色（仅用于多因子/多档对比，不抢主色）
SLATE = "#486581"
TEAL = "#3B7A75"
AMBER = "#B87D3B"
SOFT_BLUE = "#7B9ACC"
SOFT_NAVY = "#D9E2EC"

FONT_LIST = ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"]

# ---------------------------------------------------------------------------
# 尺寸预设：report（宽 16 cm）与 slide（16:9 大字号）
# ---------------------------------------------------------------------------
REPORT_WIDTH_IN = 16.0 / 2.54   # 6.2992 in (16 cm)
SLIDE_WIDTH_IN = 11.2           # 适合 13.33 x 7.5 in 16:9 幻灯片主图区

PRESETS = {
    "report": {
        "width": REPORT_WIDTH_IN,
        "dpi": 300,
        "title_size": 10.5,
        "suptitle_size": 11.5,
        "label_size": 8.5,
        "tick_size": 7.8,
        "annot_size": 7.8,
        "source_size": 7.0,
        "lw_main": 1.7,
        "lw_sub": 1.35,
        "lw_ref": 0.9,
        "marker_size": 4.5,
    },
    "slide": {
        "width": SLIDE_WIDTH_IN,
        "dpi": 300,
        "title_size": 15.0,
        "suptitle_size": 16.5,
        "label_size": 11.5,
        "tick_size": 10.5,
        "annot_size": 10.5,
        "source_size": 9.0,
        "lw_main": 2.5,
        "lw_sub": 2.0,
        "lw_ref": 1.2,
        "marker_size": 6.5,
    },
}


def get_preset(mode: str = "report") -> dict:
    if mode not in PRESETS:
        raise ValueError(f"Unknown mode '{mode}', expected 'report' or 'slide'")
    return PRESETS[mode]


def apply_style(mode: str = "report") -> dict:
    p = get_preset(mode)
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": FONT_LIST,
        "axes.unicode_minus": False,
        "figure.facecolor": BG_WHITE,
        "axes.facecolor": BG_WHITE,
        "savefig.facecolor": BG_WHITE,
        "savefig.edgecolor": "none",
        "axes.edgecolor": SPINE_GRAY,
        "axes.linewidth": 0.8,
        "axes.titlesize": p["title_size"],
        "axes.titleweight": "bold",
        "axes.titlecolor": NAVY,
        "axes.titlepad": 10 if mode == "report" else 14,
        "axes.labelsize": p["label_size"],
        "axes.labelcolor": TEXT_DARK,
        "xtick.labelsize": p["tick_size"],
        "ytick.labelsize": p["tick_size"],
        "xtick.color": TEXT_MUTED,
        "ytick.color": TEXT_MUTED,
        "xtick.major.size": 3.0,
        "ytick.major.size": 0.0,
        "grid.color": GRID_GRAY,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "text.color": TEXT_DARK,
        "figure.titlesize": p["suptitle_size"],
        "figure.titleweight": "bold",
    })
    return p


def make_figure(mode: str = "report", aspect: float = 0.56, nrows: int = 1,
                ncols: int = 1, height_in: float | None = None, **subplots_kw):
    p = apply_style(mode)
    w = p["width"]
    if height_in is None:
        if mode == "slide" and nrows == 1 and ncols == 1:
            h = w * 0.50  # 16:9 slide 留出顶部标题与底部来源空间
        else:
            h = w * aspect
    else:
        h = height_in
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(w, h),
                             facecolor=BG_WHITE, **subplots_kw)
    return fig, axes, p


def style_axes(ax, grid_axis: str = "y", zero_line: bool = False):
    ax.set_facecolor(BG_WHITE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SPINE_GRAY)
    ax.spines["bottom"].set_color(SPINE_GRAY)
    ax.spines["left"].set_linewidth(0.75)
    ax.spines["bottom"].set_linewidth(0.75)
    ax.set_axisbelow(True)
    if grid_axis in ("y", "x", "both"):
        ax.grid(True, axis=grid_axis, color=GRID_GRAY, linewidth=0.8)
    else:
        ax.grid(False)
    if zero_line:
        ax.axhline(0.0, color=SPINE_GRAY, linewidth=0.9, linestyle="-", zorder=1)


def label_line_ends(ax, items: list[dict], mode: str = "report",
                    right_pad_frac: float = 0.16, min_gap_frac: float = 0.075):
    """
    在曲线末端直接标注名称与数值，不使用图例框。
    items: list of dict with keys: x, y, text, color, [weight], [fontsize]
    """
    p = get_preset(mode)
    if not items:
        return

    # 扩展 x 右侧空间以容纳末端标签
    x0, x1 = ax.get_xlim()
    dx = x1 - x0
    if dx > 0:
        ax.set_xlim(x0, x1 + dx * right_pad_frac)

    y0, y1 = ax.get_ylim()
    yr = y1 - y0
    if yr <= 0:
        yr = 1.0

    # 提取末端 y 并排序做防重叠微调
    parsed = []
    for it in items:
        parsed.append({
            "x": it["x"],
            "y": float(it["y"]),
            "text": it["text"],
            "color": it["color"],
            "weight": it.get("weight", "semibold"),
            "fontsize": it.get("fontsize", p["annot_size"]),
        })
    parsed.sort(key=lambda d: d["y"])

    min_gap = yr * min_gap_frac
    ys = [d["y"] for d in parsed]
    for i in range(1, len(ys)):
        if ys[i] - ys[i - 1] < min_gap:
            ys[i] = ys[i - 1] + min_gap
    # 若顶部超出太多，整体或逐级向下压缩
    if ys[-1] > y1 - 0.03 * yr and len(ys) > 1:
        shift = ys[-1] - (y1 - 0.03 * yr)
        ys[-1] -= shift
        for i in range(len(ys) - 2, -1, -1):
            if ys[i + 1] - ys[i] < min_gap:
                ys[i] = ys[i + 1] - min_gap

    # 确保所有点都在当前 ylim 内
    new_y0 = min(y0, min(ys) - 0.04 * yr)
    new_y1 = max(y1, max(ys) + 0.04 * yr)
    ax.set_ylim(new_y0, new_y1)

    x_offset = (dx * 0.015) if dx > 0 else 0
    for d, y_pos in zip(parsed, ys):
        x_val = d["x"]
        # 支持 Timestamp / numeric x
        if hasattr(x_val, "toordinal") or hasattr(x_val, "timestamp"):
            import matplotlib.dates as mdates
            x_num = mdates.date2num(x_val) + x_offset
        else:
            x_num = float(x_val) + x_offset
        ax.text(
            x_num,
            y_pos,
            d["text"],
            color=d["color"],
            fontsize=d["fontsize"],
            fontweight=d["weight"],
            va="center",
            ha="left",
            clip_on=False,
        )


def add_source_note(fig, text: str, mode: str = "report"):
    p = get_preset(mode)
    fig.text(
        0.012,
        0.008,
        text,
        fontsize=p["source_size"],
        color=TEXT_MUTED,
        ha="left",
        va="bottom",
    )


def save_figure(fig, out_path: Path | str, mode: str = "report",
                source_text: str | None = None, tight_rect: tuple | None = None,
                use_tight: bool = True):
    p = get_preset(mode)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if "slide_notitle" in str(out_path):
        source_text = None
    if source_text:
        add_source_note(fig, source_text, mode=mode)
        if tight_rect is None:
            tight_rect = (0.0, 0.035, 1.0, 1.0)
    if use_tight:
        if tight_rect is not None:
            fig.tight_layout(rect=tight_rect)
        else:
            fig.tight_layout()
    fig.savefig(
        out_path,
        dpi=p["dpi"],
        facecolor=BG_WHITE,
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.08,
    )
    plt.close(fig)
