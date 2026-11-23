"""Rebuild both stock universes with the same Tushare daily data source."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from src.alternative_sources import build_alternative_industry, build_benchmarks
from src.config import PipelineConfig
from src.data_cleaner import DataCleaner
from src.exporter import export_assets
from src.tushare_source import (ADJ, BASIC, DAILY, LISTING, NAMES, Tushare, TushareConnectionError, load_listings,
                                load_symbol, token_from_environment)


UNIVERSES = ("hs300", "zz500")
# Same listed security, effective 2025-02-17. Tushare serves full history under the new code.
SECURITY_ALIASES = {"300114.SZ": "302132.SZ"}


def main(default_universe="both"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", choices=("both", *UNIVERSES), default=default_universe)
    parser.add_argument("--existing-cache", type=Path, required=True)
    parser.add_argument("--tushare-cache", type=Path, default=Path("tushare_cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("tushare_data"))
    parser.add_argument("--workers", type=int, default=8, metavar="1-16")
    parser.add_argument("--calls-per-minute", type=int, default=90, metavar="1-500")
    parser.add_argument("--check", action="store_true", help="Check required Tushare permissions before bulk work")
    args = parser.parse_args()

    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    if not 1 <= args.calls_per_minute <= 500:
        parser.error("--calls-per-minute must be between 1 and 500")
    cfg = PipelineConfig()
    bounds = dict(start_date=cfg.start_date.replace("-", ""), end_date=cfg.end_date.replace("-", ""))
    client = Tushare(token_from_environment(), args.calls_per_minute)
    if args.check:
        sample = dict(ts_code="000001.SZ", start_date="20241029", end_date="20241030")
        for api, fields, params in (
            ("daily", DAILY, sample), ("daily_basic", BASIC, sample), ("adj_factor", ADJ, sample),
            ("namechange", NAMES, dict(ts_code="000001.SZ")),
            ("stock_basic", LISTING, dict(ts_code="000001.SZ", list_status="L")),
        ):
            frame = client.query(api, fields, **params)
            if frame.empty:
                raise RuntimeError(f"{api}: empty permission check response")
            print(f"{api}: {len(frame)} rows", flush=True)
        return

    industry_history = pd.read_parquet(args.existing_cache / "sw_industry_change_history.parquet")
    industry_history["symbol"] = industry_history["symbol"].replace({"300114": "302132"})
    benchmarks = build_benchmarks(cfg, pd.read_parquet(args.existing_cache / "sina_benchmarks_raw.parquet"))
    calendar = pd.DatetimeIndex(benchmarks.loc[benchmarks["benchmark_code"].eq("000300.SH"), "trade_date"])
    months = calendar.to_series().groupby(calendar.to_period("M")).min()
    dates = list(months.dt.strftime("%Y-%m-%d"))
    if len(dates) != 94 or dates[0] != "2019-01-02" or calendar.max() != pd.Timestamp("2026-10-30"):
        raise ValueError("Unexpected study calendar. Use the original 3.0 index history.")
    rosters = {}
    universes = UNIVERSES if args.universe == "both" else (args.universe,)
    for universe in universes:
        directory = args.existing_cache / f"{universe}_constituents"
        frames = [pd.read_parquet(directory / f"{date}.parquet") for date in dates]
        roster = pd.concat(frames, ignore_index=True)
        roster["published_stock_code"] = roster["stock_code"]
        roster["stock_code"] = roster["stock_code"].replace(SECURITY_ALIASES)
        if roster.duplicated(["eff_date", "stock_code"]).any():
            raise ValueError(f"{universe}: security alias duplicated a member on the same date")
        rosters[universe] = roster
    codes = sorted(set().union(*(set(r["stock_code"]) for r in rosters.values())))
    cache = args.tushare_cache / f"{bounds['start_date']}_{bounds['end_date']}_v1"
    listings = load_listings(client, cache)
    missing = sorted(set(codes) - set(listings))
    if missing:
        raise ValueError(f"Tushare stock_basic missing {len(missing)} constituent codes: {', '.join(missing[:10])}")
    print(f"{len(codes)} unique ticker histories across the two universes", flush=True)

    def download(code):
        try:
            load_symbol(client, cache, code, bounds, listings[code], calendar)
        except (TushareConnectionError, ValueError) as exc:
            return code, str(exc)
        return code, None

    pending = [code for code in codes if not (cache / "normalized" / f"{code}.parquet").is_file()]
    failure_log = cache / "download_failures.json"
    print(f"Resuming with {len(codes) - len(pending)} completed tickers", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for attempt in range(3):
            if not pending:
                break
            failures = {}
            batch_size = args.workers * 2
            for start in range(0, len(pending), batch_size):
                for code, error in pool.map(download, pending[start:start + batch_size]):
                    if error is not None:
                        print(f"Deferred {code}: {error}", flush=True)
                        failures[code] = error
                done = len(codes) - len(pending) + min(start + batch_size, len(pending)) - len(failures)
                print(f"Ready: {done}/{len(codes)}", flush=True)
            failure_log.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
            pending = sorted(failures)
    if pending:
        raise RuntimeError(f"{len(pending)} ticker histories remain incomplete. See {failure_log}")

    for universe, roster in rosters.items():
        config = PipelineConfig(universe_index=universe, delivery_dir=args.output_dir)
        codes_in_pool = sorted(roster["stock_code"].unique())
        raw = pd.concat([pd.read_parquet(cache / "normalized" / f"{code}.parquet")
                         for code in codes_in_pool], ignore_index=True)
        industry = build_alternative_industry(config, roster, industry_history)
        panel = DataCleaner(config).clean_and_build_universe(raw, industry, roster)
        export_assets(panel, benchmarks, config, "online", "tushare_daily_shenwan_sina")
        roster.to_parquet(config.processed_dir / "historical_constituents.parquet", index=False)
        print(f"{universe}: {config.processed_dir}", flush=True)


if __name__ == "__main__":
    main()

