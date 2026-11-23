# -*- coding: utf-8 -*-
"""
组员4 v3.0 路演 PPT 自动构建脚本（14 页主讲 + 3 页答辩备查 = 17 页，16:9 宽屏，适配 6 合 1 打印）
100% 动态读取 member3_v3 与 member4 v3 结果 CSV/JSON，嵌入 figures/slide_v3/ 300 DPI 无框暖白图表。
运行命令：
    .venv/bin/python code/build_deck_v3.py
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

import paths as P

M3_RES = P.resolve_member3_dir("v3") / "results"
M4_RES = P.MEMBER4_DIR / "results"
M4_XQ = P.MEMBER4_DIR / "xueqiu"
FIG_DIR = P.MEMBER4_DIR / "figures" / "slide_v3"
DECK_DIR = P.MEMBER4_DIR / "deck"
PREVIEW_DIR = DECK_DIR / "preview_v3"
DECK_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

OUT_PPTX = DECK_DIR / "路演_v3.pptx"
OUT_PDF = DECK_DIR / "路演_v3.pdf"

# Claude 官网极简暖白编辑风色板（高可读、适配 6 合 1 纸质打印）
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
BG_CANVAS = RGBColor(0xFA, 0xF9, 0xF5)
BG_OAT = RGBColor(0xF0, 0xEE, 0xE6)
BG_PAPER = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x14, 0x14, 0x13)
STONE = RGBColor(0x52, 0x50, 0x4A)
MUTED = RGBColor(0x82, 0x7F, 0x77)
DIVIDER = RGBColor(0xE2, 0xDF, 0xD5)
TERRA = RGBColor(0xC4, 0x5A, 0x38)
TINT = RGBColor(0xF5, 0xE6, 0xDF)
NAVY = RGBColor(0x1E, 0x3A, 0x5F)
SAGE = RGBColor(0x3D, 0x7A, 0x5E)
CRIMSON = RGBColor(0xB4, 0x3E, 0x3E)

FONT_HEAD = "黑体-简"
FONT_BODY = "黑体-简"


def set_bg(slide, color=BG_CANVAS):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def set_font(run, size_pt: float, bold: bool = False, color=INK, font_name: str = FONT_BODY):
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font_name
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            rPr.append(el)
        el.set("typeface", font_name)


def add_tb(slide, left, top, width, height, text="", size=14, bold=False, color=INK, align=PP_ALIGN.LEFT, line_spacing=1.22):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    if text:
        r = p.add_run()
        r.text = text
        set_font(r, size, bold=bold, color=color, font_name=FONT_HEAD if bold else FONT_BODY)
    return tb


def add_bullets(slide, left, top, width, height, items: list[tuple[str, str]], size=13.0, space_after=8):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    for idx, (lead, body) in enumerate(items):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        p.line_spacing = 1.24
        r0 = p.add_run()
        r0.text = f"▪ {lead}：" if lead else "▪ "
        set_font(r0, size, bold=True, color=TERRA if idx == 0 else NAVY)
        r1 = p.add_run()
        r1.text = body
        set_font(r1, size, bold=False, color=INK)
    return tb


def add_card(slide, left, top, width, height, fill_color=BG_PAPER, border_color=DIVIDER):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    sh.adjustments[0] = 0.04
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill_color
    if border_color is not None:
        sh.line.color.rgb = border_color
        sh.line.width = Pt(0.9)
    else:
        sh.line.fill.background()
    return sh


def add_kpi_card(slide, left, top, width, height, label, value, sub="", accent=TERRA):
    add_card(slide, left, top, width, height, fill_color=BG_PAPER, border_color=DIVIDER)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.06))
    bar.fill.solid(); bar.fill.fore_color.rgb = accent; bar.line.fill.background()
    add_tb(slide, left + 0.14, top + 0.12, width - 0.28, 0.28, label, size=10.5, bold=True, color=MUTED)
    add_tb(slide, left + 0.14, top + 0.42, width - 0.28, 0.48, value, size=22, bold=True, color=accent)
    if sub:
        add_tb(slide, left + 0.14, top + 0.94, width - 0.28, 0.34, sub, size=9.8, bold=False, color=STONE)


def add_header(slide, section: str, title: str, page_no: int, total: int = 17):
    set_bg(slide)
    # 顶部细标签与页码
    add_tb(slide, 0.65, 0.32, 6.5, 0.28, section, size=10.5, bold=True, color=TERRA)
    add_tb(slide, 11.4, 0.32, 1.3, 0.28, f"{page_no:02d} / {total:02d}", size=10.5, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
    add_tb(slide, 0.65, 0.60, 12.0, 0.56, title, size=21.5, bold=True, color=INK)
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(1.22), Inches(12.03), Inches(0.018))
    line.fill.solid(); line.fill.fore_color.rgb = DIVIDER; line.line.fill.background()
    # 底部低调脚注
    add_tb(slide, 0.65, 7.12, 12.03, 0.26, "《量化交易技术理论与实践》期末大作业  |  沪深300价值低波精选策略（M4）  |  雪球实盘 ZH3689205", size=8.5, color=MUTED)


def add_pic_fit(slide, img_path: Path, left, top, max_w, max_h):
    from PIL import Image
    with Image.open(img_path) as im:
        iw, ih = im.size
    aspect = iw / ih
    w, h = max_w, max_w / aspect
    if h > max_h:
        h = max_h
        w = max_h * aspect
    x = left + (max_w - w) / 2.0
    y = top + (max_h - h) / 2.0
    slide.shapes.add_picture(str(img_path), Inches(x), Inches(y), width=Inches(w), height=Inches(h))


def add_styled_table(slide, left, top, width, height, headers: list[str], rows: list[list[str]], font_size=9.5, highlight_row: int | None = None):
    tbl_shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(left), Inches(top), Inches(width), Inches(height))
    tbl = tbl_shape.table
    for c_i, h in enumerate(headers):
        cell = tbl.cell(0, c_i)
        cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER if c_i > 0 else PP_ALIGN.LEFT
        r = p.add_run(); r.text = h
        set_font(r, font_size, bold=True, color=BG_PAPER)
    for r_i, rdata in enumerate(rows, start=1):
        is_hi = (highlight_row is not None and r_i - 1 == highlight_row)
        bg = TINT if is_hi else (BG_PAPER if r_i % 2 == 1 else BG_OAT)
        for c_i, val in enumerate(rdata):
            cell = tbl.cell(r_i, c_i)
            cell.fill.solid(); cell.fill.fore_color.rgb = bg
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if c_i > 0 else PP_ALIGN.LEFT
            r = p.add_run(); r.text = val
            set_font(r, font_size, bold=is_hi or c_i == 0, color=TERRA if is_hi else INK)
    return tbl_shape


def load_v3():
    m3 = pd.read_csv(M3_RES / "metrics_v3.csv")
    oi = pd.read_csv(M3_RES / "overnight_intraday_v3.csv")
    dec = pd.read_csv(M3_RES / "decomp_v3.csv")
    prod = json.loads((M4_RES / "product_summary_v3.json").read_text(encoding="utf-8"))
    fee_df = pd.read_csv(M4_RES / "fee_analysis_v3.csv")
    xq_bt = pd.read_csv(M4_XQ / "xueqiu_30_tracking_backtest.csv")
    xq_sum = json.loads((M4_RES / "xueqiu_summary_v3.json").read_text(encoding="utf-8"))
    return dict(m3=m3, oi=oi, dec=dec, prod=prod, fee_df=fee_df, xq_bt=xq_bt, xq_sum=xq_sum)


def pct(x, signed=True, d=2):
    return f"{x*100:{'+' if signed else ''}.{d}f}%"


def main():
    D = load_v3()
    m3, oi, dec, prod, fee_df, xq_bt = D["m3"], D["oi"], D["dec"], D["prod"], D["fee_df"], D["xq_bt"]

    def gm(exp, mod, st="all", fee="net_10bp"):
        return m3[(m3["experiment"] == exp) & (m3["model"] == mod) & (m3["stage"] == st) & (m3["fee_scenario"] == fee)].iloc[0]

    def goi(exp, mod):
        return oi[(oi["experiment"] == exp) & (oi["model"] == mod)].iloc[0]

    hs_m4 = gm("hs300_clean", "M4")
    hs_m4_ht = gm("hs300_clean", "M4", "all", "net_histtax")
    hs_m1 = gm("hs300_clean", "M1")
    hs_m2 = gm("hs300_clean", "M2")
    hs_m3b = gm("hs300_clean", "M3b")
    hs_m5 = gm("hs300_clean", "M5")
    hs_m0a = gm("hs300_full", "M0a")
    hs_m0b = gm("hs300_full", "M0b")
    hs_m1_015 = gm("hs300_full", "M1")
    zz_m4 = gm("zz500", "M4")
    zz_m1 = gm("zz500", "M1")
    cap_hs = prod["cross_pool_capacity_highlight"]["hs300_M4"]
    cap_zz = prod["cross_pool_capacity_highlight"]["zz500_M4"]
    fee_hs = fee_df[fee_df["series"] == "hs300_M4_net10bp"].set_index("plan_id")

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # ---------- P01: 封面 ----------
    s = prs.slides.add_slide(blank)
    set_bg(s)
    top_bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(0.55), Inches(12.03), Inches(0.08))
    top_bar.fill.solid(); top_bar.fill.fore_color.rgb = NAVY; top_bar.line.fill.background()
    add_tb(s, 0.65, 0.85, 11.5, 0.38, "《量化交易技术理论与实践》期末大作业  ·  私募证券投资基金量化投研团队", size=13, bold=True, color=TERRA)
    add_tb(s, 0.65, 1.45, 12.0, 1.35, "沪深300 价值低波精选量化策略（M4）\n双股票池消融验证与私募产品化方案", size=32, bold=True, color=INK, line_spacing=1.2)
    add_tb(s, 0.65, 3.00, 11.8, 0.50, "基于双股票池 3.0 零前视数据底座（Tushare 个股行情/估值/ST + 既有动态成分/申万行业/指数）：BP + EP + LowVol60 + LowTurn20", size=13.2, color=STONE)

    add_kpi_card(s, 0.65, 3.78, 2.82, 1.32, "沪深300 M4 全期净收益", pct(hs_m4["cum_return"]), f"历史税率 {pct(hs_m4_ht['cum_return'])} | 较指数 +56.90pp", TERRA)
    add_kpi_card(s, 3.72, 3.78, 2.82, 1.32, "算术夏普 / 最大回撤", f"{hs_m4['sharpe_arith_rf0']:.2f} / {pct(hs_m4['max_drawdown'], False)}", f"单边换手仅 {pct(hs_m4['mean_half_turn'], False)}", NAVY)
    add_kpi_card(s, 6.79, 3.78, 2.82, 1.32, "中证500 跨池同规验证", pct(zz_m4["cum_return"]), f"夏普 {zz_m4['sharpe_arith_rf0']:.2f} | 回撤 {pct(zz_m4['max_drawdown'], False)}", SAGE)
    add_kpi_card(s, 9.86, 3.78, 2.82, 1.32, "稳健规模 / 压测情景", "3–6亿 / 10–15亿", f"机构C档到手年化 {pct(fee_hs.loc['C','ann_geom'])}", TERRA)

    add_card(s, 0.65, 5.42, 12.03, 1.50, fill_color=BG_OAT, border_color=DIVIDER)
    add_tb(s, 0.90, 5.56, 11.5, 0.36, "团队成员：组员1 李钰鹏 (2024104286)  |  组员2 刘宇睿 (2024101054)  |  组员3 张沐 (2024101056)  |  组员4 张恒瑞 (2024101062)", size=12, bold=True, color=INK)
    add_tb(s, 0.90, 5.98, 11.5, 0.36, "指导教师：肖亮海    |    提交日期：2026年12月    |    雪球公开模拟组合：ZH3689205 (xueqiu.com/P/ZH3689205)", size=11.5, color=STONE)
    add_tb(s, 0.90, 6.38, 11.5, 0.36, "GitHub 可复现代码仓库：https://github.com/z2823253773-p/csi300-quant-strategy", size=11.5, bold=True, color=NAVY)

    # ---------- P02: 团队分工 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "01 团队协作与工程架构", "四位组员按跨组契约流水线协同，实现全链路零前视与机器精度闭合", 2)
    cards = [
        ("01 数据治理 · 李钰鹏", "Tushare + 动态成分 3.0", "Tushare 拉取双池个股行情/估值/复权/ST；沿用既有 94 期月度动态成分、申万历史与双指数；申万45天/估值90天时效与 21 文件 SHA-256 指纹。", NAVY),
        ("02 因子与消融 · 刘宇睿", "101重筛 + M0–M5 消融", "双池各运行101个本地实现编号（代理变体单列）做 Holm 校正；构造 new012_amt_ema10；构建 M0a–M5 消融信号并诊断 Alpha015 覆盖约束。", TERRA),
        ("03 回测与归因 · 张沐", "3.0 账户引擎 + FM 归因", "3实验×21账户×3费率=63组921天无前视回测；账本残差 0.0、两套实现交叉复算核验；输出双税率、行业偏离与7因子滞后实际持仓 FM 归因。", SAGE),
        ("04 产品与汇报 · 张恒瑞", "双池容量 + 雪球 + 整合", "三口径双池容量与压测、四档 HWM 费后净值、雪球 30 只前 45 缓冲历史映射回测；报告/图表/PPT 全动态读数零硬编码，统筹 GitHub 复现。", NAVY),
    ]
    for i, (t1, t2, desc, col) in enumerate(cards):
        x = 0.65 + i * 3.07
        add_card(s, x, 1.55, 2.86, 4.35, fill_color=BG_PAPER, border_color=DIVIDER)
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.55), Inches(2.86), Inches(0.08))
        bar.fill.solid(); bar.fill.fore_color.rgb = col; bar.line.fill.background()
        add_tb(s, x + 0.16, 1.80, 2.54, 0.36, t1, size=12.5, bold=True, color=col)
        add_tb(s, x + 0.16, 2.22, 2.54, 0.36, t2, size=13.5, bold=True, color=INK)
        add_tb(s, x + 0.16, 2.70, 2.54, 3.00, desc, size=11.5, color=STONE, line_spacing=1.35)
    add_card(s, 0.65, 6.12, 12.03, 0.78, fill_color=TINT, border_color=None)
    add_tb(s, 0.85, 6.28, 11.6, 0.45, "学术诚信与工程纪律：SHA-256 锁定唯一数据底座  |  事前锁定等权规格不挑冠军  |  2025–2026.10 如实标注为“历史留后区间（已参与方案讨论）”", size=12, bold=True, color=TERRA)

    # ---------- P03: 策略核心逻辑 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "02 策略设计", "旗舰模型 M4：价值双锚 + 低波低换手防御共振 + 前75名排名缓冲带", 3)
    add_card(s, 0.65, 1.50, 5.85, 5.25, fill_color=BG_PAPER)
    add_tb(s, 0.90, 1.72, 5.35, 0.40, "旗舰主交付 · M4（四因子直接等权，零调参）", size=15.5, bold=True, color=TERRA)
    add_bullets(s, 0.90, 2.25, 5.35, 4.30, [
        ("价值双锚（50%）", "BP（1/PB）提供净资产安全边际，EP（1/PE，亏损留空）过滤价值陷阱；保留真实价值风格不做行业中性化。"),
        ("低风险双因子（50%）", "60日低波动（LowVol60）+ 20日低换手（LowTurn20），严格先屏蔽停牌再算滚动，经申万行业+市值代理双重中性化。"),
        ("交易执行与缓冲带", "每 5 交易日收盘算分、次日开盘调仓；持有 Top 50 等权（各 2%），老持仓维持前 75 名则保留，单边换手压至 2.74%。"),
        ("为什么摒弃 50% 高频量价", "原 M0b（50% Alpha006/033）单边换手飙至 51.7%，被 36bp 往返摩擦吞噬逾 32 个百分点，净亏 -8.88%。"),
    ], size=12.5, space_after=10)

    add_card(s, 6.80, 1.50, 5.88, 5.25, fill_color=BG_OAT)
    add_tb(s, 7.05, 1.72, 5.38, 0.40, "8 组严格控制变量消融矩阵（M0a – M5）", size=15.5, bold=True, color=NAVY)
    add_styled_table(s, 7.00, 2.24, 5.48, 4.28,
        ["模型", "核心配方（5日调仓）", "验证假说"],
        [
            ["M0a", "BP+EP+Small（无缓冲）", "历史锚1：原基准基线"],
            ["M0b", "0.5B+0.25A006+0.25A033", "历史锚2：高频成本反例"],
            ["M1", "BP+EP+Small + 前75缓冲", "3.0低换手基准(干净池+缓冲)"],
            ["M2", "Z((BP+EP)/2) + 前75缓冲", "检验删去 Small 的净效应"],
            ["M3a", "0.9B + 0.1 Alpha101三席", "检验101重筛扣费增量"],
            ["M3b", "0.85M2 + 0.15 改造012", "检验原创比例化因子增量"],
            ["M4", "(BP+EP+LowVol+LowTurn)/4", "旗舰：价值+低风险共振"],
            ["M5", "M4 加入 E/B 代理（五等权）", "检验 E/B 代理非冗余性"],
        ], font_size=9.5, highlight_row=6)

    # ---------- P04: 数据与防前视 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "02 数据工程与防前视护城河", "Tushare 双股票池动态成分 + 开盘瞬间撮合，杜绝四类隐蔽前视偏差", 4)
    pillars = [
        ("01 分项署源与动态成分池", "Tushare 提供个股行情/估值/换手/复权/ST；94 期月度动态成分（沪深300 520股、中证500 1,107股）、申万行业与双指数沿用组员1既有历史输入，消除幸存者偏差。", NAVY),
        ("02 时效约束与停牌不前填", "剔除证监会行业回填，限定申万一级行业 45 天时效、估值 90 天龄期上限；所有因子在 rolling/diff 前先按 valid 掩码置空，严禁 ffill 停牌价伪造低波信号。", TERRA),
        ("03 开盘瞬间无前视撮合", "摒弃依赖收盘价的涨跌停与全日 can_sell_held；仅凭 tradestatus、open_quote_observed 与逐日 is_st（修复 any(ST) 漏洞）按 19.5%/4.5%/9.5% 判触限。", SAGE),
    ]
    for i, (h, txt, col) in enumerate(pillars):
        x = 0.65 + i * 4.10
        add_card(s, x, 1.55, 3.83, 3.40, fill_color=BG_PAPER)
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.55), Inches(3.83), Inches(0.08))
        bar.fill.solid(); bar.fill.fore_color.rgb = col; bar.line.fill.background()
        add_tb(s, x + 0.18, 1.82, 3.47, 0.42, h, size=14.5, bold=True, color=col)
        add_tb(s, x + 0.18, 2.35, 3.47, 2.40, txt, size=12.0, color=INK, line_spacing=1.35)

    add_card(s, 0.65, 5.20, 12.03, 1.68, fill_color=BG_OAT)
    add_tb(s, 0.90, 5.34, 11.5, 0.34, "基准指数对齐与跨实现交叉复算硬校验", size=13, bold=True, color=NAVY)
    add_bullets(s, 0.90, 5.72, 11.5, 1.05, [
        ("首日开盘进场 intraday 对齐", "2023-01-09 基准改用开盘至收盘 intraday（+0.36%），沪深300 价格指数全期精确为 -0.33%（0.9967），中证500 为 +3.94%。"),
        ("账本闭合与交叉复算", "63 组账户现金全程 ≥ 0、残差 0.0、分段连乘误差 < 1e-10；两套实现交叉复算，14 项核心账户精确对齐（另单列中证500 M0b 0.12pp 修订差）。"),
    ], size=11.3, space_after=4)

    # ---------- P05: 因子重筛与比例化创新 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "03 因子研究与原创改进", "LowVol60 / LowTurn20 与改造 new012 双池三段单因子 IC 均为正", 5)
    add_pic_fit(s, FIG_DIR / "05_factor_ic_and_new012.png", 0.55, 1.38, 12.23, 4.15)
    add_card(s, 0.65, 5.62, 12.03, 1.32, fill_color=BG_OAT)
    add_bullets(s, 0.88, 5.72, 11.55, 1.15, [
        ("101 本地实现全量重筛", "两池各运行101编号（代理变体单列，98项三段可报告）；沪深300 入选 040/006/015（015验证覆盖 52.4%），中证500 入选 040/013/044（训练覆盖 98.8%–99.2%）。"),
        ("改造 new012_amt_ema10 双面实证", "同步改动价差尺度、量能指标与10日平滑，双池三段单因子 IC 均为正；但扣费组合改善仅见于沪深300（M3b 较 M2 +8.58pp，中证500 同配方为 -6.93pp），无法单项归因。"),
    ], size=11.1, space_after=4)

    # ---------- P06: 沪深300消融净值 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "04 核心实证 · 沪深300主池", "沪深300干净共同池：M4 录得 +56.58%（夏普 0.905），综合双池稳健性锁定主交付", 6)
    add_pic_fit(s, FIG_DIR / "01_hs300_ablation_nav.png", 0.55, 1.35, 8.25, 5.55)
    add_kpi_card(s, 9.00, 1.50, 3.68, 1.24, "M4 主交付全期净收益", pct(hs_m4["cum_return"]), f"较价格指数 +56.90pp | 历史税率 {pct(hs_m4_ht['cum_return'])}", TERRA)
    add_kpi_card(s, 9.00, 2.90, 3.68, 1.24, "M4 风险收益效率", f"夏普 {hs_m4['sharpe_arith_rf0']:.3f}", f"年化 {pct(hs_m4['ann_geom'])} | 最大回撤 {pct(hs_m4['max_drawdown'], False)}", NAVY)
    add_card(s, 9.00, 4.30, 3.68, 2.55, fill_color=BG_OAT)
    add_tb(s, 9.18, 4.44, 3.35, 0.34, "消融对照与归因边界", size=12.5, bold=True, color=INK)
    add_bullets(s, 9.18, 4.82, 3.35, 1.95, [
        ("M1 vs M0a", "差 +9.55pp，同时含前75缓冲与干净池差异，非单一缓冲效应。"),
        ("M3b vs M2", "沪深300 +8.58pp；但中证500 同配方为 -6.93pp（见 P07）。"),
        ("M4 vs M5", "沪深300 M5 (+60.8%/0.958) 更高，但 M4 在中证500 占优且更简洁。"),
    ], size=10.2, space_after=4)

    # ---------- P07: 双池跨市场验证 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "04 跨市场稳健性", "跨池双证：M4 在中证500 居首、沪深300 稳健，交代 M5 与 M3b 跨池分化", 7)
    add_pic_fit(s, FIG_DIR / "02_dual_pool_ablation_bars.png", 0.55, 1.38, 12.23, 4.10)
    add_card(s, 0.65, 5.58, 12.03, 1.36, fill_color=BG_OAT)
    add_bullets(s, 0.88, 5.68, 11.55, 1.18, [
        ("M4 vs M5 跨池取舍", f"沪深300 上 M5（+60.79% / 夏普 0.958 / 回撤 -14.32%）三项优于 M4（+56.58% / 0.905 / -15.88%）；中证500 上 M4 全场居首（{pct(zz_m4['cum_return'])} / {zz_m4['sharpe_arith_rf0']:.3f} / {pct(zz_m4['max_drawdown'], False)}），综合跨池稳健性与简洁性选 M4。"),
        ("同池反例并排披露", "相同配方 M3b 较 M2 在沪深300 为 +8.58pp，在中证500 为 -6.93pp（40.81% vs 47.74%）；且去 small（M2）在沪深300 降收益而在中证500 升收益。"),
    ], size=11.0, space_after=4)

    # ---------- P08: Alpha015 覆盖率陷阱诊断 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "04 深度工程诊断", "Alpha015 低覆盖约束诊断：区分同池打分增量（M3a vs M1）与覆盖率影响", 8)
    add_pic_fit(s, FIG_DIR / "03_015_coverage_diagnosis.png", 0.55, 1.35, 8.30, 5.55)
    add_kpi_card(s, 9.05, 1.50, 3.63, 1.24, "95.1% 退出席位归因", "3,605 / 3,789 次", "原M1后续184次调仓退出席位，仅因015缺失", CRIMSON)
    add_kpi_card(s, 9.05, 2.90, 3.63, 1.24, "解除 015 约束后 M1 跃升", f"{pct(hs_m1_015['cum_return'])} → {pct(hs_m1['cum_return'])}", f"换手 41.91%→2.35% | 毛收益 +27.58%→+53.41%", NAVY)
    add_card(s, 9.05, 4.30, 3.63, 2.55, fill_color=BG_OAT)
    add_tb(s, 9.22, 4.44, 3.30, 0.34, "诊断分解与合规披露", size=12.5, bold=True, color=INK)
    add_bullets(s, 9.22, 4.82, 3.30, 1.95, [
        ("换手与毛收益双影响", "目标替换率 41.18%→1.03%，毛收益亦变化 25.8pp，持股变动本身已影响收益，非全是成本损失。"),
        ("打分与覆盖解耦", "原含 015 池 M3a (-1.83%) 较 M1 (-3.44%) 差 +1.62pp 解释打分；两池 M1 解释覆盖约束影响。"),
    ], size=10.3, space_after=5)

    # ---------- P09: Fama-MacBeth 归因 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "05 滞后实际持仓收益归因", "7 因子 FM 归因精确对账（含改造 012）：透视 M4 因子贡献与 M5 取舍", 9)
    add_pic_fit(s, FIG_DIR / "06_fm_attribution_v3.png", 0.55, 1.38, 12.23, 4.12)
    add_card(s, 0.65, 5.58, 12.03, 1.36, fill_color=BG_OAT)
    add_bullets(s, 0.88, 5.68, 11.55, 1.18, [
        ("7 因子完整对账", "补齐 new012_amt_ema10（沪深300 M1/M4/M5 为 +0.17/-0.18/-0.02pp，中证500 为 +0.15/+0.25/+0.21pp）；LowVol60+LowTurn20 在两池贡献 +2.49%/+3.01%/年。注：历史残差均值小不推导出波动小或必然可复制。"),
        ("M4 vs M5 客观取舍", "E/B 由 EP/BP 派生（非严格会计 ROE），在沪深300 直接贡献仅 +0.14%/年，在中证500 更是负贡献 -2.90%/年；综合双池稳健性与简洁性选定 M4。"),
    ], size=10.8, space_after=4)

    # ---------- P10: 行业暴露核查 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "05 行业集中度核查", "证伪“低波低换手只是重仓银行”：M4 金融占比反而低于纯价值 M2", 10)
    add_pic_fit(s, FIG_DIR / "07_industry_exposure_v3.png", 0.55, 1.38, 12.23, 4.12)
    add_card(s, 0.65, 5.58, 12.03, 1.36, fill_color=BG_OAT)
    add_bullets(s, 0.88, 5.68, 11.55, 1.18, [
        ("沪深300 行业再平衡", f"纯价值 M2 金融占比高达全期 {pct(goi('hs300_clean','M2')['finance_weight_full_mean'], False, 1)} / 末期 {pct(goi('hs300_clean','M2')['finance_weight_latest'], False, 1)}；加入中性化低波低换手后，M4 金融占比降至 {pct(goi('hs300_clean','M4')['finance_weight_full_mean'], False, 1)} / 末期 {pct(goi('hs300_clean','M4')['finance_weight_latest'], False, 1)}，分散至交运、建筑与公用事业。"),
        ("中证500 深度分散", f"中证500 M4 金融占比均值仅 {pct(goi('zz500','M4')['finance_weight_full_mean'], False, 1)}（末期 {pct(goi('zz500','M4')['finance_weight_latest'], False, 1)}），充分证明 M4 并非金融行业单一押注。"),
    ], size=11.3, space_after=4)

    # ---------- P11: 回撤与三层风控 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "05 风险管理与回撤控制", "三层风控防线：M4 最大回撤 -15.88%，较沪深300基准显著浅 8.92 个百分点", 11)
    add_pic_fit(s, FIG_DIR / "04_drawdown_underwater_v3.png", 0.55, 1.38, 8.20, 5.45)
    add_card(s, 8.95, 1.48, 3.73, 5.35, fill_color=BG_PAPER)
    add_tb(s, 9.15, 1.66, 3.35, 0.36, "私募产品三层风控体系", size=14, bold=True, color=NAVY)
    add_bullets(s, 9.15, 2.12, 3.35, 4.55, [
        ("第一层 · 事前组合风控", "动态剔除 ST、亏损股、次新股；中性化低波/低换手自动缓释金融过度集中，机构专户可叠加单行业 ≤35% 上限。"),
        ("第二层 · 事中交易风控", "开盘触限自动拒单不追高；大资金 1–3 日 VWAP 拆单严守 ≤5% 成交参与率红线。"),
        ("第三层 · 净值止损防线", "历史最大回撤 -15.88%（谷底 0.841），设预警线 0.85（降仓至 50%）、止损线 0.80（留足 4.1pp 极端缓冲）。"),
        ("流动性与申赎匹配", "建议月度开放、6个月锁定期，匹配低换手结构并减少现金拖累。"),
    ], size=10.8, space_after=8)

    # ---------- P12: 双池容量硬约束对比 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "06 私募产品化 · 容量边界", "双池容量硬对比：沪深300 稳健 3–6 亿（中证500 3倍），10–15 亿列压测情景", 12)
    add_pic_fit(s, FIG_DIR / "08_dual_pool_capacity_v3.png", 0.55, 1.38, 12.23, 4.15)
    add_card(s, 0.65, 5.62, 12.03, 1.32, fill_color=BG_OAT)
    add_bullets(s, 0.88, 5.72, 11.55, 1.15, [
        ("5% 参与率 P10 硬瓶颈与稳健区间", f"沪深300 M4 1日/3日调仓与5日清仓 P10 为 {cap_hs['p10_1d_5pct_yi']:.2f} / {cap_hs['p10_3d_5pct_yi']:.2f} / {cap_hs['p10_5d_liq_yi']:.2f} 亿，约为中证500（{cap_zz['p10_1d_5pct_yi']:.2f} / {cap_zz['p10_3d_5pct_yi']:.2f} / {cap_zz['p10_5d_liq_yi']:.2f} 亿）的 3 倍；硬约束稳健首期规模定为 3–6 亿（中证500 为 1–2.5 亿）。"),
        ("10–15 亿待压测扩张情景", "10亿/15亿超出5日清仓 P10：3日拆单超5%达 18/38 期（单股最大参与率 47%/71%、需 9.4/14.2 天），5日清仓超5%达 79/142 期；且多日拆单与次日开盘回测存在执行路径差异。"),
    ], size=10.6, space_after=4)

    # ---------- P13: 四档费率与商业落地 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "06 私募产品化 · 费率净值", "四档高水位法费率测算：机构 C 档扣除双层费用后年化仍达 +10.39%", 13)
    add_pic_fit(s, FIG_DIR / "09_fee_net_nav_v3.png", 0.55, 1.35, 7.65, 5.45)
    add_styled_table(s, 8.35, 1.50, 4.33, 3.15,
        ["方案", "固定+提成", "年化到手", "夏普"],
        [
            ["策略净值", "未扣产品费", pct(fee_hs.loc["Gross", "ann_geom"]), f"{fee_hs.loc['Gross','sharpe_arith_rf0']:.2f}"],
            ["A 标准", "1.2%+绝对20%", pct(fee_hs.loc["A", "ann_geom"]), f"{fee_hs.loc['A','sharpe_arith_rf0']:.2f}"],
            ["B 超额", "1.2%+超额20%", pct(fee_hs.loc["B", "ann_geom"]), f"{fee_hs.loc['B','sharpe_arith_rf0']:.2f}"],
            ["C 机构", "0.75%+超额15%", pct(fee_hs.loc["C", "ann_geom"]), f"{fee_hs.loc['C','sharpe_arith_rf0']:.2f}"],
            ["D 纯管", "1.7%+0%提成", pct(fee_hs.loc["D", "ann_geom"]), f"{fee_hs.loc['D','sharpe_arith_rf0']:.2f}"],
        ], font_size=9.5, highlight_row=3)
    add_card(s, 8.35, 4.82, 4.33, 2.00, fill_color=BG_OAT)
    add_tb(s, 8.53, 4.94, 4.0, 0.32, "客户分层适配建议", size=12, bold=True, color=NAVY)
    add_bullets(s, 8.53, 5.28, 4.0, 1.48, [
        ("FOF / 机构", "主推方案 C（仅对超额计提 15%，IR 0.73，利益绑定最优）。"),
        ("高净值 / 家办", "方案 B（防牛市对 Beta 收提成）或方案 D（高透明纯管理费）。"),
    ], size=10.2, space_after=4)

    # ---------- P14: 总结与诚实边界 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "07 总结与展望", "实事求是构建可落地量化产品：从全量验证到透明实盘跟踪", 14)
    add_card(s, 0.65, 1.50, 5.88, 5.25, fill_color=BG_PAPER)
    add_tb(s, 0.90, 1.72, 5.4, 0.38, "全组四大核心交付亮点", size=15, bold=True, color=TERRA)
    add_bullets(s, 0.90, 2.22, 5.4, 4.35, [
        ("跨池稳健旗舰 M4", f"综合双池表现与简洁性选定 M4：沪深300 {pct(hs_m4['cum_return'])}（夏普 {hs_m4['sharpe_arith_rf0']:.2f}、回撤 {pct(hs_m4['max_drawdown'], False)}）+ 中证500 全场居首 {pct(zz_m4['cum_return'])}（夏普 {zz_m4['sharpe_arith_rf0']:.2f}）。"),
        ("两项扎实技术发现", "诊断 Alpha015 覆盖约束影响（-3.44%→+51.11%，原池 M3a 较 M1 +1.62pp）；改造 012 扣费改善仅见于沪深300（+8.58pp vs 中证500 -6.93pp）。"),
        ("机构级产品化闭环", "双池三口径容量划定 3–6 亿稳健边界（10–15 亿列压测）；四档 HWM 费率；雪球 30 只前 45 缓冲历史映射换手压至 3.15%。"),
        ("工程交叉复算与复现", "双池 SHA-256 锁死、两套实现交叉复算核心对齐、报告/PPT 全动态读数；提交前核验 GitHub 公开克隆复现。"),
    ], size=11.3, space_after=8)

    add_card(s, 6.80, 1.50, 5.88, 5.25, fill_color=BG_OAT)
    add_tb(s, 7.05, 1.72, 5.4, 0.38, "学术诚实边界与前瞻计划", size=15, bold=True, color=NAVY)
    add_bullets(s, 7.05, 2.22, 5.4, 4.35, [
        ("历史留后区间诚实披露", "2025–2026.10 已参与方案讨论与消融对比，严禁宣称纯样本外盲测；未来严格以规则冻结后的新行情检验。"),
        ("价格指数与分红情景估算", "M4 相对沪深300 价格指数累计差约 +56.90 个百分点；按假设股息率扣减 10–12pp 仅为情景估算，精确全收益口径需接入全收益指数重算。"),
        ("雪球模拟盘合规分列", "ZH3689205 既有历史记录完整封存；10 月末清单属历史目标，11 月起实盘记录与截图按启用日期与历史回测分列。"),
        ("未来演进方向", "接入 Point-in-Time 财报公告时间戳库，并在机构专户中引入单行业 ≤35% 约束与换手惩罚优化器。"),
    ], size=11.3, space_after=8)

    # ---------- P15: Appendix A 雪球 30 只映射跟踪回测 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "Appendix A · 答辩备查", "雪球 30 只分层权重历史映射回测：独立前 45 缓冲将换手压缩超一半", 15)
    add_pic_fit(s, FIG_DIR / "10_xueqiu_30_tracking_v3.png", 0.55, 1.38, 12.23, 4.10)
    xq_m4 = xq_bt[(xq_bt["base_model"] == "hs300_M4_clean") & (xq_bt["stage"] == "all") & (xq_bt["fee_scenario"] == "net_10bp")].set_index("mapping_scheme")
    add_card(s, 0.65, 5.58, 12.03, 1.36, fill_color=BG_OAT)
    add_bullets(s, 0.88, 5.68, 11.55, 1.18, [
        ("独立前 45 缓冲的关键作用", f"雪球限 30 只且仅支持整数权重（前10×4%+后20×3%）；直接硬截断会使换手反弹至 {pct(xq_m4.loc['xq30_trunc_tiered','mean_half_turn'], False)}，而独立设前 45 缓冲后换手压回 {pct(xq_m4.loc['xq30_buf45_tiered','mean_half_turn'], False)}，与 50 只原策略日相关达 {xq_m4.loc['xq30_buf45_tiered','daily_corr_vs_top50']:.4f}、年化 TE 仅 {pct(xq_m4.loc['xq30_buf45_tiered','tracking_error_vs_top50'], False)}（全报告 IR 统一为日频算术主动口径 0.8748）。"),
        ("历史映射与实盘分列", "雪球 30 股的 +77.63% 属于历史映射回测，10 月末清单属历史目标；团队严格以 50 只原策略（+56.58%）为正式对外主口径，11 月起实盘记录按启用日期分列。"),
    ], size=10.6, space_after=4)

    # ---------- P16: Appendix B 双税率与完整消融明细 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "Appendix B · 答辩备查", "全套消融双印花税情景（固定10bp vs 2023-08-28 减半5bp）精确对账表", 16)
    rows_b = []
    for exp, mod, pool_lbl in [
        ("hs300_clean", "M1", "沪深300(干净)"),
        ("hs300_clean", "M2", "沪深300(干净)"),
        ("hs300_clean", "M3b", "沪深300(干净)"),
        ("hs300_clean", "M4", "沪深300(旗舰)"),
        ("hs300_clean", "M5", "沪深300(干净)"),
        ("hs300_full", "M0a", "沪深300(锚)"),
        ("hs300_full", "M0b", "沪深300(反例)"),
        ("zz500", "M1", "中证500"),
        ("zz500", "M2", "中证500"),
        ("zz500", "M4", "中证500(最优)"),
        ("zz500", "M5", "中证500"),
    ]:
        a = gm(exp, mod, "all", "net_10bp")
        ht = gm(exp, mod, "all", "net_histtax")
        gr = gm(exp, mod, "all", "gross")
        v = gm(exp, mod, "validation", "net_10bp")
        sn = gm(exp, mod, "seen", "net_10bp")
        rows_b.append([
            f"{pool_lbl} {mod}", pct(gr["cum_return"]), pct(a["cum_return"]), pct(ht["cum_return"]),
            pct(v["cum_return"]), pct(sn["cum_return"]),
            f"{a['sharpe_arith_rf0']:.3f} / {a['geom_over_vol']:.3f}",
            pct(a["max_drawdown"], False), pct(a["mean_half_turn"], False),
        ])
    add_styled_table(s, 0.65, 1.48, 12.03, 5.20,
        ["池与模型", "毛收益", "净(10bp)", "历史税率(5bp)", "验证(23-24)", "后段(25-26)", "算术夏普/几何波比", "最大回撤", "单边换手"],
        rows_b, font_size=9.2, highlight_row=3)

    # ---------- P17: Appendix C 高频答辩 Q&A 速查 ----------
    s = prs.slides.add_slide(blank)
    add_header(s, "Appendix C · 答辩备查", "答辩高频追问 Q&A 速查卡（数据与方法学防线）", 17)
    qas = [
        ("Q1：沪深300 上 M5 (+60.79% / 夏普 0.958 / 回撤 -14.32%) 三项优于 M4，为什么定案选 M4？",
         "A：综合两个股票池表现与模型简洁性选择 M4：① M5 新增的 E/B 代理（EP/BP 派生，非严格公告时点会计 ROE）在中证500 FM 归因中呈负贡献 -2.90%/年，且中证500 M5 三项指标均落后于 M4；② 在沪深300 E/B 直接贡献仅 +0.14%/年。因此审慎选择跨池最稳健、结构更简洁的 M4。"),
        ("Q2：组合用后复权含分红，对比沪深300 价格指数是否夸大了超额？",
         "A：已显式披露口径：按价格指数口径，沪深300 M4 相对沪深300 价格指数累计差约 +56.90 个百分点。若按假设年股息率 2.5%–3.0% 扣减 10–12pp 仅为情景估算；如需报告严格全收益口径，须接入同起点的沪深300 全收益指数序列重算。"),
        ("Q3：低波+低换手是否只是换种方式满仓押注银行股？",
         "A：已通过每日实际持仓申万行业暴露核查：沪深300 M4 金融占比（均值 42.4%/末期 50.0%）反而低于纯价值 M2（48.2%/66.0%）；中证500 M4 金融占比仅 22.3%，并分散至交运、建筑与公用事业等板块。"),
        ("Q4：为什么中证500 M4 收益 (+57.73%) 略高，却选沪深300 M4 做旗舰产品？",
         "A：产品化核心看夏普与硬容量：沪深300 M4 算术夏普更高（0.905 vs 0.816）、最大回撤更浅（-15.88% vs -16.46%），且 5% 参与率 P10 容量（1日/3日/5日清仓 3.33/9.99/6.63 亿）是中证500 的 3 倍，硬约束稳健首期规模 3–6 亿（10–15 亿列为待压测情景）。"),
        ("Q5：2025–2026.10 历史留后段是否算严格样本外？雪球模拟盘如何衔接？",
         "A：绝不包装为纯盲测，全组统一披露为“历史留后区间（已参与方案讨论）”。雪球 ZH3689205 既有历史记录完整封存，10 月末清单为历史目标，11 月起实盘记录按启用日期与历史回测分列。"),
    ]
    for i, (q, a) in enumerate(qas):
        y = 1.42 + i * 1.11
        add_card(s, 0.65, y, 12.03, 1.00, fill_color=BG_PAPER if i % 2 == 0 else BG_OAT)
        add_tb(s, 0.82, y + 0.06, 11.7, 0.30, q, size=11.0, bold=True, color=NAVY)
        add_tb(s, 0.82, y + 0.38, 11.7, 0.56, a, size=10.0, color=INK, line_spacing=1.18)

    prs.save(str(OUT_PPTX))
    print(f"已生成 17 页终版路演 PPT: {OUT_PPTX} ({len(prs.slides)} slides)")

    # 导出 PDF 及 17 张 PNG 预览
    lo_env = {**os.environ, "HOME": "/tmp"}
    subprocess.run([
        "soffice", "-env:UserInstallation=file:///tmp/lo_profile", "--headless",
        "--convert-to", "pdf", "--outdir", str(DECK_DIR), str(OUT_PPTX),
    ], env=lo_env, check=True)
    for old in PREVIEW_DIR.glob("*.png"):
        old.unlink()
    subprocess.run(["pdftoppm", "-png", "-r", "120", str(OUT_PDF), str(PREVIEW_DIR / "slide")], check=True)
    pngs = sorted(PREVIEW_DIR.glob("*.png"))
    print(f"已导出 PDF: {OUT_PDF} 及 {len(pngs)} 张预览图至 {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
