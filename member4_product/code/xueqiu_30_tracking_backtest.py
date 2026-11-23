# -*- coding: utf-8 -*-
"""
组员4 Step 1 必做回测：雪球 30 只分层权重（前10×4% + 后20×3%）相对 50 只等权的跟踪偏差回测
严格沿用 PRD §4 3.0 统一账户执行引擎：
- 仅用开盘已知信息判定买卖资格（tradestatus & open_quote_observed & open>0 + 逐日 is_st + 板块开盘触限 19.5%/4.5%/9.5%）
- 卖出允许已出池或变 ST 持仓在非开盘跌停时卖出
- 同时输出 gross、net_10bp（固定卖出 10bp 印花税）与 net_histtax（2023-08-28 后印花税减半至 5bp）三套费率情景
- 唯一逐日净值分段法，断言 (1+r_val)*(1+r_seen)-1 == r_all 误差 < 1e-10，断言现金全程 >= 0
- 支持 CLI 参数切换任意模型，待 Step 4 定案主模型后可一键重跑：
    .venv/bin/python code/xueqiu_30_tracking_backtest.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd

import paths as P

STAMP_HALVING_DATE = pd.Timestamp("2023-08-28")


def load_market_engine_inputs(proc_dir: Path) -> dict:
    opens = pd.read_parquet(proc_dir / "matrix_open_hfq.parquet").sort_index()
    close = pd.read_parquet(proc_dir / "matrix_close_hfq.parquet").sort_index().ffill()
    opens.index = pd.to_datetime(opens.index)
    close.index = pd.to_datetime(close.index)
    codes = opens.columns

    panel = pd.read_parquet(
        proc_dir / "clean_daily_panel.parquet",
        columns=[
            "stock_code", "trade_date", "tradestatus", "is_st",
            "open", "preclose", "in_index_universe", "is_new_stock",
        ],
    )
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    def wide(key: str) -> pd.DataFrame:
        return panel.pivot(index="trade_date", columns="stock_code", values=key).reindex(
            index=opens.index, columns=codes
        )

    open_obs = pd.read_parquet(proc_dir / "matrix_open_quote_observed.parquet").sort_index()
    open_obs.index = pd.to_datetime(open_obs.index)
    open_obs = open_obs.reindex(index=opens.index, columns=codes).fillna(False).astype(bool)

    state = wide("tradestatus").astype(str).isin(["1", "1.0", "True"])
    st = wide("is_st").fillna(False).astype(bool)
    raw_open = wide("open")
    raw_preclose = wide("preclose")
    ok = state & open_obs & raw_open.gt(0)

    is_chinext_star = np.asarray(codes.str.startswith(("688", "300", "301", "302")), dtype=bool)
    threshold = np.where(is_chinext_star[None, :], 0.195, np.where(st.to_numpy(), 0.045, 0.095))
    move = (raw_open / raw_preclose - 1.0).to_numpy(dtype=float)

    in_univ = wide("in_index_universe").fillna(False).astype(bool).to_numpy()
    is_new = wide("is_new_stock").fillna(False).astype(bool).to_numpy()
    ok_arr = ok.to_numpy()

    buy_ok = pd.DataFrame(
        ok_arr & in_univ & (~st.to_numpy()) & (~is_new) & ~(move >= threshold),
        index=opens.index, columns=codes,
    )
    sell_ok = pd.DataFrame(
        ok_arr & ~(move <= -threshold),
        index=opens.index, columns=codes,
    )

    bench = pd.read_parquet(proc_dir / "benchmark_daily.parquet")
    b300 = bench[bench["benchmark_code"].astype(str) == "000300.SH"].copy()
    b300["trade_date"] = pd.to_datetime(b300["trade_date"])
    b300 = b300.sort_values("trade_date").set_index("trade_date")
    cal_df = b300.loc["2023-01-09":"2026-10-30"].copy()
    cal = cal_df.index
    assert len(cal) == 921, f"Expected 921 calendar days, got {len(cal)}"

    hs_ret = cal_df["benchmark_close"].pct_change()
    hs_ret.iloc[0] = cal_df["benchmark_close"].iloc[0] / cal_df["benchmark_open"].iloc[0] - 1.0
    hs_nav = (1.0 + hs_ret).cumprod()

    return {
        "opens": opens,
        "close": close,
        "codes": codes,
        "buy_ok": buy_ok,
        "sell_ok": sell_ok,
        "calendar": cal,
        "hs300_ret": hs_ret,
        "hs300_nav": hs_nav,
    }


def build_mapping_weights(
    tw_df: pd.DataFrame,
    codes: pd.Index,
    scheme: str,
    score_matrix: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    从 50 只目标持仓构建不同映射方案的权重宽表（index=execution_date, columns=codes）：
    - top50_ew: 保留原始 50 只目标权重（通常 2%×50）
    - xq30_tiered: 按信号日得分降序（同分按代码升序）取前 30 只，前10×4% + 后20×3%
    - xq30_ew: 按信号日得分降序取前 30 只，各 1/30 等权
    """
    rows = {}
    has_score = "score" in tw_df.columns and tw_df["score"].notna().all()

    for exec_dt, grp in tw_df.groupby("execution_date"):
        g = grp.copy()
        if not has_score:
            if score_matrix is not None:
                sig_dt = pd.Timestamp(g["signal_date"].iloc[0])
                s_row = score_matrix.loc[sig_dt]
                g["score"] = g["stock_code"].map(s_row)
            else:
                # 若无 score 列，按原始行顺序赋递减序号
                g["score"] = np.arange(len(g), 0, -1, dtype=float)
        g = g.sort_values(["score", "stock_code"], ascending=[False, True], kind="mergesort")

        if scheme == "top50_ew":
            w_s = g.set_index("stock_code")["target_weight"]
        elif scheme == "xq30_tiered":
            top30 = g.head(30).copy()
            n = len(top30)
            if n == 30:
                w_vals = np.array([0.04] * 10 + [0.03] * 20, dtype=float)
            else:
                w_vals = np.full(n, 1.0 / n, dtype=float)
            w_s = pd.Series(w_vals, index=top30["stock_code"].values)
        elif scheme == "xq30_ew":
            top30 = g.head(30).copy()
            w_s = pd.Series(1.0 / len(top30), index=top30["stock_code"].values)
        else:
            raise ValueError(f"Unknown scheme: {scheme}")

        assert abs(float(w_s.sum()) - 1.0) < 1e-8, f"Weights sum != 1 on {exec_dt}: {w_s.sum()}"
        rows[pd.Timestamp(exec_dt)] = w_s

    w_df = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=codes).fillna(0.0).sort_index()
    return w_df


def replay_account(
    w_rebal: pd.DataFrame,
    mkt: dict,
    fee_scenario: str,
) -> pd.DataFrame:
    """严格遵循 PRD §4 与 portfolio.py 的 3.0 账户撮合引擎。"""
    cal = mkt["calendar"]
    codes = mkt["codes"]
    opens = mkt["opens"]
    close = mkt["close"]
    buying = mkt["buy_ok"].reindex(index=cal).to_numpy()
    selling = mkt["sell_ok"].reindex(index=cal).to_numpy()
    weights_by_day = w_rebal.reindex(index=cal)

    cash = 1.0
    shares = np.zeros(len(codes), dtype=float)
    history = []

    for pos, day in enumerate(cal):
        opening = opens.loc[day].to_numpy(dtype=float)
        mark = close.loc[day].to_numpy(dtype=float)
        held = shares > 0
        assert np.isfinite(opening[held]).all() and np.isfinite(mark[held]).all(), f"NaN held price on {day}"
        px = np.where(np.isfinite(opening) & (opening > 0), opening, 1.0)
        asset = cash + float(shares @ px)
        w = weights_by_day.iloc[pos]
        turn = np.nan
        cost_ratio = 0.0

        if w.notna().any():
            value = shares * px
            desired = w.to_numpy(dtype=float) * asset
            sell = np.maximum(0.0, value - desired) * selling[pos]

            if fee_scenario == "gross":
                stamp = 0.0
                comm = 0.0
                slip = 0.0
                sell_cost = 0.0
            else:
                comm = 0.0003
                slip = 0.001
                stamp = 0.0005 if (fee_scenario == "net_histtax" and day >= STAMP_HALVING_DATE) else 0.001
                # 与 portfolio.py 一致：卖出滑点+佣金+印花税
                sell_cost = stamp + (1.0 - stamp) * (comm + slip)

            cash += float(sell.sum()) * (1.0 - sell_cost)
            shares = np.maximum(shares - sell / px, 0.0)

            need = np.maximum(0.0, desired - value) * buying[pos]
            total = float(need.sum()) * (1.0 + comm)
            paid = need * min(1.0, max(0.0, cash) / total) if total > 0 else need
            cash -= float(paid.sum()) * (1.0 + comm)
            assert cash >= -1e-10, f"Negative cash {cash} on {day}"
            cash = max(0.0, cash)
            shares += paid / (px * (1.0 + slip))
            turn = (float(paid.sum()) + float(sell.sum())) / asset / 2.0
            cost_ratio = (float(sell.sum()) * sell_cost + float(paid.sum()) * (comm + slip / (1.0 + slip))) / asset

        nav = cash + float(shares @ np.nan_to_num(mark))
        history.append((day, nav, turn, cost_ratio))

    return pd.DataFrame(history, columns=["date", "nav", "half_turn", "cost_ratio"]).set_index("date")


def summarize_stage(
    frame: pd.DataFrame,
    ref_frame: pd.DataFrame,
    hs_ret: pd.Series,
    start: str,
    stop: str,
) -> dict:
    ret = frame["nav"].pct_change()
    ret.iloc[0] = frame["nav"].iloc[0] - 1.0
    ref_ret = ref_frame["nav"].pct_change()
    ref_ret.iloc[0] = ref_frame["nav"].iloc[0] - 1.0

    r = ret.loc[start:stop]
    rr = ref_ret.loc[start:stop]
    hr = hs_ret.loc[start:stop]
    n = len(r)

    wealth = (1.0 + r).cumprod()
    ref_wealth = (1.0 + rr).cumprod()
    hs_wealth = (1.0 + hr).cumprod()

    cum_ret = float(wealth.iloc[-1] - 1.0)
    ref_cum = float(ref_wealth.iloc[-1] - 1.0)
    hs_cum = float(hs_wealth.iloc[-1] - 1.0)

    ann_geom = float(wealth.iloc[-1] ** (252.0 / n) - 1.0)
    ref_ann = float(ref_wealth.iloc[-1] ** (252.0 / n) - 1.0)
    hs_ann = float(hs_wealth.iloc[-1] ** (252.0 / n) - 1.0)

    ann_vol = float(r.std(ddof=1) * np.sqrt(252.0))
    sharpe_arith = float((r.mean() / r.std(ddof=1)) * np.sqrt(252.0)) if r.std(ddof=1) > 0 else 0.0
    geom_over_vol = float(ann_geom / ann_vol) if ann_vol > 0 else 0.0
    max_dd = float((wealth / wealth.cummax().clip(lower=1.0) - 1.0).min())

    diff_daily = r - rr
    te_vs_50 = float(diff_daily.std(ddof=1) * np.sqrt(252.0))
    corr_vs_50 = float(r.corr(rr))
    max_abs_daily_diff = float(diff_daily.abs().max())
    ex_hs = r - hr
    te_hs = float(ex_hs.std(ddof=1) * np.sqrt(252.0))
    ir_hs = float((ex_hs.mean() / ex_hs.std(ddof=1)) * np.sqrt(252.0)) if ex_hs.std(ddof=1) > 0 else 0.0

    turns = frame["half_turn"].loc[start:stop].dropna()
    mean_half_turn = float(turns.mean()) if len(turns) > 0 else 0.0
    ann_half_turn = float(turns.sum() * (252.0 / n))

    return {
        "n_days": int(n),
        "cum_return": cum_ret,
        "ann_geom": ann_geom,
        "ann_vol": ann_vol,
        "sharpe_arith_rf0": sharpe_arith,
        "geom_over_vol": geom_over_vol,
        "max_drawdown": max_dd,
        "mean_half_turn": mean_half_turn,
        "ann_half_turn": ann_half_turn,
        "excess_vs_hs300_cum": cum_ret - hs_cum,
        "te_vs_hs300": te_hs,
        "ir_vs_hs300": ir_hs,
        "cum_diff_vs_top50": cum_ret - ref_cum,
        "ann_diff_vs_top50": ann_geom - ref_ann,
        "tracking_error_vs_top50": te_vs_50,
        "daily_corr_vs_top50": corr_vs_50,
        "max_abs_daily_diff_vs_top50": max_abs_daily_diff,
    }


def run_for_model(
    model_label: str,
    tw_df: pd.DataFrame,
    mkt: dict,
    score_matrix: Optional[pd.DataFrame] = None,
) -> tuple[list[dict], dict[str, pd.Series]]:
    rows = []
    nav_curves: dict[str, pd.Series] = {}
    schemes = ["top50_ew", "xq30_tiered", "xq30_ew"]
    fee_scenarios = ["net_10bp", "net_histtax", "gross"]
    stages = [
        ("all", "2023-01-09", "2026-10-30"),
        ("validation", "2023-01-09", "2024-12-31"),
        ("seen", "2025-01-01", "2026-10-30"),
    ]

    w_map = {sc: build_mapping_weights(tw_df, mkt["codes"], sc, score_matrix) for sc in schemes}

    for fee in fee_scenarios:
        frames = {sc: replay_account(w_map[sc], mkt, fee) for sc in schemes}
        ref_frame = frames["top50_ew"]

        for sc in schemes:
            fr = frames[sc]
            if fee in ("net_10bp", "net_histtax"):
                nav_curves[f"{model_label}_{sc}_{fee}"] = fr["nav"]
            stage_res = {}
            for st, s_dt, e_dt in stages:
                metrics = summarize_stage(fr, ref_frame, mkt["hs300_ret"], s_dt, e_dt)
                stage_res[st] = metrics
                rows.append({
                    "base_model": model_label,
                    "mapping_scheme": sc,
                    "fee_scenario": fee,
                    "stage": st,
                    **metrics,
                })
            # 断言三段连乘闭环
            r_all = stage_res["all"]["cum_return"]
            r_val = stage_res["validation"]["cum_return"]
            r_seen = stage_res["seen"]["cum_return"]
            err = abs((1.0 + r_val) * (1.0 + r_seen) - 1.0 - r_all)
            assert err < 1e-10, f"Chaining assertion failed for {model_label}/{sc}/{fee}: {err}"

    return rows, nav_curves


def main():
    parser = argparse.ArgumentParser(description="雪球 30 只分层权重映射跟踪偏差回测（3.0 账户引擎）")
    parser.add_argument("--data", type=Path, default=None, help="组员1数据3.0 processed/ 目录")
    parser.add_argument("--targets", type=Path, default=None, help="自定义 target_weights CSV（可选，用于 Step 4 定案模型一键重跑）")
    parser.add_argument("--model", type=str, default=None, help="自定义 CSV 中的 model 名称")
    parser.add_argument("--out-dir", type=Path, default=P.MEMBER4_DIR / "xueqiu", help="输出目录")
    args = parser.parse_args()

    proc_dir = P.resolve_data_processed(args.data)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"1. 加载 3.0 账户执行引擎底层数据: {proc_dir}")
    mkt = load_market_engine_inputs(proc_dir)
    print(f"   估值日历: {len(mkt['calendar'])} 天 ({mkt['calendar'][0].date()} ~ {mkt['calendar'][-1].date()})")
    print(f"   沪深 300 intraday 全期净值: {mkt['hs300_nav'].iloc[-1]:.6f} ({(mkt['hs300_nav'].iloc[-1]-1)*100:+.2f}%)")

    all_rows = []
    all_navs = {"hs300_intraday": mkt["hs300_nav"]}

    if args.targets is not None:
        tw = pd.read_csv(args.targets, parse_dates=["signal_date", "execution_date"])
        model_name = args.model or str(tw["model"].iloc[0])
        sub = tw[tw["model"] == model_name].copy()
        print(f"2. 回测自定义模型 {model_name} ...")
        rows, navs = run_for_model(model_name, sub, mkt)
        all_rows.extend(rows)
        all_navs.update(navs)
    else:
        # Step 1 默认同时回测：
        # (1) M0a: member2_v2 baseline（5日无缓冲，当前雪球 ZH3689205 实盘对应模型）
        # (2) M1:  3.0 common_base（5日+前75缓冲，当前 3.0 最强基准标杆，用 score_baseline 排序）
        print("2. 回测 M0a（当前雪球 ZH3689205 对应的 5 日无缓冲基准）...")
        tw_v2 = pd.read_csv(P.M2_SIG / "target_weights.csv", parse_dates=["signal_date", "execution_date"])
        tw_m0a = tw_v2[tw_v2["model"] == "baseline"].copy()
        rows_m0a, navs_m0a = run_for_model("M0a_baseline_5d", tw_m0a, mkt)
        all_rows.extend(rows_m0a)
        all_navs.update(navs_m0a)

        print("3. 回测 M1（3.0 共同池基准 + 前75缓冲，按 score_baseline 排序取前30）...")
        tw_a101 = pd.read_csv(P.ALPHA101_DIR / "target_weights.csv", parse_dates=["signal_date", "execution_date"])
        tw_m1 = tw_a101[tw_a101["model"] == "common_base"].copy()
        score_base = pd.read_parquet(P.M2_SIG / "score_baseline.parquet")
        score_base.index = pd.to_datetime(score_base.index)
        rows_m1, navs_m1 = run_for_model("M1_common_base_5d_buf75", tw_m1, mkt, score_matrix=score_base)
        all_rows.extend(rows_m1)
        all_navs.update(navs_m1)

    res_df = pd.DataFrame(all_rows)
    csv_path = out_dir / "xueqiu_30_tracking_backtest.csv"
    res_df.to_csv(csv_path, index=False, encoding="utf-8")

    nav_df = pd.DataFrame(all_navs)
    nav_df.index.name = "date"
    nav_path = out_dir / "xueqiu_30_tracking_nav.csv"
    nav_df.to_csv(nav_path, encoding="utf-8")

    summary = {
        "data_source": str(proc_dir),
        "calendar_days": int(len(mkt["calendar"])),
        "hs300_intraday_terminal_nav": float(mkt["hs300_nav"].iloc[-1]),
        "hs300_intraday_cum_return": float(mkt["hs300_nav"].iloc[-1] - 1.0),
        "tiered_rule": "前10只各4% + 第11-30只各3%（合计100%整数权重，适配雪球模拟盘30只标的上限）",
        "key_all_net_10bp": res_df[(res_df["stage"] == "all") & (res_df["fee_scenario"] == "net_10bp")].to_dict(orient="records"),
        "key_all_net_histtax": res_df[(res_df["stage"] == "all") & (res_df["fee_scenario"] == "net_histtax")].to_dict(orient="records"),
    }
    json_path = out_dir / "xueqiu_30_tracking_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 雪球 30 只分层映射跟踪偏差汇总（全期 921 天，net_10bp 压力情景）=====")
    view = res_df[(res_df["stage"] == "all") & (res_df["fee_scenario"] == "net_10bp")][
        [
            "base_model", "mapping_scheme", "cum_return", "ann_geom",
            "sharpe_arith_rf0", "max_drawdown", "mean_half_turn",
            "cum_diff_vs_top50", "tracking_error_vs_top50", "daily_corr_vs_top50",
        ]
    ].copy()
    for col in ["cum_return", "ann_geom", "max_drawdown", "mean_half_turn", "cum_diff_vs_top50", "tracking_error_vs_top50"]:
        view[col] = (view[col] * 100.0).map(lambda x: f"{x:+.2f}%" if "diff" in col or "ret" in col or "ann" in col else f"{x:.2f}%")
    view["sharpe_arith_rf0"] = view["sharpe_arith_rf0"].map(lambda x: f"{x:.3f}")
    view["daily_corr_vs_top50"] = view["daily_corr_vs_top50"].map(lambda x: f"{x:.4f}")
    print(view.to_string(index=False))
    print(f"\n已保存:\n  - {csv_path}\n  - {nav_path}\n  - {json_path}")


if __name__ == "__main__":
    main()
