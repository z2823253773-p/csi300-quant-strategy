"""Three report figures at 300 DPI."""
import numpy as np
import pandas as pd


def _plot_module():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _mark(ax, mode):
    if mode == "demo":
        ax.text(.99, .02, "SYNTHETIC DEMO", transform=ax.transAxes, ha="right", va="bottom",
                fontsize=9, color="#9a4040", alpha=.75)


def _kde(values, grid):
    values = np.asarray(values, dtype=float)
    if len(values) < 3 or np.std(values) == 0:
        return np.zeros_like(grid)
    bandwidth = max(1.06 * np.std(values) * len(values)**(-1/5), 1e-9)
    return np.exp(-.5 * ((grid[:, None] - values[None, :]) / bandwidth)**2).sum(axis=1) / (len(values) * bandwidth * np.sqrt(2*np.pi))


def create_figures(panel, config, mode, factor="raw_alpha_demo"):
    plt = _plot_module()
    out = config.figure_dir
    out.mkdir(parents=True, exist_ok=True)
    stats = panel.groupby("trade_date").agg(index_members=("in_index_universe", "sum"), tradable=("tradable_mask", "sum"))
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(stats.index, stats["index_members"], label="指数成分股", color="#456b9a")
    ax.fill_between(stats.index, stats["tradable"].to_numpy(), stats["index_members"].to_numpy(),
                    color="#dcae7a", alpha=.45, label="被过滤股票")
    ax.plot(stats.index, stats["tradable"], label="有效可交易", color="#287c5a")
    ax.set_ylim(max(0, int(stats["tradable"].min()) - 5), int(stats["index_members"].max()) + 5)
    ax.set(title="动态股票池与有效交易覆盖", ylabel="股票数")
    ax.grid(alpha=.2)
    ax.legend()
    _mark(ax, mode)
    fig.tight_layout()
    fig.savefig(out / "fig1_universe_filtering_stats.png", dpi=300)
    plt.close(fig)

    date = panel["trade_date"].max()
    sub = panel[panel["trade_date"].eq(date)]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, (column, label, color) in zip(axes, [
        (factor + "_masked", "原始可交易因子", "#466da0"),
        (factor + "_winsorized", "MAD 去极值", "#4f9b79"),
        (factor + "_clean", "行业与规模中性化 + Z 分数", "#c9824c")]):
        values = sub[column].dropna().to_numpy(float)
        if len(values):
            ax.hist(values, bins=25, density=True, color=color, alpha=.55)
            grid = np.linspace(values.min() - values.std(), values.max() + values.std(), 200)
            ax.plot(grid, _kde(values, grid), color=color, lw=2)
            series = pd.Series(values)
            ax.text(.02, .98, f"均值 {series.mean():.3f}\n中位数 {series.median():.3f}\n偏度 {series.skew():.2f}\n峰度 {series.kurt():.2f}",
                    transform=ax.transAxes, va="top", fontsize=9)
        ax.set(title=label, xlabel="因子值", ylabel="密度")
        ax.grid(alpha=.18)
        _mark(ax, mode)
    fig.suptitle(f"因子预处理三阶段：{date.date()}")
    fig.tight_layout()
    fig.savefig(out / "fig2_factor_preprocess_3stages.png", dpi=300)
    plt.close(fig)

    fields = ["open", "close_hfq", "volume", "amount", "turn", "peTTM", "pbMRQ", "ln_mkt_cap", "sw_l1_name"]
    before = [panel[f"raw_valid_{c}"].mean() if f"raw_valid_{c}" in panel else np.nan for c in fields]
    after = [panel[c].notna().mean() if c != "sw_l1_name" else panel[c].ne("未分类").mean() for c in fields]
    before[-2] = panel["raw_valid_amount"].mean() * panel["raw_valid_turn"].mean()
    before[-1] = after[-1]  # Industry is a separate point-in-time snapshot, not a filled price field.
    x = np.arange(len(fields))
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.bar(x - .18, before, .36, label="原始有效覆盖", color="#7899bf")
    ax.bar(x + .18, after, .36, label="清洗后覆盖", color="#5eaa83")
    ax.set_xticks(x, fields, rotation=25, ha="right")
    lower = max(0, min(min(before), min(after)) - .035)
    ax.set_ylim(lower, 1.035)
    ax.set_ylabel("覆盖比例")
    ax.set_title("核心字段有效覆盖率")
    for i, (a, b) in enumerate(zip(before, after)):
        ax.text(i - .18, a + .004, f"{a:.1%}", ha="center", va="bottom", fontsize=7, rotation=90)
        ax.text(i + .18, b + .004, f"{b:.1%}", ha="center", va="bottom", fontsize=7, rotation=90)
    ax.legend()
    ax.grid(axis="y", alpha=.18)
    _mark(ax, mode)
    fig.tight_layout()
    fig.savefig(out / "fig3_data_coverage_summary.png", dpi=300)
    plt.close(fig)
