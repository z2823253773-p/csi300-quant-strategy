# Tushare 双股票池重建包

本包带有已核对的 94 期月度历史成分快照、申万行业历史和双指数行情作为输入。个股行情、估值、换手、复权因子和历史 ST 信息从 Tushare 下载。沪深 300 和中证 500 使用相同的个股来源，跨池重复出现的股票只下载一次。旧 BaoStock 个股缓存仍可用于旧版回测。

在解压目录中打开 PowerShell，使用 Python 3.12。已配置 Python 依赖的环境可跳过安装。

```powershell
python -m pip install -r requirements.txt
python .etch_tushare.py --existing-cache .\seed --check
python .etch_tushare.py --existing-cache .\seed --tushare-cache ..	ushare_cache --output-dir .	ushare_data
```

在程序的隐藏输入提示中粘贴 Tushare token 后回车。也可以在进程环境中提供 TUSHARE_TOKEN。程序仅向固定的 Tushare HTTPS API 发送 token。包中没有密钥。接口配额以账号实际权限为准。命令支持 --calls-per-minute 与 --workers，遇到额度不足应降低调用频率或等配额恢复。再次运行会复用已写入的接口缓存。

每日行情成交量由手换成股，成交额由千元换成元，后复权价由未复权收盘价乘当日复权因子计算。没有报价的交易日保留为空报价、不可成交。行业归类和月度调仓候选范围沿用既有研究口径。正式数据下载完成后，两个股票池分别输出到 tushare_data/hs300/processed 和 tushare_data/zz500/processed。请用新数据重新运行因子与回测，不要沿用此前 BaoStock 回测结果。

已用 Tushare 官方接口完成两个股票池的真实行情下载并验证输出。历史成分保留 published_stock_code；中航电测 300114.SZ 与 302132.SZ 作为同一证券连接日线。600270.SH 的退市日早于研究期，保留成分记录但无行情行。部分行情通过 Tushare 合并接口取得，字段与标准接口抽样核对，成交额可能有供应商舍入差异。请参见各池 RUN_METADATA.json。

只重建一池时，可用 fetch_hs300_tushare.py 或 fetch_zz500_tushare.py，参数和共享缓存路径与通用入口相同。
