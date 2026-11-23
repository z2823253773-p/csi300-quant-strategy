"""Historical BaoStock acquisition with complete-snapshot caches."""
from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from .config import PipelineConfig
from .utils import logger, query_rows, standardize_stock_code, to_baostock_code


RAW_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,isST"


class DataFetcher:
    def __init__(self, config: PipelineConfig):
        self.cfg = config
        self.bs = None

    def __enter__(self):
        import baostock as bs
        for attempt in range(5):
            login = bs.login()
            if login.error_code == "0":
                break
            if attempt < 4:
                time.sleep(min(2 ** attempt, 16))
        if login.error_code != "0":
            raise RuntimeError(f"BaoStock login failed: {login.error_msg}")
        self.bs = bs
        return self

    def __exit__(self, *_):
        if self.bs is not None:
            self.bs.logout()

    def _query(self, fn):
        if self.bs is None:
            raise RuntimeError("Use DataFetcher as a context manager")
        last = None
        for attempt in range(6):
            try:
                return query_rows(fn, attempts=2)
            except RuntimeError as exc:
                last = exc
                logger.warning("BaoStock connection reset; reconnecting (%d/6)", attempt + 1)
                try:
                    self.bs.logout()
                except Exception:
                    pass
                time.sleep(min(2 ** attempt, 32))
                login = self.bs.login()
                if login.error_code != "0":
                    last = RuntimeError(login.error_msg)
        raise RuntimeError("BaoStock query failed after reconnects") from last

    def first_trading_days(self):
        cal = self._query(lambda: self.bs.query_trade_dates(self.cfg.start_date, self.cfg.end_date))
        if cal.empty:
            raise RuntimeError("No trading calendar returned")
        cal = cal.loc[cal["is_trading_day"].eq("1"), "calendar_date"]
        dates = pd.to_datetime(cal).sort_values()
        if dates.empty:
            raise RuntimeError("Trading calendar is empty")
        return [d.strftime("%Y-%m-%d") for d in dates.groupby(dates.dt.to_period("M")).first()]

    def fetch_dynamic_constituents(self, dates):
        cache_dir = self.cfg.raw_dir / f"{self.cfg.universe_index}_constituents"
        cache_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        for date in dates:
            path = cache_dir / f"{date}.parquet"
            if path.exists():
                frame = pd.read_parquet(path)
            else:
                fn = self.bs.query_hs300_stocks if self.cfg.universe_index == "hs300" else self.bs.query_zz500_stocks
                frame = self._query(lambda: fn(date=date))
                if frame.empty:
                    raise RuntimeError(f"No historical constituents on {date}; refusing look-ahead fill")
                frame = pd.DataFrame({
                    "eff_date": pd.Timestamp(date),
                    "stock_code": frame["code"].map(standardize_stock_code),
                    "stock_name": frame["code_name"],
                }).drop_duplicates(["eff_date", "stock_code"])
                frame.to_parquet(path, index=False)
            frames.append(frame)
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(self.cfg.raw_dir / "dynamic_constituents.parquet", index=False)
        return result

    def fetch_stock_daily_panel(self, stock_codes, collect=True, workers=3):
        if workers > 1:
            chunks = [stock_codes[i::workers] for i in range(workers)]
            with ProcessPoolExecutor(max_workers=workers) as pool:
                list(pool.map(_fetch_stock_batch, [(self.cfg, chunk) for chunk in chunks if chunk]))
            return self.fetch_stock_daily_panel(stock_codes, collect=True, workers=1)
        cache_dir = self.cfg.raw_dir / "single_stocks"
        cache_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        basic_by_code = None
        for number, code in enumerate(stock_codes, 1):
            path = cache_dir / f"{code}.parquet"
            meta_path = cache_dir / f"{code}.json"
            expected = {"start_date": self.cfg.start_date, "end_date": self.cfg.end_date}
            if path.exists() and meta_path.exists() and json.loads(meta_path.read_text(encoding="utf-8")) == expected:
                if collect:
                    frames.append(pd.read_parquet(path))
                continue
            if basic_by_code is None:
                basic_all = self._query(lambda: self.bs.query_stock_basic())
                basic_by_code = basic_all.drop_duplicates("code").set_index("code")
            bs_code = to_baostock_code(code)
            raw = self._query(lambda: self.bs.query_history_k_data_plus(
                bs_code, RAW_FIELDS, start_date=self.cfg.start_date,
                end_date=self.cfg.end_date, frequency="d", adjustflag="3"))
            if raw.empty:
                logger.warning("No raw daily prices for %s", code)
                continue
            hfq = self._query(lambda: self.bs.query_history_k_data_plus(
                bs_code, "date,close", start_date=self.cfg.start_date,
                end_date=self.cfg.end_date, frequency="d", adjustflag="1"))
            if hfq.empty:
                raise RuntimeError(f"No adjusted prices for {code}")
            hfq = hfq.rename(columns={"close": "close_hfq"})
            basic = basic_by_code.loc[bs_code] if bs_code in basic_by_code.index else None
            if basic is None or not basic.get("ipoDate"):
                individual = self._query(lambda: self.bs.query_stock_basic(code=bs_code))
                basic = individual.iloc[0] if not individual.empty else None
                if basic is None or not basic.get("ipoDate"):
                    logger.warning("IPO date unavailable for %s; it will be non-tradable", code)
            raw = raw.merge(hfq, on="date", how="left", validate="one_to_one")
            raw["stock_code"] = code
            raw["stock_name"] = basic["code_name"] if basic is not None else ""
            raw["ipo_date"] = basic["ipoDate"] if basic is not None else ""
            raw["out_date"] = basic["outDate"] if basic is not None else ""
            raw.to_parquet(path, index=False)
            meta_path.write_text(json.dumps(expected), encoding="utf-8")
            if collect:
                frames.append(raw)
            if number % 25 == 0:
                logger.info("Fetched %d / %d stocks", number, len(stock_codes))
        if not collect:
            return None
        if not frames:
            raise RuntimeError("No stock prices returned")
        return pd.concat(frames, ignore_index=True)


    def fetch_industry_history(self, dates, stock_codes, workers=1):
        """Quarterly historical industry snapshots; prefer SW, otherwise CSRC."""
        if workers > 1:
            chunks = [dates[i::workers] for i in range(workers)]
            with ProcessPoolExecutor(max_workers=workers) as pool:
                list(pool.map(_fetch_industry_batch, [(self.cfg, chunk, stock_codes) for chunk in chunks if chunk]))
            return self.fetch_industry_history(dates, stock_codes, workers=1)
        cache_dir = self.cfg.raw_dir / "industry_history"
        cache_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        universe = set(stock_codes)
        for date in dates:
            path = cache_dir / f"{date}.parquet"
            if path.exists():
                frame = pd.read_parquet(path)
            else:
                raw = self._query(lambda: self.bs.query_stock_industry(date=date))
                if raw.empty:
                    raise RuntimeError(f"No industry snapshot on {date}")
                raw["stock_code"] = raw["code"].map(standardize_stock_code)
                raw = raw[raw["stock_code"].isin(universe)].copy()
                label = raw["industryClassification"].fillna("")
                raw["priority"] = label.str.contains("申万|申银万国").astype(int)
                raw = raw.sort_values(["stock_code", "priority"]).drop_duplicates("stock_code", keep="last")
                frame = raw.rename(columns={"industry": "sw_l1_name", "industryClassification": "industry_scheme"})[
                    ["stock_code", "sw_l1_name", "industry_scheme"]].copy()
                non_sw = ~frame["industry_scheme"].fillna("").str.contains("申万|申银万国")
                frame.loc[non_sw, ["sw_l1_name", "industry_scheme"]] = pd.NA
                frame["eff_date"] = pd.Timestamp(date)
                frame.to_parquet(path, index=False)
            frames.append(frame)
        return pd.concat(frames, ignore_index=True)


    def fetch_benchmarks(self):
        frames = []
        for code in ("000300.SH", "000905.SH"):
            path = self.cfg.raw_dir / f"benchmark_{code}.parquet"
            if path.exists():
                frame = pd.read_parquet(path)
                if {"benchmark_open", "benchmark_intraday_ret"}.issubset(frame.columns) and frame["trade_date"].min() <= pd.Timestamp(self.cfg.start_date) + pd.Timedelta(days=10) and frame["trade_date"].max() >= pd.Timestamp(self.cfg.end_date) - pd.Timedelta(days=10):
                    frames.append(frame)
                    continue
            raw = self._query(lambda: self.bs.query_history_k_data_plus(
                to_baostock_code(code), "date,open,close", start_date=self.cfg.start_date,
                end_date=self.cfg.end_date, frequency="d"))
            if raw.empty:
                raise RuntimeError(f"No benchmark data for {code}")
            frame = raw.rename(columns={"date": "trade_date", "open": "benchmark_open", "close": "benchmark_close"})
            frame["trade_date"] = pd.to_datetime(frame["trade_date"])
            frame["benchmark_close"] = pd.to_numeric(frame["benchmark_close"])
            frame["benchmark_open"] = pd.to_numeric(frame["benchmark_open"], errors="coerce")
            frame = frame.sort_values("trade_date")
            frame["benchmark_ret"] = frame["benchmark_close"].pct_change(fill_method=None)
            frame["benchmark_intraday_ret"] = frame["benchmark_close"] / frame["benchmark_open"] - 1
            frame["benchmark_code"] = code
            frame.to_parquet(path, index=False)
            frames.append(frame)
        return pd.concat(frames, ignore_index=True)


def _fetch_stock_batch(args):
    config, codes = args
    with DataFetcher(config) as fetcher:
        fetcher.fetch_stock_daily_panel(codes, collect=False, workers=1)
    return len(codes)


def _fetch_industry_batch(args):
    config, dates, codes = args
    with DataFetcher(config) as fetcher:
        fetcher.fetch_industry_history(dates, codes, workers=1)
    return len(dates)


