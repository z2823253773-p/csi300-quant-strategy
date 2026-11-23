# -*- coding: utf-8 -*-
"""
组员3：模型 3.0 双股票池账户回测引擎（PRD 接口3）

三个实验，按 pool / experiment / model / fee_scenario 标识：
- hs300_clean：沪深300 不含015干净共同池，M1/M2/M3b/M4/M5。
- hs300_alpha：沪深300 含015共同池，只回放 M1/M3a 做 Alpha 专项。
- zz500：中证500 八模型 M0a-M5。
费用情景 gross / net_10bp / net_histtax；毛净同成交限制；基准首日 intraday。
"""
import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--data", default=str(ROOT / "Tushare_双股票池完整数据与代码" / "tushare_data"))
ap.add_argument("--m2", default=str(ROOT / "member2_tushare"))
ap.add_argument("--out", default=str(ROOT / "member3_v3"))
args = ap.parse_args()
DATA, M2, OUT = Path(args.data), Path(args.m2), Path(args.out)

COMMISSION = 0.0003
SLIPPAGE = 0.001
STAMP_FULL = 0.001
STAMP_HALF = 0.0005
TAX_CUT = pd.Timestamp("2023-08-28")
SCENARIOS = ["gross", "net_10bp", "net_histtax"]

EXPERIMENTS = [
    ("hs300", "hs300_clean", "000300.SH",
     r"hs300\clean_015\target_weights.csv",
     ["M1", "M2", "M3b", "M4", "M5"]),
    ("hs300", "hs300_alpha", "000300.SH",
     r"hs300\signals\target_weights_v3.csv",
     ["M1", "M3a"]),
    ("zz500", "zz500", "000905.SH",
     r"zz500\signals\target_weights_v3.csv",
     ["M0a", "M0b", "M1", "M2", "M3a", "M3b", "M4", "M5"]),
]


def fee_rates(scenario, d):
    if scenario == "gross":
        return 0.0, 0.0, 0.0
    if scenario == "net_10bp":
        return COMMISSION, SLIPPAGE, STAMP_FULL
    stamp = STAMP_FULL if pd.Timestamp(d) < TAX_CUT else STAMP_HALF
    return COMMISSION, SLIPPAGE, stamp


def board_threshold(code, is_st_flag):
    num = code.split(".")[0]
    if num.startswith(("688", "300", "301", "302")):
        return 0.195
    if is_st_flag:
        return 0.045
    return 0.095


def load_pool(pool, bcode):
    proc = DATA / pool / "processed"
    open_hfq = pd.read_parquet(proc / "matrix_open_hfq.parquet").sort_index()
    close_hfq = pd.read_parquet(proc / "matrix_close_hfq.parquet").sort_index().ffill()
    panel_cols = ["trade_date", "stock_code", "open", "preclose", "tradestatus",
                  "is_st", "is_new_stock", "in_index_universe", "sw_l1_name"]
    panel = pd.read_parquet(proc / "clean_daily_panel.parquet", columns=panel_cols)
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    def pivot(col):
        return panel.pivot(index="trade_date", columns="stock_code", values=col).sort_index()

    open_raw, preclose = pivot("open"), pivot("preclose")
    tradestatus = pivot("tradestatus")
    st_df = pivot("is_st").fillna(False).astype(bool)
    new_df = pivot("is_new_stock").fillna(False).astype(bool)
    idx_df = pivot("in_index_universe").fillna(False).astype(bool)

    tradable_status = tradestatus.astype(str).isin(["1", "1.0", "True"])
    open_valid = open_raw.notna() & (open_raw > 0)
    open_ret = open_raw / preclose - 1.0
    limit_up = pd.DataFrame(False, index=open_ret.index, columns=open_ret.columns)
    limit_down = pd.DataFrame(False, index=open_ret.index, columns=open_ret.columns)
    for c in open_ret.columns:
        th = board_threshold(c, bool(st_df[c].any()))
        limit_up[c] = open_ret[c] >= th
        limit_down[c] = open_ret[c] <= -th
    can_buy = tradable_status & open_valid & idx_df & ~st_df & ~new_df & ~limit_up
    can_sell = tradable_status & open_valid & ~limit_down

    bench = pd.read_parquet(proc / "benchmark_daily.parquet")
    b = bench[bench.benchmark_code == bcode].copy()
    b["trade_date"] = pd.to_datetime(b["trade_date"])
    b = b.set_index("trade_date").sort_index()
    ind_map = panel.pivot(index="trade_date", columns="stock_code", values="sw_l1_name")
    return dict(open_hfq=open_hfq, close_hfq=close_hfq, can_buy=can_buy, can_sell=can_sell,
                bench=b, ind_map=ind_map)


def read_targets(rel_path, models):
    tw = pd.read_csv(M2 / rel_path)
    tw["execution_date"] = pd.to_datetime(tw["execution_date"])
    out = {}
    for model in models:
        sub = tw[tw.model == model]
        out[model] = {ed: dict(zip(g.stock_code, g.target_weight))
                      for ed, g in sub.groupby("execution_date")}
    return out


def run_account(target_map, fee_scenario, ctx):
    open_hfq, close_hfq = ctx["open_hfq"], ctx["close_hfq"]
    can_buy, can_sell = ctx["can_buy"], ctx["can_sell"]
    exec_dates = sorted(target_map.keys())
    start, end = exec_dates[0], exec_dates[-1]
    dates = close_hfq.index[(close_hfq.index >= start) & (close_hfq.index <= end)]

    cash, shares, prev_close_asset = 1.0, {}, 1.0
    nav, open_w_rows, ledger, turnover_rows = {}, {}, [], []

    for d in dates:
        o_row, c_row = open_hfq.loc[d], close_hfq.loc[d]

        def px(row, c):
            v = row.get(c, np.nan)
            return v if np.isfinite(v) else np.nan

        open_before = cash
        for c, s in shares.items():
            p = px(o_row, c)
            if np.isfinite(p):
                open_before += s * p
        overnight_pnl = open_before - prev_close_asset
        cost = 0.0
        sell_gross = buy_gross = blocked_buy = blocked_sell = 0.0

        if d in target_map:
            tgt = target_map[d]
            comm, slip, stamp = fee_rates(fee_scenario, d)
            target_val = {c: open_before * w for c, w in tgt.items()}

            for c in list(shares.keys()):
                p = px(o_row, c)
                if not np.isfinite(p):
                    continue
                cur = shares[c] * p
                sell_amt = None
                if c not in tgt:
                    sell_amt = cur
                elif cur > target_val[c]:
                    sell_amt = cur - target_val[c]
                if sell_amt is not None and sell_amt > 0:
                    if bool(can_sell.loc[d, c]):
                        sell_gross += sell_amt
                        if comm or slip or stamp:
                            sc = sell_amt * slip + sell_amt * (1 - slip) * (comm + stamp)
                            cost += sc
                            cash += sell_amt - sc
                        else:
                            cash += sell_amt
                        if c not in tgt:
                            del shares[c]
                        else:
                            shares[c] = target_val[c] / p
                    else:
                        blocked_sell += sell_amt

            buys = []
            for c, w in tgt.items():
                p = px(o_row, c)
                if not np.isfinite(p):
                    continue
                cur = shares.get(c, 0.0) * p
                need = target_val[c] - cur
                if need > 0:
                    if bool(can_buy.loc[d, c]):
                        buys.append((c, p, need))
                    else:
                        blocked_buy += need
            total_need = sum(b[2] for b in buys)
            scale = 1.0
            if total_need > 0 and comm:
                need_cash = total_need * (1 + comm)
                if cash < need_cash:
                    scale = cash / need_cash
            for c, p, need in buys:
                amt = need * scale
                if amt <= 0:
                    continue
                buy_gross += amt
                if comm or slip:
                    cost += amt * (comm + slip)
                    cash -= amt * (1 + comm)
                    shares[c] = shares.get(c, 0.0) + amt / (p * (1 + slip))
                else:
                    cash -= amt
                    shares[c] = shares.get(c, 0.0) + amt / p

            half_turn = (sell_gross + buy_gross) / 2.0 / open_before if open_before > 0 else 0.0
            turnover_rows.append(dict(execution_date=d, fee_scenario=fee_scenario,
                                     buy_weight=buy_gross / open_before,
                                     sell_weight=sell_gross / open_before,
                                     half_turn=half_turn, cost_ratio=cost / open_before,
                                     blocked_buy_weight=blocked_buy / open_before,
                                     blocked_sell_weight=blocked_sell / open_before))

        open_after = open_before - cost
        ow_total, ow = cash, {}
        for c, s in shares.items():
            p = px(o_row, c)
            if np.isfinite(p):
                ow[c] = s * p
                ow_total += ow[c]
        open_w_rows[d] = {c: v / ow_total for c, v in ow.items()} if ow_total > 0 else {}

        total_close = cash
        for c, s in shares.items():
            p = px(c_row, c)
            if np.isfinite(p):
                total_close += s * p
        intraday_pnl = total_close - open_after
        nav[d] = total_close
        ledger.append(dict(date=d, prev_close_asset=prev_close_asset, open_before=open_before,
                           open_after=open_after, close_asset=total_close,
                           overnight_pnl=overnight_pnl, intraday_pnl=intraday_pnl, cost=cost,
                           residual=(total_close - prev_close_asset)
                           - overnight_pnl - intraday_pnl + cost))
        prev_close_asset = total_close

    return (pd.Series(nav).sort_index(),
            pd.DataFrame.from_dict(open_w_rows, orient="index").sort_index(),
            pd.DataFrame(ledger).set_index("date"),
            pd.DataFrame(turnover_rows))


def benchmark_nav(ctx, start):
    b = ctx["bench"][ctx["bench"].index >= start]
    out = pd.Series(index=b.index, dtype=float)
    out.iloc[0] = 1.0 + b["benchmark_intraday_ret"].iloc[0]
    for i in range(1, len(b)):
        out.iloc[i] = out.iloc[i - 1] * (1.0 + b["benchmark_ret"].iloc[i])
    return out


def daily_returns(nav_s):
    r = nav_s.pct_change()
    r.iloc[0] = nav_s.iloc[0] - 1.0
    return r


def segment_metrics(nav_s, bench_s, half_turn_s):
    r = daily_returns(nav_s)
    first_day, last_day = nav_s.index[0], nav_s.index[-1]
    seen_start = pd.Timestamp("2025-01-01")
    anchor_seen = nav_s[nav_s.index < seen_start].iloc[-1]
    segs = {
        "all": (first_day, last_day, 1.0),
        "validation": (pd.Timestamp("2023-01-09"), pd.Timestamp("2024-12-31"), 1.0),
        "seen": (seen_start, last_day, anchor_seen),
    }
    out = []
    for stage, (s, e, b0) in segs.items():
        seg_nav = nav_s[(nav_s.index >= s) & (nav_s.index <= e)]
        seg_r = r[(r.index >= s) & (r.index <= e)]
        n = len(seg_r)
        cum = seg_nav.iloc[-1] / b0 - 1
        ann_geom = (seg_nav.iloc[-1] / b0) ** (252.0 / n) - 1
        ann_vol = seg_r.std(ddof=1) * np.sqrt(252)
        sharpe = seg_r.mean() / seg_r.std(ddof=1) * np.sqrt(252)
        geom_over_vol = ann_geom / ann_vol if ann_vol > 0 else np.nan
        rel = seg_nav / seg_nav.cummax() - 1
        mdd = rel.min()
        trough = rel.idxmin()
        peak = seg_nav.loc[:trough].idxmax()
        after = seg_nav.loc[trough:]
        rec = after[after >= seg_nav.loc[peak]]
        rec_days = (rec.index[0] - trough).days if len(rec) else np.nan
        seg_bench = bench_s[(bench_s.index >= s) & (bench_s.index <= e)]
        bench_before = bench_s[bench_s.index < s]
        banch = bench_before.iloc[-1] if len(bench_before) else 1.0
        bench_cum = seg_bench.iloc[-1] / banch - 1
        excess = cum - bench_cum
        br = seg_bench.pct_change()
        br.iloc[0] = seg_bench.iloc[0] / banch - 1
        diff = seg_r.values - br.reindex(seg_r.index).values
        te = np.nanstd(diff, ddof=1) * np.sqrt(252)
        ir = np.nanmean(diff) / np.nanstd(diff, ddof=1) * np.sqrt(252)
        ht = half_turn_s[(half_turn_s.index >= s) & (half_turn_s.index <= e)]
        out.append(dict(stage=stage, n_days=n, cum_return=cum, ann_geom=ann_geom,
                        ann_vol=ann_vol, sharpe_arith_rf0=sharpe, geom_over_vol=geom_over_vol,
                        max_drawdown=mdd, dd_recovery_days=rec_days,
                        mean_half_turn=ht.mean(), ann_half_turn=ht.mean() * (252.0 / 5.0),
                        excess_vs_benchmark=excess, te_vs_benchmark=te, ir_vs_benchmark=ir))
    return out


def main():
    ctx_cache = {}
    for pool, experiment, bcode, rel, models in EXPERIMENTS:
        print("="*70, experiment)
        if pool not in ctx_cache:
            ctx_cache[pool] = load_pool(pool, bcode)
        ctx = ctx_cache[pool]
        targets = read_targets(rel, models)
        res_dir = OUT / "results" / experiment
        res_dir.mkdir(parents=True, exist_ok=True)

        nav_all, metrics_all, turn_all = {}, [], []
        for model in models:
            for scenario in SCENARIOS:
                nav_s, ow_df, ledger_df, turn_df = run_account(
                    targets[model], scenario, ctx)
                nav_all[f"{model}_{scenario}"] = nav_s
                turn_df.insert(0, "model", model)
                turn_all.append(turn_df)
                if scenario == "net_10bp":
                    ow_df.to_parquet(res_dir / f"open_weights_{model}.parquet")
                    ledger_df.to_csv(res_dir / f"ledger_{model}.csv", encoding="utf-8-sig")
            print(f"  {model} 完成")

        bench_s = benchmark_nav(ctx, nav_all[f"{models[0]}_net_10bp"].index[0])
        nav_all["benchmark"] = bench_s
        nav_df = pd.DataFrame(nav_all).sort_index()
        nav_df.to_csv(res_dir / "daily_nav_v3.csv", encoding="utf-8-sig")

        turn_df_all = pd.concat(turn_all)
        for model in models:
            model_turn = turn_df_all[turn_df_all.model == model]
            for scenario in SCENARIOS:
                sc = model_turn[model_turn.fee_scenario == scenario].set_index("execution_date")
                for m in segment_metrics(nav_df[f"{model}_{scenario}"], bench_s, sc.half_turn):
                    m.update(dict(model=model, fee_scenario=scenario))
                    metrics_all.append(m)
        pd.DataFrame(metrics_all)[
            ["model", "fee_scenario", "stage", "n_days", "cum_return", "ann_geom", "ann_vol",
             "sharpe_arith_rf0", "geom_over_vol", "max_drawdown", "dd_recovery_days",
             "mean_half_turn", "ann_half_turn", "excess_vs_benchmark",
             "te_vs_benchmark", "ir_vs_benchmark"]
        ].to_csv(res_dir / "metrics_v3.csv", index=False, encoding="utf-8-sig")
        turn_df_all.to_csv(res_dir / "turnover_v3.csv", index=False, encoding="utf-8-sig")

        err = max(pd.read_csv(res_dir / f"ledger_{m}.csv", index_col=0).residual.abs().max()
                  for m in models)
        print(f"  账本残差最大 {err:.2e} | 基准末日 {bench_s.iloc[-1]:.4f}")


if __name__ == "__main__":
    main()
