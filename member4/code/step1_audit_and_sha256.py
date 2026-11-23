# -*- coding: utf-8 -*-
"""
Step 1 会前准备工具：
1. 为组员 1 两套 3.0 数据（BaoStock quant_project 与 Tushare hs300）生成 SHA-256 指纹清单草案；
2. 核验 PRD 接口 1 全部断言（宽表对齐、open_quote_observed、逐日 is_st、raw_valid_*）；
3. 输出沪深 300 3.0 intraday 基准（2023-01-09 开盘起算 -0.33% / 0.996742）精确三段指标与双夏普口径，
   并核对与 M0a（旧 baseline）的对账结果（不覆盖正式 v2 文件）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

import paths as P

OUT_DIR = P.MEMBER4_DIR / "results" / "step1_prep"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_processed_dir(proc_dir: Path, label: str) -> tuple[dict, dict]:
    """生成 SHA-256 指纹并执行 PRD 接口 1 自检断言。"""
    hashes: dict[str, str] = {}
    parquet_files = sorted(proc_dir.glob("*.parquet"))
    for fp in parquet_files:
        hashes[fp.name] = sha256_file(fp)
    if (proc_dir / "RUN_METADATA.json").exists():
        hashes["RUN_METADATA.json"] = sha256_file(proc_dir / "RUN_METADATA.json")

    mats = sorted(proc_dir.glob("matrix_*.parquet"))
    ref_idx, ref_cols = None, None
    mismatches = []
    for m in mats:
        df = pd.read_parquet(m)
        if ref_idx is None:
            ref_idx, ref_cols = df.index, df.columns
        elif not (df.index.equals(ref_idx) and df.columns.equals(ref_cols)):
            mismatches.append(m.name)

    panel_cols = list(pd.read_parquet(proc_dir / "clean_daily_panel.parquet", columns=[]).columns)
    # pyarrow/pandas empty cols workaround: read schema via pyarrow
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(proc_dir / "clean_daily_panel.parquet")
    panel_cols = pf.schema_arrow.names
    req_panel = [
        "trade_date", "stock_code", "tradestatus", "is_st", "is_suspended",
        "is_new_stock", "in_index_universe", "open", "preclose",
        "industry_scheme", "sw_l1_name", "open_quote_observed",
    ]
    missing_panel = [c for c in req_panel if c not in panel_cols]
    raw_valid_cols = [c for c in panel_cols if c.startswith("raw_valid_")]

    bench = pd.read_parquet(proc_dir / "benchmark_daily.parquet")
    bench_cols = list(bench.columns)

    audit = {
        "label": label,
        "path": str(proc_dir),
        "matrix_count": len(mats),
        "matrix_shape": [int(len(ref_idx)), int(len(ref_cols))] if ref_idx is not None else None,
        "matrix_alignment_pass": len(mismatches) == 0,
        "matrix_mismatches": mismatches,
        "panel_rows": int(pf.metadata.num_rows),
        "panel_cols_count": len(panel_cols),
        "missing_required_panel_cols": missing_panel,
        "raw_valid_cols": raw_valid_cols,
        "benchmark_cols": bench_cols,
        "all_interface1_checks_pass": (len(mismatches) == 0 and len(missing_panel) == 0 and len(raw_valid_cols) >= 5),
    }
    return hashes, audit


def calc_period_metrics(ret: pd.Series) -> dict:
    n = len(ret)
    wealth = (1.0 + ret).cumprod()
    cum_ret = float(wealth.iloc[-1] - 1.0)
    ann_geom = float(wealth.iloc[-1] ** (252.0 / n) - 1.0)
    ann_vol = float(ret.std(ddof=1) * np.sqrt(252.0))
    sharpe_arith_rf0 = float((ret.mean() / ret.std(ddof=1)) * np.sqrt(252.0)) if ret.std(ddof=1) > 0 else 0.0
    geom_over_vol = float(ann_geom / ann_vol) if ann_vol > 0 else 0.0
    running_max = wealth.cummax().clip(lower=1.0)
    dd = wealth / running_max - 1.0
    max_dd = float(dd.min())

    # 最大回撤修复天数（从峰值次日到首次创新高/恢复峰值）
    trough_pos = int(np.argmin(dd.to_numpy()))
    peak_val = running_max.iloc[trough_pos]
    peak_candidates = np.where(wealth.iloc[: trough_pos + 1].to_numpy() >= peak_val - 1e-12)[0]
    peak_pos = int(peak_candidates[-1]) if len(peak_candidates) > 0 else 0
    rec_candidates = np.where(wealth.iloc[trough_pos + 1 :].to_numpy() >= peak_val - 1e-12)[0]
    dd_recovery_days = int(rec_candidates[0] + 1 + (trough_pos - peak_pos)) if len(rec_candidates) > 0 else None

    return {
        "n_days": int(n),
        "terminal_nav": float(wealth.iloc[-1]),
        "cum_return": cum_ret,
        "ann_geom": ann_geom,
        "ann_vol": ann_vol,
        "sharpe_arith_rf0": sharpe_arith_rf0,
        "geom_over_vol": geom_over_vol,
        "max_drawdown": max_dd,
        "dd_recovery_days": dd_recovery_days,
    }


def main():
    print("1. 核验组员 1 两套 3.0 数据并生成 SHA-256 清单草案 ...")
    baostock_proc = P.resolve_data_processed(prefer_tushare=False)
    tushare_proc = P.resolve_tushare_hs300_processed()

    h_bao, a_bao = audit_processed_dir(baostock_proc, "baostock_v3_quant_project")
    (OUT_DIR / "input_sha256_v3_baostock.json").write_text(
        json.dumps(h_bao, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    h_tus, a_tus = audit_processed_dir(tushare_proc, "tushare_v3_hs300")
    (OUT_DIR / "input_sha256_v3_tushare_hs300.json").write_text(
        json.dumps(h_tus, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"  BaoStock 3.0 PASS={a_bao['all_interface1_checks_pass']} ({a_bao['panel_rows']} rows, {a_bao['matrix_count']} matrices)")
    print(f"  Tushare  3.0 PASS={a_tus['all_interface1_checks_pass']} ({a_tus['panel_rows']} rows, {a_tus['matrix_count']} matrices)")

    print("2. 核对沪深 300 3.0 intraday 基准（2023-01-09 ~ 2026-10-30，921天）...")
    bench = pd.read_parquet(baostock_proc / "benchmark_daily.parquet")
    b300 = bench[bench["benchmark_code"].astype(str) == "000300.SH"].copy()
    b300["trade_date"] = pd.to_datetime(b300["trade_date"])
    b300 = b300.sort_values("trade_date").set_index("trade_date")
    sub = b300.loc["2023-01-09":"2026-10-30"].copy()
    assert len(sub) == 921, f"Expected 921 days, got {len(sub)}"

    hs_ret = sub["benchmark_close"].pct_change()
    hs_ret.iloc[0] = sub["benchmark_close"].iloc[0] / sub["benchmark_open"].iloc[0] - 1.0
    hs_nav = (1.0 + hs_ret).cumprod()

    stages = {
        "all": ("2023-01-09", "2026-10-30"),
        "validation": ("2023-01-09", "2024-12-31"),
        "seen": ("2025-01-01", "2026-10-30"),
    }
    hs_metrics = {st: calc_period_metrics(hs_ret.loc[s:e]) for st, (s, e) in stages.items()}

    # 断言连乘闭环
    chain_err = abs((1.0 + hs_metrics["validation"]["cum_return"]) * (1.0 + hs_metrics["seen"]["cum_return"]) - 1.0 - hs_metrics["all"]["cum_return"])
    assert chain_err < 1e-12, f"Chaining error: {chain_err}"

    # 对照历史 M0a (v2 baseline) 在 3.0 intraday 基准下的超额与 IR
    m3_nav = pd.read_csv(P.M3_RES / "nav.csv", index_col=0, parse_dates=True)
    b_ret = m3_nav["baseline"].pct_change()
    b_ret.iloc[0] = m3_nav["baseline"].iloc[0] - 1.0
    r_ret = m3_nav["research"].pct_change()
    r_ret.iloc[0] = m3_nav["research"].iloc[0] - 1.0

    m0a_metrics = {}
    for st, (s, e) in stages.items():
        bm = calc_period_metrics(b_ret.loc[s:e])
        ex_daily = b_ret.loc[s:e] - hs_ret.loc[s:e]
        te = float(ex_daily.std(ddof=1) * np.sqrt(252.0))
        bm["excess_vs_hs300_cum"] = bm["cum_return"] - hs_metrics[st]["cum_return"]
        bm["excess_vs_hs300_ann"] = bm["ann_geom"] - hs_metrics[st]["ann_geom"]
        bm["te_vs_hs300"] = te
        bm["ir_vs_hs300"] = float(bm["excess_vs_hs300_ann"] / te) if te > 0 else 0.0
        m0a_metrics[st] = bm

    m0b_metrics = {st: calc_period_metrics(r_ret.loc[s:e]) for st, (s, e) in stages.items()}

    report = {
        "data_audit": {"baostock_v3": a_bao, "tushare_v3_hs300": a_tus},
        "hs300_intraday_3_0": {
            "first_day_date": "2023-01-09",
            "first_day_intraday_ret": float(hs_ret.iloc[0]),
            "first_day_close_to_close_ret_old_bug": float(sub["benchmark_ret"].iloc[0]),
            "chain_error": float(chain_err),
            "stages": hs_metrics,
        },
        "m0a_baseline_reconciled_vs_hs300_intraday": m0a_metrics,
        "m0b_research_reconciled": m0b_metrics,
    }
    (OUT_DIR / "hs300_intraday_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n===== 沪深 300 3.0 Intraday 基准核对结果 =====")
    for st, d in hs_metrics.items():
        print(
            f"  {st:10s} | n={d['n_days']:3d} | nav={d['terminal_nav']:.6f} | "
            f"cum={d['cum_return']*100:+6.2f}% | ann_geom={d['ann_geom']*100:+6.2f}% | "
            f"vol={d['ann_vol']*100:5.2f}% | sharpe_arith={d['sharpe_arith_rf0']:+.3f} | "
            f"geom/vol={d['geom_over_vol']:+.3f} | maxDD={d['max_drawdown']*100:6.2f}%"
        )
    print("\n===== M0a (v2 baseline) 相对 3.0 沪深 300 修正后指标 =====")
    for st, d in m0a_metrics.items():
        print(
            f"  {st:10s} | cum={d['cum_return']*100:+6.2f}% | excess_cum={d['excess_vs_hs300_cum']*100:+6.2f}pp | "
            f"sharpe_arith={d['sharpe_arith_rf0']:+.3f} | geom/vol={d['geom_over_vol']:+.3f} | "
            f"TE={d['te_vs_hs300']*100:5.2f}% | IR={d['ir_vs_hs300']:+.3f}"
        )
    print(f"\n输出已保存至: {OUT_DIR}")


if __name__ == "__main__":
    main()
