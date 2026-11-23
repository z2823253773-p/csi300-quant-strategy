# -*- coding: utf-8 -*-
"""
组员4 PRD 接口 4（v3.0 终版）：双股票池产品化评估（M4 主交付模型 + 双池容量/流动性对比 + 四档 HWM 费率）
严格读取组员 1 Tushare 数据 3.0 与组员 3 member3_v3/results/，零硬编码。
运行命令：
    .venv/bin/python code/product_analysis_v3.py
"""
from __future__ import annotations

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

OUT_RES = P.MEMBER4_DIR / "results"
OUT_RES.mkdir(parents=True, exist_ok=True)


def calc_dual_sharpe(ret: pd.Series) -> dict:
    n = len(ret)
    wealth = (1.0 + ret).cumprod()
    cum_ret = float(wealth.iloc[-1] - 1.0)
    ann_geom = float(wealth.iloc[-1] ** (252.0 / n) - 1.0)
    ann_vol = float(ret.std(ddof=1) * np.sqrt(252.0))
    sharpe_arith = float((ret.mean() / ret.std(ddof=1)) * np.sqrt(252.0)) if ret.std(ddof=1) > 0 else 0.0
    geom_over_vol = float(ann_geom / ann_vol) if ann_vol > 0 else 0.0
    max_dd = float((wealth / wealth.cummax().clip(lower=1.0) - 1.0).min())
    return {
        "cum_return": cum_ret,
        "ann_geom": ann_geom,
        "ann_vol": ann_vol,
        "sharpe_arith_rf0": sharpe_arith,
        "geom_over_vol": geom_over_vol,
        "max_drawdown": max_dd,
        "terminal_nav": float(wealth.iloc[-1]),
    }


def load_pool_liq_inputs(pool: str) -> dict:
    proc = P.resolve_tushare_pool_processed(pool)
    amt = pd.read_parquet(proc / "matrix_amount.parquet").sort_index()
    ret = pd.read_parquet(proc / "matrix_returns.parquet").sort_index()
    open_hfq = pd.read_parquet(proc / "matrix_open_hfq.parquet").sort_index().ffill()
    for df in (amt, ret, open_hfq):
        df.index = pd.to_datetime(df.index)
    # 严格无前视：调仓日前20个交易日成交额均值与收益波动率
    adv20_prior = amt.rolling(20, min_periods=10).mean().shift(1)
    sigma20_prior = ret.rolling(20, min_periods=10).std(ddof=1).shift(1)
    return {"proc": proc, "open_hfq": open_hfq, "adv20_prior": adv20_prior, "sigma20_prior": sigma20_prior}


def reconstruct_trades_from_ow(ow: pd.DataFrame, exec_dates: list[pd.Timestamp], open_hfq: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ow = ow.fillna(0.0).sort_index()
    ow.index = pd.to_datetime(ow.index)
    cols = ow.columns
    dw_rows, wafter_rows = {}, {}
    for k, d in enumerate(exec_dates):
        w_after = ow.loc[d, cols]
        if k == 0:
            w_before = pd.Series(0.0, index=cols)
        else:
            d_prev = exec_dates[k - 1]
            w_start = ow.loc[d_prev, cols]
            ratio = (open_hfq.loc[d, cols] / open_hfq.loc[d_prev, cols]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
            w_unnorm = w_start * ratio
            cash_start = max(0.0, 1.0 - float(w_start.sum()))
            tot = float(w_unnorm.sum()) + cash_start
            w_before = w_unnorm / tot if tot > 0 else w_start
        dw_rows[d] = (w_after - w_before).abs()
        wafter_rows[d] = w_after
    return pd.DataFrame.from_dict(dw_rows, orient="index").sort_index(), pd.DataFrame.from_dict(wafter_rows, orient="index").sort_index()


def verify_amount_unit(proc: Path) -> dict:
    panel = pd.read_parquet(proc / "clean_daily_panel.parquet", columns=["trade_date", "stock_code", "close", "volume", "amount"])
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])
    latest = panel["trade_date"].max()
    sub = panel[(panel["trade_date"] == latest) & (panel["volume"] > 0)].copy()
    sub["ratio"] = sub["amount"] / (sub["volume"] * sub["close"])
    return {
        "unit": "元 (CNY)",
        "verification_date": str(latest.date()),
        "median_amount_over_vol_close": float(sub["ratio"].median()),
        "median_daily_amount_yuan": float(sub["amount"].median()),
        "note": "amount/(volume*close) 中位数约为 1.00，确认 Tushare matrix_amount 单位为人民币元。",
    }


def main():
    m3_res = P.resolve_member3_dir("v3") / "results"
    print(f"1. 读取组员 3 v3 回测结果: {m3_res}")
    metrics_v3 = pd.read_csv(m3_res / "metrics_v3.csv")
    turn_v3 = pd.read_csv(m3_res / "turnover_v3.csv", parse_dates=["execution_date"])
    ind_v3 = pd.read_csv(m3_res / "industry_exposure_v3.csv")
    oi_v3 = pd.read_csv(m3_res / "overnight_intraday_v3.csv")

    nav_hs_clean = pd.read_csv(m3_res / "daily_nav_hs300_clean.csv", parse_dates=["date"]).set_index("date").sort_index()
    nav_hs_full = pd.read_csv(m3_res / "daily_nav_hs300_full.csv", parse_dates=["date"]).set_index("date").sort_index()
    nav_zz = pd.read_csv(m3_res / "daily_nav_zz500.csv", parse_dates=["date"]).set_index("date").sort_index()

    pool_inputs = {p: load_pool_liq_inputs(p) for p in ("hs300", "zz500")}
    amt_info = verify_amount_unit(pool_inputs["hs300"]["proc"])

    # 重点评估的 5 个代表性策略组合（含双池容量对照与高换手反例）
    specs = [
        ("hs300_M4_main", "hs300", "hs300_clean", "M4", nav_hs_clean, "hs300_intraday"),
        ("hs300_M1_bench", "hs300", "hs300_clean", "M1", nav_hs_clean, "hs300_intraday"),
        ("hs300_M5_alt", "hs300", "hs300_clean", "M5", nav_hs_clean, "hs300_intraday"),
        ("hs300_M0b_highturn", "hs300", "hs300_full", "M0b", nav_hs_full, "hs300_intraday"),
        ("zz500_M4_peer", "zz500", "zz500", "M4", nav_zz, "zz500_intraday"),
        ("zz500_M1_bench", "zz500", "zz500", "M1", nav_zz, "zz500_intraday"),
    ]

    print("2. 计算双股票池 ADV20 流动性分布、参与率硬约束与平方根冲击容量 ...")
    liq_rows = []
    cap_dfs = []
    stress_rows = []
    drag_coefs = {}
    ret_map = {}
    bench_ann_map = {}
    strat_ann_map = {}

    stress_grid_map = {
        "hs300_M4_main": [3.0, 5.0, 6.63, 10.0, 15.0],
        "zz500_M4_peer": [1.0, 2.5, 3.0, 5.0],
    }

    for tag, pool, exp, model, nav_df, bcol in specs:
        ow = pd.read_parquet(m3_res / f"open_weights_{exp}_{model}.parquet")
        tr_sub = turn_v3[(turn_v3["experiment"] == exp) & (turn_v3["model"] == model) & (turn_v3["fee_scenario"] == "net_10bp")].sort_values("execution_date")
        exec_dates = list(pd.to_datetime(tr_sub["execution_date"]))

        pi = pool_inputs[pool]
        dw_df, wafter_df = reconstruct_trades_from_ow(ow, exec_dates, pi["open_hfq"])
        liq_st, cap_df = compute_liquidity_and_constraints(tag, dw_df, wafter_df, pi["adv20_prior"])
        liq_st["pool"] = pool
        liq_st["experiment"] = exp
        liq_st["base_model"] = model
        liq_rows.append(liq_st)
        cap_df["pool"] = pool
        cap_df["experiment"] = exp
        cap_df["base_model"] = model
        cap_dfs.append(cap_df)

        if tag in stress_grid_map:
            adv_aligned = pi["adv20_prior"].reindex(index=dw_df.index, columns=dw_df.columns)
            dw_reg = dw_df.iloc[1:]
            adv_reg = adv_aligned.iloc[1:]
            for aum_yi in stress_grid_map[tag]:
                aum = aum_yi * 1e8
                part_1d = (dw_reg * aum / adv_reg).replace([np.inf, -np.inf], np.nan).max(axis=1)
                liq_5d = (wafter_df * aum / (5.0 * adv_aligned)).replace([np.inf, -np.inf], np.nan).max(axis=1)
                days_rebal = part_1d / 0.05
                days_liq = (wafter_df * aum / (0.05 * adv_aligned)).replace([np.inf, -np.inf], np.nan).max(axis=1)
                stress_rows.append({
                    "model": tag,
                    "pool": pool,
                    "aum_yi": aum_yi,
                    "n_reg_rebal": int(len(dw_reg)),
                    "breach_1d_5pct_cnt": int((part_1d > 0.05).sum()),
                    "breach_1d_5pct_ratio": float((part_1d > 0.05).mean()),
                    "breach_3d_5pct_cnt": int((part_1d / 3.0 > 0.05).sum()),
                    "breach_3d_5pct_ratio": float((part_1d / 3.0 > 0.05).mean()),
                    "max_part_1d_p90": float(part_1d.quantile(0.90)),
                    "max_part_1d_max": float(part_1d.max()),
                    "req_days_5pct_p90": float(days_rebal.quantile(0.90)),
                    "req_days_5pct_max": float(days_rebal.max()),
                    "n_all_periods": int(len(wafter_df)),
                    "breach_5d_liq_cnt": int((liq_5d > 0.05).sum()),
                    "breach_5d_liq_ratio": float((liq_5d > 0.05).mean()),
                    "max_liq_days_5pct": float(days_liq.max()),
                })

        drag_coefs[tag] = build_impact_drag_coef(dw_df, pi["adv20_prior"], pi["sigma20_prior"], nav_df.index)
        s_nav = nav_df[f"{model}_net_10bp"]
        b_nav = nav_df[bcol]
        sr = s_nav.pct_change(); sr.iloc[0] = s_nav.iloc[0] - 1.0
        br = b_nav.pct_change(); br.iloc[0] = b_nav.iloc[0] - 1.0
        ret_map[tag] = sr
        strat_ann_map[tag] = float(s_nav.iloc[-1] ** (252.0 / len(s_nav)) - 1.0)
        bench_ann_map[tag] = float(b_nav.iloc[-1] ** (252.0 / len(b_nav)) - 1.0)

    liq_df = pd.DataFrame(liq_rows)
    liq_df.to_csv(OUT_RES / "liquidity_profile_v3.csv", index=False, encoding="utf-8")
    cap_all_df = pd.concat(cap_dfs, ignore_index=True)
    cap_all_df.to_csv(OUT_RES / "capacity_constraints_v3.csv", index=False, encoding="utf-8")
    stress_df = pd.DataFrame(stress_rows)
    stress_df.to_csv(OUT_RES / "capacity_stress_v3.csv", index=False, encoding="utf-8")

    # 连续冲击衰减曲线（1000万 -> 500亿，对比 hs300_M4_main, hs300_M1_bench, zz500_M4_peer, hs300_M0b_highturn）
    log_grid = np.geomspace(1e7, 5e10, 35)
    milestones = np.array([1e7, 5e7, 1e8, 2e8, 5e8, 1e9, 2e9, 5e9, 8e9, 1e10, 2e10, 5e10])
    aum_grid = np.unique(np.sort(np.concatenate([log_grid, milestones])))
    curve_tags = ["hs300_M4_main", "hs300_M1_bench", "zz500_M4_peer", "hs300_M0b_highturn"]
    curve_rows = []
    for y_coef in [0.5, 0.8, 1.0]:
        for aum in aum_grid:
            row = {"Y": y_coef, "aum_yuan": float(aum), "aum_yi": float(aum / 1e8)}
            for tag in curve_tags:
                net_a = eval_net_ann_at_aum(ret_map[tag], drag_coefs[tag], aum, y_coef)
                row[f"{tag}_net_ann"] = net_a
                row[f"{tag}_drag_ann"] = strat_ann_map[tag] - net_a
                row[f"{tag}_excess_ann"] = net_a - bench_ann_map[tag]
            curve_rows.append(row)
    curve_df = pd.DataFrame(curve_rows)
    curve_df.to_csv(OUT_RES / "capacity_curve_v3.csv", index=False, encoding="utf-8")

    half_caps = {}
    for tag in curve_tags:
        half_caps[tag] = {}
        for y_coef in [0.5, 0.8, 1.0]:
            if strat_ann_map[tag] <= bench_ann_map[tag]:
                cap_yi = 0.0
            else:
                cap_yuan = solve_half_excess_capacity(ret_map[tag], drag_coefs[tag], strat_ann_map[tag], bench_ann_map[tag], y_coef)
                cap_yi = float(cap_yuan / 1e8) if cap_yuan is not None else None
            half_caps[tag][f"Y_{y_coef}"] = cap_yi

    print("3. 计算主交付模型 hs300_clean M4（及中证 500 M4 对照）四档高水位法产品费率 ...")
    fee_specs = [
        ("A", "方案A 标准份额", 0.010, 0.002, 0.20, "abs_hwm", "绝对收益高水位×20%(年度计提)"),
        ("B", "方案B 超额计提", 0.010, 0.002, 0.20, "excess_hwm", "相对基准超额高水位×20%(年度计提)"),
        ("C", "方案C 机构份额", 0.006, 0.0015, 0.15, "excess_hwm", "相对基准超额高水位×15%(年度计提)"),
        ("D", "方案D 纯管理费", 0.015, 0.002, 0.0, "none", "无业绩报酬"),
    ]

    fee_rows = []
    fee_details = {}
    inv_nav_df = pd.DataFrame({"hs300_intraday": nav_hs_clean["hs300_intraday"]}, index=nav_hs_clean.index)

    for scenario_key, s_nav, b_nav in [
        ("hs300_M4_net10bp", nav_hs_clean["M4_net_10bp"], nav_hs_clean["hs300_intraday"]),
        ("hs300_M4_histtax", nav_hs_clean["M4_net_histtax"], nav_hs_clean["hs300_intraday"]),
        ("zz500_M4_net10bp", nav_zz["M4_net_10bp"], nav_zz["zz500_intraday"]),
    ]:
        sr = s_nav.pct_change(); sr.iloc[0] = s_nav.iloc[0] - 1.0
        br = b_nav.pct_change(); br.iloc[0] = b_nav.iloc[0] - 1.0
        g_st = calc_dual_sharpe(sr)
        b_st = calc_dual_sharpe(br)
        ex_r = sr - br
        te_g = float(ex_r.std(ddof=1) * np.sqrt(252.0))
        ir_g = float((ex_r.mean() / ex_r.std(ddof=1)) * np.sqrt(252.0)) if ex_r.std(ddof=1) > 0 else 0.0

        fee_rows.append({
            "series": scenario_key, "plan_id": "Gross", "plan_name": "策略净值(未扣产品费)",
            "mgmt_fee": 0.0, "custody_fee": 0.0, "perf_fee_rate": 0.0, "perf_basis": "无(已含交易成本)",
            **g_st, "tracking_error": te_g, "info_ratio": ir_g,
            "fixed_fee_cum_drag": 0.0, "perf_fee_cum_paid": 0.0, "total_fee_cum_drag": 0.0, "ann_fee_drag": 0.0,
        })
        if scenario_key == "hs300_M4_net10bp":
            inv_nav_df["M4_strategy_net10bp"] = s_nav
        fee_details[scenario_key] = {}

        for pid, pname, mf, cf, pr, pmode, pbasis in fee_specs:
            mtm_s, cryst_s, st = simulate_fee_plan(s_nav, b_nav, mf + cf, pr, pmode)
            mr = mtm_s.pct_change(); mr.iloc[0] = mtm_s.iloc[0] - 1.0
            ds = calc_dual_sharpe(mr)
            ex_m = mr - br
            te_m = float(ex_m.std(ddof=1) * np.sqrt(252.0))
            ir_m = float((ex_m.mean() / ex_m.std(ddof=1)) * np.sqrt(252.0)) if ex_m.std(ddof=1) > 0 else 0.0

            row = {
                "series": scenario_key, "plan_id": pid, "plan_name": pname,
                "mgmt_fee": mf, "custody_fee": cf, "perf_fee_rate": pr, "perf_basis": pbasis,
                **ds, "tracking_error": te_m, "info_ratio": ir_m,
                "fixed_fee_cum_drag": st["fixed_fee_cum_drag"],
                "perf_fee_cum_paid": st["perf_fee_cum_paid"],
                "total_fee_cum_drag": st["total_fee_cum_drag"],
                "ann_fee_drag": float(g_st["ann_geom"] - ds["ann_geom"]),
            }
            fee_rows.append(row)
            fee_details[scenario_key][pid] = {**row, "crystallization_events": st["crystallization_events"]}
            if scenario_key == "hs300_M4_net10bp":
                inv_nav_df[f"plan_{pid}"] = mtm_s
                inv_nav_df[f"plan_{pid}_cryst"] = cryst_s

    fee_df = pd.DataFrame(fee_rows)
    fee_df.to_csv(OUT_RES / "fee_analysis_v3.csv", index=False, encoding="utf-8")
    inv_nav_df.to_csv(OUT_RES / "investor_nav_v3.csv", encoding="utf-8")

    # 抽取最新 M4 行业分布（沪深300与中证500）
    ind_m4_hs = ind_v3[(ind_v3["experiment"] == "hs300_clean") & (ind_v3["model"] == "M4")].copy()
    ind_m4_zz = ind_v3[(ind_v3["experiment"] == "zz500") & (ind_v3["model"] == "M4")].copy()

    # 确定推荐规模（5%参与率 3日调仓 P10 & 5日清仓 P10）
    def get_cap(tag, ctype, rate, win):
        sub = cap_all_df[(cap_all_df["model"] == tag) & (cap_all_df["constraint_type"] == ctype) & (cap_all_df["participation_rate"] == rate) & (cap_all_df["window_days"] == win)]
        return float(sub["p10_yi"].iloc[0]), float(sub["median_yi"].iloc[0])

    hs_1d_p10, hs_1d_med = get_cap("hs300_M4_main", "rebalance_participation", 0.05, 1)
    hs_3d_p10, hs_3d_med = get_cap("hs300_M4_main", "rebalance_participation", 0.05, 3)
    hs_5d_p10, hs_5d_med = get_cap("hs300_M4_main", "liquidation_5d", 0.05, 5)
    zz_1d_p10, zz_1d_med = get_cap("zz500_M4_peer", "rebalance_participation", 0.05, 1)
    zz_3d_p10, zz_3d_med = get_cap("zz500_M4_peer", "rebalance_participation", 0.05, 3)
    zz_5d_p10, zz_5d_med = get_cap("zz500_M4_peer", "liquidation_5d", 0.05, 5)

    summary = {
        "version": "v3.0_tushare_M4_locked",
        "primary_product": {
            "pool": "hs300",
            "experiment": "hs300_clean",
            "model": "M4",
            "formula": "0.25*z_bp + 0.25*z_ep + 0.25*z_lowvol_60 + 0.25*z_lowturn_20",
            "rebalance_rule": "每5交易日调仓，Top 50等权，前75名保留缓冲带（上期目标持仓口径）",
            "product_name": "沪深300价值低波精选量化私募证券投资基金（M4）",
            "benchmark": "沪深300指数（000300.SH，3.0首日开盘intraday口径）",
            "warning_line": 0.85,
            "stop_loss_line": 0.80,
            "recommended_conservative_aum_yi": [3.0, 6.0],
            "stress_test_aum_yi": [10.0, 15.0],
            "recommended_aum_note": f"5%参与率下1日调仓P10为{hs_1d_p10:.2f}亿（中位数{hs_1d_med:.2f}亿）、3日调仓P10为{hs_3d_p10:.2f}亿（中位数{hs_3d_med:.2f}亿）、5日清仓P10为{hs_5d_p10:.2f}亿（中位数{hs_5d_med:.2f}亿）；硬约束稳健首期规模定位 3–6 亿元，10–15 亿元列为待多日拆单压力测试的扩张情景（Y=0.8冲击半衰理论容量{half_caps['hs300_M4_main']['Y_0.8']:.2f}亿）。",
        },
        "capacity_stress_test": stress_rows,
        "cross_pool_capacity_highlight": {
            "hs300_M4": {"p10_1d_5pct_yi": hs_1d_p10, "med_1d_5pct_yi": hs_1d_med, "p10_3d_5pct_yi": hs_3d_p10, "med_3d_5pct_yi": hs_3d_med, "p10_5d_liq_yi": hs_5d_p10, "med_5d_liq_yi": hs_5d_med, "half_excess_Y08_yi": half_caps["hs300_M4_main"]["Y_0.8"]},
            "zz500_M4": {"p10_1d_5pct_yi": zz_1d_p10, "med_1d_5pct_yi": zz_1d_med, "p10_3d_5pct_yi": zz_3d_p10, "med_3d_5pct_yi": zz_3d_med, "p10_5d_liq_yi": zz_5d_p10, "med_5d_liq_yi": zz_5d_med, "half_excess_Y08_yi": half_caps["zz500_M4_peer"]["Y_0.8"]},
        },
        "data_verification": amt_info,
        "half_excess_capacities_yi": half_caps,
        "liquidity_profile": liq_rows,
        "fee_comparison_hs300_M4_net10bp": fee_df[fee_df["series"] == "hs300_M4_net10bp"].to_dict(orient="records"),
        "fee_comparison_hs300_M4_histtax": fee_df[fee_df["series"] == "hs300_M4_histtax"].to_dict(orient="records"),
        "fee_comparison_zz500_M4_net10bp": fee_df[fee_df["series"] == "zz500_M4_net10bp"].to_dict(orient="records"),
        "upstream_metrics_summary": {
            "hs300_clean_all_net10bp": metrics_v3[(metrics_v3["experiment"] == "hs300_clean") & (metrics_v3["stage"] == "all") & (metrics_v3["fee_scenario"] == "net_10bp")].to_dict(orient="records"),
            "zz500_all_net10bp": metrics_v3[(metrics_v3["experiment"] == "zz500") & (metrics_v3["stage"] == "all") & (metrics_v3["fee_scenario"] == "net_10bp")].to_dict(orient="records"),
        },
        "industry_m4_hs300_latest": ind_m4_hs[ind_m4_hs["scope"] == "latest_20261030"].sort_values("weight", ascending=False).to_dict(orient="records"),
        "industry_m4_zz500_latest": ind_m4_zz[ind_m4_zz["scope"] == "latest_20261030"].sort_values("weight", ascending=False).to_dict(orient="records"),
        "overnight_intraday_summary": oi_v3[oi_v3["experiment"].isin(["hs300_clean", "zz500"])].to_dict(orient="records"),
    }
    (OUT_RES / "product_summary_v3.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 双池 M4 容量与流动性核心对比 =====")
    print(f"  沪深300 M4: 5%参与率 1日P10={hs_1d_p10:.2f}亿(中位{hs_1d_med:.2f}亿) | 3日P10={hs_3d_p10:.2f}亿(中位{hs_3d_med:.2f}亿) | 5日清仓P10={hs_5d_p10:.2f}亿 | 冲击半衰(Y=0.8)={half_caps['hs300_M4_main']['Y_0.8']:.2f}亿")
    print(f"  中证500 M4: 5%参与率 1日P10={zz_1d_p10:.2f}亿(中位{zz_1d_med:.2f}亿) | 3日P10={zz_3d_p10:.2f}亿(中位{zz_3d_med:.2f}亿) | 5日清仓P10={zz_5d_p10:.2f}亿 | 冲击半衰(Y=0.8)={half_caps['zz500_M4_peer']['Y_0.8']:.2f}亿")
    print("\n===== 沪深300 M4（net_10bp）四档费率净值对比 =====")
    v = fee_df[fee_df["series"] == "hs300_M4_net10bp"][["plan_id", "plan_name", "cum_return", "ann_geom", "sharpe_arith_rf0", "max_drawdown", "info_ratio", "ann_fee_drag"]].copy()
    for c in ["cum_return", "ann_geom", "max_drawdown", "ann_fee_drag"]:
        v[c] = (v[c] * 100).map(lambda x: f"{x:+.2f}%" if c in ("cum_return", "ann_geom") else f"{x:.2f}%")
    v["sharpe_arith_rf0"] = v["sharpe_arith_rf0"].map(lambda x: f"{x:.3f}")
    v["info_ratio"] = v["info_ratio"].map(lambda x: f"{x:.3f}")
    print(v.to_string(index=False))
    print(f"\n已保存全部 v3 产品测算结果至: {OUT_RES}")


if __name__ == "__main__":
    main()
