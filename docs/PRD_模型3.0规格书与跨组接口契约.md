# 《沪深300 多因子量化策略与产品化方案》PRD（模型 3.0 规格书与跨组接口契约）

> **文档性质**：全组唯一权威 PRD（Product & Engineering Requirements Document），同时面向**四位组员**与**各位组员的 AI 助手（Codex / Claude / Cursor 等）**。  
> **执行闸门（Gate）**：文末 **§7《会议待勾选参数表》** 共有 4 个方框选项。**在小组会议勾选锁定前，各 AI 仅作接口检查与代码准备，不得覆盖正式结果、不得提前宣布主模型、不得修改雪球组合 `ZH3689205`。** 勾选锁定后，全组严格按本 PRD 接口契约无歧义推进，零返工、零口径冲突。

---

## 1. 产品目标、考核映射与项目边界

### 1.1 产品定位与课程交付物
- **投资定位**：沪深 300 历史动态成分股纯多头（Long-Only）、低换手、大容量的私募量化股票策略 / 机构专户产品。
- **四项硬性交付物**（截止 `2026-12-20 00:00`，内部封版目标 `2026-12-15`）：
  1. **书面技术报告**：20–30 页（Word + PDF，12 号字，1.5 倍行距，页边距 2.55 cm，正文无代码片段，封面含课程/全员姓名学号/角色/策略名/GitHub/雪球链接）。
  2. **产品路演 PPT**：17 页（14 页正文 + 3 页 Appendix 备查，严格 `≤ 20 页`，适配答辩“每页 6 张水平排列”纸质打印）。
  3. **可复现 Python 代码仓库**：上传 GitHub（从零克隆可一键复现，清理个人本地硬编码路径）。
  4. **公开雪球模拟组合**：`ZH3689205`（`https://www.xueqiu.com/P/ZH3689205`），披露 30 只分层映射与跟踪偏差，保留切换前历史记录。

### 1.2 学术诚信与版本隔离红线
- **严格区分“数据 3.0”与“模型 3.0”**：底层唯一数据为组员 1 的 **数据 3.0**（以 SHA-256 哈希核验，严禁混用 2.0）；模型按 `M0a / M0b / M1 / M2 / M3a / M3b / M4 / M5` 独立命名，**绝不覆盖历史基线**。
- **留后样本诚实披露**：`2019-01-02 ~ 2022-12-31` 为训练期，`2023-01-01 ~ 2024-12-31` 为验证期，`2025-01-01 ~ 2026-10-30` 统一称 **“历史留后区间（已参与方案讨论）”**，绝不宣称未接触过的纯盲测；仅规则冻结后用当时新行情生成的雪球实盘记录才算前瞻样本外检验。

---

## 2. 全部模型与因子的精确数学定义（供 AI 100% 精确实现）

### 2.1 输入数据掩码与预处理公理（所有因子必须遵守）
1. **原始有效观测掩码 `valid`**（必须在所有滚动、差分、平滑**之前**执行；**严禁先 `ffill` 收盘价再算因子**）：
   ```python
   valid = (
       tradestatus.astype(str).isin(['1', '1.0', 'True'])
       & (~is_suspended.fillna(True).astype(bool))
       & raw_valid_open & raw_valid_close & raw_valid_high & raw_valid_low & raw_valid_volume
       & (volume > 0)
   )
   # 所有量价原矩阵先执行 df = df.where(valid) 后，再做任何 rolling / diff / ewm！
   mask = tradable_mask.fillna(False).astype(bool) & valid  # 当日可入池截面掩码
   ```
2. **截面清洗与中性化函数 `clean(x, mask, size, industry, neutral)`**：
   - 截尾：当日 `mask` 内取中位数 `med` 与 `scale = 1.4826 * MAD`（若 `scale <= 1e-12` 回退至 `IQR / 1.349`），裁剪到 `[med - 5*scale, med + 5*scale]`；
   - 中性化（仅当 `neutral=True`）：对当日有效股票（要求 `ok.sum() >= 30` 且自由度 `ok.sum() > rank(X) + 10`）以 `industry`（申万一级行业 + 未知组单独成哑变量）和当日标准化 `ln_float_mv_proxy` 做 OLS，取残差；
   - 截面标准化：`z = (a - mean) / std`（均值 0、样本标准差 1，当日 `ddof=1`）。
3. **关键清洗分流**：
   - 基本面主锚 `bp`、`ep`、`small`：**`neutral = False`**（保留真实价值/规模风格配置）；
   - 全部新增量价/风险/代理因子（`alpha*`、`new012_amt_ema10`、`lowvol_60`、`lowturn_20`、`eb_proxy`）：**`neutral = True`**（控制申万一级行业+未知组与对数流通市值代理）。

### 2.2 全量单因子精确表达式清单

| 因子 ID | 中文规范名称 | 原始矩阵输入（3.0） | 精确数学 / Python 表达式（先 `.where(valid)` 再算） | `neutral` | 说明 |
|---|---|---|---|---|---|
| `bp` | 账面市值比 | `matrix_bp` | `bp` | `False` | 保留价值风格 |
| `ep` | 盈利收益率 | `matrix_ep` | `ep`（亏损缺失保持 `NaN`，不填 0） | `False` | 自动剔除当期亏损股 |
| `small` | 负对数流通市值代理 | `matrix_ln_float_mv_proxy` | `-ln_float_mv_proxy` | `False` | 流通市值代理 `ln(amount/(turn/100))` |
| `alpha006` | 10日开盘价量负相关 | `open_hfq`, `volume` | `-open_hfq.rolling(10, min_periods=10).corr(volume).clip(-1, 1)` | `True` | Kakushadze 原式（历史锚 & 3.0 重筛） |
| `alpha033` | 日内开收反转 | `open_hfq`, `close_hfq` | `rank_cs((open_hfq / close_hfq - 1).where(mask))` | `True` | 仅用于历史锚 `M0b` |
| `alpha040` | 波动调节高价量相关 | `high_hfq`, `volume` | 沿用 `沪深300_Alpha101全量重筛/expressions.json` 第 40 号 | `True` | 3.0 全量重筛入选 |
| `alpha016` | 高价量排名5日负协方差 | `high_hfq`, `volume` | 沿用 `沪深300_Alpha101全量重筛/expressions.json` 第 16 号 | `True` | 3.0 全量重筛入选 |
| `new012_amt_ema10` | 比例化成交额012平滑 | `amount`, `close_hfq` | `(-np.sign(amount.diff(1)) * (close_hfq / close_hfq.shift(1) - 1)).ewm(span=10, min_periods=5, adjust=True, ignore_na=False).mean()` | `True` | 标明为新公式；已在 3.0 独立复现 20 日 IC `0.020/0.023/0.036`（t 全 > 2） |
| `lowvol_60` | 60日低波动 | `returns` | `-returns.rolling(60, min_periods=40).std(ddof=1)` | `True` | 先 `.where(valid)` 防停牌零收益伪低波 |
| `lowturn_20` | 20日低换手 | `turn` | `-np.log(turn.rolling(20, min_periods=15).mean().where(lambda x: x > 0))` | `True` | `log` 仅对严格正数计算 |
| `eb_proxy` | **隐含账面盈利率代理** | `ep`, `bp` | `(ep / bp.where(bp > 0)).where(ep.notna() & (bp > 0))` | `True` | **严禁称严格公告时点会计 ROE**；须披露与 `bp/ep` 相关性及去留对照 |

> **注**：`diff(1)` 与 `shift(1)` 在原始交易日历上计算，若 `t` 或 `t-1` 任一日无效（停牌/缺失），结果自动为 `NaN`（不跨停牌日强行差分）。

### 2.3 模型 3.0 全套对照与消融矩阵（`M0a` – `M5`）

> **共同股票池铁律**：同组对照模型（如 `M1–M5`）在每个信号日 `t` **必须在所有参与模型得分均非空的共同有效股票集合 `common` 上计算和排序**，绝不允许某模型因某因子缺失而静默变成动态权重或不同股票池。  
> 记 `Z(x)` 为当日在 `common` 池上的截面标准化 `(x - mean) / std`。

| 模型 ID | 类别 | 精确得分公式（写死，零歧义） | 调仓与缓冲规则 | 状态 |
|---|---|---|---|---|
| **`M0a`** | 历史锚 1 | `B_old = (z_bp + z_ep + z_small) / 3` | 每 5 交易日，Top 50 等权，无缓冲 | 已冻结（`+45.38%`） |
| **`M0b`** | 历史锚 2 | `0.5 * B_old + 0.25 * z_alpha006 + 0.25 * z_alpha033` | 每 5 交易日，Top 50 等权，无缓冲 | 已冻结（`-6.52%`） |
| **`M1`** | **3.0 基准标杆** | `B_old = (z_bp + z_ep + z_small) / 3` | 5 日 + 前 75 缓冲（若加测 20 日组则同步跑 20 日 + 前 65 缓冲） | 5 日+75 已有（`+55.12%`） |
| **`M2`** | 消融 1（去 `small`） | `V_pure = Z((z_bp + z_ep) / 2)` | 与 `M1` 同频率、同缓冲、同共同池 | 待 3.0 实测 |
| **`M3a`** | 3.0 Alpha101 重筛 | `0.9 * B_old + 0.1 * (z_alpha040 + z_alpha006 + z_alpha016) / 3` | 5 日 + 前 75 缓冲 | 已跑完（`+54.41%`） |
| **`M3b`** | 消融 2（改造 012） | `0.85 * Base + 0.15 * z_new012_amt_ema10`（`Base` 为 `Z(B_old)` 或 `V_pure`，与 `M1/M2` 对齐） | 同频率、同缓冲、同共同池 | 待 3.0 实测 |
| **`M4`** | 消融 3（低波+低换手，不含 E/B） | 方式见 §7 勾选：① **因子等权**：`(z_bp + z_ep + z_lowvol_60 + z_lowturn_20) / 4`；② **分块等权**：`0.5 * V_pure + 0.5 * Z((z_lowvol_60 + z_lowturn_20) / 2)` | 同频率、同缓冲、同共同池 | 待 3.0 实测 |
| **`M5`** | 消融 4（加 E/B 代理） | 方式见 §7 勾选（唯一主规格提前写死）：① **五因子等权**：`(z_bp + z_ep + z_eb_proxy + z_lowvol_60 + z_lowturn_20) / 5`（初始价值 40% / 其他 60%）；② **分块二次 Z 化 50/50**：`0.5 * V_pure + 0.5 * Z((z_eb_proxy + z_lowvol_60 + z_lowturn_20) / 3)` | 同频率、同缓冲、同共同池 | 待 3.0 实测 |

### 2.4 排名缓冲带（Buffer）精确伪代码（消除目标持仓 vs 实际持仓歧义）
```python
# 设 Top-N = 50，保留阈值 K = 75（5日组）或 65（20日组）
# 信号日 t 收盘算分，t+1 开盘执行；并列分数按 stock_code 升序稳定排序
scores_t = score_df.loc[t].dropna().sort_values(ascending=False, kind='mergesort')  # 同分按代码升序
rank_map = {code: r for r, code in enumerate(scores_t.index, start=1)}

# prev_held 定义由 §7 第 3 项锁定（默认与 3.0 portfolio.py 一致：上期目标持仓 prev_target）
kept = [c for c in scores_t.index if c in prev_held and rank_map[c] <= K][:50]
adds = [c for c in scores_t.index if c not in kept][:50 - len(kept)]
chosen = kept + adds  # 若当日有效股票 < 50，按实际数量等权（1 / len(chosen)），记录告警
```

---

## 3. 跨组标准化文件接口契约（Interface Contracts）

> **强制格式约定**：
> - 日期统一 `YYYY-MM-DD` 字符串（CSV）或 `datetime64[ns]` 升序索引（Parquet）；
> - 股票代码统一 `600015.SH` / `000001.SZ`（6 位数字 + 大写交易所后缀）；
> - 所有收益率、换手率、回撤、权重在 CSV/JSON 中一律存为**小数比例**（如 `0.1276` 表示 `12.76%`），**仅在最终报告/PPT 渲染层乘 100 加 `%`**；
> - 全部 CSV 统一使用 **英文 Snake_Case 列名**、`UTF-8` 编码、不写无名索引列（除非显式标为 `date`）。

### 接口 1：组员 1 → 全组（数据 3.0 只读输入）
- **目录**：`quant_project_v3/processed/`（同步后全组锁定唯一路径）
- **核心文件**：
  - `matrix_{open_hfq,close_hfq,high_hfq,low_hfq,vwap_hfq,volume,amount,turn,returns,bp,ep,ln_float_mv_proxy,tradable_mask,open_quote_observed}.parquet`
  - `clean_daily_panel.parquet`（必须含 `trade_date, stock_code, tradestatus, is_st, is_suspended, is_new_stock, in_index_universe, open, preclose, industry_scheme, sw_l1_name, raw_valid_*`）
  - `benchmark_daily.parquet`（必须含沪深 300 指数 `open, close, preclose, ret`）
  - `input_sha256_v3.json`（上述全部文件的 SHA-256 指纹）

### 接口 2：组员 2 → 组员 3 & 4（信号与因子检验交付）
- **目录**：`member2_v3/`
- **必交文件与精确列名**：
  1. `signals/target_weights_v3.csv`：`model, signal_date, execution_date, stock_code, score, target_weight, stage`
     - `model` 取值严格限定为 `M0a, M0b, M1, M2, M3a, M3b, M4, M5`（及对应频率后缀如 `_5d` / `_20d`）；
     - `stage` 取值严格限定为 `validation`（2023–2024）、`seen`（2025–2026.10 历史留后段）。
  2. `signals/factor_{name}.parquet`：索引 `trade_date`、列 `stock_code`、`float32`，包含全部 11 个清洗后因子。
  3. `results/factor_ic_v3.csv`：`factor, horizon, stage, n, mean_ic, std_ic, icir, pos_ratio, hac_t, hac_p, ac_5d, ac_20d`
  4. `results/paired_ic_v3.csv`：`model_a, model_b, horizon, stage, n, mean_diff, hac_t, hac_p`（同日配对 IC 差）
  5. `results/factor_corr_v3.csv`：各因子（含 `bp, ep, eb_proxy, lowvol_60, lowturn_20, new012_amt_ema10`）训练期与全期截面秩相关矩阵。
  6. `results/model_config_v3.json`：记录全部勾选参数、模型公式、输入哈希指纹。

### 接口 3：组员 3 → 组员 4（3.0 账户回测、行业偏离与归因交付）
- **目录**：`member3_v3/results/`
- **必交文件与精确列名**：
  1. `daily_nav_v3.csv`：`date, hs300_intraday, {model}_net_10bp, {model}_net_histtax, {model}_gross`（唯一 921 天估值日历，从 `2023-01-09` 至 `2026-10-30`，首日 `2023-01-09` 为开盘进场后收盘净值，初始资产为 `1.0`）。
  2. `metrics_v3.csv`：`model, fee_scenario, stage, n_days, cum_return, ann_geom, ann_vol, sharpe_arith_rf0, geom_over_vol, max_drawdown, dd_recovery_days, mean_half_turn, ann_half_turn, excess_vs_hs300, te_vs_hs300, ir_vs_hs300`
     - `fee_scenario` 取值：`gross`（无费）、`net_10bp`（固定卖出 10 bp 压力情景）、`net_histtax`（2023-08-28 后印花税减半 5 bp 历史税率情景）；
     - `stage` 取值：`all`、`validation`、`seen`。
  3. `turnover_v3.csv`：`execution_date, model, fee_scenario, buy_weight, sell_weight, half_turn, cost_ratio, blocked_buy_weight, blocked_sell_weight`
  4. `open_weights_{model}.parquet`：账户开盘调仓后**实际持仓权重**矩阵（供归因与容量计算）。
  5. `industry_exposure_v3.csv`：`model, scope, sw_l1_name, weight`（`scope` 为 `full_mean` 全期均值与 `latest_20261030` 末期持仓，核查银行/金融集中度）。
  6. `decomp_v3.csv`：`model, component, daily_mean_bp, ann_arith_pct`（滞后实际持仓暴露归因，须分列各因子贡献、隔夜、盘中、现金、费用、特异残差并给出与实际毛/净收益的对账差）。

### 接口 4：组员 4 → 终版产品、报告、PPT 与 Codex
- **目录**：`member4/`
- **核心交付**：
  1. `results/product_summary_v3.json`（动态读取接口 2 & 3，零硬编码，含四档 HWM 费率、ADV20 流动性分布、5% 参与率硬约束与平方根冲击半衰容量）；
  2. `xueqiu/xueqiu_30_tracking_backtest.csv`（雪球 30 只分层权重 `前10×4%+后20×3%` 相对 50 只等权的跟踪偏差回测）；
  3. `report/技术报告终版.{docx,pdf}`、`deck/路演.{pptx,pdf}`（由 Codex 按更新后的 `CODEX_PPT_BRIEF.md` 一键出图+成稿）、`deck/逐页讲稿.md`、`deck/QA手册.md`。

---

## 4. 账户执行引擎与评估指标硬性公式（零口径偏差）

1. **开盘买卖许可（沿用 3.0 `portfolio.py`）**：
   - `ok = tradestatus & open_quote_observed & (open > 0)`
   - `threshold = 0.195 (688/300/301/302), 0.045 (当日 is_st), 0.095 (其他主板)`
   - `move = open / preclose - 1`
   - `buy_ok = ok & in_index_universe & (~is_st) & (~is_new_stock) & ~(move >= threshold)`
   - `sell_ok = ok & ~(move <= -threshold)`（允许已出池或变 ST 持仓在非开盘跌停时卖出）
2. **双印花税情景**：
   - 买侧统一：佣金 `3 bp` + 滑点 `10 bp`；
   - 卖侧 `net_10bp`（固定压力情景）：全期印花税 `10 bp` + 佣金 `3 bp` + 滑点 `10 bp`（等额往返约 `36 bp`）；
   - 卖侧 `net_histtax`（历史税率情景）：`date < 2023-08-28` 印花税 `10 bp`，`date >= 2023-08-28` 按财政部税务总局 2023 年第 39 号公告减半为 `5 bp`。
3. **唯一逐日净值分段与沪深 300 对齐**：
   - 组合日收益：`ret = nav.pct_change(); ret.iloc[0] = nav.iloc[0] - 1`；
   - 沪深 300 首日（`2023-01-09`）：`hs300_ret.iloc[0] = close / open - 1`（`+0.36%`，全期期末 `0.9967` / `-0.33%`），次日起为标准 `close / prev_close - 1`；
   - 任意子段累计收益：`(1 + ret.loc[start:stop]).cumprod().iloc[-1] - 1`，确保 `(1 + r_val) * (1 + r_seen) - 1 == r_all`。
4. **双夏普口径**：
   - `sharpe_arith_rf0`（主口径）：`(ret.mean() / ret.std(ddof=1)) * np.sqrt(252)`（标准日频算术年化夏普，$R_f=0$）；
   - `geom_over_vol`（附列口径）：`ann_geom / ann_vol`。

---

## 5. 四位组员分工与强制验收断言（Acceptance Checklist）

| 组员 | 核心职责 | 交付前必须通过的自检断言（PASS 才能往下游交接） |
|---|---|---|
| **组员 1** | 同步数据 3.0 只读底表与 SHA-256 指纹；核对第 3 章数据边界说明 | ① 全部宽表 `index`/`columns` 100% 相同；② `open_quote_observed`、逐日 `is_st`、`benchmark_daily` 开盘价完整无异常；③ 交付 `input_sha256_v3.json` |
| **组员 2** | 整合 101 全量重筛；生成 `M1–M5` 消融信号与配对 IC 检验 | ① 6 项+ 单元测试全通过（含前缀因果性测试、停牌非 `ffill` 测试、权重和严格为 1.0）；② 同日 `M1–M5` 共享完全相同的 `common` 有效股票集；③ `input_sha256_v3.json` 校验一致 |
| **组员 3** | 3.0 同一账户引擎重放 `M0–M5`；输出双税率、行业偏离与归因对账 | ① 全模型共用同一 921 天日历；② 任意模型 `(1+r_val)*(1+r_seen)-1` 与 `r_all` 误差 `< 1e-10`；③ `hs300_intraday` 全期精确等于 `-0.33%`（`0.9967`）；④ 现金全程 `>= 0`；⑤ 清理 `extract_suspended.py` |
| **组员 4** | 先修旧稿沪深 300 硬伤 & 补雪球 30 只映射回测；定案后完成产品分析、报告、Codex 17 页 PPT 与 GitHub 整合 | ① 报告/PPT/讲稿全部数字动态读取 `v3` CSV/JSON，零硬编码、零旧 `+0.12%` 残留；② PPT 17 页渲染 PNG 逐页核查零重叠溢出且适配 6 合 1 打印；③ GitHub 从零克隆可完整复现 |

---

## 6. 5 步推进计划（按顺序执行，绝不返工）

1. **Step 1（会前同步 & 硬伤先修）**：组员 1/2/3 将数据 3.0 与 3.0 代码包同步到全组统一目录；组员 4 先修掉现有报告里沪深 300 `+0.12% → -0.33%` 口径，并补跑雪球 30 只映射跟踪偏差回测。
2. **Step 2（明天下午小组会，30 分钟）**：全组勾选并锁死下方 **§7 的 4 个参数**，同时收齐封面真实姓名、学号与 GitHub 仓库负责人。
3. **Step 3（会后 1–2 天，组员 2 → 组员 3 流水线）**：组员 2 交付接口 2（`M1–M5` 消融信号与配对 IC）→ 组员 3 交付接口 3（3.0 账户绩效、双税率、行业偏离与归因表）。
4. **Step 4（全组评审定案，0.5 天）**：对照 `M1–M5` 公平消融表正式拍板最终交付主模型（若 `M4/M5` 综合胜出且无过度行业/市值扭曲则升级；若 `M1` 最稳则以 `M1` 定案），再决定是否更新雪球组合 `ZH3689205`（绝不改写切换前历史记录）。
5. **Step 5（定案后 2–3 天，12 月 15 日前封版）**：组员 4 重跑产品费率/容量/雪球导出、刷新 30 页书面技术报告、更新 `CODEX_PPT_BRIEF.md` 交给 Codex 一键出图并生成 17 页终版 PPT，全组联审复现后于 `2026-12-20 00:00` 前提交。

---

## 7. 明天下午会议唯一待勾选参数表（勾完即冻结执行！）

请全组明天下午只针对以下 **4 项** 勾选定案，勾完后立刻交给各位组员的 AI 启动 Step 3：

1. **消融实验的调仓频率与缓冲带组合（可单选或双跑）**：
   - [ ] 仅跑 **`5 交易日 + 前 75 缓冲`**（直接与 3.0 已有标杆 `M1: +55.12%` 同条件对齐）
   - [ ] 同时跑 **`5 交易日 + 前 75 缓冲`** 与 **`20 交易日 + 前 65 缓冲`**（完整对比周度与月度频率差异）
2. **提前锁定的 `M4 / M5` 唯一主合成规格（不事后挑高的）**：
   - [ ] **因子直接等权**（`M4` 四因子各 25%，`M5` 五因子各 20%，最朴素零调参）
   - [ ] **分块二次 Z 化 50/50**（`50% V_pure + 50% QLT`，价值与风险/质量大类均衡）
3. **缓冲带“原持仓 `prev_held`”判定口径**：
   - [ ] **上期目标持仓**（与现有 3.0 `portfolio.py` 逻辑保持 100% 一致，信号层与账户层解耦）
   - [ ] **账户当前实际持仓**（遇开盘触限受阻时以实际持仓进入保留区，需由账户引擎内生选股）
4. **各模块交付 DDL 与封面信息**：
   - 组员 2 交付接口 2 日期：`2026-11-__` ｜ 组员 3 交付接口 3 日期：`2026-11-__` ｜ 组员 4 封版报告与 PPT 日期：`2026-12-__`
   - 封面四位组员姓名 & 学号 + GitHub 仓库 URL：`[会后填入]`
