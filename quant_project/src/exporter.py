"""Stable Parquet hand-off for factor and backtest teams."""
import json

import pandas as pd


MATRIX_FIELDS = ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "vwap_hfq", "returns",
                 "volume", "amount", "turn", "ln_mkt_cap", "bp", "ep",
                 "tradable_mask", "is_limit_up", "is_limit_down", "can_sell_held", "ln_float_mv_proxy",
                 "open_quote_observed"]


def export_assets(panel, benchmarks, config, mode, source_variant):
    out = config.processed_dir
    out.mkdir(parents=True, exist_ok=True)
    if panel.duplicated(["trade_date", "stock_code"]).any():
        raise ValueError("Duplicate panel keys")
    if not set(MATRIX_FIELDS).issubset(panel.columns):
        raise ValueError("Missing mandatory matrix columns")
    panel.to_parquet(out / "clean_daily_panel.parquet", index=False)
    for col in MATRIX_FIELDS:
        matrix = panel.pivot(index="trade_date", columns="stock_code", values=col).sort_index().sort_index(axis=1)
        matrix.to_parquet(out / f"matrix_{col}.parquet")
    benchmarks.to_parquet(out / "benchmark_daily.parquet", index=False)
    metadata = {
        "mode": mode, "source_variant": source_variant,
        "sample_start": str(panel["trade_date"].min().date()),
        "sample_end": str(panel["trade_date"].max().date()),
        "rows": int(len(panel)), "stocks": int(panel["stock_code"].nunique()),
        "dates": int(panel["trade_date"].nunique()),
        "tradable_rows": int(panel["tradable_mask"].sum()),
        "market_cap_proxy_fraction": float(panel["mkt_cap_is_proxy"].mean()),
        "valuation_max_age_days": config.valuation_max_age_days,
        "valuation_age_days": {c: {"p50": float(panel[c].median()), "p95": float(panel[c].quantile(.95)), "max": float(panel[c].max())} for c in ("peTTM_age_days", "pbMRQ_age_days")},
        "industry_max_age_days": config.industry_max_age_days,
        "industry_unclassified_fraction": float(panel["sw_l1_name"].eq("未分类").mean()),
        "industry_schemes": sorted(panel["industry_scheme"].dropna().unique().tolist()),
    }
    (out / "RUN_METADATA.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata
