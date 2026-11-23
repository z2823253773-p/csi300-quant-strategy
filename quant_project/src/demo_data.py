"""Deterministic synthetic edge cases; never represent these as market results."""
import numpy as np
import pandas as pd


def generate_synthetic_raw_data(n_days=80, n_stocks=120):
    rng = np.random.default_rng(2026)
    dates = pd.bdate_range("2026-06-01", periods=n_days)
    codes = [f"{600000+i:06d}.SH" if i % 2 == 0 else f"{i+1:06d}.SZ" for i in range(n_stocks)]
    industries = ["银行", "电子", "医药生物", "机械", "食品饮料", "计算机", "非银金融", "电力设备"]
    rows = []
    for j, code in enumerate(codes):
        price = float(rng.uniform(10, 80))
        factor = 1.0
        ipo = "2026-05-15" if j < 5 else "2018-01-01"
        for d, date in enumerate(dates):
            prev = price
            if d == 30 and j % 10 == 0:
                factor *= 1.25
                prev /= 1.25
                price /= 1.25
            ret = float(rng.normal(0.0005, 0.014))
            price = max(1.0, price * (1 + ret))
            high = price * (1 + abs(float(rng.normal(0, 0.008))))
            low = price * (1 - abs(float(rng.normal(0, 0.008))))
            open_ = (price + prev) / 2
            if j == 10 and d == 12:
                price = prev * 1.10
                open_ = high = low = price
            if j == 11 and d == 13:
                price = prev * 0.90
                open_ = high = low = price
            suspended = bool(rng.random() < 0.02 or (j == 12 and d == 20))
            volume = 0.0 if suspended else float(rng.lognormal(15.5, 0.6))
            amount = volume * price
            turn = 0.0 if suspended else float(rng.uniform(0.3, 5.5))
            pb = np.nan if j == 13 and d == 25 else float(rng.uniform(0.7, 5))
            rows.append({"date": date, "stock_code": code, "stock_name": "ST样本" if 5 <= j < 10 else "样本股",
                         "open": open_, "high": high, "low": low, "close": price, "preclose": prev,
                         "close_hfq": price * factor, "volume": volume, "amount": amount, "turn": turn,
                         "tradestatus": "0" if suspended else "1", "pctChg": ret * 100,
                         "peTTM": float(rng.uniform(8, 60)), "pbMRQ": pb,
                         "psTTM": float(rng.uniform(1, 12)), "isST": "1" if 5 <= j < 10 else "0",
                         "ipo_date": ipo, "out_date": "", "total_mv": float(rng.uniform(2e9, 2e11))})
    snapshots = []
    industry = []
    for month, group in pd.DataFrame({"date": dates}).groupby(dates.to_period("M")):
        effective = group["date"].min()
        for j, code in enumerate(codes):
            if (j + month.month) % 11 != 0:
                snapshots.append({"eff_date": effective, "stock_code": code, "stock_name": "样本股"})
            industry.append({"eff_date": effective, "stock_code": code,
                             "sw_l1_name": industries[j % len(industries)], "industry_scheme": "synthetic"})
    benchmark = []
    for code, drift in (("000300.SH", 0.0002), ("000905.SH", 0.0001)):
        level = 4000.0
        for date in dates:
            level *= 1 + drift + float(rng.normal(0, 0.008))
            benchmark.append({"trade_date": date, "benchmark_code": code, "benchmark_close": level})
    benchmark = pd.DataFrame(benchmark).sort_values(["benchmark_code", "trade_date"])
    benchmark["benchmark_ret"] = benchmark.groupby("benchmark_code")["benchmark_close"].pct_change(fill_method=None)
    return pd.DataFrame(rows), pd.DataFrame(industry), pd.DataFrame(snapshots), benchmark
