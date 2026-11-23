# 因子研究与模型构建：新版交接

本包使用组员1的 `2.0version.zip` 数据。阅读顺序：`意见核验与修订总结.md` → `因子与模型报告.md` → `组员3交接说明.md`。所有报告和总结均为Markdown；图表为PNG，不含页脚、水印或署名覆盖层。

## 复现

Python 3.12；在本包根目录执行。输入为新版 `quant_project/quant_project_data/processed`，不需要下载新行情。

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s code -p "test_*.py" -v
python code/research.py --data "新版数据目录/processed"
python code/extensions.py --data "新版数据目录/processed"
python code/write_reports.py
```

可选：重新比较两版输入数据（主研究不依赖旧数据）：

```powershell
python code/audit_data.py --old "旧版数据目录/processed" --new "新版数据目录/processed" --out results
```

`write_reports.py`使用本包随附的审计结果，不会自动寻找旧版目录；若更换输入，需先重新审计。新数据读入失败会报错，不会自动退回旧版或演示数据。

## 文件目录

- `code/research.py`：5个原始候选、训练内筛选、冻结基准/研究模型、1/5/20日检验和五分组诊断。
- `code/extensions.py`：两个比例化新公式、价格单位压力检验、已知行业子样本、配对IC、固定权重/调仓/成本网格。
- `code/test_research.py`：公式手工值、比例不变性、收益对齐、行业规模中性化、持仓漂移与交易额测试。
- `results/`：CSV数值结果及JSON输入指纹/参数。CSV只是检验数据表；叙述和总结在Markdown文档中。
- `signals/`：因子矩阵、主模型分数、目标持仓。`diagnostic_*`是探索因子，不属于主模型。
- `figures/`：5张可直接整合的图，图题和坐标标签用于解释内容，无水印。

本包不重复包含组员1的大型数据输入。`input_sha256.json`记录本次输入文件校验值。统计结果依赖给定样本及处理口径；未来输入更新应另存版本，不能沿用旧报告数字。
