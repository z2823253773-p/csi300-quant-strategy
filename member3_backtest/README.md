# member3_v3 说明

模型 3.0 双股票池无前视回测、收益归因与风险分析，按 PRD 接口 3 交付。

## 目录结构

```
member3_v3/
├── code/
│   ├── engine_v3.py      # 账户引擎：三实验、三费率、成交限制、账本闭合
│   └── analysis_v3.py    # 行业暴露、decomp 归因、风险图表
├── results/
│   ├── hs300_clean/      # 沪深300 不含015干净池，M1/M2/M3b/M4/M5
│   ├── hs300_alpha/      # 沪深300 含015池，M1/M3a 专项诊断
│   └── zz500/            # 中证500 八模型 M0a-M5
├── figures/              # 16 张图
├── 组员3_v3_回测归因与风险说明.md
└── README.md
```

## 实验与账户

| 实验 | 股票池 | 模型 | 账户数 |
|---|---|---|---|
| hs300_clean | 沪深300，干净共同池（中位数284只） | M1 M2 M3b M4 M5 | 5 |
| hs300_alpha | 沪深300，含015共同池（中位数152只） | M1 M3a | 2 |
| zz500 | 中证500 | M0a M0b M1 M2 M3a M3b M4 M5 | 8 |

15 个账户，每个跑 gross / net_10bp / net_histtax 三种费用情景，共 45 次回测。

## 输出文件（PRD 接口3）

每个实验目录下：

- daily_nav_v3.csv：每个模型三情景的日度净值和基准净值。
- metrics_v3.csv：全样本、验证期、样本外三段的收益、年化、夏普、回撤、换手、超额、跟踪误差、信息比率。
- turnover_v3.csv：每次调仓的买卖权重、单边换手、费用占比和被阻断的买卖。
- industry_exposure_v3.csv：申万一级行业暴露的全期均值和最新值。
- decomp_v3.csv：隔夜、盘中、费用的累计分解，加总闭合。
- open_weights_{model}.parquet：每个模型调仓日按开盘价计的实际持仓权重。
- ledger_{model}.csv：逐日账本，用于核对恒等式。

所有结果带 pool / experiment / model / fee_scenario 标识，两个实验的 M1 分目录存放，不会互相覆盖。

## 复现方法

两个脚本按顺序运行，默认路径相对项目根目录，无需额外参数：

```
python code/engine_v3.py
python code/analysis_v3.py
```

依赖 numpy、pandas、pyarrow、matplotlib。回测区间 2023-01-09 至 2026-10-30，921 个交易日、185 次调仓。

## 关键口径

- 调仓日按开盘价估值后成交，开盘价不 ffill，无真实报价不成交。
- 停牌、ST、新股、开盘一字涨停不可买，开盘一字跌停不可卖；卖不掉的旧股继续持有，现金不足时买入按比例缩减。
- 费率：佣金 0.0003、滑点 0.001；印花税 2023-08-28 前 0.001、之后 0.0005；现金零息。
- 基准首日按 intraday（开盘到收盘），之后按 close-to-close，须按 benchmark_code 过滤。
- 逐日账本残差最大 1.11e-16，分段闭合误差不超过 2.22e-16。
