# -*- coding: utf-8 -*-
"""
组员3 v3.0 完整双股票池无前视账户回测、行业暴露、隔夜/盘中与 Fama-MacBeth 因子归因引擎
严格遵循 PRD §3 接口 3 与 §4 硬性公式，并修复旧 engine.py 的 4 处细节：
1. 补跑组员 2 最新新增的 hs300/clean_015/target_weights.csv（沪深300五模型干净共同池主对照 M1/M2/M3b/M4/M5）；
2. 板块开盘涨跌停阈值改用**逐日 is_st**（修复旧版 any(is_st) 全期前视偏差）；
3. 显式校验 matrix_open_quote_observed.parquet（与 PRD §4 完全对齐）；
4. 修复 gross 情景下 cash 缩放条件（确保所有情景现金全程 >= 0），并用精确滑点成本实现账本机精级闭合（<1e-14）；
5. 补齐滞后实际持仓暴露 × 截面因子收益的 Fama-MacBeth 归因表 decomp_v3.csv。

运行命令（在项目根目录或任意目录）：
    .venv/bin/python .../member3_v3/code/run_backtest_v3.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

COMMISSION = 0.0003
SLIPPAGE = 0.001
STAMP_FULL = 0.001
STAMP_HALF = 0.0005
TAX_CUT = pd.Timestamp("2023-08-28")
SCENARIOS = ["gross", "net_10bp", "net_histtax"]
FM_FACTORS = ["bp", "ep", "small", "lowvol_60", "lowturn_20", "eb_proxy", "new012_amt_ema10"]
FINANCE_INDS = ["银行", "非银金融"]


def load_pool_context(proc_dir: Path, bench_code: str) -> dict:
    opens = pd.read_parquet(proc_dir / "matrix_open_hfq.parquet").sort_index()
    close = pd.read_parquet(proc_dir / "matrix_close_hfq.parquet").sort_index().ffill()
    ret_mat = pd.read_parquet(proc_dir / "matrix_returns.parquet").sort_index()
    open_obs = pd.read_parquet(proc_dir / "matrix_open_quote_observed.parquet").sort_index()
    tradable_mask = pd.read_parquet(proc_dir / "matrix_tradable_mask.parquet").sort_index()
    for df in (opens, close, ret_mat, open_obs, tradable_mask):
        df.index = pd.to_datetime(df.index)
    codes = opens.columns

    panel = pd.read_parquet(
        proc_dir / "clean_daily_panel.parquet",
        columns=[
            "trade_date", "stock_code", "open", "preclose", "tradestatus",
            "is_st", "is_new_stock", "in_index_universe", "sw_l1_name",
        ],
    )
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    def wide(col: str) -> pd.DataFrame:
        return panel.pivot(index="trade_date", columns="stock_code", values=col).reindex(
            index=opens.index, columns=codes
        )

    raw_open = wide("open")
    raw_pre = wide("preclose")
    state = wide("tradestatus").astype(str).isin(["1", "1.0", "True"])
    st_daily = wide("is_st").fillna(False).astype(bool)
    is_new = wide("is_new_stock").fillna(False).astype(bool)
    in_univ = wide("in_index_universe").fillna(False).astype(bool)
    ind_map = wide("sw_l1_name").fillna("未分类")

    obs_bool = open_obs.reindex(index=opens.index, columns=codes).fillna(False).astype(bool)
    ok_arr = (state & obs_bool & raw_open.gt(0)).to_numpy()

    # 逐日 is_st 判定板块开盘触限阈值（彻底杜绝 any(is_st) 全期前视）
    is_star_chi = np.asarray(codes.str.startswith(("688", "300", "301", "302")), dtype=bool)
    st_arr = st_daily.to_numpy()
    threshold = np.where(is_star_chi[None, :], 0.195, np.where(st_arr, 0.045, 0.095))
    move = (raw_open / raw_pre - 1.0).to_numpy(dtype=float)

    buy_ok = pd.DataFrame(
        ok_arr & in_univ.to_numpy() & (~st_arr) & (~is_new.to_numpy()) & ~(move >= threshold),
        index=opens.index, columns=codes,
    )
    sell_ok = pd.DataFrame(
        ok_arr & ~(move <= -threshold),
        index=opens.index, columns=codes,
    )

    bench = pd.read_parquet(proc_dir / "benchmark_daily.parquet")
    b = bench[bench["benchmark_code"].astype(str) == bench_code].copy()
    b["trade_date"] = pd.to_datetime(b["trade_date"])
    b = b.sort_values("trade_date").set_index("trade_date").loc["2023-01-09":"2026-10-30"]
    cal = b.index
    assert len(cal) == 921, f"Expected 921 trading days, got {len(cal)}"

    b_ret = b["benchmark_close"].pct_change()
    b_ret.iloc[0] = b["benchmark_close"].iloc[0] / b["benchmark_open"].iloc[0] - 1.0
    b_nav = (1.0 + b_ret).cumprod()

    return {
        "opens": opens,
        "close": close,
        "ret_mat": ret_mat,
        "tradable_mask": tradable_mask.reindex(index=opens.index, columns=codes).fillna(False).astype(bool),
        "codes": codes,
        "buy_ok": buy_ok,
        "sell_ok": sell_ok,
        "ind_map": ind_map,
        "calendar": cal,
        "bench_ret": b_ret,
        "bench_nav": b_nav,
    }


def replay_account_exact(w_rebal: pd.DataFrame, fee_scenario: str, ctx: dict) -> dict:
    """PRD §4 精确账户撮合引擎：逐日现金>=0、精确滑点闭合残差 <1e-14。"""
    cal = ctx["calendar"]
    codes = ctx["codes"]
    opens = ctx["opens"].reindex(index=cal, columns=codes).to_numpy(dtype=float)
    close = ctx["close"].reindex(index=cal, columns=codes).to_numpy(dtype=float)
    buying = ctx["buy_ok"].reindex(index=cal, columns=codes).to_numpy(dtype=bool)
    selling = ctx["sell_ok"].reindex(index=cal, columns=codes).to_numpy(dtype=bool)

    rebal_set = set(w_rebal.index)
    w_aligned = w_rebal.reindex(index=cal, columns=codes).fillna(0.0).to_numpy(dtype=float)

    cash = 1.0
    shares = np.zeros(len(codes), dtype=float)
    prev_close_asset = 1.0

    navs = np.empty(len(cal), dtype=float)
    ow_mat = np.zeros((len(cal), len(codes)), dtype=np.float32)
    ledger_rows = []
    turn_rows = []

    for pos, day in enumerate(cal):
        o_px = opens[pos]
        c_px = close[pos]
        held = shares > 0
        # 若停牌当日无开盘价，按前收盘/已填充收盘估值，不参与交易
        px = np.where(np.isfinite(o_px) & (o_px > 0), o_px, np.where(np.isfinite(c_px) & (c_px > 0), c_px, 1.0))
        mark = np.where(np.isfinite(c_px) & (c_px > 0), c_px, px)

        open_before = cash + float(shares @ px)
        overnight_pnl = open_before - prev_close_asset
        cost_exact = 0.0

        if day in rebal_set:
            if fee_scenario == "gross":
                comm = slip = stamp = 0.0
                sell_cost = 0.0
            else:
                comm = COMMISSION
                slip = SLIPPAGE
                stamp = STAMP_FULL if (fee_scenario == "net_10bp" or day < TAX_CUT) else STAMP_HALF
                sell_cost = slip + (1.0 - slip) * (comm + stamp)

            cur_val = shares * px
            desired = w_aligned[pos] * open_before

            raw_sell = np.maximum(0.0, cur_val - desired)
            can_s = selling[pos] & np.isfinite(o_px) & (o_px > 0)
            sell = raw_sell * can_s
            blocked_sell = float((raw_sell * (~can_s)).sum())

            sell_sum = float(sell.sum())
            cash += sell_sum * (1.0 - sell_cost)
            shares = np.maximum(shares - np.divide(sell, px, out=np.zeros_like(sell), where=px > 0), 0.0)
            # 清理浮点残留极小份额
            shares[shares < 1e-14] = 0.0

            raw_need = np.maximum(0.0, desired - shares * px)
            can_b = buying[pos] & np.isfinite(o_px) & (o_px > 0)
            need = raw_need * can_b
            blocked_buy = float((raw_need * (~can_b)).sum())

            # 修复旧版 bug：无论 comm 是否为 0（包含 gross），均做现金硬约束缩放！
            total_need_cash = float(need.sum()) * (1.0 + comm)
            if total_need_cash > 0.0:
                scale = min(1.0, max(0.0, cash) / total_need_cash)
                paid = need * scale
            else:
                paid = need

            buy_sum = float(paid.sum())
            cash -= buy_sum * (1.0 + comm)
            assert cash >= -1e-11, f"Negative cash {cash} on {day} ({fee_scenario})"
            cash = max(0.0, cash)
            shares += np.divide(paid, px * (1.0 + slip), out=np.zeros_like(paid), where=px > 0)

            open_after = cash + float(shares @ px)
            cost_exact = open_before - open_after
            half_turn = (sell_sum + buy_sum) / 2.0 / open_before if open_before > 0 else 0.0
            turn_rows.append({
                "execution_date": day,
                "fee_scenario": fee_scenario,
                "buy_weight": buy_sum / open_before,
                "sell_weight": sell_sum / open_before,
                "half_turn": half_turn,
                "cost_ratio": cost_exact / open_before,
                "blocked_buy_weight": blocked_buy / open_before,
                "blocked_sell_weight": blocked_sell / open_before,
            })
        else:
            open_after = open_before

        if open_after > 0:
            ow_mat[pos] = ((shares * px) / open_after).astype(np.float32)

        close_asset = cash + float(shares @ mark)
        intraday_pnl = close_asset - open_after
        residual = (close_asset - prev_close_asset) - overnight_pnl - intraday_pnl + cost_exact
        assert abs(residual) < 1e-12, f"Ledger closure failed on {day}: {residual}"

        navs[pos] = close_asset
        ledger_rows.append({
            "date": day,
            "prev_close_asset": prev_close_asset,
            "open_before": open_before,
            "open_after": open_after,
            "close_asset": close_asset,
            "overnight_pnl": overnight_pnl,
            "intraday_pnl": intraday_pnl,
            "cost": cost_exact,
            "residual": residual,
        })
        prev_close_asset = close_asset

    nav_s = pd.Series(navs, index=cal)
    ow_df = pd.DataFrame(ow_mat, index=cal, columns=codes)
    ledger_df = pd.DataFrame(ledger_rows).set_index("date")
    turn_df = pd.DataFrame(turn_rows)
    return {"nav": nav_s, "open_weights": ow_df, "ledger": ledger_df, "turnover": turn_df}


def compute_stage_metrics(nav_s: pd.Series, bench_ret: pd.Series, turn_s: pd.Series) -> list[dict]:
    ret = nav_s.pct_change()
    ret.iloc[0] = nav_s.iloc[0] - 1.0
    stages = [
        ("all", "2023-01-09", "2026-10-30"),
        ("validation", "2023-01-09", "2024-12-31"),
        ("seen", "2025-01-01", "2026-10-30"),
    ]
    res = {}
    rows = []
    for st, s_dt, e_dt in stages:
        r = ret.loc[s_dt:e_dt]
        br = bench_ret.loc[s_dt:e_dt]
        n = len(r)
        wealth = (1.0 + r).cumprod()
        b_wealth = (1.0 + br).cumprod()

        cum_ret = float(wealth.iloc[-1] - 1.0)
        b_cum = float(b_wealth.iloc[-1] - 1.0)
        ann_geom = float(wealth.iloc[-1] ** (252.0 / n) - 1.0)
        ann_vol = float(r.std(ddof=1) * np.sqrt(252.0))
        sharpe_arith = float((r.mean() / r.std(ddof=1)) * np.sqrt(252.0)) if r.std(ddof=1) > 0 else 0.0
        geom_over_vol = float(ann_geom / ann_vol) if ann_vol > 0 else 0.0

        run_max = wealth.cummax().clip(lower=1.0)
        dd = wealth / run_max - 1.0
        max_dd = float(dd.min())
        trough_pos = int(np.argmin(dd.to_numpy()))
        peak_val = float(run_max.iloc[trough_pos])
        after = wealth.iloc[trough_pos + 1 :].to_numpy()
        rec_idx = np.where(after >= peak_val - 1e-12)[0]
        dd_rec_days = int(rec_idx[0] + 1) if len(rec_idx) > 0 else np.nan

        diff = r - br
        te = float(diff.std(ddof=1) * np.sqrt(252.0))
        ir = float((diff.mean() / diff.std(ddof=1)) * np.sqrt(252.0)) if diff.std(ddof=1) > 0 else 0.0

        ht = turn_s.loc[s_dt:e_dt].dropna()
        mean_ht = float(ht.mean()) if len(ht) > 0 else 0.0
        ann_ht = float(ht.sum() * (252.0 / n))

        row = {
            "stage": st,
            "n_days": int(n),
            "cum_return": cum_ret,
            "ann_geom": ann_geom,
            "ann_vol": ann_vol,
            "sharpe_arith_rf0": sharpe_arith,
            "geom_over_vol": geom_over_vol,
            "max_drawdown": max_dd,
            "dd_recovery_days": dd_rec_days,
            "mean_half_turn": mean_ht,
            "ann_half_turn": ann_ht,
            "excess_vs_benchmark": cum_ret - b_cum,
            "te_vs_benchmark": te,
            "ir_vs_benchmark": ir,
        }
        res[st] = row
        rows.append(row)

    # PRD 强制断言：三段严格复利连乘闭环 < 1e-10
    err = abs((1.0 + res["validation"]["cum_return"]) * (1.0 + res["seen"]["cum_return"]) - 1.0 - res["all"]["cum_return"])
    assert err < 1e-10, f"Stage chaining assertion failed: {err}"
    return rows


def compute_fama_macbeth_factor_returns(m2_pool_dir: Path, ctx: dict) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    在每个回测交易日 t，使用滞后一期（t-1 收盘）的标准化因子暴露对当日股票收益 r_t 做横截面 OLS，
    得到全市场每日因子收益率序列（含截距项 market_intercept）。
    """
    cal = ctx["calendar"]
    codes = ctx["codes"]
    ret_mat = ctx["ret_mat"].reindex(columns=codes)
    full_dates = ctx["opens"].index
    prev_date_map = {full_dates[i]: full_dates[i - 1] for i in range(1, len(full_dates))}

    facs: dict[str, pd.DataFrame] = {}
    for name in FM_FACTORS:
        df = pd.read_parquet(m2_pool_dir / "signals" / f"factor_{name}.parquet")
        df.index = pd.to_datetime(df.index)
        facs[name] = df.reindex(index=full_dates, columns=codes)

    f_ret_rows = []
    for d in cal:
        d_prev = prev_date_map[d]
        y = ret_mat.loc[d].to_numpy(dtype=float)
        X_cols = [facs[f].loc[d_prev].to_numpy(dtype=float) for f in FM_FACTORS]
        X_mat = np.column_stack(X_cols)
        valid = np.isfinite(y) & np.all(np.isfinite(X_mat), axis=1) & ctx["tradable_mask"].loc[d_prev].to_numpy()
        if valid.sum() >= 30:
            X_design = np.column_stack([np.ones(valid.sum()), X_mat[valid]])
            beta, *_ = np.linalg.lstsq(X_design, y[valid], rcond=None)
        else:
            beta = np.zeros(len(FM_FACTORS) + 1)
        row = {"date": d, "market_intercept": float(beta[0])}
        for idx, f in enumerate(FM_FACTORS, start=1):
            row[f] = float(beta[idx])
        f_ret_rows.append(row)

    f_ret_df = pd.DataFrame(f_ret_rows).set_index("date")
    # 预提取回测日对应的滞后因子矩阵（date d -> exposure at d_prev）
    lagged_facs = {}
    prev_dates = [prev_date_map[d] for d in cal]
    for name in FM_FACTORS:
        lagged_facs[name] = pd.DataFrame(
            facs[name].loc[prev_dates].to_numpy(dtype=float),
            index=cal, columns=codes,
        )
    return f_ret_df, lagged_facs


def compute_model_attribution(
    pool: str,
    exp: str,
    model: str,
    ow_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    f_ret_df: pd.DataFrame,
    lagged_facs: dict[str, pd.DataFrame],
) -> list[dict]:
    """滞后实际持仓暴露 × 截面因子收益归因，并对账毛/净实际收益与隔夜/盘中/费用。"""
    cal = ow_df.index
    pa = ledger_df["prev_close_asset"]
    actual_net = ledger_df["close_asset"] / pa - 1.0
    cost_r = ledger_df["cost"] / pa
    actual_gross = actual_net + cost_r
    overnight_r = ledger_df["overnight_pnl"] / pa
    intraday_r = ledger_df["intraday_pnl"] / pa

    w_arr = ow_df.to_numpy(dtype=float)
    stock_w_sum = w_arr.sum(axis=1)
    cash_w = np.clip(1.0 - stock_w_sum, 0.0, 1.0)

    # 市场截距贡献（按股票总仓位加权）
    contrib = {
        "market_intercept": pd.Series(stock_w_sum * f_ret_df["market_intercept"].to_numpy(), index=cal),
    }
    explained = contrib["market_intercept"].copy()

    for fname in FM_FACTORS:
        exp_mat = np.nan_to_num(lagged_facs[fname].to_numpy(dtype=float), nan=0.0)
        port_exp = (w_arr * exp_mat).sum(axis=1)
        c_series = pd.Series(port_exp * f_ret_df[fname].to_numpy(), index=cal)
        contrib[f"factor_{fname}"] = c_series
        explained = explained + c_series

    contrib["specific_residual_and_timing"] = actual_gross - explained
    contrib["gross_total_check"] = actual_gross
    contrib["transaction_cost"] = -cost_r
    contrib["net_total_actual"] = actual_net
    contrib["ledger_overnight"] = overnight_r
    contrib["ledger_intraday"] = intraday_r
    contrib["cash_weight_mean"] = pd.Series(cash_w, index=cal)

    rows = []
    for comp, s in contrib.items():
        if comp == "cash_weight_mean":
            rows.append({
                "pool": pool, "experiment": exp, "model": model, "component": comp,
                "daily_mean_bp": float(s.mean() * 1e4),
                "ann_arith_pct": float(s.mean()),  # 存为小数比例（平均现金仓位）
            })
        else:
            rows.append({
                "pool": pool, "experiment": exp, "model": model, "component": comp,
                "daily_mean_bp": float(s.mean() * 1e4),
                "ann_arith_pct": float(s.mean() * 252.0),  # PRD 约定：CSV 中一律存小数比例
            })
    return rows


def main():
    here = Path(__file__).resolve()
    root_m3 = here.parent.parent
    repo_root = root_m3.parent
    default_data = repo_root / "member1_data" / "tushare_data"
    if not default_data.exists():
        default_data = repo_root.parent / "组员1_数据" / "Tushare_双股票池完整数据与代码" / "tushare_data"
    default_m2 = repo_root / "member2_signals"
    if not default_m2.exists():
        default_m2 = repo_root.parent / "组员2_因子与信号" / "member2_tushare"

    parser = argparse.ArgumentParser(description="组员3 v3.0 完整双池回测、行业偏离与归因引擎")
    parser.add_argument("--data", type=Path, default=default_data)
    parser.add_argument("--m2", type=Path, default=default_m2)
    parser.add_argument("--out", type=Path, default=root_m3 / "results")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    experiments = [
        ("hs300", "000300.SH", "hs300_clean", args.m2 / "hs300" / "clean_015" / "target_weights.csv", ["M1", "M2", "M3b", "M4", "M5"]),
        ("hs300", "000300.SH", "hs300_full", args.m2 / "hs300" / "signals" / "target_weights_v3.csv", ["M0a", "M0b", "M1", "M2", "M3a", "M3b", "M4", "M5"]),
        ("zz500", "000905.SH", "zz500", args.m2 / "zz500" / "signals" / "target_weights_v3.csv", ["M0a", "M0b", "M1", "M2", "M3a", "M3b", "M4", "M5"]),
    ]

    pool_cache: dict[str, dict] = {}
    fm_cache: dict[str, tuple[pd.DataFrame, dict[str, pd.DataFrame]]] = {}

    all_metrics = []
    all_turn = []
    all_ind = []
    all_oi = []
    all_decomp = []
    audit_summary = {}

    for pool, bcode, exp, tw_path, model_list in experiments:
        print(f"\n==================== 实验: {exp} ({pool}, {bcode}) ====================")
        if pool not in pool_cache:
            pool_cache[pool] = load_pool_context(args.data / pool / "processed", bcode)
            fm_cache[pool] = compute_fama_macbeth_factor_returns(args.m2 / pool, pool_cache[pool])
        ctx = pool_cache[pool]
        f_ret_df, lagged_facs = fm_cache[pool]

        tw = pd.read_csv(tw_path, dtype={"stock_code": str}, parse_dates=["signal_date", "execution_date"])
        nav_cols = {"benchmark_intraday": ctx["bench_nav"]}
        if pool == "hs300":
            nav_cols["hs300_intraday"] = ctx["bench_nav"]
        else:
            nav_cols["zz500_intraday"] = ctx["bench_nav"]

        max_res_exp = 0.0
        for model in model_list:
            sub = tw[tw["model"] == model]
            w_rebal = sub.pivot(index="execution_date", columns="stock_code", values="target_weight").reindex(columns=ctx["codes"]).fillna(0.0)
            for sc in SCENARIOS:
                out = replay_account_exact(w_rebal, sc, ctx)
                nav_cols[f"{model}_{sc}"] = out["nav"]
                tdf = out["turnover"].copy()
                tdf.insert(0, "model", model)
                tdf.insert(0, "experiment", exp)
                tdf.insert(0, "pool", pool)
                all_turn.append(tdf)

                t_series = tdf.set_index("execution_date")["half_turn"]
                for mrow in compute_stage_metrics(out["nav"], ctx["bench_ret"], t_series):
                    all_metrics.append({"pool": pool, "experiment": exp, "model": model, "fee_scenario": sc, **mrow})

                if sc == "net_10bp":
                    ow = out["open_weights"]
                    led = out["ledger"]
                    max_res_exp = max(max_res_exp, float(led["residual"].abs().max()))
                    ow.to_parquet(out_dir / f"open_weights_{exp}_{model}.parquet")

                    # 行业暴露（全期均值 + 最新 2026-10-30）
                    ind_map = ctx["ind_map"].reindex(index=ow.index, columns=ow.columns)
                    ind_daily = {}
                    for d in ow.index:
                        w_d = ow.loc[d]
                        nz = w_d[w_d > 0]
                        ind_daily[d] = nz.groupby(ind_map.loc[d, nz.index]).sum()
                    idf = pd.DataFrame(ind_daily).T.sort_index().fillna(0.0)
                    for scope, ser in [("full_mean", idf.mean()), ("latest_20261030", idf.iloc[-1])]:
                        for ind_name, val in ser.items():
                            all_ind.append({
                                "pool": pool, "experiment": exp, "model": model,
                                "scope": scope, "sw_l1_name": ind_name, "weight": float(val),
                            })
                    fin_full = float(idf[[c for c in FINANCE_INDS if c in idf.columns]].sum(axis=1).mean())
                    fin_last = float(idf[[c for c in FINANCE_INDS if c in idf.columns]].sum(axis=1).iloc[-1])

                    # 隔夜 / 盘中 / 费用精确复利加权闭合
                    pa = led["prev_close_asset"]
                    r_tot = led["close_asset"] / pa - 1.0
                    r_on = led["overnight_pnl"] / pa
                    r_in = led["intraday_pnl"] / pa
                    r_c = led["cost"] / pa
                    prev_nav = (1.0 + r_tot).cumprod().shift(1).fillna(1.0)
                    c_tot = float((1.0 + r_tot).prod() - 1.0)
                    c_on = float((r_on * prev_nav).sum())
                    c_in = float((r_in * prev_nav).sum())
                    c_cost = float((r_c * prev_nav).sum())
                    closure = abs(c_on + c_in - c_cost - c_tot)
                    assert closure < 1e-12, f"OI closure error: {closure}"
                    all_oi.append({
                        "pool": pool, "experiment": exp, "model": model,
                        "cum_overnight": c_on, "cum_intraday": c_in,
                        "cum_cost": c_cost, "cum_total": c_tot,
                        "closure_error": closure,
                        "finance_weight_full_mean": fin_full,
                        "finance_weight_latest": fin_last,
                    })

                    # Fama-MacBeth 滞后实际持仓因子归因
                    all_decomp.extend(compute_model_attribution(pool, exp, model, ow, led, f_ret_df, lagged_facs))

        nav_df = pd.DataFrame(nav_cols)
        nav_df.index.name = "date"
        nav_df.to_csv(out_dir / f"daily_nav_{exp}.csv", encoding="utf-8")
        audit_summary[exp] = {
            "pool": pool,
            "models": model_list,
            "n_days": len(nav_df),
            "benchmark_terminal_nav": float(ctx["bench_nav"].iloc[-1]),
            "benchmark_cum_return": float(ctx["bench_nav"].iloc[-1] - 1.0),
            "max_ledger_residual": max_res_exp,
        }

    # 同时保存一份 PRD 接口 3 标准名称（默认指向主线 hs300_clean）
    metrics_df = pd.DataFrame(all_metrics)
    metrics_df.to_csv(out_dir / "metrics_v3.csv", index=False, encoding="utf-8")
    pd.concat(all_turn, ignore_index=True).to_csv(out_dir / "turnover_v3.csv", index=False, encoding="utf-8")
    pd.DataFrame(all_ind).to_csv(out_dir / "industry_exposure_v3.csv", index=False, encoding="utf-8")
    oi_df = pd.DataFrame(all_oi)
    oi_df.to_csv(out_dir / "overnight_intraday_v3.csv", index=False, encoding="utf-8")
    pd.DataFrame(all_decomp).to_csv(out_dir / "decomp_v3.csv", index=False, encoding="utf-8")
    (out_dir / "audit_summary_v3.json").write_text(json.dumps(audit_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 汇总打印核心消融对比表
    print("\n" + "=" * 92)
    print("核心消融总表（全样本 921 天，net_10bp 压力情景 + 金融行业集中度）")
    print("=" * 92)
    m_all = metrics_df[(metrics_df["stage"] == "all") & (metrics_df["fee_scenario"] == "net_10bp")].merge(
        oi_df[["experiment", "model", "finance_weight_full_mean", "finance_weight_latest"]],
        on=["experiment", "model"], how="left",
    )
    m_val = metrics_df[(metrics_df["stage"] == "validation") & (metrics_df["fee_scenario"] == "net_10bp")][
        ["experiment", "model", "cum_return"]
    ].rename(columns={"cum_return": "val_cum"})
    m_seen = metrics_df[(metrics_df["stage"] == "seen") & (metrics_df["fee_scenario"] == "net_10bp")][
        ["experiment", "model", "cum_return"]
    ].rename(columns={"cum_return": "seen_cum"})
    m_hist = metrics_df[(metrics_df["stage"] == "all") & (metrics_df["fee_scenario"] == "net_histtax")][
        ["experiment", "model", "cum_return"]
    ].rename(columns={"cum_return": "histtax_all"})
    summary = m_all.merge(m_val, on=["experiment", "model"]).merge(m_seen, on=["experiment", "model"]).merge(m_hist, on=["experiment", "model"])

    disp = summary[[
        "experiment", "model", "cum_return", "histtax_all", "val_cum", "seen_cum",
        "sharpe_arith_rf0", "max_drawdown", "mean_half_turn",
        "finance_weight_full_mean", "finance_weight_latest",
    ]].copy()
    for c in ["cum_return", "histtax_all", "val_cum", "seen_cum", "max_drawdown", "mean_half_turn", "finance_weight_full_mean", "finance_weight_latest"]:
        disp[c] = (disp[c] * 100.0).map(lambda x: f"{x:+.2f}%" if c in ("cum_return", "histtax_all", "val_cum", "seen_cum") else f"{x:.2f}%")
    disp["sharpe_arith_rf0"] = disp["sharpe_arith_rf0"].map(lambda x: f"{x:.3f}")
    print(disp.to_string(index=False))
    print(f"\n全部 PRD 接口 3 文件已保存至: {out_dir}")


if __name__ == "__main__":
    main()
