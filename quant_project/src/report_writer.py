"""Generate reproducible hand-off documentation from actual run metadata."""
from pathlib import Path


def write_docs(config, metadata):
    docs = Path(__file__).resolve().parents[1] / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    mode = metadata["mode"]
    data_kind = "合成演示数据（不得作为真实市场实证结果）" if mode == "demo" else "BaoStock 历史市场数据"
    variant = metadata["source_variant"]
    source_note = {
        "synthetic": "合成演示序列。",
        "baostock_shenwan_sina_cached": "股票行情与历史成分股来自 BaoStock；行业仅使用申万变更历史，未覆盖者保留未分类；两条指数来自新浪历史日线。",
        "baostock_direct": "股票行情、历史成分股、季度历史行业快照和两条指数日线均来自 BaoStock。",
    }[variant]
    industry_method = {
        "synthetic": "模拟行业按月构造并按时点对齐",
        "baostock_shenwan_sina_cached": "申万行业变更记录以起始日与更新日中较晚者作为可用日，月度快照超过 45 天即失效；未混用证监会分类",
        "baostock_direct": "历史行业按季度取 BaoStock 快照，只利用当日及此前已发布分类",
    }[variant]
    dictionary = f"""# 数据字典与接口调用手册

## 本次运行

| 属性 | 值 |
|---|---|
| 模式 | {mode} |
| 数据路径 | {variant} |
| 数据属性 | {data_kind} |
| 实际交易日 | {metadata['sample_start']} 至 {metadata['sample_end']} |
| 日期数 / 股票数 / 面板行数 | {metadata['dates']} / {metadata['stocks']} / {metadata['rows']} |
| 可交易行数 | {metadata['tradable_rows']} |
| 市值代理占比 | {metadata['market_cap_proxy_fraction']:.1%} |

数据来源：{source_note}

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

`benchmark_daily.parquet` 包含 `000300.SH` 与 `000905.SH`，`benchmark_open` / `benchmark_close` 为指数开盘/收盘点位，`benchmark_ret` 为收盘到收盘收益，`benchmark_intraday_ret` 为当日开盘到收盘收益。策略若首日开盘建仓，首日基准用后者，其后串接前者。`open_quote_observed` 仅说明原始日线有正开盘价及昨收价，不保证开盘可成交。价格填充仅使用已知过去数据，不使用向后填充。行业对齐规则：{industry_method}。申万变更历史可能事后补录；采用起始日与更新日中较晚的可用日期。

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
"""
    (docs / "DATA_DICTIONARY.md").write_text(dictionary, encoding="utf-8")
    report = rf"""# 第 3 节 数据与预处理，以及第 7 节相关讨论（初稿）

## 3.1 数据来源、样本区间与动态股票池

本研究以沪深 300 历史成分股为主要研究对象，并保留中证 500 作为可切换股票池及对照指数。计划样本区间为 2019 年 1 月 1 日至 2026 年 11 月 1 日；样本内时期截至 2024 年 12 月 31 日，2025 年 1 月 1 日起为样本外时期。由于 2026 年 11 月 1 日为非交易日，真实行情的最后观测日期应以数据源实际返回的最近交易日为准。两条指数收盘点位和按相邻收盘点位计算的日收益用于后续超额收益与风险比较。

{source_note}不复权行情提供开高低收、成交股数、成交金额、换手率、停牌与 ST 标志，以及市盈率、市净率。对每月首个交易日记录当时可获得的指数成分股名单，并以样本期所有曾入选股票的并集抓取行情。每个交易日只使用该日及此前最近一次快照判断指数归属，不把期末成分股反推到历史日期。股票上市日期来自证券基本资料；上市未满 60 个自然日、ST、停牌及价格异常记录均从可交易池中剔除。

本次生成文件的审计摘要如下。当前运行属于**{data_kind}**，下表仅证明流水线能够产出结构化数据；若为合成演示数据，不得把数值写成真实市场的经验结果。

| 审计指标 | 本次输出 |
|---|---:|
| 实际首个交易日 | {metadata['sample_start']} |
| 实际最后交易日 | {metadata['sample_end']} |
| 交易日数 | {metadata['dates']} |
| 历史股票数 | {metadata['stocks']} |
| 股票日观测数 | {metadata['rows']} |
| 可交易观测数 | {metadata['tradable_rows']} |
| 市值代理使用比例 | {metadata['market_cap_proxy_fraction']:.1%} |

图 1 显示逐日历史指数成分股数量与过滤后的有效股票数；图 3 对比量价、估值与行业字段的有效覆盖率。两图对应本次运行的数据属性，不能跨模式引用。

## 3.2 因子构建与截面预处理方法

为避免分红送转在不复权价格中形成虚假的收益跳跃，设个股 $i$ 在交易日 $t$ 的后复权因子为 $A_{{i,t}}=P^{{HFQ}}_{{i,t}}/P^{{raw}}_{{i,t}}$。将当日不复权开盘、最高、最低价分别乘以该因子，得到同口径后复权量价矩阵。成交均价先按不复权成交额除以成交股数计算，再乘以后复权因子；无成交股数时仅为保持字段可读而使用后复权收盘价，停牌掩码仍排除该记录。日收益定义为 $P^{{HFQ}}_{{i,t}}/P^{{HFQ}}_{{i,t-1}}-1$，首个可观测日保留缺失，不设为零。

估值候选因子使用账面市值比 $BP_{{i,t}}=1/PB_{{i,t}}$ 与盈利收益率 $EP_{{i,t}}=1/PE_{{i,t}}$。非正市净率和非正市盈率不参与倒数运算。市值中性化优先使用可得的总市值；若行情接口没有提供总市值，以成交金额除以换手率小数近似流通市值，取自然对数作为规模代理。该代理并非总市值，尤其在高换手或价格波动较大的日期可能有误差，须在模型解释中单独标示。

在每个交易日先将不属于可交易池的因子观测置为缺失。随后以截面中位数 $M_t$ 和绝对中位差 $MAD_t=\operatorname{{median}}_i|F_{{i,t}}-M_t|$ 形成裁剪边界 $M_t\pm5(1.4826 MAD_t)$。裁剪后的因子对当日对数市值及行业虚拟变量进行最小二乘回归，保留残差作为规模与行业中性化结果。最后以当日残差均值和样本标准差计算 Z 分数。样本不足、设计矩阵秩不足或残差方差为零时，输出缺失，而不强行制造标准化值。图 2 展示某一代表性日期上该三阶段分布及其均值、中位数、偏度和峰度。

清洗中的价格、估值和市值缺失只在同一股票时间轴上利用过去观测向前填充；成交股数、成交金额和换手率的停牌缺失置零。指数成分股按月取历史快照；{industry_method}。所有计算均按时点推进，禁止用未来的行情、指数成分或行业信息填补过去数据。

## 7 数据与因子处理关键选择及其理由

历史动态成分股可减少只选取期末存续股票导致的幸存者偏差；其代价是月度快照之间的指数临时调整无法逐日精确重建。60 个自然日的新股过滤减少上市初期涨跌停与成交约束对选股信号的扰动，但会牺牲部分早期价格发现信息。ST、停牌及一字板分别处理：前两者决定因子研究样本，一字板标志供回测执行时限制买卖，不能简单视为可成交价。

后复权价用于收益和价格类因子，原始成交金额与换手率用于流动性和产品容量估算，避免把复权价格与未复权成交金额混合后造成量纲偏差。行业中性化有助于辨别行业轮动与个股因子收益，但也可能剔除因子真实的行业配置价值；后续应并列报告中性化前后的 IC 与分组收益。市值估算代理、行业记录的发布时间和早期行业缺口是数据源约束，建议在正式回测中检验这些口径对模型表现的敏感性。

本节只论述数据和预处理。模型有效性、回测收益、归因及风险结论须由组员 2 和组员 3 的真实样本分析补充，并引用各自可复现结果。图表与表格均应保留数据源、期间与运行模式标注。
"""
    (docs / "REPORT_SECTION_3_DRAFT.md").write_text(report, encoding="utf-8")
