# 数据字典与接口调用手册

## 本次运行

| 属性 | 值 |
|---|---|
| 模式 | online |
| 数据路径 | baostock_shenwan_sina_cached |
| 数据属性 | BaoStock 历史市场数据 |
| 实际交易日 | 2019-01-02 至 2026-10-30 |
| 日期数 / 股票数 / 面板行数 | 1897 / 520 / 940696 |
| 可交易行数 | 568036 |
| 市值代理占比 | 100.0% |

数据来源：股票行情与历史成分股来自 BaoStock；行业仅使用申万变更历史，未覆盖者保留未分类；两条指数来自新浪历史日线。

## 文件与维度

根目录 `quant_project_data/processed/`。`clean_daily_panel.parquet` 是 `(trade_date, stock_code)` 唯一的长表；`benchmark_daily.parquet` 是 `(trade_date, benchmark_code)` 唯一的两指数长表。`matrix_<field>.parquet` 是宽表，行索引为 `trade_date`，列为 `stock_code`。矩阵字段完整列表如下：

`open_hfq`, `high_hfq`, `low_hfq`, `close_hfq`, `vwap_hfq`, `returns`, `volume`, `amount`, `turn`, `ln_mkt_cap`, `bp`, `ep`, `tradable_mask`, `is_limit_up`, `is_limit_down`, `can_sell_held`, `ln_float_mv_proxy`, `open_quote_observed`。

## 字段定义与口径

| 字段 | 含义与单位 | 缺失及使用规则 |
|---|---|---|
| `trade_date`, `stock_code` | 交易日 Timestamp；六位代码加交易所后缀 | 唯一主键 |
| `open/high/low/close` | 不复权价格，元/股 | 同股过去值向前填充；仅用于原始价格与交易限制 |
| `close_hfq` | BaoStock 后复权收盘价，元/股 | 由后复权查询及当日因子计算 |
| `adj_factor` | 后复权收盘价 / 不复权收盘价 | 仅沿该股票时间轴向前填充 |
| `open_hfq/high_hfq/low_hfq` | 不复权价乘 `adj_factor`，元/股 | Alpha101 量价输入 |
| `vwap_hfq` | `amount / volume × adj_factor`，元/股；零成交量用后复权收盘价 | 停牌日不得用于可交易信号 |
| `returns` | 同股后复权收盘价日收益 | 首个可观测日为缺失，非零填充 |
| `volume` | 不复权成交股数，股 | 缺失及停牌为 0 |
| `amount` | 不复权成交额，人民币元 | 缺失及停牌为 0；容量分析使用 |
| `turn` | 换手率，百分数 | 缺失及停牌为 0；不是小数比率 |
| `circ_mv_est` | `amount / (turn/100)`，流通市值估计，人民币元 | 仅正成交额与换手率计算，同股向前填充 |
| `total_mv` | 原始总市值，人民币元 | BaoStock 行情接口不提供；online 模式保留缺失 |
| `ln_mkt_cap` | 可得总市值或流通市值代理的自然对数 | `mkt_cap_is_proxy` 标示代理；不可声称均为总市值 |
| `bp` | `1/pbMRQ` | PB 非正时缺失 |
| `ep` | `1/peTTM` | PE 非正时缺失，保留亏损公司的缺失状态 |
| `sw_l1_name`, `industry_scheme` | 行业名称及实际分类体系 | 仅使用申万变更记录向后对齐，未覆盖则记未分类 |
| `in_index_universe` | 最近已生效快照的成分股 | 快照前全部为 False，不使用未来成分 |
| `is_st`, `is_new_stock`, `is_suspended`, `is_abnormal` | ST、上市未满 60 自然日、停牌、价格/换手率异常 | 均为 bool；未知 IPO 日期视为不可交易 |
| `tradable_mask` | 成分股且四个排除条件均不成立 | 供因子研究与回测过滤 |
| `is_limit_up/down` | 一字板且当日原始收益越过分板块阈值 | 主板 9.5%、科创/创业 19.5%、北交 29.5% 为识别阈值，非交易所精确撮合规则 |
| `sample_split` | `in_sample` / `out_of_sample` | 截止 2024-12-31 的历史样本内划分 |

`benchmark_daily.parquet` 包含 `000300.SH` 与 `000905.SH`，`benchmark_open` / `benchmark_close` 为指数开盘/收盘点位，`benchmark_ret` 为收盘到收盘收益，`benchmark_intraday_ret` 为当日开盘到收盘收益。策略若首日开盘建仓，首日基准用后者，其后串接前者。`open_quote_observed` 仅说明原始日线有正开盘价及昨收价，不保证开盘可成交。价格填充仅使用已知过去数据，不使用向后填充。行业对齐规则：申万行业变更记录以起始日与更新日中较晚者作为可用日，月度快照超过 45 天即失效；未混用证监会分类。申万变更历史可能事后补录；采用起始日与更新日中较晚的可用日期。

## 组员 2：Alpha101 输入

```python
import pandas as pd
from pathlib import Path
p = Path('quant_project_data/processed')
close = pd.read_parquet(p / 'matrix_close_hfq.parquet')
vwap = pd.read_parquet(p / 'matrix_vwap_hfq.parquet')
returns = pd.read_parquet(p / 'matrix_returns.parquet')
mask = pd.read_parquet(p / 'matrix_tradable_mask.parquet')
factor_input = ((vwap - close) / close).where(mask)
from src.factor_preprocessor import process_factor_panel
panel = pd.read_parquet(p / 'clean_daily_panel.parquet')
processed = process_factor_panel(panel, 'raw_alpha_demo')
```

## 组员 3：回测输入

```python
import pandas as pd
from pathlib import Path
p = Path('quant_project_data/processed')
tradable = pd.read_parquet(p / 'matrix_tradable_mask.parquet')
limit_up = pd.read_parquet(p / 'matrix_is_limit_up.parquet')
limit_down = pd.read_parquet(p / 'matrix_is_limit_down.parquet')
close = pd.read_parquet(p / 'matrix_close_hfq.parquet')
bench = pd.read_parquet(p / 'benchmark_daily.parquet')
can_buy = tradable & ~limit_up
can_sell = pd.read_parquet(p / 'matrix_can_sell_held.parquet')
```

调仓时应使用信号日之后的可成交价格，并处理停牌/一字板、交易成本、非成分股退出及新入选成分股；此数据工程不定义回测成交时点。`can_sell` 仅演示正常卖出条件，已持有股票被剔除指数或停牌时需在回测里继续跟踪并推迟执行。
