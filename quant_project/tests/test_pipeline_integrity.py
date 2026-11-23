"""Behavioral and causal integrity checks, runnable with unittest."""
import unittest

import numpy as np
import pandas as pd

from src.config import PipelineConfig
from src.data_cleaner import DataCleaner
from src.demo_data import generate_synthetic_raw_data
from src.factor_preprocessor import process_factor_panel
from src.universe_filter import align_snapshot


class PipelineIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.industry, cls.constituents, _ = generate_synthetic_raw_data()
        cls.cleaner = DataCleaner(PipelineConfig())
        cls.panel = cls.cleaner.clean_and_build_universe(cls.raw, cls.industry, cls.constituents)

    def test_unique_key_and_boolean_masks(self):
        p = self.panel
        self.assertFalse(p.duplicated(["trade_date", "stock_code"]).any())
        for col in ("tradable_mask", "is_limit_up", "is_limit_down", "is_st", "is_suspended", "is_new_stock"):
            self.assertEqual(p[col].dtype, bool)
        tradable = p[p["tradable_mask"]]
        self.assertFalse(tradable[["is_st", "is_suspended", "is_new_stock", "is_abnormal"]].any().any())
        self.assertTrue(tradable["close_hfq"].notna().all())

    def test_adjustment_ex_date_and_one_price_limits(self):
        p = self.panel
        stock = p[p["stock_code"].eq("600000.SH")].sort_values("trade_date").reset_index(drop=True)
        before, after = stock.iloc[29], stock.iloc[30]
        self.assertLess(after["close"] / before["close"], .9)
        self.assertLess(abs(after["close_hfq"] / before["close_hfq"] - 1), .08)
        self.assertLess(abs(after["vwap_hfq"] / before["vwap_hfq"] - 1), .08)
        self.assertTrue(p["is_limit_up"].any())
        self.assertTrue(p["is_limit_down"].any())

    def test_no_future_data_in_cleaning_or_membership(self):
        cutoff = pd.Timestamp("2026-07-15")
        reduced_raw = self.raw[pd.to_datetime(self.raw["date"]).le(cutoff)]
        reduced_ind = self.industry[self.industry["eff_date"].le(cutoff)]
        reduced_const = self.constituents[self.constituents["eff_date"].le(cutoff)]
        earlier = self.cleaner.clean_and_build_universe(reduced_raw, reduced_ind, reduced_const)
        full_earlier = self.panel[self.panel["trade_date"].le(cutoff)].reset_index(drop=True)
        for col in ("close_hfq", "vwap_hfq", "returns", "tradable_mask", "in_index_universe", "sw_l1_name"):
            pd.testing.assert_series_equal(earlier[col], full_earlier[col], check_names=False)
        dates = pd.DataFrame({"trade_date": pd.to_datetime(["2025-01-01", "2025-01-03"]), "stock_code": ["600000.SH"]*2})
        snap = pd.DataFrame({"eff_date": pd.to_datetime(["2025-01-02"]), "stock_code": ["600000.SH"], "flag": [True]})
        aligned = align_snapshot(dates, snap, ["flag"])
        self.assertTrue(pd.isna(aligned.iloc[0]["flag"]))

    def test_cross_sectional_properties(self):
        p = self.panel.copy()
        p["alpha"] = (p["vwap_hfq"] / p["close_hfq"] - 1) + .05 * p["bp"]
        last = p["trade_date"].max()
        p.loc[p.index[p["trade_date"].eq(last) & p["tradable_mask"]][:1], "alpha"] += 10
        result = process_factor_panel(p, "alpha")
        self.assertTrue(result.loc[~result["tradable_mask"], "alpha_clean"].isna().all())
        checked = 0
        for _, group in result.groupby("trade_date"):
            good = group[["alpha_clean", "ln_mkt_cap"]].dropna()
            if len(good) < 10:
                continue
            checked += 1
            self.assertLess(abs(good["alpha_clean"].mean()), 1e-6)
            self.assertLess(abs(good["alpha_clean"].std(ddof=1) - 1), 1e-6)
            self.assertLess(abs(good["alpha_clean"].corr(good["ln_mkt_cap"])), 1e-6)
        self.assertGreater(checked, 50)


if __name__ == "__main__":
    unittest.main()
