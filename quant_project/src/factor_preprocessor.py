"""Date-by-date MAD, industry/size residualization and Z-score processing."""
import numpy as np
import pandas as pd


def winsorize_mad_series(values: pd.Series, n=5.0):
    valid = values.dropna()
    if valid.empty:
        return values.astype(float)
    median = valid.median()
    mad = (valid - median).abs().median()
    if mad <= 0 or not np.isfinite(mad):
        return values.astype(float)
    width = n * 1.4826 * mad
    return values.clip(median - width, median + width).astype(float)


def neutralize_cross_section(frame, factor_col):
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    valid = frame[[factor_col, "ln_mkt_cap", "sw_l1_name"]].dropna()
    if valid.empty:
        return result
    dummies = pd.get_dummies(valid["sw_l1_name"], drop_first=True, dtype=float)
    design = np.column_stack((np.ones(len(valid)), valid["ln_mkt_cap"].to_numpy(float), dummies.to_numpy()))
    if len(valid) <= design.shape[1] or np.linalg.matrix_rank(design) < design.shape[1]:
        return result
    y = valid[factor_col].to_numpy(float)
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    result.loc[valid.index] = y - design @ coefficients
    return result


def standardize_zscore_series(values):
    valid = values.dropna()
    if len(valid) < 2:
        return pd.Series(np.nan, index=values.index, dtype=float)
    sd = valid.std(ddof=1)
    if not np.isfinite(sd) or sd <= 1e-12:
        return pd.Series(np.nan, index=values.index, dtype=float)
    return (values - valid.mean()) / sd


def process_factor_panel(df_panel, factor_col, mad_n=5.0, do_neutralize=True):
    if factor_col not in df_panel:
        raise KeyError(factor_col)
    if not df_panel[["trade_date", "stock_code"]].equals(df_panel[["trade_date", "stock_code"]].drop_duplicates()):
        raise ValueError("Duplicate stock/date keys")
    out = df_panel.copy()
    masked, winsor, neutral, clean = [f"{factor_col}_{stage}" for stage in ("masked", "winsorized", "neutralized", "clean")]
    out[masked] = pd.to_numeric(out[factor_col], errors="coerce").where(out["tradable_mask"])
    out[winsor] = out.groupby("trade_date", sort=False)[masked].transform(lambda s: winsorize_mad_series(s, mad_n))
    if do_neutralize:
        out[neutral] = np.nan
        for _, group in out.groupby("trade_date", sort=False):
            out.loc[group.index, neutral] = neutralize_cross_section(group, winsor)
    else:
        out[neutral] = out[winsor]
    out[clean] = out.groupby("trade_date", sort=False)[neutral].transform(standardize_zscore_series)
    return out
