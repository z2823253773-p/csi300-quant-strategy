"""One-command synthetic demo or historical online data preparation."""
import argparse

import numpy as np
import pandas as pd

from src.config import PipelineConfig
from src.alternative_sources import load_cached_online
from src.data_cleaner import DataCleaner
from src.data_fetcher import DataFetcher
from src.demo_data import generate_synthetic_raw_data
from src.exporter import export_assets
from src.factor_preprocessor import process_factor_panel
from src.report_writer import write_docs
from src.utils import configure_logging, ensure_dirs, logger
from src.visualizer import create_figures


def run_pipeline(mode="demo", universe="hs300"):
    configure_logging()
    cfg = PipelineConfig(universe_index=universe)
    ensure_dirs(cfg.raw_dir, cfg.processed_dir, cfg.figure_dir)
    if mode == "demo":
        raw, industry, constituents, benchmarks = generate_synthetic_raw_data()
        source_variant = "synthetic"
    elif mode == "online":
        cached = load_cached_online(cfg)
        if cached is not None:
            raw, industry, constituents, benchmarks = cached
            source_variant = "baostock_shenwan_sina_cached"
        else:
            with DataFetcher(cfg) as fetcher:
                dates = fetcher.first_trading_days()
                constituents = fetcher.fetch_dynamic_constituents(dates)
                codes = sorted(constituents["stock_code"].unique())
                raw = fetcher.fetch_stock_daily_panel(codes)
                quarterly_dates = [date for date in dates if pd.Timestamp(date).month in (1, 4, 7, 10)]
                industry = fetcher.fetch_industry_history(quarterly_dates, codes)
                benchmarks = fetcher.fetch_benchmarks()
            source_variant = "baostock_direct"
    else:
        raise ValueError(mode)
    panel = DataCleaner(cfg).clean_and_build_universe(raw, industry, constituents)
    panel["raw_alpha_demo"] = (panel["vwap_hfq"] - panel["close_hfq"]) / panel["close_hfq"] + .05 * panel["bp"]
    if mode == "demo":
        last = panel["trade_date"].max()
        candidates = panel.index[panel["trade_date"].eq(last) & panel["tradable_mask"]][:3]
        panel.loc[candidates, "raw_alpha_demo"] += np.array([1.5, -1.4, 2.0])[:len(candidates)]
    panel = process_factor_panel(panel, "raw_alpha_demo", cfg.mad_multiplier)
    metadata = export_assets(panel, benchmarks, cfg, mode, source_variant)
    create_figures(panel, cfg, mode)
    write_docs(cfg, metadata)
    logger.info("Completed %s run: %s", mode, metadata)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["demo", "online"], default="demo")
    parser.add_argument("--universe", choices=["hs300", "zz500"], default="hs300")
    args = parser.parse_args()
    run_pipeline(args.mode, args.universe)
