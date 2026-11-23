# -*- coding: utf-8 -*-
"""
组员4 PRD 接口 4（v3.0 契约版）：产品化评估（四档 HWM 费率、ADV20 流动性、参与率硬约束与平方根冲击容量）
严格读取 PRD 接口 1（数据 3.0）与接口 3（member3_v3/results/），零硬编码，不覆盖旧 v2 文件。

用法示例（待组员 3 交付 member3_v3 后一键执行）：
    .venv/bin/python code/product_analysis_v3.py --model M1 --fee-scenario net_10bp
    .venv/bin/python code/product_analysis_v3.py --check-contract
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

import paths as P
from product_analysis import (
    build_impact_drag_coef,
    compute_liquidity_and_constraints,
    eval_net_ann_at_aum,
    simulate_fee_plan,
    solve_half_excess_capacity,
)

REQUIRED_M3_V3_FILES = [
    "daily_nav_v3.csv",
    "metrics_v3.csv",
    "turnover_v3.csv",
    "industry_exposure_v3.csv",
    "decomp_v3.csv",
]


def calc_dual_sharpe(ret: pd.Series) -> tuple[float, float, float, float]:
    n = len(ret)
    wealth = (1.0 + ret).cumprod()
    ann_geom = float(wealth.iloc[-1] ** (252.0 / n) - 1.0)
    ann_vol = float(ret.std(ddof=1) * np.sqrt(252.0))
    sharpe_arith_rf0 = float((ret.mean() / ret.std(ddof=1)) * np.sqrt(252.0)) if ret.std(ddof=1) > 0 else 0.0
    geom_over_vol = float(ann_geom / ann_vol) if ann_vol > 0 else 0.0
    return ann_geom, ann_vol, sharpe_arith_rf0, geom_over_vol


def check_contract(proc_dir: Path, m3_v3_res: Path) -> dict:
    status = {
        "data_v3_dir": str(proc_dir),
        "data_v3_exists": proc_dir.exists(),
        "m3_v3_dir": str(m3_v3_res),
        "m3_v3_exists": m3_v3_res.exists(),
        "missing_m3_v3_files": [f for f in REQUIRED_M3_V3_FILES if not (m3_v3_res / f).exists()],
        "open_weights_files": sorted(p.name for p in m3_v3_res.glob("open_weights_*.parquet")) if m3_v3_res.exists() else [],
    }
    status["ready_for_step5"] = (
        status["data_v3_exists"]
        and status["m3_v3_exists"]
        and len(status["missing_m3_v3_files"]) == 0
        and len(status["open_weights_files"]) > 0
    )
    return status


def reconstruct_trades_from_open_weights(
    ow: pd.DataFrame,
    exec_dates: list[pd.Timestamp],
    all_dates: list[pd.Timestamp],
    open_hfq: pd.DataFrame,
    close_hfq: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    仅依赖 PRD 接口 3 的 open_weights_{model}.parquet（结合量价漂移），重建调仓日 |Δw_i| 与 w_after。
    若存在收盘权重文件 weights_{model}.parquet 则直接复用；否则按日内收益率从上一调仓日漂移推算。
    """
    ow = ow.fillna(0.0).sort_index()
    ow.index = pd.to_datetime(ow.index)
    cols = ow.columns
    date_to_idx = {d: i for i, d in enumerate(all_dates)}

    dw_rows = {}
    wafter_rows = {}
    w_prev_close = pd.Series(0.0, index=cols)

    for k, d in enumerate(exec_dates):
        w_after = ow.loc[d, cols]
        if k == 0:
            w_before = pd.Series(0.0, index=cols)
        else:
            d_prev_exec = exec_dates[k - 1]
            # 从上期开盘持仓漂移到本期开盘前权重
            w_start = ow.loc[d_prev_exec, cols]
            ratio = (open_hfq.loc[d, cols] / open_hfq.loc[d_prev_exec, cols]).replace(
                [np.inf, -np.inf], np.nan
            ).fillna(1.0)
            w_unnorm = w_start * ratio
            cash_start = max(0.0, 1.0 - float(w_start.sum()))
            tot = float(w_unnorm.sum()) + cash_start
            w_before = w_unnorm / tot if tot > 0 else w_start
        dw_rows[d] = (w_after - w_before).abs()
        wafter_rows[d] = w_after
        _ = (w_prev_close, date_to_idx)

    dw_df = pd.DataFrame.from_dict(dw_rows, orient="index").sort_index()
    wafter_df = pd.DataFrame.from_dict(wafter_rows, orient="index").sort_index()
    return dw_df, wafter_df


def run_v3(proc_dir: Path, m3_v3_res: Path, model: str, fee_scenario: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    nav_df = pd.read_csv(m3_v3_res / "daily_nav_v3.csv", parse_dates=["date"]).set_index("date").sort_index()
    metrics_df = pd.read_csv(m3_v3_res / "metrics_v3.csv")
    turn_df = pd.read_csv(m3_v3_res / "turnover_v3.csv", parse_dates=["execution_date"])
    ow = pd.read_parquet(m3_v3_res / f"open_weights_{model}.parquet")

    nav_col = f"{model}_{fee_scenario}"
    if nav_col not in nav_df.columns:
        raise KeyError(f"Column {nav_col} not found in daily_nav_v3.csv: {list(nav_df.columns)}")
    if "hs300_intraday" not in nav_df.columns:
        raise KeyError("Column hs300_intraday not found in daily_nav_v3.csv")

    s_nav = nav_df[nav_col]
    h_nav = nav_df["hs300_intraday"]
    s_ret = s_nav.pct_change()
    s_ret.iloc[0] = s_nav.iloc[0] - 1.0
    h_ret = h_nav.pct_change()
    h_ret.iloc[0] = h_nav.iloc[0] - 1.0

    amt = pd.read_parquet(proc_dir / "matrix_amount.parquet").sort_index()
    ret = pd.read_parquet(proc_dir / "matrix_returns.parquet").sort_index()
    open_hfq = pd.read_parquet(proc_dir / "matrix_open_hfq.parquet").sort_index().ffill()
    close_hfq = pd.read_parquet(proc_dir / "matrix_close_hfq.parquet").sort_index().ffill()
    for df in (amt, ret, open_hfq, close_hfq):
        df.index = pd.to_datetime(df.index)

    adv20_prior = amt.rolling(20, min_periods=10).mean().shift(1)
    sigma20_prior = ret.rolling(20, min_periods=10).std(ddof=1).shift(1)

    tr_sub = turn_df[(turn_df["model"] == model) & (turn_df["fee_scenario"] == fee_scenario)].sort_values("execution_date")
    exec_dates = list(pd.to_datetime(tr_sub["execution_date"]))
    all_dates = list(nav_df.index)

    dw_df, wafter_df = reconstruct_trades_from_open_weights(ow, exec_dates, all_dates, open_hfq, close_hfq)
    liq_stats, cap_df = compute_liquidity_and_constraints(model, dw_df, wafter_df, adv20_prior)
    drag_coef = build_impact_drag_coef(dw_df, adv20_prior, sigma20_prior, nav_df.index)

    s_ann0, s_vol0, s_sharpe_arith, s_geom_vol = calc_dual_sharpe(s_ret)
    h_ann0, h_vol0, h_sharpe_arith, h_geom_vol = calc_dual_sharpe(h_ret)

    half_caps = {}
    for y in [0.5, 0.8, 1.0]:
        cap_yuan = solve_half_excess_capacity(s_ret, drag_coef, s_ann0, h_ann0, y)
        half_caps[f"Y_{y}"] = {
            "half_excess_aum_yuan": cap_yuan,
            "half_excess_aum_yi": float(cap_yuan / 1e8) if cap_yuan is not None else None,
        }

    fee_specs = [
        ("A", "方案A 标准份额", 0.010, 0.002, 0.20, "abs_hwm", "绝对收益高水位×20%(年度计提)"),
        ("B", "方案B 超额计提", 0.010, 0.002, 0.20, "excess_hwm", "相对沪深300超额高水位×20%(年度计提)"),
        ("C", "方案C 机构份额", 0.006, 0.0015, 0.15, "excess_hwm", "相对沪深300超额高水位×15%(年度计提)"),
        ("D", "方案D 纯管理费", 0.015, 0.002, 0.0, "none", "无业绩报酬"),
    ]
    fee_rows = []
    fee_details = {}
    inv_nav = pd.DataFrame({"hs300_intraday": h_nav, f"{model}_strategy": s_nav}, index=nav_df.index)
    for pid, pname, mf, cf, pr, pmode, pbasis in fee_specs:
        mtm_s, cryst_s, st = simulate_fee_plan(s_nav, h_nav, mf + cf, pr, pmode)
        r_mtm = mtm_s.pct_change()
        r_mtm.iloc[0] = mtm_s.iloc[0] - 1.0
        _, _, sh_arith, g_vol = calc_dual_sharpe(r_mtm)
        st["sharpe_arith_rf0"] = sh_arith
        st["geom_over_vol"] = g_vol
        inv_nav[f"plan_{pid}"] = mtm_s
        inv_nav[f"plan_{pid}_cryst"] = cryst_s
        fee_rows.append({"plan_id": pid, "plan_name": pname, "mgmt_fee": mf, "custody_fee": cf, "perf_fee_rate": pr, "perf_basis": pbasis, **st})
        fee_details[pid] = st

    cap_df.to_csv(out_dir / "capacity_constraints_v3.csv", index=False, encoding="utf-8")
    pd.DataFrame(fee_rows).drop(columns=["crystallization_events"]).to_csv(out_dir / "fee_analysis_v3.csv", index=False, encoding="utf-8")
    inv_nav.to_csv(out_dir / "investor_nav_v3.csv", encoding="utf-8")

    summary = {
        "model": model,
        "fee_scenario": fee_scenario,
        "strategy_metrics_all": {
            "cum_return": float(s_nav.iloc[-1] - 1.0),
            "ann_geom": s_ann0,
            "ann_vol": s_vol0,
            "sharpe_arith_rf0": s_sharpe_arith,
            "geom_over_vol": s_geom_vol,
        },
        "hs300_intraday_all": {
            "terminal_nav": float(h_nav.iloc[-1]),
            "cum_return": float(h_nav.iloc[-1] - 1.0),
            "ann_geom": h_ann0,
            "ann_vol": h_vol0,
            "sharpe_arith_rf0": h_sharpe_arith,
            "geom_over_vol": h_geom_vol,
        },
        "upstream_metrics_v3": metrics_df[metrics_df["model"] == model].to_dict(orient="records"),
        "liquidity_profile": liq_stats,
        "half_excess_capacities": half_caps,
        "capacity_constraints": cap_df.to_dict(orient="records"),
        "fees": fee_details,
    }
    (out_dir / "product_summary_v3.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已完成 v3 产品化测算 -> {out_dir / 'product_summary_v3.json'}")


def main():
    parser = argparse.ArgumentParser(description="组员4 PRD v3.0 产品化分析入口")
    parser.add_argument("--data", type=Path, default=None, help="数据 3.0 processed/ 目录")
    parser.add_argument("--m3", type=Path, default=None, help="组员 3 v3 results/ 目录")
    parser.add_argument("--model", type=str, default="M1", help="主模型名称（如 M1/M4/M5）")
    parser.add_argument("--fee-scenario", type=str, default="net_10bp", choices=["net_10bp", "net_histtax", "gross"])
    parser.add_argument("--out-dir", type=Path, default=P.MEMBER4_DIR / "results")
    parser.add_argument("--check-contract", action="store_true", help="仅检查 PRD 接口 1 & 3 是否就绪")
    args = parser.parse_args()

    proc_dir = P.resolve_data_processed(args.data)
    m3_v3_res = Path(args.m3) if args.m3 else (P.resolve_member3_dir("v3") / "results")

    if args.check_contract:
        status = check_contract(proc_dir, m3_v3_res)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return

    run_v3(proc_dir, m3_v3_res, args.model, args.fee_scenario, args.out_dir)


if __name__ == "__main__":
    main()
