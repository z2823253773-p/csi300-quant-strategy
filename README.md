# 沪深300 价值低波多因子量化策略研究与产品化设计（模型 3.0 · M4）

**《量化交易技术理论与实践》期末大作业**  
**角色定位**：私募证券投资基金量化投研团队 ｜ **指导教师**：肖亮海  
**公开模拟组合（雪球）**：[ZH3689205](https://www.xueqiu.com/P/ZH3689205) ｜ **版本**：`v3.2`（全组联审终版定稿）

---

## 一、团队成员与流水线分工

| 组员 | 姓名 | 学号 | 核心模块与职责 | 仓库目录 |
|---|---|---|---|---|
| 组员 1 | 李钰鹏 | 2024104286 | 双股票池数据工程（Tushare 个股行情/估值/复权/ST + 既有动态成分/申万行业/指数）、时效清洗与 SHA-256 校验 | [`member1_data/`](member1_data/) |
| 组员 2 | 刘宇睿 | 2024101054 | Alpha101 101 编号本地实现全量重筛、Holm 多重校正、`new012_amt_ema10` 改造、M0a–M5 消融信号与 Alpha015 覆盖诊断 | [`member2_signals/`](member2_signals/) |
| 组员 3 | 张沐 | 2024101056 | 3.0 开盘无前视账户回测（63 组账户、残差 0.0）、双印花税情景、行业暴露与 7 因子滞后持仓 FM 归因 | [`member3_backtest/`](member3_backtest/) |
| 组员 4 | 张恒瑞 | 2024101062 | 双池容量执行情景与压测、四档 HWM 产品费率、雪球 30 只前 45 缓冲映射回测、29 页 XeLaTeX 终版报告/15+5 页 PPT 与仓库整合 | [`member4_product/`](member4_product/) |

---

## 二、核心定案结论（净收益统一为固定卖出千 1 印花税 `net_10bp`，2023.01–2026.10，921 天）

- **课程主交付策略**：**沪深 300 干净共同池 `M4`** — `(z_bp + z_ep + z_lowvol_60 + z_lowturn_20) / 4` 四因子等权，每 5 交易日调仓，Top 50 等权，前 75 名保留缓冲带（上期目标持仓口径）。
- **绩效与跨池验证**：
  - **沪深 300 M4**：全期净收益 **`+56.58%`**（历史减半印花税 `net_histtax` 为 `+56.86%`），相对沪深 300 价格指数（`-0.33%`）累计差约 **`+56.90` 个百分点**，几何年化 `+13.05%`，算术年化夏普 **`0.905`**，最大回撤 **`-15.88%`**，平均单边换手仅 **`2.74%`**，标准日频算术 IR **`0.8748`**。
  - **M4 vs M5 取舍**：在沪深 300 单池内，M5（`+60.79% / 0.958 / -14.32%`）三项指标高于 M4；但在中证 500 同规格对照中，**M4 全面居首**（`+57.73% / 0.816 / -16.46%` 优于 M5 的 `+55.17% / 0.795 / -20.21%`），且由 `EP/BP` 派生的 `eb_proxy` 在中证 500 FM 归因中呈负贡献（`-2.90%/年`）。综合两个股票池跨池稳健性与模型简洁性，选定 **M4**。
- **两项核心工程发现**：
  1. **Alpha015 低覆盖约束诊断**：沪深 300 原 M1 在后续 184 次调仓退出的 `3,789` 个持股席位中，有 `3,605` 次（`95.1%`）仅因 `Alpha015` 缺失退出；解除该入池约束后，同一 M1 目标替换率由 `41.18%` 降至 `1.03%`，实际单边换手由 `41.91%` 降至 `2.35%`，毛收益由 `+27.58%` 升至 `+53.41%`，净收益由 `-3.44%` 升至 `+51.11%`（原含 015 同池内 `M3a -1.83%` 较 `M1 -3.44%` 差 `+1.62` 个百分点）。
  2. **改造 012 同池双面检验**：`new012_amt_ema10` 在两池三段单因子平均 IC 均为正，但扣费后组合改善仅见于沪深 300（同池 `M3b` 较 `M2` 增量 **`+8.58` 个百分点**；中证 500 同配方为 **`-6.93` 个百分点**）。
- **产品化容量执行情景与历史模拟费后表现**：
  - 5% 日均成交参与率上限下，沪深 300 M4 的单日调仓、假设 3 日拆单与 5 日清仓 P10 容量指标为 **`3.33 / 9.99 / 6.63` 亿元**（约为中证 500 M4 `1.09 / 3.27 / 2.64` 亿元的 3 倍）。逐期超限压测显示：`3.00` 亿元情景下假设 3 日拆单与 5 日清仓均 `0` 期超限（单日调仓 `15/184` 期超限）；`5.00` 亿元情景下单日调仓 `38/184` 期、假设 3 日拆单 `4/184` 期、5 日清仓 `1/185` 期（最长 `5.013` 天）超限；`10.00` 亿元与 `15.00` 亿元情景下假设 3 日拆单超限升至 `18/184` 与 `38/184` 期、5 日清仓超限升至 `79/185` 与 `142/185` 期（详见 `member4_product/results/capacity_stress_v3.csv`）。主回测采用次日开盘集中撮合，多日拆单属独立执行情景，首期募资宜控制在 `3–6` 亿元低超限情景并配合尾部拆单。
  - 机构 C 档费率（`0.60%` 管理费 + `0.15%` 托管费，相对沪深 300 价格指数超额收益按年度高水位计提 `15%`）下，扣除产品费用后的历史模拟累计收益为 **`+43.51%`**、几何年化 **`+10.39%`**、日频算术 IR **`0.730`**，产品层年化总费率拖累为 **`2.66` 个百分点**。

---

## 三、目录结构与成果索引

```text
csi300-quant-strategy/
├── README.md                                  # 项目总览与复现说明（本文件）
├── requirements.txt                           # Python 3.12 统一依赖
├── docs/
│   ├── PRD_模型3.0规格书与跨组接口契约.md      # 全组接口契约与红线规范
│   ├── 终版定稿说明_v3.2.md                    # 29 页 XeLaTeX 报告与 15+5 页路演定稿说明
│   └── 联审修订回执_v3.1.md                    # 历史阶段联审回执留档（已被 v3.2 替代）
├── member1_data/                              # 阶段 1：数据拉取与清洗脚本 + 2.25 MB 历史 seed
│   ├── fetch_tushare.py                       # Tushare 双池主拉取入口
│   ├── src/                                   # 清洗、复权、时效与导出模块
│   ├── seed/                                  # 94 期双池历史成分快照 + 申万行业历史 + 双指数原始输入
│   └── metadata/                              # hs300 & zz500 RUN_METADATA.json
├── member2_signals/                           # 阶段 2：101 重筛、改造 012 与 M0a-M5 信号代码 + 检验结果 CSV
│   ├── code/                                  # run_pool.py, models.py, operators.py, check_015.py 等
│   ├── hs300/{results,clean_015}/             # 沪深 300 全套 IC / 覆盖 / 015 退出审计表
│   └── zz500/results/                         # 中证 500 全套 IC / 覆盖表
├── member3_backtest/                          # 阶段 3：3.0 账户撮合、行业暴露与 7 因子 FM 归因
│   ├── code/run_backtest_v3.py                # 本文唯一净值源修订版回测引擎
│   ├── code/member3_official_ref/             # 组员 3 随包参考实现（留档交叉复算差异）
│   └── results/                               # metrics_v3.csv, decomp_v3.csv, daily_nav_*.csv 等
└── member4_product/                           # 阶段 4：双池容量/压测、四档费率、雪球映射、报告与 PPT
    ├── code/                                  # product_analysis_v3.py, xueqiu_export_v3.py, make_figures_report_tex.py, build_report_tex_v3.py, make_figures_v3_brand.py, build_deck_v3.py
    ├── results/                               # 费率、容量、压测、汇总 JSON/CSV
    ├── xueqiu/                                # 历史末期持仓、近8期调仓、30只映射回测、2026-11-25拟议切换单与截图人工核验记录
    ├── figures/{report_tex,slide_v3_brand}/   # 11 张矢量 PDF 研报图 + 12 张 300 DPI 暖白路演图
    ├── report/                                # REPORT_V3_FINAL.{tex,pdf}（29 页券商研报级 XeLaTeX 终版技术报告）
    └── deck/                                  # 路演_v3.{pptx,pdf}（15 页主路演）、技术备查_v3.{pptx,pdf}（5 页备查）与逐页讲稿_v3.md
```

> **关于大文件与数据获取**：仓库体积精简控制在 ~30 MB（单文件均 `< 7 MB`），已通过 `.gitignore` 排除体积达数百 MB 的日线/因子/权重 `.parquet` 中间矩阵，同时**完整保留了 2.25 MB 的 `member1_data/seed/` 历史种子数据与全部阶段 2–4 的轻量化 CSV/JSON/图表/报告产出**。

---

## 四、环境配置与复现指南

### 0. 安装环境（Python 3.12）

```bash
git clone https://github.com/z2823253773-p/csi300-quant-strategy.git
cd csi300-quant-strategy
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 方式 A：无需 Tushare Token —— 直接基于已提交的阶段 2–4 CSV/JSON 验证图表、报告与 PPT

克隆后即可在任意干净目录直接重跑全部矢量研报图表、动态生成并编译 29 页 XeLaTeX 终版 PDF 技术报告（内置页数、行距、全类型 `Overfull \hbox` 与 7 因子 FM 归因闭合 `< 1e-10` 自动断言，需本机已安装 TeX Live `xelatex`）及 15 页路演 PPT（导出 PDF 需安装 LibreOffice `soffice`）：

```bash
python member4_product/code/make_figures_report_tex.py
python member4_product/code/build_report_tex_v3.py
python member4_product/code/make_figures_v3_brand.py
python member4_product/code/build_deck_v3.py
```

> **跨平台字体配置说明**：`build_report_tex_v3.py` 生成的 `REPORT_V3_FINAL.tex` 内置 `\IfFileExists` 跨平台字体分支——在 **macOS** 环境下优先调用系统原生 `/System/Library/Fonts/Supplemental/Songti.ttc`（精确指定 `FontIndex=6` 常规体与 `FontIndex=1` 原生粗体）、`/System/Library/Fonts/STHeiti Medium.ttc` 与 `Times New Roman.ttf`；在 **Linux / Windows** 标准 TeX Live 环境下自动回退至 TeX Live 内置开源字体集 `FandolSong`、`FandolHei`、`TeX Gyre Termes` 与 `TeX Gyre Heros`，无需手动改码即可跨平台编译（跨系统字体度量差异可能导致分页微调 1 页属正常现象，逐页精确版式复现建议在 macOS + TeX Live 环境执行）。

### 方式 B：从零全链路端到端复现（阶段 1 → 阶段 4，需自备 Tushare Token）

**数据来源说明**：个股日行情、估值（`peTTM`/`pbMRQ`）、换手、复权因子与历史 ST 通过 Tushare 官方接口拉取；94 期月度历史成分快照、申万一级行业历史变更与双指数日行情直接读取仓库自带的 `member1_data/seed/`。

```bash
# 阶段 1：拉取 Tushare 双股票池真实数据并生成 processed/ 宽表（运行中提示输入 Tushare Token，或预先 export TUSHARE_TOKEN=...）
python member1_data/fetch_tushare.py \
  --existing-cache member1_data/seed \
  --tushare-cache member1_data/tushare_cache \
  --output-dir member1_data/tushare_data

# 阶段 2：运行沪深 300 与中证 500 的 101 编号重筛、改造 012、M0a-M5 信号与沪深 300 解除 015 覆盖对照
python member2_signals/code/run_pool.py --data member1_data/tushare_data/hs300/processed --out member2_signals/hs300
python member2_signals/code/run_pool.py --data member1_data/tushare_data/zz500/processed --out member2_signals/zz500
python member2_signals/code/check_015.py

# 阶段 3：运行 3.0 双池无前视账户回测（63 组账户、行业暴露与 7 因子 FM 归因）
python member3_backtest/code/run_backtest_v3.py \
  --data member1_data/tushare_data \
  --m2 member2_signals \
  --out member3_backtest/results

# 阶段 4：运行双池容量/压测、四档 HWM 费率、雪球 30 只前 45 缓冲回测、矢量图表、XeLaTeX 终版报告与 PPT
python member4_product/code/product_analysis_v3.py
python member4_product/code/xueqiu_export_v3.py
python member4_product/code/make_figures_report_tex.py
python member4_product/code/build_report_tex_v3.py
python member4_product/code/make_figures_v3_brand.py
python member4_product/code/build_deck_v3.py
```

---

## 五、交叉复算版本与学术诚信声明

1. **唯一净值源与交叉复算差异**：本项目以 `member3_backtest/code/run_backtest_v3.py` 生成的结果为唯一净值源。将其与组员 3 随包参考实现 `member3_backtest/code/member3_official_ref/engine_v3.py` 交叉复算后，全部 14 项核心账户精确对齐（最大差 `0.0000` 个百分点）；仅中证 500 `M0b` 存在 `0.12` 个百分点差异（修订版 `-10.96%` vs 随包旧净值 `-10.84%`，源于参考实现第 90 行仍采用全期 `any(is_st)` 而修订版改用逐日 `is_st`）。
2. **历史留后区间边界**：`2025-01-01` 至 `2026-10-30` 已参与方案讨论与消融比较，全文统一标注为“历史留后区间（已参与方案讨论）”，不宣称纯样本外盲测。
3. **价格指数与分红口径**：策略净值按后复权含分红计算，基准沪深 300（`000300.SH`）为价格指数；报告中按假设年股息率扣减 10–12 个百分点仅为情景估算，精确全收益超额需采用同起点全收益指数重算。
4. **雪球模拟记录与核验元数据分列**：雪球 30 股的 `+77.63%` 属历史映射回测，`2026-10-30` 清单属历史末期目标；`ZH3689205` 于 `2026-11-18` 按前期 M0a 30 股分层建仓，本地归档截图支持披露至 `2026-11-23`（净值 `0.9909`、累计 `-0.91%`，经人工核验记录于 `member4_product/xueqiu/xueqiu_screenshot_verified.json`），`2026-11-25` 拟议切换指令单（单边换手 `16.00%`）的平台生效时间以调仓成交回执为准。
