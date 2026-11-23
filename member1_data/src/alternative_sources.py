"""Cached BaoStock equities plus Shenwan change history and Sina indices."""
import pandas as pd


SW_L1 = {
    "11": "农林牧渔", "21": "采掘", "22": "基础化工", "23": "钢铁", "24": "有色金属",
    "26": "机械设备", "27": "电子", "28": "汽车", "33": "家用电器", "34": "食品饮料",
    "35": "纺织服饰", "36": "轻工制造", "37": "医药生物", "41": "公用事业",
    "42": "交通运输", "43": "房地产", "45": "商贸零售", "46": "社会服务",
    "48": "银行", "49": "非银金融", "51": "综合", "61": "建筑材料",
    "62": "建筑装饰", "63": "电力设备", "64": "机械设备", "65": "国防军工",
    "71": "计算机", "72": "传媒", "73": "通信", "74": "煤炭", "75": "石油石化",
    "76": "环保", "77": "美容护理",
}
SW_LEGACY_NAMES = {"22": "化工", "35": "纺织服装", "45": "商业贸易",
                   "46": "休闲服务", "63": "电气设备"}


def load_or_fetch_alternatives(config):
    industry_path = config.raw_dir / "sw_industry_change_history.parquet"
    bench_path = config.raw_dir / "sina_benchmarks_raw.parquet"
    if not industry_path.exists() or not bench_path.exists():
        import akshare as ak
        if not industry_path.exists():
            ak.stock_industry_clf_hist_sw().to_parquet(industry_path, index=False)
        if not bench_path.exists():
            frames = []
            for code in ("000300.SH", "000905.SH"):
                frames.append(ak.index_zh_daily_sina(symbol="sh" + code[:6]).assign(benchmark_code=code))
            pd.concat(frames, ignore_index=True).to_parquet(bench_path, index=False)
    return pd.read_parquet(industry_path), pd.read_parquet(bench_path)


def build_alternative_industry(config, constituents, history):
    codes = sorted(constituents["stock_code"].unique())
    dates = sorted(pd.to_datetime(constituents["eff_date"]).unique())
    grid = pd.MultiIndex.from_product([dates, codes], names=["eff_date", "stock_code"]).to_frame(index=False)
    grid["eff_date"] = pd.to_datetime(grid["eff_date"]).astype("datetime64[ns]")
    code_map = {code[:6]: code for code in codes}
    sw = history[history["symbol"].isin(code_map)].copy()
    sw["stock_code"] = sw["symbol"].map(code_map)
    sw["start_date"] = pd.to_datetime(sw["start_date"])
    sw["update_time"] = pd.to_datetime(sw["update_time"])
    # The provider can backdate starts. Publication/update time is a conservative availability bound.
    sw["available_date"] = sw[["start_date", "update_time"]].max(axis=1).astype("datetime64[ns]")
    sw = sw[sw["available_date"].le(pd.Timestamp(config.end_date))]
    sw = sw.sort_values(["available_date", "start_date"]).drop_duplicates(["stock_code", "available_date"], keep="last")
    aligned = pd.merge_asof(grid.sort_values("eff_date"),
                            sw[["stock_code", "available_date", "industry_code"]].sort_values("available_date"),
                            left_on="eff_date", right_on="available_date", by="stock_code", direction="backward")
    prefix = aligned["industry_code"].astype("string").str[:2]
    aligned["sw_l1_name"] = prefix.map(SW_L1)
    for old_code, old_name in SW_LEGACY_NAMES.items():
        historical = prefix.eq(old_code).fillna(False) & aligned["eff_date"].lt(pd.Timestamp("2021-08-01"))
        aligned.loc[historical, "sw_l1_name"] = old_name
    aligned["industry_scheme"] = aligned["sw_l1_name"].notna().map({True: "申万行业变更历史", False: None})
    # Keep one classification scheme; CSRC labels are not interchangeable with SW L1.
    return aligned[["eff_date", "stock_code", "sw_l1_name", "industry_scheme"]]


def build_benchmarks(config, raw_benchmarks):
    benchmark = raw_benchmarks.rename(columns={"date": "trade_date", "open": "benchmark_open", "close": "benchmark_close"})
    benchmark["trade_date"] = pd.to_datetime(benchmark["trade_date"])
    benchmark = benchmark[benchmark["trade_date"].between(config.start_date, config.end_date)]
    benchmark = benchmark[["trade_date", "benchmark_code", "benchmark_open", "benchmark_close"]].copy()
    benchmark["benchmark_open"] = pd.to_numeric(benchmark["benchmark_open"], errors="coerce")
    benchmark["benchmark_close"] = pd.to_numeric(benchmark["benchmark_close"], errors="coerce")
    benchmark = benchmark.sort_values(["benchmark_code", "trade_date"])
    benchmark["benchmark_ret"] = benchmark.groupby("benchmark_code")["benchmark_close"].pct_change(fill_method=None)
    benchmark["benchmark_intraday_ret"] = benchmark["benchmark_close"] / benchmark["benchmark_open"] - 1
    if set(benchmark["benchmark_code"].unique()) != {"000300.SH", "000905.SH"}:
        raise RuntimeError("Both benchmark indices are required")
    return benchmark
