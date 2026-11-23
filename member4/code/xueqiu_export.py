# -*- coding: utf-8 -*-
"""
组员4 模块2：雪球模拟组合导出与调仓记录
严格遵循 member4/PLAN.md 第3节规范，上游数据只读。
复现命令（在 member4 目录）：
    .venv/bin/python code/xueqiu_export.py
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

import paths as P

ROOT = P.WORKSPACE_ROOT
MEMBER4 = P.MEMBER4_DIR
PROC = P.PROC
M2_SIG = P.M2_SIG
M3_RES = P.M3_RES
OUT_XQ = MEMBER4 / "xueqiu"
OUT_SS = OUT_XQ / "screenshots"
OUT_RES = MEMBER4 / "results"
OUT_XQ.mkdir(parents=True, exist_ok=True)
OUT_SS.mkdir(parents=True, exist_ok=True)
OUT_RES.mkdir(parents=True, exist_ok=True)


def main():
    print("1. 加载最新信号、持仓权重与面板元数据 ...")
    tw = pd.read_csv(M2_SIG / "target_weights.csv")
    tw["signal_date"] = pd.to_datetime(tw["signal_date"])
    tw["execution_date"] = pd.to_datetime(tw["execution_date"])
    tw_base = tw[tw["model"] == "baseline"].copy()

    latest_exec = tw_base["execution_date"].max()
    latest_sig = tw_base[tw_base["execution_date"] == latest_exec]["signal_date"].iloc[0]
    latest_tw = tw_base[tw_base["execution_date"] == latest_exec].sort_values("score", ascending=False).copy()

    # 标准化因子暴露（与组员2打分、组员3归因一致）
    fac_bp = pd.read_parquet(M2_SIG / "factor_bp.parquet").sort_index()
    fac_ep = pd.read_parquet(M2_SIG / "factor_ep.parquet").sort_index()
    fac_small = pd.read_parquet(M2_SIG / "factor_small.parquet").sort_index()
    fac_bp.index = pd.to_datetime(fac_bp.index)
    fac_ep.index = pd.to_datetime(fac_ep.index)
    fac_small.index = pd.to_datetime(fac_small.index)

    # 长面板元数据（股票名称、申万行业、原始估值/收盘价）
    panel = pd.read_parquet(
        PROC / "clean_daily_panel.parquet",
        columns=["trade_date", "stock_code", "stock_name", "sw_l1_name", "bp", "ep", "close", "amount"],
    )
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    # 最新股票名称与行业映射（取最新可用日或信号日）
    p_sig = panel[panel["trade_date"] == latest_sig].set_index("stock_code")
    name_map = (
        panel.sort_values("trade_date")
        .dropna(subset=["stock_name"])
        .groupby("stock_code")["stock_name"]
        .last()
        .to_dict()
    )
    ind_map = (
        panel.sort_values("trade_date")
        .dropna(subset=["sw_l1_name"])
        .groupby("stock_code")["sw_l1_name"]
        .last()
        .to_dict()
    )

    ow_b = pd.read_parquet(M3_RES / "open_weights_baseline.parquet").fillna(0.0)
    cw_b = pd.read_parquet(M3_RES / "weights_baseline.parquet").fillna(0.0)
    ow_b.index = pd.to_datetime(ow_b.index)
    cw_b.index = pd.to_datetime(cw_b.index)

    open_hfq = pd.read_parquet(PROC / "matrix_open_hfq.parquet").sort_index().ffill()
    close_hfq = pd.read_parquet(PROC / "matrix_close_hfq.parquet").sort_index().ffill()
    open_hfq.index = pd.to_datetime(open_hfq.index)
    close_hfq.index = pd.to_datetime(close_hfq.index)

    tr = pd.read_csv(M3_RES / "turnover.csv", index_col=0, parse_dates=True)
    nav = pd.read_csv(M3_RES / "nav.csv", index_col=0, parse_dates=True)

    # -----------------------------------------------------------------------
    # 2. 导出最新一期 50 只持仓 & 前 30 只备用版
    # -----------------------------------------------------------------------
    rows_50 = []
    for rank, (_, r) in enumerate(latest_tw.iterrows(), start=1):
        code = r["stock_code"]
        rows_50.append({
            "排名": rank,
            "股票代码": code,
            "股票名称": p_sig.loc[code, "stock_name"] if code in p_sig.index else name_map.get(code, ""),
            "申万一级行业": p_sig.loc[code, "sw_l1_name"] if code in p_sig.index else ind_map.get(code, "未分类"),
            "信号日": str(latest_sig.date()),
            "执行日": str(latest_exec.date()),
            "目标权重": float(r["target_weight"]),
            "目标权重(%)": round(float(r["target_weight"]) * 100.0, 2),
            "回测开盘实际权重(%)": round(float(ow_b.loc[latest_exec, code]) * 100.0, 4) if code in ow_b.columns else 0.0,
            "综合得分": float(r["score"]),
            "BP暴露(标准化)": float(fac_bp.loc[latest_sig, code]),
            "EP暴露(标准化)": float(fac_ep.loc[latest_sig, code]),
            "Small暴露(标准化)": float(fac_small.loc[latest_sig, code]),
            "BP原始(1/PB)": float(p_sig.loc[code, "bp"]) if code in p_sig.index else np.nan,
            "EP原始(1/PE)": float(p_sig.loc[code, "ep"]) if code in p_sig.index else np.nan,
            "信号日收盘价(元)": float(p_sig.loc[code, "close"]) if code in p_sig.index else np.nan,
        })

    df_50 = pd.DataFrame(rows_50)
    date_tag = str(latest_exec.date())
    path_50 = OUT_XQ / f"最新持仓_{date_tag}.csv"
    df_50.to_csv(path_50, index=False, encoding="utf-8-sig")

    # 前 30 只等权备用版
    df_30 = df_50.head(30).copy()
    df_30["目标权重"] = 1.0 / 30.0
    df_30["目标权重(%)"] = round(100.0 / 30.0, 4)
    path_30 = OUT_XQ / f"最新持仓_前30只备用_{date_tag}.csv"
    df_30.to_csv(path_30, index=False, encoding="utf-8-sig")

    # 前 20 只等权备用版（适配雪球部分账户 20 只持仓上限）
    df_20 = df_50.head(20).copy()
    df_20["目标权重"] = 1.0 / 20.0
    df_20["目标权重(%)"] = round(100.0 / 20.0, 4)
    path_20 = OUT_XQ / f"最新持仓_前20只备用_{date_tag}.csv"
    df_20.to_csv(path_20, index=False, encoding="utf-8-sig")

    # 最新持仓行业分布表（供画图与报告引用）
    ind_dist = (
        df_50.groupby("申万一级行业")
        .agg(
            持仓只数=("股票代码", "count"),
            权重合计=("目标权重(%)", "sum"),
            平均得分=("综合得分", "mean"),
            平均BP暴露=("BP暴露(标准化)", "mean"),
            平均EP暴露=("EP暴露(标准化)", "mean"),
        )
        .sort_values(["持仓只数", "权重合计"], ascending=False)
        .reset_index()
    )
    ind_dist.to_csv(OUT_RES / "latest_industry_distribution.csv", index=False, encoding="utf-8-sig")

    # -----------------------------------------------------------------------
    # 3. 导出近 8 期调仓记录与买卖名单（对账 turnover.csv）
    # -----------------------------------------------------------------------
    exec_dates = list(pd.to_datetime(tr.index))
    all_dates = list(pd.to_datetime(nav.index))
    date_to_idx = {d: i for i, d in enumerate(all_dates)}
    cols = ow_b.columns

    last8_dates = exec_dates[-8:]
    summary_rows = []
    detail_rows = []

    for d in last8_dates:
        sig_d = tw_base[tw_base["execution_date"] == d]["signal_date"].iloc[0]
        w_after = ow_b.loc[d, cols]
        d_prev = all_dates[date_to_idx[d] - 1]
        w_prev = cw_b.loc[d_prev, cols]
        ov = (open_hfq.loc[d, cols] / close_hfq.loc[d_prev, cols]).replace(
            [np.inf, -np.inf], np.nan
        ).fillna(1.0)
        w_unnorm = w_prev * ov
        cash_prev = max(0.0, 1.0 - float(w_prev.sum()))
        tot = float(w_unnorm.sum()) + cash_prev
        w_before = w_unnorm / tot if tot > 0 else w_prev

        dw = w_after - w_before
        tr_reconstructed = float(dw.abs().sum() / 2.0)
        tr_m3 = float(tr.loc[d, "baseline_turnover"])

        buys_new = [c for c in cols if w_before[c] <= 1e-6 and w_after[c] > 1e-6]
        sells_all = [c for c in cols if w_before[c] > 1e-6 and w_after[c] <= 1e-6]

        def fmt_names(codes):
            return "、".join([f"{name_map.get(c, c)}({c})" for c in codes]) if codes else "无"

        summary_rows.append({
            "调仓执行日": str(d.date()),
            "信号日": str(sig_d.date()),
            "单边换手率_turnover_csv(%)": round(tr_m3 * 100.0, 2),
            "重建单边换手率(%)": round(tr_reconstructed * 100.0, 2),
            "对账差值(%)": round((tr_reconstructed - tr_m3) * 100.0, 4),
            "新买入只数": len(buys_new),
            "全部卖出只数": len(sells_all),
            "新买入名单": fmt_names(buys_new),
            "全部卖出名单": fmt_names(sells_all),
            "调仓后持仓只数": int((w_after > 1e-6).sum()),
        })

        for c in cols:
            wb_c = float(w_before[c])
            wa_c = float(w_after[c])
            delta_c = wa_c - wb_c
            if abs(delta_c) <= 5e-5 and wb_c <= 1e-6 and wa_c <= 1e-6:
                continue
            if wb_c <= 1e-6 and wa_c > 1e-6:
                act = "新进买入"
            elif wb_c > 1e-6 and wa_c <= 1e-6:
                act = "清仓卖出"
            elif delta_c > 5e-4:
                act = "权重上调"
            elif delta_c < -5e-4:
                act = "权重下调"
            else:
                continue
            detail_rows.append({
                "调仓执行日": str(d.date()),
                "信号日": str(sig_d.date()),
                "股票代码": c,
                "股票名称": name_map.get(c, ""),
                "申万一级行业": ind_map.get(c, "未分类"),
                "操作类型": act,
                "调仓前权重(%)": round(wb_c * 100.0, 3),
                "调仓后权重(%)": round(wa_c * 100.0, 3),
                "权重变动(%)": round(delta_c * 100.0, 3),
            })

    df_8 = pd.DataFrame(summary_rows)
    df_8_detail = pd.DataFrame(detail_rows)
    df_8.to_csv(OUT_XQ / "近8期调仓记录.csv", index=False, encoding="utf-8-sig")
    df_8_detail.to_csv(OUT_XQ / "近8期调仓明细.csv", index=False, encoding="utf-8-sig")

    # -----------------------------------------------------------------------
    # 4. 生成雪球操作手册与日志模板 & 截图占位说明
    # -----------------------------------------------------------------------
    (OUT_SS / ".gitkeep").write_text("", encoding="utf-8")

    # 取最近一期调仓记录用于示例展示
    last_row = df_8.iloc[-1]
    manual_lines = [
        "# 雪球模拟组合操作手册与实盘跟踪日志模板",
        "",
        f"> 策略名称：**沪深300价值精选量化（Baseline）** | 数据截止：**{date_tag}**（信号日 {latest_sig.date()} → 执行日 {date_tag}）",
        "",
        "## 一、雪球组合基本信息与链接占位",
        "",
        "| 项目 | 内容 / 占位符 |",
        "|---|---|",
        "| 组合名称 | 沪深300价值精选量化（Baseline） |",
        "| 雪球组合链接 | 【待填：雪球模拟组合 URL，例如 https://xueqiu.com/P/ZHXXXXXX】 |",
        "| 创建日期 | 【待填：YYYY-MM-DD】 |",
        "| 业绩比较基准 | 沪深300指数（000300.SH） |",
        "| 持仓规范 | 50 只等权（单票目标权重 2.00%）；若平台限制持仓上限，按实测上限启用 30 只（3.33%）或 20 只（5.00%）等权备用版（需披露集中度差异） |",
        "| 调仓频率 | 每 5 个交易日（周度调仓），信号日 T 收盘后生成目标权重，T+1 开盘执行 |",
        "",
        "## 二、建组合与周度调仓标准操作流程（SOP）",
        "",
        "1. **初始建仓（T+1 开盘集合竞价 / 09:30–09:45）**：",
        f"   - 读取 `member4/xueqiu/最新持仓_{date_tag}.csv` 中的 50 只标的，按 **2.00%** 等权买入（总仓位 100%，或保留 ≤1% 现金应对撮合四舍五入）。",
        f"   - 若雪球页面对单组合持仓数量有限制（雪球 FAQ 与历史说明曾分别提及 20 只与 30 只上限），按实际账户上限切换至 `最新持仓_前30只备用_{date_tag}.csv`（单票 3.33%）或 `最新持仓_前20只备用_{date_tag}.csv`（单票 5.00%），并在报告中明确披露精简组合与 50 只原策略的权重差异。",
        "2. **定期调仓（每 5 个交易日）**：",
        "   - 组员 1 增量更新行情与财报估值快照 → 组员 2 生成最新一期 `target_weights.csv` → 运行 `python code/xueqiu_export.py` 导出最新持仓与调仓差额。",
        "   - 先卖后买：对移出前 50 名的持仓（或因停牌/涨跌停未完全成交者顺延）先执行卖出；非停牌/非一字跌停（即使已被剔除沪深300或变为 ST）按规则择机卖出。",
        "   - 权重偏移控制：对继续保留在 50 只名单内但因涨跌偏离 2.00% 的标的，仅当偏离超过阈值（如 ±0.5%）或存在新进换仓需求时做再平衡，以控制滑点。",
        "3. **运行与披露纪律**：",
        "   - 本文件所导出持仓与调仓记录仅覆盖至 **2026-10-30**，后续实盘模拟运行需补充最新交易日行情后重跑信号流水线。",
        "",
        "## 三、最新一期（2026-10-30）行业分布与前 10 大权重候选",
        "",
        "| 申万一级行业 | 持仓只数 | 目标权重合计 | 平均综合得分 | 平均 BP 暴露 | 平均 EP 暴露 |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in ind_dist.iterrows():
        manual_lines.append(
            f"| {r['申万一级行业']} | {int(r['持仓只数'])} | {r['权重合计']:.1f}% | {r['平均得分']:.3f} | {r['平均BP暴露']:.2f} | {r['平均EP暴露']:.2f} |"
        )

    manual_lines.extend([
        "",
        "前 10 名最高得分持仓预览（完整 50 只见 `最新持仓_2026-10-30.csv`）：",
        "",
        "| 排名 | 股票代码 | 股票名称 | 申万一级行业 | 目标权重 | 综合得分 | BP暴露 | EP暴露 |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for _, r in df_50.head(10).iterrows():
        manual_lines.append(
            f"| {int(r['排名'])} | {r['股票代码']} | {r['股票名称']} | {r['申万一级行业']} | {r['目标权重(%)']:.2f}% | {r['综合得分']:.3f} | {r['BP暴露(标准化)']:.2f} | {r['EP暴露(标准化)']:.2f} |"
        )

    manual_lines.extend([
        "",
        "## 四、近 8 期调仓对账摘要（与 member3/results/turnover.csv 核对）",
        "",
        "| 调仓执行日 | 信号日 | 单边换手率 | 新买入只数 | 全部卖出只数 | 新买入名单 | 全部卖出名单 |",
        "|---|---|---|---|---|---|---|",
    ])
    for _, r in df_8.iterrows():
        manual_lines.append(
            f"| {r['调仓执行日']} | {r['信号日']} | {r['单边换手率_turnover_csv(%)']:.2f}% | {int(r['新买入只数'])} | {int(r['全部卖出只数'])} | {r['新买入名单']} | {r['全部卖出名单']} |"
        )

    manual_lines.extend([
        "",
        "## 五、雪球实盘调仓日志模板（每周填写）",
        "",
        "| 期数 | 信号日 | 实际调仓日 | 计划单边换手 | 实际成交偏离/受阻情况 | 组合净值 | 沪深300净值 | 累计超额 | 记录人 | 备注 |",
        "|---|---|---|---|---|---|---|---|---|---|",
        f"| 第1期(建仓) | {latest_sig.date()} | {date_tag} | 50.00%（建仓） | 【待填：是否全额成交】 | 1.0000 | 1.0000 | 0.00% | 【待填】 | 初始50只等权建仓 |",
        "| 第2期 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 |",
        "| 第3期 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 |",
        "",
        "## 六、雪球截图占位目录与命名规范",
        "",
        "请将雪球组合截图按以下固定文件名放入 `member4/xueqiu/screenshots/`，重新运行 `build_report.py` 与 `build_deck.py` 即可自动嵌入终版报告与路演 PPT：",
        "",
        "- `member4/xueqiu/screenshots/xueqiu_portfolio_overview.png`：雪球组合主页概览（含组合名称、累计收益、调仓次数）",
        "- `member4/xueqiu/screenshots/xueqiu_holdings.png`：雪球当前持仓明细截图",
        "- `member4/xueqiu/screenshots/xueqiu_nav_curve.png`：雪球组合净值 vs 沪深300 走势对比截图",
        "",
        f"（附：最近一期调仓 {last_row['调仓执行日']} 单边换手率 {last_row['单边换手率_turnover_csv(%)']:.2f}%，新买入 {int(last_row['新买入只数'])} 只，卖出 {int(last_row['全部卖出只数'])} 只。）",
    ])

    (OUT_XQ / "雪球操作手册与日志模板.md").write_text("\n".join(manual_lines), encoding="utf-8")

    # 保存雪球摘要 JSON
    xq_summary = {
        "latest_signal_date": str(latest_sig.date()),
        "latest_execution_date": date_tag,
        "holdings_count": len(df_50),
        "fallback_top30_count": len(df_30),
        "latest_avg_score": float(df_50["综合得分"].mean()),
        "latest_avg_bp_z": float(df_50["BP暴露(标准化)"].mean()),
        "latest_avg_ep_z": float(df_50["EP暴露(标准化)"].mean()),
        "latest_avg_small_z": float(df_50["Small暴露(标准化)"].mean()),
        "industry_distribution": ind_dist.to_dict(orient="records"),
        "last8_rebalances": summary_rows,
        "last8_mean_turnover_pct": float(df_8["单边换手率_turnover_csv(%)"].mean()),
        "last8_max_turnover_diff_pct": float(df_8["对账差值(%)"].abs().max()),
        "screenshot_placeholders": [
            "member4/xueqiu/screenshots/xueqiu_portfolio_overview.png",
            "member4/xueqiu/screenshots/xueqiu_holdings.png",
            "member4/xueqiu/screenshots/xueqiu_nav_curve.png",
        ],
    }
    with open(OUT_RES / "xueqiu_summary.json", "w", encoding="utf-8") as f:
        json.dump(xq_summary, f, ensure_ascii=False, indent=2)

    print("===== 雪球导出完成 =====")
    print(f"最新持仓: {path_50.name} ({len(df_50)} 只)")
    print(f"备用持仓: {path_30.name} ({len(df_30)} 只)")
    print("行业分布:\n", ind_dist.to_string(index=False))
    print("\n近8期调仓摘要:")
    print(df_8[["调仓执行日", "单边换手率_turnover_csv(%)", "对账差值(%)", "新买入只数", "全部卖出只数"]].to_string(index=False))


if __name__ == "__main__":
    main()
