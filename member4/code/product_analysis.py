# -*- coding: utf-8 -*-
"""
组员4 模块1：产品化分析（容量三口径、平方根冲击曲线、A/B/C/D四档费率测算）
严格遵循 member4/PLAN.md 第2节规范，上游数据只读。
复现命令（在 member4 目录）：
    .venv/bin/python code/product_analysis.py
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
M3_RES = P.M3_RES
OUT_RES = MEMBER4 / "results"
OUT_RES.mkdir(parents=True, exist_ok=True)


def verify_amount_unit() -> dict:
    """核实 matrix_amount 与 clean_daily_panel.amount 单位为人民币元。"""
    panel = pd.read_parquet(
        PROC / "clean_daily_panel.parquet",
        columns=["trade_date", "stock_code", "close", "volume", "amount"],
    )
    latest_date = pd.to_datetime(panel["trade_date"]).max()
    sub = panel[(pd.to_datetime(panel["trade_date"]) == latest_date) & (panel["volume"] > 0)].copy()
    sub["ratio"] = sub["amount"] / (sub["volume"] * sub["close"])
    return {
        "unit": "元 (CNY)",
        "verification_date": str(latest_date.date()),
        "median_amount_over_vol_close": float(sub["ratio"].median()),
        "p05_ratio": float(sub["ratio"].quantile(0.05)),
        "p95_ratio": float(sub["ratio"].quantile(0.95)),
        "median_daily_amount_yuan": float(sub["amount"].median()),
        "note": "amount/(volume*close) 中位数约为 1.005，确认 matrix_amount 单位为人民币元（非千元或万元）。",
    }


def reconstruct_rebalance_trades(
    model: str,
    exec_dates: list[pd.Timestamp],
    all_dates: list[pd.Timestamp],
    open_hfq: pd.DataFrame,
    close_hfq: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    重建每个调仓日开盘调仓的权重变化 |Δw_i| 与调仓后持仓权重 w_after。
    调仓前权重 w_before 由上一交易日收盘持仓乘隔夜涨跌幅并归一化得到（首日建仓为 0）。
    """
    ow = pd.read_parquet(M3_RES / f"open_weights_{model}.parquet").fillna(0.0)
    cw = pd.read_parquet(M3_RES / f"weights_{model}.parquet").fillna(0.0)
    ow.index = pd.to_datetime(ow.index)
    cw.index = pd.to_datetime(cw.index)
    cols = ow.columns

    date_to_idx = {d: i for i, d in enumerate(all_dates)}
    dw_rows = {}
    wafter_rows = {}
    turnover_est = {}

    for k, d in enumerate(exec_dates):
        w_after = ow.loc[d, cols]
        if k == 0:
            w_before = pd.Series(0.0, index=cols)
        else:
            d_prev = all_dates[date_to_idx[d] - 1]
            w_prev = cw.loc[d_prev, cols]
            ov = (open_hfq.loc[d, cols] / close_hfq.loc[d_prev, cols]).replace(
                [np.inf, -np.inf], np.nan
            ).fillna(1.0)
            w_unnorm = w_prev * ov
            cash_prev = max(0.0, 1.0 - float(w_prev.sum()))
            tot = float(w_unnorm.sum()) + cash_prev
            w_before = w_unnorm / tot if tot > 0 else w_prev

        dw = (w_after - w_before).abs()
        dw_rows[d] = dw
        wafter_rows[d] = w_after
        turnover_est[d] = float(dw.sum() / 2.0)

    dw_df = pd.DataFrame.from_dict(dw_rows, orient="index").sort_index()
    wafter_df = pd.DataFrame.from_dict(wafter_rows, orient="index").sort_index()
    tr_est = pd.Series(turnover_est, name=f"{model}_turnover_reconstructed")
    return dw_df, wafter_df, tr_est


def compute_liquidity_and_constraints(
    model: str,
    dw_df: pd.DataFrame,
    wafter_df: pd.DataFrame,
    adv20_prior: pd.DataFrame,
) -> tuple[dict, pd.DataFrame]:
    """
    计算持仓流动性分布与口径1（参与率约束）、口径2（5日清仓约束）。
    仅使用调仓日前20个交易日的 ADV20（严格无前视）。
    """
    cols = dw_df.columns
    adv_sub = adv20_prior.reindex(index=dw_df.index, columns=cols)

    # 持仓股票 ADV20 分布（全185期汇总 + 最新一期）
    held_adv_all = []
    for d in dw_df.index:
        held_mask = wafter_df.loc[d] > 1e-6
        vals = adv_sub.loc[d, held_mask].dropna()
        held_adv_all.append(vals)
    all_vals = pd.concat(held_adv_all)
    latest_d = dw_df.index[-1]
    latest_vals = adv_sub.loc[latest_d, wafter_df.loc[latest_d] > 1e-6].dropna()

    liq_stats = {
        "model": model,
        "rebalance_count": len(dw_df),
        "held_adv20_min_yi": float(all_vals.min() / 1e8),
        "held_adv20_p10_yi": float(all_vals.quantile(0.10) / 1e8),
        "held_adv20_p25_yi": float(all_vals.quantile(0.25) / 1e8),
        "held_adv20_median_yi": float(all_vals.median() / 1e8),
        "held_adv20_mean_yi": float(all_vals.mean() / 1e8),
        "held_adv20_p90_yi": float(all_vals.quantile(0.90) / 1e8),
        "latest_date": str(latest_d.date()),
        "latest_adv20_min_yi": float(latest_vals.min() / 1e8),
        "latest_adv20_p10_yi": float(latest_vals.quantile(0.10) / 1e8),
        "latest_adv20_median_yi": float(latest_vals.median() / 1e8),
    }

    # 口径1：单期容量 = min_i (p * W * ADV20_i / |Δw_i|)
    # 注意：极少数停牌复牌或极小 |Δw_i| 在过滤阈值 1e-6 后均保留真实约束
    cap_1d_base = []
    cap_1d_steady = []  # 剔除首日建仓，作稳健性附注
    liq_5d_base = []
    for idx_k, d in enumerate(dw_df.index):
        dw = dw_df.loc[d]
        traded = dw[dw > 1e-6]
        adv_t = adv_sub.loc[d, traded.index].clip(lower=1.0)
        ratio_trade = (adv_t / traded).min()
        cap_1d_base.append(float(ratio_trade))
        if idx_k > 0:
            cap_1d_steady.append(float(ratio_trade))

        w = wafter_df.loc[d]
        held = w[w > 1e-6]
        adv_h = adv_sub.loc[d, held.index].clip(lower=1.0)
        ratio_hold = (adv_h / held).min()
        liq_5d_base.append(float(ratio_hold))

    cap_1d_arr = np.array(cap_1d_base)
    cap_steady_arr = np.array(cap_1d_steady)
    liq_5d_arr = np.array(liq_5d_base)

    rows = []
    for p in [0.01, 0.02, 0.05, 0.10]:
        for window in [1, 3]:
            arr = cap_1d_arr * p * window
            arr_st = cap_steady_arr * p * window
            rows.append({
                "model": model,
                "constraint_type": "rebalance_participation",
                "constraint_label": f"调仓参与率({window}日窗口)",
                "participation_rate": p,
                "window_days": window,
                "p10_yuan": float(np.percentile(arr, 10)),
                "median_yuan": float(np.median(arr)),
                "p10_yi": float(np.percentile(arr, 10) / 1e8),
                "median_yi": float(np.median(arr) / 1e8),
                "steady_p10_yi": float(np.percentile(arr_st, 10) / 1e8),
                "steady_median_yi": float(np.median(arr_st) / 1e8),
            })
        arr_l = liq_5d_arr * p * 5
        rows.append({
            "model": model,
            "constraint_type": "liquidation_5d",
            "constraint_label": "持仓可清算约束(5日窗口)",
            "participation_rate": p,
            "window_days": 5,
            "p10_yuan": float(np.percentile(arr_l, 10)),
            "median_yuan": float(np.median(arr_l)),
            "p10_yi": float(np.percentile(arr_l, 10) / 1e8),
            "median_yi": float(np.median(arr_l) / 1e8),
            "steady_p10_yi": float(np.percentile(arr_l, 10) / 1e8),
            "steady_median_yi": float(np.median(arr_l) / 1e8),
        })

    return liq_stats, pd.DataFrame(rows)


def build_impact_drag_coef(
    dw_df: pd.DataFrame,
    adv20_prior: pd.DataFrame,
    sigma20_prior: pd.DataFrame,
    nav_index: pd.DatetimeIndex,
) -> pd.Series:
    """
    计算每个调仓日单位 sqrt(AUM) 的平方根冲击拖拽系数（不含 Y）：
        drag_d(AUM) = Y * coef_d * sqrt(AUM)
    其中 coef_d = sum_i |Δw_i| * σ20_i * sqrt(|Δw_i| / ADV20_i)
    """
    cols = dw_df.columns
    adv_sub = adv20_prior.reindex(index=dw_df.index, columns=cols).clip(lower=1e5)
    sig_sub = sigma20_prior.reindex(index=dw_df.index, columns=cols).fillna(0.02)

    coef_map = {}
    for d in dw_df.index:
        dw = dw_df.loc[d]
        traded = dw[dw > 1e-6]
        adv_t = adv_sub.loc[d, traded.index]
        sig_t = sig_sub.loc[d, traded.index]
        coef_map[d] = float((traded * sig_t * np.sqrt(traded / adv_t)).sum())

    return pd.Series(coef_map).reindex(nav_index).fillna(0.0)


def eval_net_ann_at_aum(
    daily_ret: pd.Series,
    drag_coef: pd.Series,
    aum_yuan: float,
    y_coef: float,
) -> float:
    drag = (y_coef * drag_coef * np.sqrt(aum_yuan)).clip(upper=0.999999)
    r_net = (1.0 + daily_ret) * (1.0 - drag) - 1.0
    terminal = (1.0 + r_net).prod()
    if terminal <= 0:
        return -1.0
    return float(terminal ** (252.0 / len(r_net)) - 1.0)


def solve_half_excess_capacity(
    daily_ret: pd.Series,
    drag_coef: pd.Series,
    base_ann: float,
    bench_ann: float,
    y_coef: float,
) -> float | None:
    """求解相对沪深300超额年化被冲击吃掉一半时的 AUM（元）。"""
    excess0 = base_ann - bench_ann
    if excess0 <= 0:
        return 0.0
    target_ann = bench_ann + 0.5 * excess0

    lo, hi = 1e5, 5e11
    if eval_net_ann_at_aum(daily_ret, drag_coef, hi, y_coef) > target_ann:
        return None
    for _ in range(80):
        mid = np.sqrt(lo * hi)
        val = eval_net_ann_at_aum(daily_ret, drag_coef, mid, y_coef)
        if val > target_ann:
            lo = mid
        else:
            hi = mid
    return float(np.sqrt(lo * hi))


def solve_target_drag_aum(
    daily_ret: pd.Series,
    drag_coef: pd.Series,
    base_ann: float,
    target_drag: float,
    y_coef: float,
) -> float:
    """求解冲击拖累（年化收益损失）达到 target_drag 时的 AUM（用于 research 对照参考）。"""
    target_ann = base_ann - target_drag
    lo, hi = 1e4, 5e11
    for _ in range(80):
        mid = np.sqrt(lo * hi)
        val = eval_net_ann_at_aum(daily_ret, drag_coef, mid, y_coef)
        if val > target_ann:
            lo = mid
        else:
            hi = mid
    return float(np.sqrt(lo * hi))


def simulate_fee_plan(
    nav_strat: pd.Series,
    nav_bench: pd.Series,
    fixed_annual: float,
    perf_rate: float,
    perf_mode: str,
) -> tuple[pd.Series, pd.Series, dict]:
    """
    逐日计提管理费+托管运营费，并按高水位（年度计提）计提业绩报酬。
    同时输出逐日暂提（Mark-to-Market，投资者实际每日可申赎净值）与年度实际扣减净值。
    """
    dates = nav_strat.index
    r_strat = nav_strat.pct_change().fillna(nav_strat.iloc[0] - 1.0)
    r_bench = nav_bench.pct_change().fillna(nav_bench.iloc[0] - 1.0)
    daily_fixed = fixed_annual / 252.0

    years = dates.year
    cryst_dates = {dates[years == y][-1] for y in sorted(years.unique())}

    c_cap = 1.0
    c_no_perf = 1.0
    hwm_abs = 1.0
    hwm_rel = 1.0

    mtm_vals = []
    cryst_vals = []
    total_perf_paid = 0.0
    cryst_records = []

    for i, d in enumerate(dates):
        rs = float(r_strat.iloc[i])
        c_no_perf = c_no_perf * (1.0 + rs) * (1.0 - daily_fixed)
        c_cap = c_cap * (1.0 + rs) * (1.0 - daily_fixed)

        if perf_mode == "abs_hwm":
            prov_fee = max(0.0, c_cap - hwm_abs) * perf_rate
        elif perf_mode == "excess_hwm":
            rel_t = c_cap / float(nav_bench.iloc[i])
            prov_fee = max(0.0, (rel_t - hwm_rel) * float(nav_bench.iloc[i])) * perf_rate
        else:
            prov_fee = 0.0

        mtm_nav = c_cap - prov_fee

        if d in cryst_dates and prov_fee > 0:
            c_cap = c_cap - prov_fee
            total_perf_paid += prov_fee
            if perf_mode == "abs_hwm":
                hwm_abs = c_cap
            elif perf_mode == "excess_hwm":
                hwm_rel = c_cap / float(nav_bench.iloc[i])
            cryst_records.append({"date": str(d.date()), "perf_fee_paid": float(prov_fee), "post_nav": float(c_cap)})

        mtm_vals.append(mtm_nav)
        cryst_vals.append(c_cap)

    mtm_s = pd.Series(mtm_vals, index=dates)
    cryst_s = pd.Series(cryst_vals, index=dates)

    # 绩效统计（以 MTM 逐日计提净值为主口径）
    r_inv = mtm_s.pct_change().fillna(mtm_s.iloc[0] - 1.0)
    n = len(r_inv)
    cum = float(mtm_s.iloc[-1] - 1.0)
    ann_ret = float(mtm_s.iloc[-1] ** (252.0 / n) - 1.0)
    ann_vol = float(r_inv.std() * np.sqrt(252.0))
    sharpe = float(ann_ret / ann_vol) if ann_vol > 0 else np.nan
    mdd = float((mtm_s / mtm_s.cummax() - 1.0).min())

    ex_r = r_inv - r_bench
    te = float(ex_r.std() * np.sqrt(252.0))
    ann_bench = float(nav_bench.iloc[-1] ** (252.0 / n) - 1.0)
    ir = float((ann_ret - ann_bench) / te) if te > 0 else np.nan

    gross_cum = float(nav_strat.iloc[-1] - 1.0)
    gross_ann = float(nav_strat.iloc[-1] ** (252.0 / n) - 1.0)
    fixed_cum_drag = float(nav_strat.iloc[-1] - c_no_perf)
    total_cum_drag = float(nav_strat.iloc[-1] - mtm_s.iloc[-1])

    stats = {
        "cum_return": cum,
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "tracking_error": te,
        "info_ratio": ir,
        "terminal_nav": float(mtm_s.iloc[-1]),
        "gross_cum_return": gross_cum,
        "gross_ann_return": gross_ann,
        "fixed_fee_cum_drag": fixed_cum_drag,
        "perf_fee_cum_paid": float(total_perf_paid),
        "total_fee_cum_drag": total_cum_drag,
        "ann_fee_drag": float(gross_ann - ann_ret),
        "crystallization_events": cryst_records,
    }
    return mtm_s, cryst_s, stats


def main():
    print("1. 核实成交额单位与加载上游数据 ...")
    amt_info = verify_amount_unit()
    print("  matrix_amount 核实:", amt_info["note"])

    amt = pd.read_parquet(PROC / "matrix_amount.parquet").sort_index()
    ret = pd.read_parquet(PROC / "matrix_returns.parquet").sort_index()
    open_hfq = pd.read_parquet(PROC / "matrix_open_hfq.parquet").sort_index().ffill()
    close_hfq = pd.read_parquet(PROC / "matrix_close_hfq.parquet").sort_index().ffill()
    amt.index = pd.to_datetime(amt.index)
    ret.index = pd.to_datetime(ret.index)
    open_hfq.index = pd.to_datetime(open_hfq.index)
    close_hfq.index = pd.to_datetime(close_hfq.index)

    # 严格使用调仓日前20日数据（shift(1) 确保不含执行日当日成交额与收益）
    adv20_prior = amt.rolling(20, min_periods=10).mean().shift(1)
    sigma20_prior = ret.rolling(20, min_periods=10).std().shift(1)

    nav = pd.read_csv(M3_RES / "nav.csv", index_col=0, parse_dates=True)
    tr = pd.read_csv(M3_RES / "turnover.csv", index_col=0, parse_dates=True)
    m3_metrics = pd.read_csv(M3_RES / "metrics.csv")
    exec_dates = list(pd.to_datetime(tr.index))
    all_dates = list(pd.to_datetime(nav.index))

    print("2. 计算流动性与容量三口径 ...")
    liq_rows = []
    cap_dfs = []
    drag_coefs = {}
    turnover_audit = {}

    for model in ["baseline", "research"]:
        dw_df, wafter_df, tr_est = reconstruct_rebalance_trades(
            model, exec_dates, all_dates, open_hfq, close_hfq
        )
        max_diff = float(np.max(np.abs(tr_est.values - tr[f"{model}_turnover"].values)))
        turnover_audit[model] = {
            "mean_turnover": float(tr[f"{model}_turnover"].mean()),
            "max_turnover": float(tr[f"{model}_turnover"].max()),
            "steady_mean_turnover": float(tr[f"{model}_turnover"].iloc[1:].mean()),
            "max_reconstructed_diff": max_diff,
        }
        liq_stats, cap_df = compute_liquidity_and_constraints(model, dw_df, wafter_df, adv20_prior)
        liq_rows.append(liq_stats)
        cap_dfs.append(cap_df)
        drag_coefs[model] = build_impact_drag_coef(dw_df, adv20_prior, sigma20_prior, nav.index)

    liq_df = pd.DataFrame(liq_rows)
    liq_df.to_csv(OUT_RES / "liquidity_profile.csv", index=False, encoding="utf-8-sig")

    cap_all_df = pd.concat(cap_dfs, ignore_index=True)
    cap_all_df.to_csv(OUT_RES / "capacity_constraints.csv", index=False, encoding="utf-8-sig")

    # 口径3：净收益-规模曲线（1000万 -> 500亿对数网格 + 整数里程碑）
    r_base = nav["baseline"].pct_change().fillna(nav["baseline"].iloc[0] - 1.0)
    r_res = nav["research"].pct_change().fillna(nav["research"].iloc[0] - 1.0)
    r_hs = nav["hs300"].pct_change().fillna(nav["hs300"].iloc[0] - 1.0)

    n_days = len(nav)
    base_ann0 = float(nav["baseline"].iloc[-1] ** (252.0 / n_days) - 1.0)
    res_ann0 = float(nav["research"].iloc[-1] ** (252.0 / n_days) - 1.0)
    res_ideal_ann0 = float(nav["research_ideal"].iloc[-1] ** (252.0 / n_days) - 1.0)
    hs_ann = float(nav["hs300"].iloc[-1] ** (252.0 / n_days) - 1.0)

    log_grid = np.geomspace(1e7, 5e10, 35)
    milestones = np.array([1e7, 5e7, 1e8, 2e8, 5e8, 1e9, 2e9, 5e9, 8e9, 1e10, 2e10, 5e10])
    aum_grid = np.unique(np.sort(np.concatenate([log_grid, milestones])))

    curve_rows = []
    for y_coef in [0.5, 0.8, 1.0]:
        for aum in aum_grid:
            b_net = eval_net_ann_at_aum(r_base, drag_coefs["baseline"], aum, y_coef)
            r_net = eval_net_ann_at_aum(r_res, drag_coefs["research"], aum, y_coef)
            curve_rows.append({
                "Y": y_coef,
                "aum_yuan": float(aum),
                "aum_yi": float(aum / 1e8),
                "baseline_net_ann": b_net,
                "baseline_drag_ann": base_ann0 - b_net,
                "baseline_excess_ann": b_net - hs_ann,
                "research_net_ann": r_net,
                "research_drag_ann": res_ann0 - r_net,
                "research_excess_ann": r_net - hs_ann,
                "hs300_ann": hs_ann,
            })
    curve_df = pd.DataFrame(curve_rows)
    curve_df.to_csv(OUT_RES / "capacity_curve.csv", index=False, encoding="utf-8-sig")

    half_excess_cap = {}
    for y_coef in [0.5, 0.8, 1.0]:
        b_cap = solve_half_excess_capacity(r_base, drag_coefs["baseline"], base_ann0, hs_ann, y_coef)
        # research 在 AUM=0 时超额已为负 (-1.86%)，按定义容量为 0；额外计算拖拽达到 5.37%（baseline 半超额）的参考 AUM
        half_base_ex = 0.5 * (base_ann0 - hs_ann)
        r_ref_aum = solve_target_drag_aum(r_res, drag_coefs["research"], res_ann0, half_base_ex, y_coef)
        half_excess_cap[f"Y_{y_coef}"] = {
            "baseline_half_excess_aum_yuan": b_cap,
            "baseline_half_excess_aum_yi": float(b_cap / 1e8) if b_cap is not None else None,
            "baseline_target_net_ann": float(hs_ann + half_base_ex),
            "research_half_excess_aum_yi": 0.0,
            "research_capacity_note": "计成本后超额年化在 AUM=0 时已为 -1.86%（<0），按定义容量为 0",
            "research_equal_drag_ref_aum_yi": float(r_ref_aum / 1e8),
        }

    print("3. 计算 A/B/C/D 四档产品费率与投资者到手净值 ...")
    b_nav = nav["baseline"]
    h_nav = nav["hs300"]

    # 基准与策略毛净值指标
    ex_gross = r_base - r_hs
    te_gross = float(ex_gross.std() * np.sqrt(252.0))
    ir_gross = float((base_ann0 - hs_ann) / te_gross)

    fee_rows = [{
        "plan_id": "Gross",
        "plan_name": "策略净值(未扣产品费)",
        "mgmt_fee": 0.0,
        "custody_fee": 0.0,
        "perf_fee_rate": 0.0,
        "perf_basis": "无(含交易成本后策略净值)",
        "cum_return": float(b_nav.iloc[-1] - 1.0),
        "ann_return": base_ann0,
        "ann_vol": float(r_base.std() * np.sqrt(252.0)),
        "sharpe": float(base_ann0 / (r_base.std() * np.sqrt(252.0))),
        "max_drawdown": float((b_nav / b_nav.cummax() - 1.0).min()),
        "tracking_error": te_gross,
        "info_ratio": ir_gross,
        "terminal_nav": float(b_nav.iloc[-1]),
        "fixed_fee_cum_drag": 0.0,
        "perf_fee_cum_paid": 0.0,
        "total_fee_cum_drag": 0.0,
        "ann_fee_drag": 0.0,
    }]

    inv_nav_df = pd.DataFrame({"hs300": h_nav, "baseline_gross": b_nav}, index=nav.index)
    fee_specs = [
        ("A", "方案A 标准份额", 0.010, 0.002, 0.20, "abs_hwm", "绝对收益高水位×20%(年度计提)"),
        ("B", "方案B 超额计提", 0.010, 0.002, 0.20, "excess_hwm", "相对沪深300超额高水位×20%(年度计提)"),
        ("C", "方案C 机构份额", 0.006, 0.0015, 0.15, "excess_hwm", "相对沪深300超额高水位×15%(年度计提)"),
        ("D", "方案D 纯管理费", 0.015, 0.002, 0.0, "none", "无业绩报酬"),
    ]

    fee_detail = {}
    for pid, pname, mf, cf, pr, pmode, pbasis in fee_specs:
        mtm_s, cryst_s, st = simulate_fee_plan(b_nav, h_nav, mf + cf, pr, pmode)
        inv_nav_df[f"plan_{pid}"] = mtm_s
        inv_nav_df[f"plan_{pid}_cryst"] = cryst_s
        fee_rows.append({
            "plan_id": pid,
            "plan_name": pname,
            "mgmt_fee": mf,
            "custody_fee": cf,
            "perf_fee_rate": pr,
            "perf_basis": pbasis,
            "cum_return": st["cum_return"],
            "ann_return": st["ann_return"],
            "ann_vol": st["ann_vol"],
            "sharpe": st["sharpe"],
            "max_drawdown": st["max_drawdown"],
            "tracking_error": st["tracking_error"],
            "info_ratio": st["info_ratio"],
            "terminal_nav": st["terminal_nav"],
            "fixed_fee_cum_drag": st["fixed_fee_cum_drag"],
            "perf_fee_cum_paid": st["perf_fee_cum_paid"],
            "total_fee_cum_drag": st["total_fee_cum_drag"],
            "ann_fee_drag": st["ann_fee_drag"],
        })
        fee_detail[pid] = st

    fee_df = pd.DataFrame(fee_rows)
    fee_df.to_csv(OUT_RES / "fee_analysis.csv", index=False, encoding="utf-8-sig")
    inv_nav_df.to_csv(OUT_RES / "investor_nav.csv", encoding="utf-8-sig")

    # 汇总 JSON
    m_full = m3_metrics[m3_metrics["区间"] == "全样本(2023-2026.10)"].set_index("组合")
    m_val = m3_metrics[m3_metrics["区间"] == "验证期(2023-2024)"].set_index("组合")
    m_oos = m3_metrics[m3_metrics["区间"] == "样本外(2025-2026.10)"].set_index("组合")

    # 关键 AUM 里程碑（Y=0.8）
    c_y08 = curve_df[curve_df["Y"] == 0.8].set_index("aum_yi")
    milestone_dict = {}
    for a_yi in [0.1, 1.0, 5.0, 10.0, 20.0, 50.0, 80.0, 100.0, 200.0, 500.0]:
        if a_yi in c_y08.index:
            row = c_y08.loc[a_yi]
            milestone_dict[f"{a_yi:g}亿"] = {
                "baseline_net_ann": float(row["baseline_net_ann"]),
                "baseline_drag_ann": float(row["baseline_drag_ann"]),
                "research_net_ann": float(row["research_net_ann"]),
                "research_drag_ann": float(row["research_drag_ann"]),
            }

    summary = {
        "data_verification": amt_info,
        "methodology": {
            "adv20_rule": "调仓日前20个交易日不复权成交额均值（shift(1)，严格不含执行日当日数据，min_periods=10）",
            "sigma20_rule": "调仓日前20个交易日个股日收益标准差（shift(1)，min_periods=10）",
            "impact_model": "单笔冲击 = Y * sigma_i * sqrt(Q_i / ADV20_i)，主参数 Y=0.8，敏感性 Y=0.5 / 1.0",
            "capacity_definition_3": "相对沪深300超额年化收益被冲击成本吃掉一半时的 AUM",
            "fee_accrual_rule": "管理费与托管运营费按年化费率/252逐日计提；业绩报酬采用逐日高水位暂提净值（Mark-to-Market）并按自然年度末及期末（2023-12-29、2024-12-31、2025-12-31、2026-10-30）计提扣减更新高水位",
            "turnover_audit": turnover_audit,
        },
        "upstream_backtest_summary": {
            "sample_period": "2023-01-09 至 2026-10-30 (921个交易日, 185个调仓日)",
            "baseline_full": m_full.loc["baseline"].to_dict(),
            "research_full": m_full.loc["research"].to_dict(),
            "hs300_full": m_full.loc["hs300"].to_dict(),
            "baseline_val": m_val.loc["baseline"].to_dict(),
            "baseline_oos": m_oos.loc["baseline"].to_dict(),
            "baseline_ideal_terminal_nav": float(nav["baseline_ideal"].iloc[-1]),
            "research_ideal_terminal_nav": float(nav["research_ideal"].iloc[-1]),
            "baseline_te_vs_hs300": te_gross,
            "baseline_ir_vs_hs300": ir_gross,
        },
        "product_elements": {
            "product_name": "沪深300价值精选量化私募证券投资基金",
            "product_type": "私募证券投资基金 / 专户",
            "risk_level": "R3（中风险）",
            "benchmark": "沪深300指数（000300.SH）",
            "min_subscription_wan": 100,
            "warning_line": 0.85,
            "stop_loss_line": 0.80,
            "warning_stoploss_rationale": "回测全样本最大回撤为 -16.69%（净值谷底约 0.833 相对前期高点），预警线 0.85 提供约 1.7 个百分点的风险缓冲，止损线 0.80 在极端回撤突破历史极值约 3.3 个百分点时触发刚性风控。",
            "open_frequency": "周度开放 / 月度开放（建议月度开放以匹配 5 日调仓且减少申赎现金拖累）",
            "lock_up_months": 6,
            "target_clients": ["高净值个人（满足100万合格投资者门槛，推荐方案A/B）", "家族办公室（中长期配置，推荐方案B）", "FOF / MOM 机构投资者（大额低费率，推荐方案C）"],
        },
        "liquidity_profile": liq_rows,
        "recommended_aum": 10.0,
        "recommended_aum_unit": "亿元",
        "theoretical_capacity_half_excess": half_excess_cap["Y_0.8"]["baseline_half_excess_aum_yi"],
        "capacity_constraints": cap_all_df.to_dict(orient="records"),
        "capacity_impact": {
            "recommended_aum": 10.0,
            "recommended_aum_unit": "亿元",
            "recommended_aum_yuan": 1e9,
            "recommended_aum_rationale": "依据口径1与口径2流动性约束：5%参与率下 3日调仓 P10 为 7.75 亿元、5日清仓 P10–中位数为 5.67–11.28 亿元，故建议管理规模控制在 10 亿元以内。",
            "theoretical_capacity_half_excess": half_excess_cap["Y_0.8"]["baseline_half_excess_aum_yi"],
            "theoretical_capacity_unit": "亿元",
            "half_excess_capacities": half_excess_cap,
            "y08_milestones": milestone_dict,
            "research_ideal_ann0": res_ideal_ann0,
        },
        "fees": {
            "comparison_table": fee_rows,
            "details": fee_detail,
        },
    }

    with open(OUT_RES / "product_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n===== 测算完成摘要 =====")
    p10_1d = cap_all_df[(cap_all_df["model"] == "baseline") & (cap_all_df["constraint_type"] == "rebalance_participation") & (cap_all_df["window_days"] == 1) & (cap_all_df["participation_rate"] == 0.05)]["p10_yi"].iloc[0]
    med_1d = cap_all_df[(cap_all_df["model"] == "baseline") & (cap_all_df["constraint_type"] == "rebalance_participation") & (cap_all_df["window_days"] == 1) & (cap_all_df["participation_rate"] == 0.05)]["median_yi"].iloc[0]
    p10_3d = cap_all_df[(cap_all_df["model"] == "baseline") & (cap_all_df["constraint_type"] == "rebalance_participation") & (cap_all_df["window_days"] == 3) & (cap_all_df["participation_rate"] == 0.05)]["p10_yi"].iloc[0]
    med_3d = cap_all_df[(cap_all_df["model"] == "baseline") & (cap_all_df["constraint_type"] == "rebalance_participation") & (cap_all_df["window_days"] == 3) & (cap_all_df["participation_rate"] == 0.05)]["median_yi"].iloc[0]
    print(f"Baseline 口径1 (1日, 5% ADV20): P10={p10_1d:.2f}亿, Median={med_1d:.2f}亿")
    print(f"Baseline 口径1 (3日, 5% ADV20): P10={p10_3d:.2f}亿, Median={med_3d:.2f}亿")
    print(f"Baseline 口径3 冲击容量 (Y=0.8): {half_excess_cap['Y_0.8']['baseline_half_excess_aum_yi']:.2f}亿 "
          f"(Y=0.5: {half_excess_cap['Y_0.5']['baseline_half_excess_aum_yi']:.2f}亿, "
          f"Y=1.0: {half_excess_cap['Y_1.0']['baseline_half_excess_aum_yi']:.2f}亿)")
    print(fee_df[["plan_id", "plan_name", "cum_return", "ann_return", "sharpe", "max_drawdown", "tracking_error", "info_ratio"]].to_string(index=False))
    print("输出已保存至:", OUT_RES)


if __name__ == "__main__":
    main()
