"""Causal daily cleaning and back-adjusted price construction."""
import numpy as np
import pandas as pd

from .config import PipelineConfig
from .universe_filter import add_universe_masks, align_snapshot
from .utils import standardize_stock_code


NUMERIC = ["open", "high", "low", "close", "preclose", "close_hfq", "volume", "amount",
           "turn", "pctChg", "peTTM", "pbMRQ", "psTTM", "total_mv"]
PRICE = ["open", "high", "low", "close", "preclose", "close_hfq"]


class DataCleaner:
    def __init__(self, config: PipelineConfig):
        self.cfg = config

    def clean_and_build_universe(self, raw, industry=None, constituents=None):
        df = raw.copy().rename(columns={"date": "trade_date"})
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="raise")
        df["stock_code"] = df["stock_code"].map(standardize_stock_code)
        df["ipo_date"] = pd.to_datetime(df["ipo_date"], errors="coerce")
        df["out_date"] = pd.to_datetime(df.get("out_date", pd.Series(pd.NaT, index=df.index)), errors="coerce")
        for col in NUMERIC:
            if col in df:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values(["stock_code", "trade_date"]).drop_duplicates(["stock_code", "trade_date"], keep="last").reset_index(drop=True)
        for col in PRICE + ["volume", "amount", "turn", "peTTM", "pbMRQ", "psTTM"]:
            if col not in df:
                df[col] = np.nan
            df[f"raw_valid_{col}"] = df[col].notna()
        # A recorded quote is necessary for an open execution, but daily data cannot prove fillability.
        df["open_quote_observed"] = (df["raw_valid_open"] & df["open"].gt(0) &
                                     df["preclose"].gt(0)).astype(bool)
        df["raw_invalid"] = (df["close"].le(0) | df["high"].lt(df["low"]) |
                             (df["close_hfq"].isna() & df["tradestatus"].astype(str).ne("0")))
        # Only past observations of the same security can fill missing values.
        df[PRICE] = df.groupby("stock_code", sort=False)[PRICE].ffill()
        df[["volume", "amount", "turn"]] = df[["volume", "amount", "turn"]].fillna(0.0)
        valuation = ["peTTM", "pbMRQ", "psTTM"]
        for col in valuation:
            observed = df["trade_date"].where(df[col].notna())
            last_seen = observed.groupby(df["stock_code"], sort=False).ffill()
            df[f"{col}_age_days"] = (df["trade_date"] - last_seen).dt.days
            df[col] = df.groupby("stock_code", sort=False)[col].ffill().where(
                df[f"{col}_age_days"].le(self.cfg.valuation_max_age_days))
        factor = (df["close_hfq"] / df["close"].where(df["close"].gt(0))).replace([np.inf, -np.inf], np.nan)
        df["adj_factor"] = factor.groupby(df["stock_code"]).ffill()
        for col in ("open", "high", "low"):
            df[f"{col}_hfq"] = df[col] * df["adj_factor"]
        df["close_hfq"] = df["close"] * df["adj_factor"]
        vwap_raw = np.where(df["volume"].gt(0), df["amount"] / df["volume"], df["close"])
        df["vwap_hfq"] = vwap_raw * df["adj_factor"]
        df["returns"] = df.groupby("stock_code", sort=False)["close_hfq"].pct_change(fill_method=None)
        # Amount / turnover estimates circulating market value, not total capitalization.
        circ = (df["amount"] / (df["turn"] / 100).where(df["turn"].gt(0) & df["amount"].gt(0))).replace([np.inf, -np.inf], np.nan)
        df["circ_mv_est"] = circ.groupby(df["stock_code"]).ffill()
        if "total_mv" not in df:
            df["total_mv"] = np.nan
        df["total_mv"] = df.groupby("stock_code", sort=False)["total_mv"].ffill()
        df["mkt_cap_for_neutralization"] = df["total_mv"].where(df["total_mv"].gt(0), df["circ_mv_est"])
        df["mkt_cap_is_proxy"] = df["total_mv"].isna()
        df["ln_mkt_cap"] = np.log(df["mkt_cap_for_neutralization"].where(df["mkt_cap_for_neutralization"].gt(0)))
        df["ln_float_mv_proxy"] = np.log(df["circ_mv_est"].where(df["circ_mv_est"].gt(0)))
        df["bp"] = 1 / df["pbMRQ"].where(df["pbMRQ"].gt(0))
        df["ep"] = 1 / df["peTTM"].where(df["peTTM"].gt(0))
        if industry is not None:
            df = align_snapshot(df, industry, ["sw_l1_name", "industry_scheme"])
            df["industry_age_days"] = (df["trade_date"] - df["eff_date"]).dt.days
            expired = df["industry_age_days"].gt(self.cfg.industry_max_age_days)
            df.loc[expired, ["sw_l1_name", "industry_scheme"]] = np.nan
            df = df.drop(columns=["eff_date"])
        else:
            if "sw_l1_name" not in df:
                df["sw_l1_name"] = "模拟行业"
            if "industry_scheme" not in df:
                df["industry_scheme"] = "synthetic"
        df["sw_l1_name"] = df["sw_l1_name"].replace("", np.nan).fillna("未分类")
        df = add_universe_masks(df, constituents, self.cfg.min_list_days)
        df["sample_split"] = np.where(df["trade_date"].le(pd.Timestamp(self.cfg.in_sample_end)), "in_sample", "out_of_sample")
        return df.sort_values(["trade_date", "stock_code"]).reset_index(drop=True)
