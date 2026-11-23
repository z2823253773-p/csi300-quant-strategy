"""Point-in-time index membership and trading restriction masks."""
import numpy as np
import pandas as pd


def align_snapshot(panel, snapshots, value_columns):
    """Map the last snapshot at or before each trading date; never backfill."""
    dates = pd.DataFrame({"trade_date": pd.to_datetime(sorted(panel["trade_date"].unique())).astype("datetime64[ns]")})
    effective = pd.DataFrame({"eff_date": pd.to_datetime(sorted(pd.to_datetime(snapshots["eff_date"]).unique())).astype("datetime64[ns]")})
    mapping = pd.merge_asof(dates, effective, left_on="trade_date", right_on="eff_date", direction="backward")
    out = panel.merge(mapping, on="trade_date", how="left", sort=False)
    snap = snapshots.copy()
    snap["eff_date"] = pd.to_datetime(snap["eff_date"]).astype("datetime64[ns]")
    snap["stock_code"] = snap["stock_code"].astype(str)
    return out.merge(snap[["eff_date", "stock_code", *value_columns]].drop_duplicates(["eff_date", "stock_code"]),
                     on=["eff_date", "stock_code"], how="left", sort=False, validate="many_to_one")


def add_universe_masks(panel, constituents, min_list_days=60):
    df = panel.copy()
    if constituents is not None:
        const = constituents[["eff_date", "stock_code", "stock_name"]].copy()
        const["membership"] = True
        df = align_snapshot(df, const, ["membership", "stock_name"])
        df["in_index_universe"] = df.pop("membership").fillna(False).astype(bool)
        if "stock_name_x" in df.columns:
            # A query_stock_basic name is current, so never project it into history.
            df["stock_name"] = df["stock_name_y"]
            df = df.drop(columns=["stock_name_x", "stock_name_y"])
        df = df.drop(columns=["eff_date"])
    else:
        df["in_index_universe"] = True
    name = df.get("stock_name", pd.Series("", index=df.index)).fillna("").astype(str)
    df["is_st"] = df["isST"].astype(str).eq("1") | name.str.contains(r"ST|退", case=False, regex=True)
    df["is_suspended"] = df["tradestatus"].astype(str).eq("0") | df["volume"].le(0) | df["amount"].le(0)
    df["list_days"] = (df["trade_date"] - df["ipo_date"]).dt.days
    df["is_new_stock"] = df["list_days"].lt(min_list_days) | df["list_days"].isna()
    df["is_abnormal"] = (df["close"].le(0) | df["high"].lt(df["low"]) |
                         df["turn"].gt(100) | df["close_hfq"].isna() |
                         df["raw_invalid"] | df["ipo_date"].gt(df["trade_date"]))
    symbol = df["stock_code"].str[:6]
    threshold = np.select([symbol.str.startswith(("30", "68")), df["stock_code"].str.endswith(".BJ")],
                          [0.195, 0.295], default=0.095)
    raw_return = np.where(df["preclose"].gt(0), df["close"] / df["preclose"] - 1, np.nan)
    one_price = df["high"].eq(df["low"]) & ~df["is_suspended"]
    df["is_limit_up"] = (one_price & (raw_return >= threshold)).astype(bool)
    df["is_limit_down"] = (one_price & (raw_return <= -threshold)).astype(bool)
    df["tradable_mask"] = (df["in_index_universe"] & ~df["is_st"] & ~df["is_suspended"] &
                           ~df["is_new_stock"] & ~df["is_abnormal"]).astype(bool)
    df["can_sell_held"] = (~df["is_suspended"] & ~df["is_limit_down"] & ~df["is_abnormal"]).astype(bool)
    return df
