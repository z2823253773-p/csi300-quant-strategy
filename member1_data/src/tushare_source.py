"""Tushare Pro requests and conversion to the existing raw panel schema."""
import getpass
import os
import re
import threading
import time
from pathlib import Path
from uuid import uuid4

import pandas as pd
import requests


KEY = "trade_date"
ENDPOINT = "https://api.tushare.pro"
DAILY = "ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount"
BASIC = "ts_code,trade_date,turnover_rate,pe_ttm,pb,ps_ttm"
ADJ = "ts_code,trade_date,adj_factor"
NAMES = "ts_code,name,start_date,end_date,ann_date"
LISTING = "ts_code,list_date,delist_date"
RAW_COLUMNS = ["date", "stock_code", "stock_name", "ipo_date", "out_date", "isST", "tradestatus",
               "open", "high", "low", "close", "preclose", "close_hfq", "pctChg", "volume", "amount",
               "turn", "peTTM", "pbMRQ", "psTTM"]


def token_from_environment():
    return (os.getenv("TUSHARE_TOKEN") or getpass.getpass("Tushare token (hidden): ")).strip()


class TushareConnectionError(RuntimeError):
    pass


class Tushare:
    def __init__(self, token, calls_per_minute):
        if not token:
            raise ValueError("Tushare token is required")
        self.token = token
        self.interval = 60 / calls_per_minute
        self.next_request = 0.0
        self.lock = threading.Lock()
        self.connections = threading.local()

    def query(self, api, fields, **params):
        if not hasattr(self.connections, "session"):
            self.connections.session = requests.Session()
        for attempt in range(3):
            with self.lock:
                now = time.monotonic()
                scheduled = max(now, self.next_request)
                self.next_request = scheduled + self.interval
            time.sleep(max(0, scheduled - time.monotonic()))
            try:
                response = self.connections.session.post(
                    ENDPOINT, json=dict(api_name=api, fields=fields, params=params, token=self.token),
                    timeout=(10, 24), allow_redirects=False,
                )
            except (requests.ConnectionError, requests.Timeout):
                self.connections.session.close()
                self.connections.session = requests.Session()
                if attempt == 2:
                    raise TushareConnectionError(f"{api}: Tushare connection failed after retries") from None
            else:
                if response.status_code in {502, 503, 504} and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code in {502, 503, 504}:
                    raise TushareConnectionError(f"{api}: Tushare HTTP {response.status_code}")
                if response.status_code != 200:
                    raise RuntimeError(f"{api}: Tushare HTTP {response.status_code}")
                try:
                    result = response.json()
                except ValueError:
                    raise RuntimeError(f"{api}: Tushare response is not JSON") from None
                if result.get("code") != 0:
                    message = str(result.get("msg") or "").replace(self.token, "[redacted]")
                    raise RuntimeError(f"{api}: Tushare {result.get('code')}: {message}")
                data = result.get("data") or {}
                columns = fields.split(",")
                if not data.get("items"):
                    return pd.DataFrame(columns=columns)
                frame = pd.DataFrame(data["items"], columns=data["fields"])
                return frame[columns]
            time.sleep(2 ** attempt)
        raise RuntimeError(f"{api}: Tushare query failed")


def cached(cache, name, loader):
    path = cache / f"{name}.parquet"
    if path.is_file():
        return pd.read_parquet(path)
    cache.mkdir(parents=True, exist_ok=True)
    frame = loader()
    temporary = cache / f".{name}.{uuid4().hex}.tmp"
    try:
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return frame


def date_column(series):
    return pd.to_datetime(series, format="%Y%m%d", errors="coerce")


def normalize(code, price, daily_basic, adjustment, names, listing, calendar):
    if price.empty or daily_basic.empty or adjustment.empty:
        raise ValueError(f"{code}: missing daily, daily_basic, or adj_factor")
    price = price.copy()
    for frame in (price, daily_basic, adjustment, names):
        if not frame.empty and not frame["ts_code"].eq(code).all():
            raise ValueError(f"{code}: provider returned another ticker")
    merged = price.merge(daily_basic.drop(columns="ts_code"), on=KEY, how="left",
                         validate="one_to_one", indicator=True)
    if not merged["_merge"].eq("both").all():
        raise ValueError(f"{code}: daily_basic does not cover all returned trading dates")
    merged = merged.drop(columns="_merge").merge(
        adjustment.drop(columns="ts_code"), on=KEY, how="left", validate="one_to_one")
    if not pd.to_numeric(merged["adj_factor"], errors="coerce").gt(0).all():
        raise ValueError(f"{code}: missing or invalid adjustment factor on traded dates")
    merged[KEY] = date_column(merged[KEY])
    ipo = pd.to_datetime(listing["list_date"], format="%Y%m%d", errors="raise")
    end = pd.to_datetime(listing["delist_date"], format="%Y%m%d", errors="coerce")
    if pd.isna(ipo):
        raise ValueError(f"{code}: missing IPO date")
    active = calendar[calendar >= ipo]
    if pd.notna(end):
        active = active[active <= end]
    if not merged[KEY].isin(active).all():
        raise ValueError(f"{code}: reported dates outside the listing calendar")
    merged = merged.set_index(KEY).reindex(active.rename(KEY))
    # Tushare daily omits suspended days. Preserve these dates with missing execution quotes.
    merged["tradestatus"] = merged["ts_code"].notna().astype(int)
    merged["volume"] = pd.to_numeric(merged["vol"], errors="coerce").fillna(0) * 100
    merged["amount"] = pd.to_numeric(merged["amount"], errors="coerce").fillna(0) * 1000
    merged["close_hfq"] = pd.to_numeric(merged["close"], errors="coerce") * pd.to_numeric(merged["adj_factor"], errors="coerce")
    merged = merged.rename(columns={"pre_close": "preclose", "pct_chg": "pctChg",
                                    "turnover_rate": "turn", "pe_ttm": "peTTM", "pb": "pbMRQ",
                                    "ps_ttm": "psTTM"})
    merged["stock_code"] = code
    merged["stock_name"] = ""
    merged["ipo_date"] = ipo
    merged["out_date"] = end
    merged["isST"] = 0
    for row in names.itertuples(index=False):
        if not re.match(r"^(?:\*?ST|S\*?ST)|退", str(row.name), re.IGNORECASE):
            continue
        start = pd.to_datetime(row.start_date, format="%Y%m%d", errors="coerce")
        finish = pd.to_datetime(row.end_date, format="%Y%m%d", errors="coerce")
        if pd.isna(start):
            raise ValueError(f"{code}: ST name history missing effective date")
        # end_date is the last effective date in the supplied name interval.
        affected = merged.index >= start
        if pd.notna(finish):
            affected &= merged.index <= finish
        merged.loc[affected, "isST"] = 1
    return merged.reset_index().rename(columns={KEY: "date"})[RAW_COLUMNS]


def load_listings(client, cache):
    frames = []
    for status in ("L", "D", "P"):
        frames.append(cached(cache, f"stock_basic_{status}",
                             lambda status=status: client.query("stock_basic", LISTING, list_status=status)))
    all_rows = pd.concat(frames, ignore_index=True)
    return all_rows.drop_duplicates("ts_code").set_index("ts_code").to_dict("index")


def load_symbol(client, cache, code, bounds, listing, calendar):
    def build():
        delist_date = listing["delist_date"]
        if pd.notna(delist_date) and str(delist_date) and str(delist_date) < bounds["start_date"]:
            # Keep the original constituent record but yield no prices outside its listing life.
            return pd.DataFrame(columns=RAW_COLUMNS)
        frames = []
        for api, fields in (("daily", DAILY), ("daily_basic", BASIC), ("adj_factor", ADJ), ("namechange", NAMES)):
            params = {} if api == "namechange" else bounds
            frame = cached(cache / api, code, lambda: client.query(api, fields, ts_code=code, **params))
            frames.append(frame)
        return normalize(code, *frames, listing, calendar)
    return cached(cache / "normalized", code, build)
