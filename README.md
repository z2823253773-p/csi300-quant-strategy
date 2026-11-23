# 沪深300 多因子量化策略与产品化方案（CSI 300 Quantitative Strategy）

> **课程名称**：《量化交易技术理论与实践》期末大作业可复现代码仓库  
> **当前版本**：`v2.0`（全链路无前视验证版；`v3.0` 升级方案规划见 [`docs/PRD_模型3.0规格书与跨组接口契约.md`](docs/PRD_模型3.0规格书与跨组接口契约.md)）  
> **GitHub 仓库**：https://github.com/z2823253773-p/csi300-quant-strategy  
> **雪球公开模拟组合**：`ZH3689205`（https://www.xueqiu.com/P/ZH3689205）

---

## 一、团队成员与职责分工

| 组员 | 姓名 | 学号 | 核心模块与职责 | 代码目录 |
| :--- | :--- | :--- | :--- | :--- |
| 组员 1 | 李钰鹏 | `2024104286` | 数据获取、动态股票池清洗、防前视掩码与截面预处理 | [`quant_project/`](quant_project/) |
| 组员 2 | 刘宇睿 | `2024101054` | Alpha101 候选因子检验、无量纲比例化改进、120 组成本网格与信号构建 | [`member2_v2/`](member2_v2/) |
| 组员 3 | 张沐 | `2024101056` | 开盘无前视账户回测、Fama-MacBeth 收益归因与多维风险分析 | [`member3/`](member3/) |
| 组员 4 | 张恒瑞 | `2024101062` | 三口径策略容量测算、四档高水位费率核算、雪球跟踪映射与报告/PPT 整合 | [`member4/`](member4/) |

---

## 二、v2.0 核心实证结果速览（2023-01-09 至 2026-10-30，921 个交易日）

全流程严格遵守 **t 日收盘生成信号、t+1 日开盘价成交**，计入双边万 3 佣金、卖出千 1 印花税、双边千 1 滑点，并施加开盘一字涨跌停与停牌约束（已持仓出池/ST 股票可通过 `can_sell_held` 正常卖出）：

| 组合 / 基准 | 累计收益 | 年化收益 | 年化波动 | 夏普比率 | 最大回撤 | 单边换手均值 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Baseline（价值+规模代理，正式交付）** | **+45.38%** | **10.78%** | 16.00% | **0.67** | **-16.69%** | **5.9%** |
| Research（50% Baseline + 50% Alpha006/033） | -6.52% | -1.83% | 16.26% | -0.11 | -27.11% | 51.2% |
| 沪深 300 基准（`000300.SH`） | +0.12% | 0.03% | 17.42% | 0.00 | -24.80% | — |

* **核心发现与独立贡献**：
  1. **算子尺度改进**：揭示 Kakushadze (2016) 原版 `Alpha012` 与 `Alpha101` 的价格尺度敏感缺陷，提出无量纲改进公式 `new012_return`（训练/验证/样本外三期 5 日 Rank IC 分别为 `0.0096`、`0.0092`、`0.0156`，全面优于原版）。
  2. **频率错配与交易摩擦机理**：Fama-MacBeth 归因与 120 组三维成本网格证实，短周期量价因子以 50% 权重接入 5 日调仓会稀释价值暴露并将换手放大 8.7 倍（累计吞噬 37.2 个百分点收益）；拉长至 20 日调仓可使 10bp 样本外净年化恢复至 `10.36%`。
  3. **产品化闭环**：Baseline 在 5% 参与率下 1 日/3 日调仓 P10 硬约束容量为 `2.58 / 7.75 亿元`，Almgren 平方根冲击理论半衰容量达 `80.87 亿元`，机构 C 档费后年化 `8.48%`（信息比率 `0.68`）。

---

## 三、仓库目录结构

```text
csi300-quant-strategy/
├── quant_project/       # 组员 1：数据获取与时点清洗管道、4 项单元测试、数据字典与配图
├── member2_v2/          # 组员 2：因子检验、比例化扩展、6 项单元测试、结果表与 5 张配图
├── member3/             # 组员 3：开盘无前视回测、FM 收益归因、风险分析、结果表与 7 张配图
├── member4/             # 组员 4：容量/费率测算、雪球持仓导出、统一视觉图、报告与讲稿源稿
├── docs/                # 项目总控验收记录与模型 3.0 PRD 规格书
├── requirements.txt     # 统一 Python 3.12 依赖清单
└── README.md
```

> **关于大文件说明**：组员 1 生成的 `clean_daily_panel.parquet`（约 170 MB）及各原始/宽表 `.parquet` 文件超出 GitHub 单文件大小限制，已通过 `.gitignore` 排除。运行下方第一步数据管道即可在本地完整重建全部 Parquet 文件并校验元数据（[`quant_project/quant_project_data/processed/RUN_METADATA.json`](quant_project/quant_project_data/processed/RUN_METADATA.json)）。

---

## 四、一键复现步骤（Python 3.12）

```bash
# 0. 安装依赖
python3 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt

# 1. 组员 1：运行 4 项数据完整性单元测试 & 构建历史市场数据（首次需联网拉取 BaoStock/申万/新浪）
python -m unittest discover -s quant_project/tests -t quant_project -v
cd quant_project && python run_pipeline.py --mode online --universe hs300 && cd ..

# 2. 组员 2：运行 6 项因子单元测试 & 重算主模型与 120 组成本敏感性网格
python -m unittest discover -s member2_v2/code -p "test_*.py" -v
cd member2_v2
python code/research.py --data ../quant_project/quant_project_data/processed
python code/extensions.py --data ../quant_project/quant_project_data/processed
cd ..

# 3. 组员 3：运行开盘无前视账户回测、Fama-MacBeth 收益归因与风险分析
python member3/code/backtest.py
python member3/code/attribution.py
python member3/code/risk.py

# 4. 组员 4：运行产品容量/费率测算、雪球持仓导出与统一视觉出图
python member4/code/product_analysis.py
python member4/code/xueqiu_export.py
python member4/code/make_figures.py
```

---

## 五、版本迭代记录

* **`v2.0`（2026-11-23）**：归档并推送全组通过验收的 v2.0 完整可复现代码、10 项单元测试、核心分析结果表、统一视觉配图与雪球 `ZH3689205` 跟踪清单；已清理废弃脚本 `extract_suspended.py` 及全部个人本机路径。
* **`v3.0`（规划中）**：按 [`docs/PRD_模型3.0规格书与跨组接口契约.md`](docs/PRD_模型3.0规格书与跨组接口契约.md) 迭代推进 Alpha101 全量重筛、M0–M5 消融回测、行业集中度上限与终版封板报告。
