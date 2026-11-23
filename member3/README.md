# member3 —— 回测、收益归因与风险分析（组员3交付）

## 目录结构

```
member3/
├── README.md                    本文件
├── 组员3_回测与归因风险.md        报告正文（可直接并入小组技术报告）
├── code/
│   ├── backtest.py              回测引擎：调仓/开盘成交资格/成本/现金账本 → 净值、指标、换手
│   ├── attribution.py           收益归因：开盘调仓后持仓 × 当日收益，分解到 5 因子
│   └── risk.py                  风险分析：回撤、风格暴露、滚动波动、月度统计
├── results/                     全部结果（CSV / parquet）
│   ├── nav.csv                  四条净值 + 理想版（baseline/research/hs300/ideal）
│   ├── metrics.csv              分区间绩效指标表
│   ├── turnover.csv             逐调仓日单边换手率
│   ├── factor_returns.csv       因子收益显著性（日均/t值/年化）
│   ├── decomp_compare.csv       两模型因子贡献对比
│   ├── decomp_baseline.csv       baseline 逐日收益分解
│   ├── decomp_research.csv       research 逐日收益分解
│   ├── exposure.csv             组合因子暴露均值
│   ├── monthly_returns.csv      月度收益
│   ├── weights_baseline.parquet baseline 逐日收盘持仓权重
│   ├── weights_research.parquet research 逐日收盘持仓权重
│   ├── open_weights_baseline.parquet baseline 逐日开盘调仓后持仓权重
│   └── open_weights_research.parquet research 逐日开盘调仓后持仓权重
└── figures/                     报告配图（PNG）
    ├── nav_curve.png            净值曲线（沪深300 vs baseline vs research）
    ├── excess_curve.png         相对沪深300累计超额收益
    ├── attribution.png          两模型累计收益分解
    ├── attribution_diff.png     research 相对 baseline 收益差分解
    ├── drawdown.png             回撤曲线
    ├── style_exposure.png       BP/EP/Small 风格暴露时间序列
    └── rolling_vol.png          滚动30日年化波动
```

## 成本口径（组员3设定）

- 佣金：双边万3
- 印花税：卖出千1
- 滑点：双边千1
- 现金：不计息

## 执行口径（对齐组员2接口约定 + 评审修订）

- t 日收盘信号，t+1 交易日开盘执行；每 5 交易日调仓，前 50 只等权。
- 开盘成交资格用「开盘时点可获得」的信息判断，避免前视：
  - 买入 = 成分股、非ST、非次新、非停牌、且开盘未一字涨停（开盘价/昨收价判断）。
  - 卖出 = 非停牌、且开盘未一字跌停；采用组员1 `can_sell_held` 的语义，出池/ST 仍可卖。
- 交易受阻保留原持仓、现金与未完成指令；现金硬约束（不透支）。
- 成交价用后复权开盘价，成交额/成交股数用不复权口径。
- 首日建仓盈亏与成本计入累计收益（初始资金 1.0 为首日开盘前基准）。

## 复现方式

环境：Python 3.13，依赖 numpy / pandas / pyarrow / matplotlib。

三个脚本路径均参数化，默认相对总包根目录（`quant_project/`、`member2_v2/`、`member3/` 同级），也可用 `--proc`、`--member2`、`--out` 覆盖：

```powershell
python code/backtest.py
python code/attribution.py
python code/risk.py
```

依赖输入：
- 组员2目标持仓：`member2_v2/signals/target_weights.csv`
- 组员2因子暴露：`member2_v2/signals/factor_{bp,ep,small,alpha006,alpha033}.parquet`
- 组员1数据：`quant_project/quant_project_data/processed/`（matrix_*、clean_daily_panel.parquet、benchmark_daily.parquet）

## 核心结论（详见报告）

1. baseline（基准模型）计成本后年化 10.78%、夏普 0.67、最大回撤 -16.7%，全样本与样本外均显著跑赢沪深300。
2. research（增强模型）计成本后为负收益（-6.52%），全面跑输。
3. 原因分两层：选股层面价值暴露被 Alpha 因子稀释、特异选股收益为负；交易层面高换手（单边均值 51.2% 对 baseline 5.9%）带来严重成本侵蚀。
4. 结论：保留 baseline 为正式策略，research 作为研究讨论对象。
