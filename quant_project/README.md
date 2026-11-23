# 量化多因子项目：组员 1 数据工程

该项目实现历史成分股、日度量价、估值与行业数据的获取、时点清洗、因子预处理及 Parquet 交接。`demo` 是确定性合成数据，仅用于工程验收；真实市场研究必须运行 `online` 并核验输出。

## 环境与复现

建议使用 Python 3.12。于项目根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe run_pipeline.py --mode demo
.\.venv\Scripts\python.exe run_pipeline.py --mode online --universe hs300
```

中证 500 股票池改为 `--universe zz500`。`online` 首次运行调用 BaoStock，按月查询历史成分股、按季度查询历史行业并下载所有历史成分股日线。已有完整缓存时直接复用股票行情与成分股，并优先使用申万行业变更历史和新浪双指数日线。按单股和历史快照保存到 `quant_project_data/raw/`，网络查询失败时保留已成功缓存的数据并抛错退出。切换股票池前请将先前的 `processed/` 和 `figures/` 交付物另行保存。

## 模块与交付

`src/config.py` 统一配置；`data_fetcher.py` 负责 BaoStock 历史拉取与断点缓存；`data_cleaner.py` 统一后复权、估值和缺失口径；`universe_filter.py` 做历史成分和交易状态过滤；`factor_preprocessor.py` 实现 MAD、OLS 中性化、Z 分数；`exporter.py` 导出长面板、18 个宽矩阵及双基准指数；`visualizer.py` 生成三张 300 DPI 图。`docs/DATA_DICTIONARY.md` 包含字段及下游读取示例；`docs/REPORT_SECTION_3_DRAFT.md` 是不含代码的报告文字初稿。

`RUN_METADATA.json` 标注最近一次运行模式、实际样本日期和市值代理占比。`demo` 覆盖除权、停牌、ST、次新、一字涨跌停和极端因子值。没有执行在线模式时，任何图表和统计数字均不得宣称来自真实市场。

本地交付目录保留了完整原始缓存和处理后数据。`clean_daily_panel.parquet` 约 170 MB，超过 GitHub 的单文件限制；`.gitignore` 将 `raw/`、`processed/` 排除在普通代码仓库之外。团队共享数据请另用文件存储或 Git LFS，并保留 `RUN_METADATA.json` 及来源说明；GitHub 仓库中的一键入口可重新抓取数据。

## 已知口径限制

BaoStock 日线提供成交股数、成交额和换手率，未在本实现中提供逐日总市值。在线模式以成交金额除以换手率的小数近似**流通市值**，并在 `mkt_cap_is_proxy` 中标记，不能称作总市值。行业字段 `sw_l1_name` 是兼容列名，`industry_scheme` 记录实际申万或证监会分类。申万变更历史可能事后补录，因此取分类起始日与更新日中较晚者作为可用日；早期缺口保留为未分类。指数成分按月抽样，月内临时调整无法逐日精确复原。涨跌停一字板识别使用宽松阈值，不代替交易所撮合规则。信号形成与回测成交价必须由组员 2、3 明确定义，避免同日收盘价形成信号又同价成交。

代码和报告使用数据与接口时请引用 [BaoStock 官方文档](https://www.baostock.com/)、[申万行业分类资料](https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls) 和 [新浪财经指数数据](https://finance.sina.com.cn/realstock/company/sh000300/nc.shtml)。课程提交仍需团队完成真实样本回测、产品分析、雪球模拟盘和完整报告。


## 开盘对齐补充（2026-11-18）

enchmark_daily.parquet 新增 enchmark_open 与 enchmark_intraday_ret。首个交易日若策略从开盘前资金 1.0 起算，沪深300首日用开盘至收盘收益；后续交易日用收盘至收盘收益。clean_daily_panel.parquet 与 matrix_open_quote_observed.parquet 新增原始开盘报价观测标记。它只保证日线存在正开盘价与昨收价；停牌股也可能保留开盘字段，本批数据中 2,586 个停牌股票日该标记仍为真，绝不可把它单独用作开盘可成交条件。日线 is_suspended 也含全日量额信息，不能冒充开盘可知状态。组员3须使用当时可得的交易状态或明确报告成交假设，报告不能称其为严格无前视成交验证。
