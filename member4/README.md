# 组员 4：产品分析、雪球模拟盘与汇报整合交付

本目录包含期末大作业组员 4 的全部测算代码、统一视觉图表、雪球模拟组合材料、29 页终版技术报告与 20 页路演 PPT。

## 一、环境与一键复现

所有脚本均在 `member4/` 目录下运行，使用已配置的虚拟环境 `.venv`（Python 3.12）：

```bash
cd /Users/henryz/Desktop/量化课程/大作业/member4

# 1. 产品分析（三口径容量测算 + 四档费率逐日计提）
.venv/bin/python code/product_analysis.py

# 2. 雪球模拟组合最新持仓与近 8 期调仓导出
.venv/bin/python code/xueqiu_export.py

# 3. 按统一视觉规范重绘全组 16 张核心图表（report / slide / slide_notitle 三套）
.venv/bin/python code/make_figures.py

# 4. 生成终版技术报告（Word + PDF + 预览图，29 页）
.venv/bin/python code/build_report.py

# 5. 生成路演 PPT（PPTX + PDF + 20 页逐页预览图）
.venv/bin/python code/build_deck.py
```

如需从零重建 `.venv`：
```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
```

## 二、目录结构

| 目录 / 文件 | 说明 |
|---|---|
| `code/style.py` | 全组统一视觉系统（主色 `#14284B`、Research `#A38F6E`、沪深300 `#9AA0A6`、强调 `#C23B22`） |
| `code/product_analysis.py` | 流动性分布、三口径容量测算、四档费率净值核算 |
| `code/xueqiu_export.py` | 最新一期 50 只持仓、30 只备用持仓、近 8 期调仓与操作手册 |
| `code/make_figures.py` | 16 张核心图表重绘（含组员 1 三张数据图） |
| `code/build_report.py` | `REPORT_FINAL.md` → `REPORT_FINAL.docx` / `REPORT_FINAL.pdf` |
| `code/build_deck.py` | `路演.pptx` / `路演.pdf` 与逐页 `preview/` |
| `results/` | `product_summary.json`、`RUN_LOG.md`、`capacity_*.csv`、`fee_analysis.csv` 等 |
| `figures/` | `report/`（16cm）、`slide/`（16:9）、`slide_notitle/`（PPT 专用无内标题版） |
| `xueqiu/` | 最新持仓 CSV、调仓记录、`雪球操作手册与日志模板.md`、`screenshots/` |
| `report/` | `REPORT_FINAL.md`（唯一源稿）、`REPORT_FINAL.docx`、`REPORT_FINAL.pdf` |
| `deck/` | `路演.pptx`、`路演.pdf`、`逐页讲稿.md`（15 分钟四段）、`QA手册.md`（20 题） |

## 三、待补全占位符与上游说明

1. **待填占位符**：`report/REPORT_FINAL.md`、`deck/路演.pptx` 与 `deck/逐页讲稿.md` 中保留了 `【待填：...】` 占位符（课程全称、四位组员姓名与学号、指导教师、GitHub 链接、雪球组合链接）。
2. **雪球截图自动接入**：在雪球创建组合并截图后，将图片放入 `member4/xueqiu/screenshots/`，重新运行 `code/build_deck.py` 与 `code/build_report.py` 即可自动嵌入。
3. **上游脚本说明**：`member3/code/extract_suspended.py` 为早期遗留辅助脚本（含 Windows 硬编码路径），`member3/code/backtest.py` 已直接读取 `clean_daily_panel.parquet` 的 `is_suspended`，该脚本已废弃，不参与复现。
