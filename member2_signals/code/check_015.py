"""Build the HS300 five-model comparison on the common pool excluding the Alpha015 filter."""
from pathlib import Path

import numpy as np
import pandas as pd

from run_pool import zscore

ROOT = Path(__file__).resolve().parents[1] / "hs300"
NAMES = ("bp", "ep", "small", "new012_amt_ema10", "lowvol_60", "lowturn_20",
         "eb_proxy", "alpha006", "alpha040")


def build():
    signals = ROOT / "signals"
    out = ROOT / "clean_015"
    out.mkdir(exist_ok=True)
    factors = {k: pd.read_parquet(signals / f"factor_{k}.parquet") for k in NAMES}
    bp, ep = factors["bp"], factors["ep"]
    common = bp.notna()
    for x in factors.values():
        assert x.index.equals(bp.index) and x.columns.equals(bp.columns)
        common &= x.notna()
    restricted = pd.read_parquet(signals / "common.parquet")
    valid015 = pd.read_parquet(signals / "factor_alpha015.parquet").notna()
    assert (common & valid015).equals(restricted)
    common.to_parquet(out / "common.parquet")
    value = zscore(((bp + ep) / 2).where(common))
    risk_sum = bp + ep + factors["lowvol_60"] + factors["lowturn_20"]
    scores = {"M1": (bp + ep + factors["small"]) / 3, "M2": value,
              "M3b": .85 * value + .15 * factors["new012_amt_ema10"],
              "M4": risk_sum / 4, "M5": (risk_sum + factors["eb_proxy"]) / 5}
    original = pd.read_csv(signals / "target_weights_v3.csv")
    m1 = original[original.model.eq("M1")].copy()
    m1["signal_date"] = pd.to_datetime(m1.signal_date)
    old_holdings = m1.groupby("signal_date").stock_code.agg(set)
    dates = common.index
    positions = range(dates.get_loc("2023-01-06"), len(dates)-1, 5)
    assert list(old_holdings.index) == list(dates[list(positions)])
    rows, audits = [], []
    for model, score in scores.items():
        score = score.where(common)
        assert score.notna().equals(common)
        score.to_parquet(out / f"score_{model}.parquet")
        previous = set()
        for i in positions:
            day, execution = dates[i:i+2]
            rank = score.loc[day].dropna().sort_index().sort_values(ascending=False, kind="stable")
            keep = previous.intersection(rank.index[:75])
            chosen = keep.union(rank.drop(index=list(keep)).index[:50-len(keep)])
            assert len(chosen) == 50 and chosen.issubset(rank.index)
            for code in (k for k in rank.index if k in chosen):
                rows.append(dict(model=model, signal_date=day, execution_date=execution, stock_code=code,
                                 score=rank[code], target_weight=.02, stage="validation" if execution.year<=2024 else "seen"))
            audits.append(dict(model=model, signal_date=day, common_n=len(rank),
                               target_replacement=len(previous-chosen)/50 if previous else np.nan))
            previous = chosen
    targets = pd.DataFrame(rows)
    key = ["model","execution_date","stock_code"]
    assert not targets.duplicated(key).any()
    assert np.allclose(targets.groupby(key[:2]).target_weight.sum(),1)
    baseline = targets[targets.model.eq("M1")].assign(model="M1_without_015_filter")
    legacy = signals / "diagnostic_015_coverage_weights.csv"
    if legacy.exists():
        old = pd.read_csv(legacy, parse_dates=["signal_date","execution_date"])
        pd.testing.assert_frame_equal(baseline.sort_values(key).reset_index(drop=True),
                                      old.sort_values(key).reset_index(drop=True),check_dtype=False,
                                      rtol=1e-6,atol=1e-7)
    else:
        baseline.to_csv(legacy,index=False)
    targets.to_csv(out / "target_weights.csv",index=False)
    pd.DataFrame(audits).to_csv(out / "target_checks.csv",index=False)
    exits = []
    for j in range(1,len(old_holdings)):
        day = old_holdings.index[j]
        departed = old_holdings.iloc[j-1] - old_holdings.iloc[j]
        only015 = common.loc[day] & ~valid015.loc[day]
        exits.append(dict(signal_date=day, exits=len(departed),
                          ineligible_only_015=sum(bool(only015[k]) for k in departed)))
    pd.DataFrame(exits).to_csv(out / "original_m1_exits.csv",index=False)


if __name__ == "__main__":
    build()
