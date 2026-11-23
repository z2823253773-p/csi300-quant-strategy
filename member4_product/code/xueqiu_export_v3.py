# -*- coding: utf-8 -*-
"""
组员4 v3.0 模块 2：主交付模型 hs300_clean M4 的雪球 30 只映射（含独立前 45 名缓冲带）
跟踪偏差回测与最新 2026-10-30 持仓/近 8 期调仓导出。
严格遵守 PRD 合规要求：保留既定历史记录，不将 2026-10-30 历史末期清单冒充 11 月新信号。
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

import paths as P
import xueqiu_30_tracking_backtest as xq

OUT_XQ = P.MEMBER4_DIR / "xueqiu"
OUT_RES = P.MEMBER4_DIR / "results"
OUT_XQ.mkdir(parents=True, exist_ok=True)
OUT_RES.mkdir(parents=True, exist_ok=True)


def build_independent_buf45_weights(
    score_df: pd.DataFrame,
    sched: pd.DataFrame,
    codes: pd.Index,
    tiered: bool = True,
    keep_k: int = 45,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    独立 30 只前 45 名保留缓冲带（上期目标持仓口径，与 PRD §2.4 规则完全一致）：
    每期选出 30 只后按当日得分降序（同分按代码升序），tiered=True 时前 10×4% + 后 20×3%。
    """
    prev: set[str] = set()
    rows = {}
    latest_records = []
    for pos, row in enumerate(sched.itertuples(index=False)):
        sig_dt = pd.Timestamp(row.signal_date)
        exec_dt = pd.Timestamp(row.execution_date)
        s_row = score_df.loc[sig_dt].dropna().sort_index().sort_values(ascending=False, kind="stable")
        kept = [c for c in s_row.index[:keep_k] if c in prev][:30]
        adds = [c for c in s_row.index if c not in kept][: 30 - len(kept)]
        chosen = sorted(kept + adds, key=lambda c: (-float(s_row[c]), c))
        assert len(chosen) == 30
        if tiered:
            w_vals = [0.04] * 10 + [0.03] * 20
        else:
            w_vals = [1.0 / 30.0] * 30
        rows[exec_dt] = pd.Series(w_vals, index=chosen)
        prev = set(chosen)
        if pos == len(sched) - 1:
            for rk, (c, wv) in enumerate(zip(chosen, w_vals), start=1):
                latest_records.append({
                    "排名": rk, "股票代码": c, "信号日": str(sig_dt.date()),
                    "执行日": str(exec_dt.date()), "目标权重": wv,
                    "目标权重(%)": round(wv * 100.0, 2), "综合得分": float(s_row[c]),
                })
    w_df = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=codes).fillna(0.0).sort_index()
    return w_df, latest_records


def main():
    proc = P.resolve_tushare_pool_processed("hs300")
    m2_hs = P.resolve_member2_tushare_pool("hs300")
    m3_res = P.resolve_member3_dir("v3") / "results"

    print("1. 加载 Tushare 沪深 300 3.0 账户执行引擎与 M4 信号 ...")
    mkt = xq.load_market_engine_inputs(proc)

    tw_clean = pd.read_csv(m2_hs / "clean_015" / "target_weights.csv", dtype={"stock_code": str}, parse_dates=["signal_date", "execution_date"])
    tw_m4 = tw_clean[tw_clean["model"] == "M4"].copy()
    score_m4 = pd.read_parquet(m2_hs / "clean_015" / "score_M4.parquet")
    score_m4.index = pd.to_datetime(score_m4.index)
    sched = tw_m4[["signal_date", "execution_date"]].drop_duplicates().sort_values("execution_date")

    tw_full = pd.read_csv(m2_hs / "signals" / "target_weights_v3.csv", dtype={"stock_code": str}, parse_dates=["signal_date", "execution_date"])
    tw_m0a = tw_full[tw_full["model"] == "M0a"].copy()

    print("2. 回测 M4（50只等权 / 硬截断30只分层 / 独立前45缓冲30只分层 / 独立前45缓冲30只等权）及 M0a 历史对照 ...")
    w_m4_50 = xq.build_mapping_weights(tw_m4, mkt["codes"], "top50_ew")
    w_m4_trunc30 = xq.build_mapping_weights(tw_m4, mkt["codes"], "xq30_tiered")
    w_m4_buf45_tiered, latest_30_recs = build_independent_buf45_weights(score_m4, sched, mkt["codes"], tiered=True, keep_k=45)
    w_m4_buf45_ew, _ = build_independent_buf45_weights(score_m4, sched, mkt["codes"], tiered=False, keep_k=45)

    w_m0a_50 = xq.build_mapping_weights(tw_m0a, mkt["codes"], "top50_ew")
    w_m0a_30 = xq.build_mapping_weights(tw_m0a, mkt["codes"], "xq30_tiered")

    all_rows = []
    nav_curves = {"hs300_intraday": mkt["hs300_nav"]}
    stages = [
        ("all", "2023-01-09", "2026-10-30"),
        ("validation", "2023-01-09", "2024-12-31"),
        ("seen", "2025-01-01", "2026-10-30"),
    ]

    groups = [
        ("hs300_M4_clean", [("top50_ew", w_m4_50), ("xq30_buf45_tiered", w_m4_buf45_tiered), ("xq30_buf45_ew", w_m4_buf45_ew), ("xq30_trunc_tiered", w_m4_trunc30)]),
        ("hs300_M0a_hist", [("top50_ew", w_m0a_50), ("xq30_tiered", w_m0a_30)]),
    ]

    for gname, scheme_list in groups:
        for fee in ["net_10bp", "net_histtax", "gross"]:
            frames = {sc: xq.replay_account(wdf, mkt, fee) for sc, wdf in scheme_list}
            ref_frame = frames["top50_ew"]
            for sc, fr in frames.items():
                if fee in ("net_10bp", "net_histtax"):
                    nav_curves[f"{gname}_{sc}_{fee}"] = fr["nav"]
                st_res = {}
                for st, s_dt, e_dt in stages:
                    m = xq.summarize_stage(fr, ref_frame, mkt["hs300_ret"], s_dt, e_dt)
                    st_res[st] = m
                    all_rows.append({"base_model": gname, "mapping_scheme": sc, "fee_scenario": fee, "stage": st, **m})
                err = abs((1.0 + st_res["validation"]["cum_return"]) * (1.0 + st_res["seen"]["cum_return"]) - 1.0 - st_res["all"]["cum_return"])
                assert err < 1e-10, f"Chaining failed: {err}"

    res_df = pd.DataFrame(all_rows)
    res_df.to_csv(OUT_XQ / "xueqiu_30_tracking_backtest.csv", index=False, encoding="utf-8")
    nav_df = pd.DataFrame(nav_curves)
    nav_df.index.name = "date"
    nav_df.to_csv(OUT_XQ / "xueqiu_30_tracking_nav.csv", encoding="utf-8")

    print("3. 导出 M4 最新一期（2026-10-30）50 只与雪球 30 只前 45 缓冲清单及近 8 期调仓记录 ...")
    panel = pd.read_parquet(
        proc / "clean_daily_panel.parquet",
        columns=["trade_date", "stock_code", "stock_name", "sw_l1_name", "bp", "ep", "close", "amount"],
    )
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])
    latest_exec = pd.Timestamp(sched["execution_date"].iloc[-1])
    latest_sig = pd.Timestamp(sched["signal_date"].iloc[-1])
    p_sig = panel[panel["trade_date"] == latest_sig].set_index("stock_code")
    name_map = panel.sort_values("trade_date").dropna(subset=["stock_name"]).groupby("stock_code")["stock_name"].last().to_dict()
    ind_map = panel.sort_values("trade_date").dropna(subset=["sw_l1_name"]).groupby("stock_code")["sw_l1_name"].last().to_dict()

    facs = {}
    for fn in ["bp", "ep", "lowvol_60", "lowturn_20"]:
        df = pd.read_parquet(m2_hs / "signals" / f"factor_{fn}.parquet")
        df.index = pd.to_datetime(df.index)
        facs[fn] = df

    ow_m4 = pd.read_parquet(m3_res / "open_weights_hs300_clean_M4.parquet")
    ow_m4.index = pd.to_datetime(ow_m4.index)

    latest_tw50 = tw_m4[tw_m4["execution_date"] == latest_exec].sort_values(["score", "stock_code"], ascending=[False, True])
    rows_50 = []
    for rk, (_, r) in enumerate(latest_tw50.iterrows(), start=1):
        c = r["stock_code"]
        rows_50.append({
            "排名": rk,
            "股票代码": c,
            "股票名称": p_sig.loc[c, "stock_name"] if c in p_sig.index else name_map.get(c, ""),
            "申万一级行业": p_sig.loc[c, "sw_l1_name"] if c in p_sig.index else ind_map.get(c, "未分类"),
            "信号日": str(latest_sig.date()),
            "执行日": str(latest_exec.date()),
            "目标权重": float(r["target_weight"]),
            "目标权重(%)": round(float(r["target_weight"]) * 100.0, 2),
            "回测开盘实际权重(%)": round(float(ow_m4.loc[latest_exec, c]) * 100.0, 4) if c in ow_m4.columns else 0.0,
            "M4综合得分": float(r["score"]),
            "BP暴露": float(facs["bp"].loc[latest_sig, c]),
            "EP暴露": float(facs["ep"].loc[latest_sig, c]),
            "LowVol60暴露": float(facs["lowvol_60"].loc[latest_sig, c]),
            "LowTurn20暴露": float(facs["lowturn_20"].loc[latest_sig, c]),
            "信号日收盘价(元)": float(p_sig.loc[c, "close"]) if c in p_sig.index else np.nan,
        })
    df_50 = pd.DataFrame(rows_50)
    df_50.to_csv(OUT_XQ / "M4_最新持仓_2026-10-30_完整50只.csv", index=False, encoding="utf-8-sig")

    for rec in latest_30_recs:
        c = rec["股票代码"]
        rec["股票名称"] = p_sig.loc[c, "stock_name"] if c in p_sig.index else name_map.get(c, "")
        rec["申万一级行业"] = p_sig.loc[c, "sw_l1_name"] if c in p_sig.index else ind_map.get(c, "未分类")
        rec["BP暴露"] = float(facs["bp"].loc[latest_sig, c])
        rec["EP暴露"] = float(facs["ep"].loc[latest_sig, c])
        rec["LowVol60暴露"] = float(facs["lowvol_60"].loc[latest_sig, c])
        rec["LowTurn20暴露"] = float(facs["lowturn_20"].loc[latest_sig, c])
    df_30 = pd.DataFrame(latest_30_recs)
    df_30.to_csv(OUT_XQ / "M4_最新持仓_2026-10-30_雪球30只分层_前45缓冲.csv", index=False, encoding="utf-8-sig")

    # 近 8 期调仓记录（对账 member3_v3 turnover_v3.csv）
    tr_v3 = pd.read_csv(m3_res / "turnover_v3.csv", parse_dates=["execution_date"])
    tr_m4 = tr_v3[(tr_v3["experiment"] == "hs300_clean") & (tr_v3["model"] == "M4") & (tr_v3["fee_scenario"] == "net_10bp")].sort_values("execution_date").set_index("execution_date")
    last9 = list(sched["execution_date"].iloc[-9:])
    sig_lookup = dict(zip(sched["execution_date"], sched["signal_date"]))
    rec8 = []
    for k in range(1, len(last9)):
        prev_d, cur_d = pd.Timestamp(last9[k - 1]), pd.Timestamp(last9[k])
        s_prev = set(tw_m4[tw_m4["execution_date"] == prev_d]["stock_code"])
        s_cur = set(tw_m4[tw_m4["execution_date"] == cur_d]["stock_code"])
        buys = sorted(s_cur - s_prev)
        sells = sorted(s_prev - s_cur)
        rec8.append({
            "调仓执行日": str(cur_d.date()),
            "信号生成日": str(pd.Timestamp(sig_lookup[cur_d]).date()),
            "单边换手(%)": round(float(tr_m4.loc[cur_d, "half_turn"]) * 100.0, 2),
            "买入只数": len(buys),
            "卖出只数": len(sells),
            "新调入标的": "、".join(f"{name_map.get(c, c)}({c})" for c in buys) if buys else "无（全保留）",
            "全卖出标的": "、".join(f"{name_map.get(c, c)}({c})" for c in sells) if sells else "无（全保留）",
        })
    df_rec8 = pd.DataFrame(rec8)
    df_rec8.to_csv(OUT_XQ / "M4_近8期调仓记录.csv", index=False, encoding="utf-8-sig")

    ind_dist50 = df_50.groupby("申万一级行业").agg(股票数=("股票代码", "count"), 权重=("目标权重", "sum")).sort_values("权重", ascending=False).reset_index()
    ind_dist50.to_csv(OUT_RES / "latest_industry_distribution_v3.csv", index=False, encoding="utf-8-sig")

    summary = {
        "model": "hs300_clean_M4",
        "latest_signal_date": str(latest_sig.date()),
        "latest_execution_date": str(latest_exec.date()),
        "xueqiu_code": "ZH3689205",
        "xueqiu_url": "https://www.xueqiu.com/P/ZH3689205",
        "compliance_note": "数据截点为 2026-10-30；ZH3689205 既有 M0a 历史记录完整保留，仅在规则冻结后基于新交易日行情操作时才记为前瞻模拟。",
        "top5_holdings_50": df_50.head(5)[["排名", "股票代码", "股票名称", "申万一级行业", "M4综合得分"]].to_dict(orient="records"),
        "industry_distribution_50": ind_dist50.to_dict(orient="records"),
        "last8_rebalances": rec8,
        "tracking_backtest_all_net10bp": res_df[(res_df["stage"] == "all") & (res_df["fee_scenario"] == "net_10bp")].to_dict(orient="records"),
        "tracking_backtest_all_histtax": res_df[(res_df["stage"] == "all") & (res_df["fee_scenario"] == "net_histtax")].to_dict(orient="records"),
    }
    (OUT_RES / "xueqiu_summary_v3.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== M4 与 M0a 雪球 30 只映射跟踪偏差汇总（全期 921 天，net_10bp）=====")
    view = res_df[(res_df["stage"] == "all") & (res_df["fee_scenario"] == "net_10bp")][
        ["base_model", "mapping_scheme", "cum_return", "ann_geom", "sharpe_arith_rf0", "max_drawdown", "mean_half_turn", "cum_diff_vs_top50", "tracking_error_vs_top50", "daily_corr_vs_top50"]
    ].copy()
    for c in ["cum_return", "ann_geom", "max_drawdown", "mean_half_turn", "cum_diff_vs_top50", "tracking_error_vs_top50"]:
        view[c] = (view[c] * 100).map(lambda x: f"{x:+.2f}%" if c in ("cum_return", "ann_geom", "cum_diff_vs_top50") else f"{x:.2f}%")
    view["sharpe_arith_rf0"] = view["sharpe_arith_rf0"].map(lambda x: f"{x:.3f}")
    view["daily_corr_vs_top50"] = view["daily_corr_vs_top50"].map(lambda x: f"{x:.4f}")
    print(view.to_string(index=False))
    print("\n===== M4 近 8 期调仓换手 =====")
    print(df_rec8[["调仓执行日", "单边换手(%)", "买入只数", "卖出只数"]].to_string(index=False))


if __name__ == "__main__":
    main()
