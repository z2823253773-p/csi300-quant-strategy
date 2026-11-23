# -*- coding: utf-8 -*-
"""
组员4 模块4（Claude 官网极简编辑风路演 PPT）：生成 14 页路演 PPT
四大板块：封面与团队介绍 -> 策略介绍 -> 产品介绍 -> 总结与答辩致谢
视觉系统：
- 画布 #FAF9F5（P14 封底 #141413）、主墨 #141413、次墨 #57554F、浅墨 #8C8980
- 燕麦卡 #F0EEE6、陶土点睛 #D97757 / #C45A38、浅陶土底 #F5E6DF、细线 #E5E2D9
- 衬线大标题（Songti SC + Georgia）+ 无衬线正文（Heiti SC + Helvetica Neue）
- 彻底清除所有形状 XML 默认阴影（<a:effectLst/>），底部完全留白无来源文字
复现命令（在 member4 目录）：
    .venv/bin/python code/build_deck.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

import paths as P

MEMBER4_DIR = P.MEMBER4_DIR
ROOT_DIR = P.WORKSPACE_ROOT
M3_RES_DIR = P.M3_RES
RES_DIR = MEMBER4_DIR / "results"
FIG_DIR = MEMBER4_DIR / "figures" / "slide_claude"
XQ_SHOTS = MEMBER4_DIR / "xueqiu" / "screenshots"
DECK_DIR = MEMBER4_DIR / "deck"
OUT_PPTX = DECK_DIR / "路演.pptx"

# ---------------------------------------------------------------------------
# Claude 官网极简编辑风视觉系统常量（16:9 宽屏）
# ---------------------------------------------------------------------------
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
M_LEFT = Inches(0.80)
M_RIGHT = Inches(0.80)
CONTENT_W = SLIDE_W - M_LEFT - M_RIGHT  # 11.733 in

FONT_SERIF_CN = "宋体-简"
FONT_SERIF_EN = "Georgia"
FONT_SANS_CN = "黑体-简"
FONT_SANS_EN = "Helvetica Neue"

BG_CANVAS = RGBColor(0xFA, 0xF9, 0xF5)  # #FAF9F5 温润羊皮纸米白
BG_OAT = RGBColor(0xF0, 0xEE, 0xE6)     # #F0EEE6 次级表面燕麦底
BG_PAPER = RGBColor(0xFF, 0xFF, 0xFF)   # #FFFFFF 极简浮卡
INK = RGBColor(0x14, 0x14, 0x13)        # #141413 主墨色
STONE = RGBColor(0x57, 0x55, 0x4F)      # #57554F 次墨色
MUTED = RGBColor(0x8C, 0x89, 0x80)      # #8C8980 浅墨色
DIVIDER = RGBColor(0xE5, 0xE2, 0xD9)    # #E5E2D9 发丝细线
TERRA = RGBColor(0xD9, 0x77, 0x57)      # #D97757 陶土珊瑚橙
CLAY = RGBColor(0xC4, 0x5A, 0x38)       # #C45A38 高对比深陶土
TINT = RGBColor(0xF5, 0xE6, 0xDF)       # #F5E6DF 浅陶土底
TINT_TEXT = RGBColor(0xB0, 0x4A, 0x2A)  # #B04A2A 浅陶土胶囊文字
SAGE = RGBColor(0x5F, 0x7A, 0x6A)       # #5F7A6A 鼠尾草绿
DARK_MUTED = RGBColor(0xA8, 0xA4, 0x9B) # 深色封底辅助文字


def load_data() -> dict:
    with open(RES_DIR / "product_summary.json", "r", encoding="utf-8") as f:
        prod = json.load(f)
    with open(RES_DIR / "xueqiu_summary.json", "r", encoding="utf-8") as f:
        xq = json.load(f)
    fee_df = pd.read_csv(RES_DIR / "fee_analysis.csv")
    cap_df = pd.read_csv(RES_DIR / "capacity_constraints.csv")
    metrics_df = pd.read_csv(M3_RES_DIR / "metrics.csv")
    nav_df = pd.read_csv(M3_RES_DIR / "nav.csv", index_col=0)
    turn_df = pd.read_csv(M3_RES_DIR / "turnover.csv", index_col=0)
    monthly_df = pd.read_csv(M3_RES_DIR / "monthly_returns.csv", index_col=0)
    return {
        "prod": prod,
        "xq": xq,
        "fee": fee_df,
        "cap": cap_df,
        "metrics": metrics_df,
        "nav": nav_df,
        "turn": turn_df,
        "monthly": monthly_df,
    }


def clear_shadow(shape):
    """彻底清除形状默认阴影：spPr 写入空 <a:effectLst/> 且将 style/effectRef 设为 idx=0。"""
    try:
        shape.shadow.inherit = False
    except NotImplementedError:
        pass
    el = shape._element
    spPr = getattr(el, "spPr", None)
    if spPr is not None:
        for tag in ("a:effectLst", "a:effectDag"):
            for old in spPr.findall(qn(tag)):
                spPr.remove(old)
        spPr.append(OxmlElement("a:effectLst"))
    style_el = el.find(qn("p:style"))
    if style_el is not None:
        eff_ref = style_el.find(qn("a:effectRef"))
        if eff_ref is not None:
            eff_ref.set("idx", "0")
    return shape


def set_slide_bg(slide, color: RGBColor):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _set_font(run, size: int, bold: bool = False, color: RGBColor = INK, serif: bool = False):
    en_font = FONT_SERIF_EN if serif else FONT_SANS_EN
    cn_font = FONT_SERIF_CN if serif else FONT_SANS_CN
    run.font.name = en_font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag, typeface in (("a:latin", en_font), ("a:ea", cn_font), ("a:cs", en_font)):
        el = rPr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            rPr.append(el)
        el.set("typeface", typeface)


def add_rect(slide, left, top, width, height, fill_color: RGBColor | None = None,
             line_color: RGBColor | None = None, line_pt: float = 0.75):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    if fill_color is not None:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill_color
    else:
        shp.fill.background()
    if line_color is not None:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_pt)
    else:
        shp.line.fill.background()
    return clear_shadow(shp)


def add_round_rect(slide, left, top, width, height, fill_color: RGBColor | None = None,
                   line_color: RGBColor | None = None, line_pt: float = 0.75, radius: float = 0.04):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shp.adjustments[0] = radius
    if fill_color is not None:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill_color
    else:
        shp.fill.background()
    if line_color is not None:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_pt)
    else:
        shp.line.fill.background()
    return clear_shadow(shp)


def add_circle(slide, cx, cy, diameter, fill_color: RGBColor,
               line_color: RGBColor | None = None, line_pt: float = 0.75):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        int(cx - diameter / 2),
        int(cy - diameter / 2),
        int(diameter),
        int(diameter),
    )
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill_color
    if line_color is not None:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_pt)
    else:
        shp.line.fill.background()
    return clear_shadow(shp)


def add_line(slide, x1, y1, x2, y2, color: RGBColor, width_pt: float = 1.0):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, int(x1), int(y1), int(x2), int(y2))
    conn.line.color.rgb = color
    conn.line.width = Pt(width_pt)
    return clear_shadow(conn)


def add_pill(slide, left, top, width, height, text: str,
             fill_color: RGBColor = INK, text_color: RGBColor = BG_CANVAS,
             line_color: RGBColor | None = None, font_size: int = 12, bold: bool = True):
    shp = add_round_rect(
        slide, left, top, width, height,
        fill_color=fill_color, line_color=line_color, line_pt=0.75, radius=0.48,
    )
    tf = shp.text_frame
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.10)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    _set_font(r, font_size, bold=bold, color=text_color, serif=False)
    return shp


def add_textbox(slide, left, top, width, height, text: str = "", font_size: int = 16,
                bold: bool = False, color: RGBColor = INK, align: PP_ALIGN = PP_ALIGN.LEFT,
                valign: MSO_ANCHOR = MSO_ANCHOR.TOP, line_spacing: float = 1.25,
                serif: bool = False, word_wrap: bool = True):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = word_wrap
    tf.vertical_anchor = valign
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0.02)
    if text:
        p = tf.paragraphs[0]
        p.alignment = align
        p.line_spacing = line_spacing
        r = p.add_run()
        r.text = text
        _set_font(r, font_size, bold=bold, color=color, serif=serif)
    return tb


def add_rich_lines(slide, left, top, width, height, items: Iterable[dict],
                   default_size: int = 15, line_spacing: float = 1.28,
                   valign: MSO_ANCHOR = MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0.02)
    for idx, item in enumerate(items):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = item.get("align", PP_ALIGN.LEFT)
        p.line_spacing = item.get("line_spacing", line_spacing)
        p.space_after = Pt(item.get("space_after", 8))
        if "runs" in item:
            for r_text, r_bold, r_color, r_size, r_serif in item["runs"]:
                r = p.add_run()
                r.text = r_text
                _set_font(r, r_size, bold=r_bold, color=r_color, serif=r_serif)
        else:
            sz = item.get("size", default_size)
            if item.get("lead"):
                r1 = p.add_run()
                r1.text = item["lead"]
                _set_font(r1, sz, bold=True, color=item.get("lead_color", INK),
                          serif=item.get("lead_serif", False))
            if item.get("text"):
                r2 = p.add_run()
                r2.text = item["text"]
                _set_font(r2, sz, bold=item.get("bold", False), color=item.get("color", STONE),
                          serif=item.get("serif", False))
    return tb


def add_editorial_chrome(slide, breadcrumb: str, title: str, page_num: int,
                         total_pages: int = 14, title_size: int = 26):
    """Claude 官网式极简顶栏 + 编辑感单行衬线大标题；底部完全留白。"""
    set_slide_bg(slide, BG_CANVAS)
    add_textbox(slide, M_LEFT, Inches(0.36), Inches(7.5), Inches(0.28),
                text=breadcrumb, font_size=12, bold=False, color=MUTED, serif=False)
    add_textbox(slide, SLIDE_W - M_RIGHT - Inches(1.4), Inches(0.36), Inches(1.4), Inches(0.28),
                text=f"{page_num:02d} / {total_pages:02d}", font_size=12, bold=False,
                color=MUTED, align=PP_ALIGN.RIGHT, serif=False)
    # 0.5pt 发丝分割线
    add_rect(slide, M_LEFT, Inches(0.68), CONTENT_W, Inches(0.01), fill_color=DIVIDER)
    # 编辑感衬线大标题（单行，不折行）
    add_textbox(slide, M_LEFT, Inches(0.84), CONTENT_W, Inches(0.52),
                text=title, font_size=title_size, bold=True, color=INK, serif=True, word_wrap=False)


def add_note(slide, note_text: str):
    slide.notes_slide.notes_text_frame.text = note_text


def add_picture_fit(slide, img_path: Path, box_left, box_top, box_w, box_h):
    from PIL import Image
    with Image.open(img_path) as im:
        iw, ih = im.size
    ratio = iw / ih
    bw = float(box_w)
    bh = float(box_h)
    if bw / bh > ratio:
        target_h = bh
        target_w = bh * ratio
    else:
        target_w = bw
        target_h = bw / ratio
    left = int(box_left + (bw - target_w) / 2)
    top = int(box_top + (bh - target_h) / 2)
    slide.shapes.add_picture(str(img_path), left, top, width=int(target_w), height=int(target_h))


def _set_cell_borders(cell, top_hex=None, bottom_hex=None, top_sz="12", bottom_sz="12"):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("lnL", "lnR", "lnT", "lnB"):
        old = tcPr.find(qn(f"a:{tag}"))
        if old is not None:
            tcPr.remove(old)
    for tag in ("lnL", "lnR"):
        ln = OxmlElement(f"a:{tag}")
        ln.append(OxmlElement("a:noFill"))
        tcPr.append(ln)
    for tag, color_hex, sz in (("lnT", top_hex, top_sz), ("lnB", bottom_hex, bottom_sz)):
        ln = OxmlElement(f"a:{tag}")
        if color_hex:
            ln.set("w", str(int(float(sz) * 12700 / 8)))
            sf = OxmlElement("a:solidFill")
            srgb = OxmlElement("a:srgbClr")
            srgb.set("val", color_hex)
            sf.append(srgb)
            ln.append(sf)
        else:
            ln.append(OxmlElement("a:noFill"))
        tcPr.append(ln)


def add_warm_three_line_table(slide, left, top, width, height, headers: list[str], rows: list[list[str]],
                              col_widths: list[float], aligns: list[PP_ALIGN],
                              font_size: int = 14, highlight_row: int | None = None):
    n_rows = len(rows) + 1
    n_cols = len(headers)
    tbl_shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    clear_shadow(tbl_shape)
    tbl = tbl_shape.table
    total_w = sum(col_widths)
    for j, cw in enumerate(col_widths):
        tbl.columns[j].width = int(width * (cw / total_w))

    for j, h in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = BG_OAT
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = cell.margin_right = Inches(0.08)
        cell.margin_top = cell.margin_bottom = Inches(0.05)
        _set_cell_borders(cell, top_hex="141413", bottom_hex="141413", top_sz="12", bottom_sz="8")
        p = cell.text_frame.paragraphs[0]
        p.alignment = aligns[j]
        r = p.add_run()
        r.text = h
        _set_font(r, font_size, bold=True, color=INK, serif=False)

    for i, row in enumerate(rows):
        is_hl = (highlight_row is not None and i == highlight_row)
        is_last = (i == len(rows) - 1)
        bg = TINT if is_hl else (BG_CANVAS if i % 2 == 0 else BG_OAT)
        for j, val in enumerate(row):
            cell = tbl.cell(i + 1, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.05)
            _set_cell_borders(
                cell, top_hex=None,
                bottom_hex="141413" if is_last else "E5E2D9",
                bottom_sz="12" if is_last else "4",
            )
            p = cell.text_frame.paragraphs[0]
            p.alignment = aligns[j]
            r = p.add_run()
            r.text = val
            txt_col = TINT_TEXT if (is_hl and j in (0, 2)) else (INK if is_hl else STONE)
            _set_font(r, font_size, bold=is_hl, color=txt_col, serif=False)
    return tbl_shape


def draw_cover_constellation(slide, cx_in: float, cy_in: float):
    """P01 封面右侧：克制优雅的 Claude 风格陶土橙多因子网络/星芒矢量装饰。"""
    cx, cy = Inches(cx_in), Inches(cy_in)
    # 中心锚点 + 外围 6 因子/节点坐标（英寸相对偏移）
    offsets = [
        (0.00, -1.45, 0.24, TERRA),   # 顶部主节点 BP
        (1.30, -0.68, 0.18, TERRA),   # 右上 EP
        (1.18,  0.88, 0.22, TERRA),   # 右下 Small
        (-0.15, 1.48, 0.16, TERRA),   # 底部节点
        (-1.32, 0.68, 0.20, TERRA),   # 左下节点
        (-1.22,-0.78, 0.16, TERRA),   # 左上节点
    ]
    pts = [(cx + Inches(dx), cy + Inches(dy), Inches(d), col) for dx, dy, d, col in offsets]

    # 细网络连线（先画线后盖圆点）
    ring_edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (0, 2), (1, 4), (3, 5)]
    for i, j in ring_edges:
        add_line(slide, pts[i][0], pts[i][1], pts[j][0], pts[j][1], color=DIVIDER, width_pt=1.0)
    for px, py, _, _ in pts:
        add_line(slide, cx, cy, px, py, color=TERRA, width_pt=1.15)

    # 外围小星芒卫星点（极简点缀）
    sat = [
        (cx + Inches(0.68), cy - Inches(1.32), Inches(0.08), DIVIDER),
        (cx + Inches(1.52), cy + Inches(0.14), Inches(0.08), DIVIDER),
        (cx - Inches(0.86), cy + Inches(1.30), Inches(0.08), DIVIDER),
    ]
    for sx, sy, sd, scol in sat:
        add_circle(slide, sx, sy, sd, fill_color=scol)

    # 外围 6 个陶土实心圆节点
    for px, py, pdia, pcol in pts:
        add_circle(slide, px, py, pdia, fill_color=pcol, line_color=BG_CANVAS, line_pt=1.5)

    # 中心 1 个主墨黑锚点节点 + 细外环
    add_circle(slide, cx, cy, Inches(0.46), fill_color=BG_CANVAS, line_color=TERRA, line_pt=1.2)
    add_circle(slide, cx, cy, Inches(0.28), fill_color=INK)


def draw_back_starburst(slide, cx_in: float, cy_in: float):
    """P14 封底左侧：小型 Claude 风格陶土星芒符号。"""
    cx, cy = Inches(cx_in), Inches(cy_in)
    angles = [0, 30, 60, 90, 120, 150]
    r_outer = Inches(0.62)
    for idx, deg in enumerate(angles):
        rad = math.radians(deg)
        dx = int(r_outer * math.cos(rad))
        dy = int(r_outer * math.sin(rad))
        w_pt = 1.8 if idx % 2 == 0 else 1.2
        add_line(slide, cx - dx, cy - dy, cx + dx, cy + dy, color=TERRA, width_pt=w_pt)
    # 中心圆点与 6 个末端小圆点
    for deg in range(0, 360, 60):
        rad = math.radians(deg)
        nx = cx + int(Inches(0.66) * math.cos(rad))
        ny = cy + int(Inches(0.66) * math.sin(rad))
        add_circle(slide, nx, ny, Inches(0.11), fill_color=TERRA)
    add_circle(slide, cx, cy, Inches(0.20), fill_color=BG_CANVAS)


def build_deck():
    data = load_data()
    fee_df = data["fee"]
    nav_df = data["nav"]
    turn_df = data["turn"]
    metrics_df = data["metrics"]
    monthly_df = data["monthly"]

    b_full = metrics_df[(metrics_df["区间"].str.contains("全样本")) & (metrics_df["组合"] == "baseline")].iloc[0]
    b_val = metrics_df[(metrics_df["区间"].str.contains("验证期")) & (metrics_df["组合"] == "baseline")].iloc[0]
    h_full = metrics_df[(metrics_df["区间"].str.contains("全样本")) & (metrics_df["组合"] == "hs300")].iloc[0]
    h_val = metrics_df[(metrics_df["区间"].str.contains("验证期")) & (metrics_df["组合"] == "hs300")].iloc[0]
    r_full = metrics_df[(metrics_df["区间"].str.contains("全样本")) & (metrics_df["组合"] == "research")].iloc[0]

    oos_base_seamless = (nav_df.loc["2026-10-30", "baseline"] / nav_df.loc["2024-12-31", "baseline"] - 1.0) * 100
    oos_hs_seamless = (nav_df.loc["2026-10-30", "hs300"] / nav_df.loc["2024-12-31", "hs300"] - 1.0) * 100
    b_turn_mean = turn_df["baseline_turnover"].mean() * 100
    r_turn_mean = turn_df["research_turnover"].mean() * 100
    ir_base = data["prod"]["upstream_backtest_summary"]["baseline_ir_vs_hs300"]
    cap_half = data["prod"]["theoretical_capacity_half_excess"]

    n_months = len(monthly_df)
    pos_months = int((monthly_df["baseline"] > 0).sum())
    win_rate = pos_months / n_months * 100
    worst_month = float(monthly_df["baseline"].min()) * 100

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # P01: 封面（Claude 官网极简编辑风）
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s1, BG_CANVAS)
    add_textbox(s1, M_LEFT, Inches(0.36), Inches(7.5), Inches(0.28),
                text="量化交易技术理论与实践  /  期末路演", font_size=12, color=MUTED)
    add_textbox(s1, SLIDE_W - M_RIGHT - Inches(1.4), Inches(0.36), Inches(1.4), Inches(0.28),
                text="01 / 14", font_size=12, color=MUTED, align=PP_ALIGN.RIGHT)
    add_rect(s1, M_LEFT, Inches(0.68), CONTENT_W, Inches(0.01), fill_color=DIVIDER)

    # 左侧错落双行衬线封面主标
    add_textbox(s1, M_LEFT, Inches(1.38), Inches(7.4), Inches(0.76),
                text="沪深300", font_size=46, bold=True, color=INK, serif=True, word_wrap=False)
    add_textbox(s1, Inches(1.15), Inches(2.14), Inches(7.4), Inches(0.78),
                text="价值精选量化策略", font_size=46, bold=True, color=INK, serif=True, word_wrap=False)

    add_textbox(s1, M_LEFT, Inches(3.16), Inches(7.5), Inches(0.45),
                text="低换手价值主线 · 高频成本摩擦实证 · 私募产品化方案",
                font_size=18, color=STONE, serif=False)

    # 两个 Claude 官网标志性胶囊
    add_pill(s1, M_LEFT, Inches(3.86), Inches(2.85), Inches(0.40),
             text="主交付 · Baseline 价值组合", fill_color=INK, text_color=BG_CANVAS, font_size=13)
    add_pill(s1, M_LEFT + Inches(3.03), Inches(3.86), Inches(2.55), Inches(0.40),
             text="雪球实盘 · ZH3689205", fill_color=BG_OAT, text_color=INK,
             line_color=DIVIDER, font_size=13)

    # 极简信息区（无框线，留白呼吸）
    add_rect(s1, M_LEFT, Inches(4.62), Inches(7.2), Inches(0.01), fill_color=DIVIDER)
    add_rich_lines(s1, M_LEFT, Inches(4.84), Inches(7.6), Inches(1.45), [
        {"lead": "课程教师：", "lead_color": INK, "text": "【待填：课程全称】  ｜  【待填：指导教师姓名】", "size": 14, "space_after": 8},
        {"lead": "研究团队：", "lead_color": INK, "text": "【待填：组员1 数据 · 组员2 因子 · 组员3 回测 · 组员4 产品】", "size": 14, "space_after": 8},
        {"lead": "实盘与代码：", "lead_color": INK, "text": "https://www.xueqiu.com/P/ZH3689205  ｜  【待填：GitHub 链接】", "size": 14, "space_after": 0},
    ], line_spacing=1.25)

    # 底部极简一行元信息
    add_rect(s1, M_LEFT, Inches(6.62), CONTENT_W, Inches(0.01), fill_color=DIVIDER)
    add_textbox(s1, M_LEFT, Inches(6.76), CONTENT_W, Inches(0.30),
                text="汇报日期：【待填：YYYY-MM-DD】  ｜  回测样本：2023-01-09 至 2026-10-30  ｜  921 个交易日",
                font_size=12, color=MUTED)

    # 右侧极简陶土橙多因子网络矢量图
    draw_cover_constellation(s1, 10.65, 3.75)

    add_note(s1, "开场问好，点明本组汇报主题：聚焦沪深300大盘蓝筹低换手价值选股策略，并严格用实盘约束与产品化容量闭环检验。")

    # =========================================================================
    # P02: 团队介绍
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s2, "01 团队介绍  /  全链路协同", "四位组员全链路协同，构建无前视研究闭环", 2)

    members = [
        ("01 数据", "组员 1 · 数据工程", "【待填：姓名 学号】", INK, BG_CANVAS, [
            {"lead": "核心职责\n", "text": "动态成分股与真时点清洗流水线", "space_after": 12},
            {"lead": "关键把关\n", "text": "剥离回填、开放出池卖出，杜绝幸存者偏差", "space_after": 0},
        ]),
        ("02 因子", "组员 2 · 因子模型", "【待填：姓名 学号】", INK, BG_CANVAS, [
            {"lead": "核心职责\n", "text": "BP/EP/规模基准与 Alpha101 筛选", "space_after": 12},
            {"lead": "关键把关\n", "text": "提出无量纲 new012，严守训练锁定不改参", "space_after": 0},
        ]),
        ("03 回测", "组员 3 · 回测归因", "【待填：姓名 学号】", INK, BG_CANVAS, [
            {"lead": "核心职责\n", "text": "账户级开盘撮合、归因与风险分析", "space_after": 12},
            {"lead": "关键把关\n", "text": "开盘一字板判定消除前视，拆解高换手侵蚀", "space_after": 0},
        ]),
        ("04 产品", "组员 4 · 产品汇报", "【待填：姓名 学号】", TINT, TINT_TEXT, [
            {"lead": "核心职责\n", "text": "三口径容量、四档费率与雪球实盘", "space_after": 12},
            {"lead": "关键把关\n", "text": "统一全组口径与视觉体系，完成报告与路演", "space_after": 0},
        ]),
    ]
    cw2 = (CONTENT_W - Inches(0.28 * 3)) / 4
    for idx, (pill_txt, role, who, p_bg, p_fg, items) in enumerate(members):
        x = M_LEFT + idx * (cw2 + Inches(0.28))
        add_round_rect(s2, x, Inches(1.62), cw2, Inches(3.88), fill_color=BG_OAT, radius=0.03)
        add_pill(s2, x + Inches(0.24), Inches(1.88), Inches(1.12), Inches(0.34),
                 text=pill_txt, fill_color=p_bg, text_color=p_fg, font_size=12)
        add_textbox(s2, x + Inches(0.24), Inches(2.38), cw2 - Inches(0.48), Inches(0.36),
                    text=role, font_size=17, bold=True, color=INK, serif=True)
        add_textbox(s2, x + Inches(0.24), Inches(2.74), cw2 - Inches(0.48), Inches(0.28),
                    text=who, font_size=13, color=MUTED)
        add_rect(s2, x + Inches(0.24), Inches(3.14), cw2 - Inches(0.48), Inches(0.01), fill_color=DIVIDER)
        add_rich_lines(s2, x + Inches(0.24), Inches(3.32), cw2 - Inches(0.48), Inches(1.98),
                       items, default_size=14, line_spacing=1.28)

    add_rect(s2, M_LEFT, Inches(5.88), CONTENT_W, Inches(0.01), fill_color=DIVIDER)
    add_rich_lines(s2, M_LEFT, Inches(6.06), CONTENT_W, Inches(0.60), [
        {"lead": "协同纪律：", "lead_color": CLAY, "text": "上游交付只读锁定，下游逐项核验指纹与接口口径。全流程严守「无未来信息 · 实盘可成交 · 不回避负结果」底线。", "size": 15, "space_after": 0}
    ], line_spacing=1.3)
    add_note(s2, "介绍团队四人流水线分工：组员1把关数据真时点，组员2负责因子筛选与比例化创新，组员3负责无前视回测归因，组员4完成产品容量与雪球落地。")

    # =========================================================================
    # P03: 策略核心思想
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s3, "02 策略介绍  /  核心思想", "以大盘价值为锚，严守交易成本与研究纪律", 3)

    hw3 = (CONTENT_W - Inches(0.36)) / 2
    # 左卡：Paper #FFFFFF 精卡 + 墨黑胶囊
    lx3 = M_LEFT
    add_round_rect(s3, lx3, Inches(1.56), hw3, Inches(3.86),
                   fill_color=BG_PAPER, line_color=DIVIDER, line_pt=0.75, radius=0.03)
    add_pill(s3, lx3 + Inches(0.30), Inches(1.86), Inches(1.95), Inches(0.36),
             text="主交付 · Baseline", fill_color=INK, text_color=BG_CANVAS, font_size=12)
    add_textbox(s3, lx3 + Inches(0.30), Inches(2.38), hw3 - Inches(0.60), Inches(0.46),
                text="B = ( Z_BP + Z_EP + Z_Small ) / 3",
                font_size=17, bold=True, color=INK, serif=True, word_wrap=False)
    add_rect(s3, lx3 + Inches(0.30), Inches(2.96), hw3 - Inches(0.60), Inches(0.01), fill_color=DIVIDER)
    add_rich_lines(s3, lx3 + Inches(0.30), Inches(3.16), hw3 - Inches(0.60), Inches(2.05), [
        {"lead": "选股方式：", "lead_color": INK, "text": "沪深300 动态成分内按综合得分等权买入前 50 只，每 5 个交易日调仓。", "space_after": 14},
        {"lead": "风格保留：", "lead_color": INK, "text": "估值因子仅去极值与标准化，刻意不做行业中性化，保留天然价值配置收益。", "space_after": 0},
    ], default_size=15, line_spacing=1.32)

    # 右卡：Oat #F0EEE6 燕麦卡 + 暖胶囊
    rx3 = M_LEFT + hw3 + Inches(0.36)
    add_round_rect(s3, rx3, Inches(1.56), hw3, Inches(3.86),
                   fill_color=BG_OAT, radius=0.03)
    add_pill(s3, rx3 + Inches(0.30), Inches(1.86), Inches(2.05), Inches(0.36),
             text="科学对照 · Research", fill_color=TINT, text_color=TINT_TEXT, font_size=12)
    add_textbox(s3, rx3 + Inches(0.30), Inches(2.38), hw3 - Inches(0.60), Inches(0.46),
                text="S = 0.5 × Baseline + 0.5 × Alpha(006, 033)",
                font_size=16, bold=True, color=STONE, serif=True, word_wrap=False)
    add_rect(s3, rx3 + Inches(0.30), Inches(2.96), hw3 - Inches(0.60), Inches(0.01), fill_color=DIVIDER)
    add_rich_lines(s3, rx3 + Inches(0.30), Inches(3.16), hw3 - Inches(0.60), Inches(2.05), [
        {"lead": "设计初衷：", "lead_color": STONE, "text": "检验 WorldQuant 短周期量价反转信号能否增厚周度价值组合。", "space_after": 14},
        {"lead": "实证定案：", "lead_color": CLAY, "text": "高换手与价值暴露稀释致计费后亏损，团队拒绝事后调参，保留为反例对照。", "space_after": 0},
    ], default_size=15, line_spacing=1.32)

    # 底部深墨黑圆角金句通栏
    add_round_rect(s3, M_LEFT, Inches(5.72), CONTENT_W, Inches(1.06), fill_color=INK, radius=0.08)
    add_rich_lines(s3, M_LEFT + Inches(0.36), Inches(5.96), CONTENT_W - Inches(0.72), Inches(0.65), [
        {"runs": [
            ("核心定调  ｜  ", True, TERRA, 17, True),
            ("在低换手、大容量的沪深300 蓝筹池中，干净纯粹的价值多因子明显优于生硬嫁接高频量价信号。", False, BG_CANVAS, 16, False),
        ], "space_after": 0}
    ], line_spacing=1.3)
    add_note(s3, "讲清核心立意：Baseline聚焦BP+EP+小市值平衡，Research作为科学对照检验Alpha101，发现高频信号在5日调仓下反而破坏收益，因此果断锁定Baseline为主交付策略。")

    # =========================================================================
    # P04: 因子体系与创新
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s4, "02 策略介绍  /  因子与创新", "基本面双锚驱动，辅以无量纲比例化改进", 4)

    lw4 = Inches(5.45)
    f_items = [
        ("BP 账面市值比", "1 / PB", "资产安全边际锚：捕捉低市净率蓝筹估值修复，持仓高度稳定", CLAY),
        ("EP 盈利收益率", "1 / PE", "盈利现金流锚：剔除亏损陷阱，强化当期盈利支撑，与 BP 互补", INK),
        ("Small 规模平衡", "-ln 市值", "指数内均衡权重：防止前 50 只过度集中超大盘金融股", INK),
    ]
    for i, (ftitle, ftag, fdesc, fcol) in enumerate(f_items):
        y = Inches(1.58) + i * Inches(1.18)
        add_textbox(s4, M_LEFT, y, Inches(3.2), Inches(0.36),
                    text=ftitle, font_size=18, bold=True, color=fcol, serif=True)
        add_textbox(s4, M_LEFT + Inches(3.25), y + Inches(0.03), Inches(2.2), Inches(0.30),
                    text=ftag, font_size=14, color=MUTED, align=PP_ALIGN.RIGHT, serif=True)
        add_textbox(s4, M_LEFT, y + Inches(0.42), lw4, Inches(0.52),
                    text=fdesc, font_size=13, color=STONE, line_spacing=1.28)
        add_rect(s4, M_LEFT, y + Inches(1.04), lw4, Inches(0.01), fill_color=DIVIDER)

    # 底部浅陶土底创新亮点卡
    add_round_rect(s4, M_LEFT, Inches(5.22), lw4, Inches(1.56), fill_color=TINT, radius=0.04)
    add_pill(s4, M_LEFT + Inches(0.24), Inches(5.42), Inches(1.30), Inches(0.32),
             text="原创改进", fill_color=CLAY, text_color=BG_CANVAS, font_size=12)
    add_rich_lines(s4, M_LEFT + Inches(0.24), Inches(5.84), lw4 - Inches(0.48), Inches(0.86), [
        {"lead": "无量纲 new012_return：", "lead_color": TINT_TEXT,
         "text": "消除 Alpha012 价格尺度偏差，三期 5 日 IC 全面超越原版，样本外达 0.0156；严守纪律不事后改模型。", "size": 14, "space_after": 0},
    ], line_spacing=1.25)

    # 右侧无缝融合图表
    add_picture_fit(s4, FIG_DIR / "08_new012_vs_alpha012_ic.png",
                    M_LEFT + lw4 + Inches(0.40), Inches(1.52),
                    CONTENT_W - lw4 - Inches(0.40), Inches(5.26))
    add_note(s4, "介绍Baseline三因子的经济学逻辑，重点突出团队独立贡献：发现Alpha012对股价绝对水平敏感，用日收益率替换价差构造new012_return，三期IC均明显提升。")

    # =========================================================================
    # P05: 核心优势（极简大留白 3 栏杂志排版）
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s5, "02 策略介绍  /  核心优势", "三道工程护城河：真时点、无前视、低换手", 5)

    advs = [
        ("01", "真时点 · 防幸存者偏差", [
            {"lead": "动态历史池\n", "lead_color": INK, "text": "按月度快照构建 520 只历史成分池，每日仅读取当时可见名单。", "space_after": 18},
            {"lead": "时效硬约束\n", "lead_color": INK, "text": "申万行业限 45 天时效、估值限 90 天前填，不拿未来信息回填历史。", "space_after": 0},
        ]),
        ("02", "无前视 · 开盘可成交", [
            {"lead": "开盘价判定\n", "lead_color": INK, "text": "摒弃收盘涨跌停标志，仅用开盘已知跳空幅度按板块阈值判定一字板。", "space_after": 18},
            {"lead": "出池防锁死\n", "lead_color": INK, "text": "持仓若出池或变为 ST 仍允许非跌停日卖出，资金周转真实闭环。", "space_after": 0},
        ]),
        ("03", "低换手 · 高成本效率", [
            {"lead": f"单边仅 {b_turn_mean:.1f}%\n", "lead_color": CLAY, "text": "价值锚稳定，每次调仓仅微调 1–5 只股票，交易成本全年拖累仅约 1.5%。", "space_after": 18},
            {"lead": "对比鲜明\n", "lead_color": INK, "text": f"同期量价增强模型单边换手达 {r_turn_mean:.1f}%，达我们的 8.7 倍换手损耗。", "space_after": 0},
        ]),
    ]
    cw3 = (CONTENT_W - Inches(0.45 * 2)) / 3
    for i, (num, atitle, aitems) in enumerate(advs):
        x = M_LEFT + i * (cw3 + Inches(0.45))
        add_textbox(s5, x, Inches(1.68), cw3, Inches(0.68),
                    text=num, font_size=38, bold=True, color=TERRA, serif=True)
        add_textbox(s5, x, Inches(2.46), cw3, Inches(0.44),
                    text=atitle, font_size=20, bold=True, color=INK, serif=True)
        add_rect(s5, x, Inches(3.04), cw3, Inches(0.012), fill_color=DIVIDER)
        add_rich_lines(s5, x, Inches(3.28), cw3, Inches(3.20),
                       aitems, default_size=15, line_spacing=1.35)
    add_note(s5, "总结策略区别于普通回测的三大优势：数据真时点防幸存者偏差、T+1开盘一字板防未来信息、以及极低换手带来的高实盘可落地性。")

    # =========================================================================
    # P06: 风险管理
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s6, "02 策略介绍  /  风险管理", "三层风控防线，历史回撤显著浅于基准指数", 6)

    gw6 = Inches(6.85)
    add_picture_fit(s6, FIG_DIR / "03_drawdown_underwater.png",
                    M_LEFT, Inches(1.54), gw6, Inches(4.55))
    add_textbox(s6, M_LEFT, Inches(6.22), gw6, Inches(0.42),
                text="Baseline 最大回撤 -16.7%，较沪深300 浅 8.1 pct，仅 5 个月收复失地",
                font_size=14, bold=True, color=CLAY, align=PP_ALIGN.CENTER, serif=True, word_wrap=False)

    rx6 = M_LEFT + gw6 + Inches(0.38)
    rw6 = CONTENT_W - gw6 - Inches(0.38)
    add_round_rect(s6, rx6, Inches(1.54), rw6, Inches(5.16), fill_color=BG_OAT, radius=0.03)
    add_textbox(s6, rx6 + Inches(0.30), Inches(1.82), rw6 - Inches(0.60), Inches(0.40),
                text="三道防线严控下行风险", font_size=19, bold=True, color=INK, serif=True)
    add_rect(s6, rx6 + Inches(0.30), Inches(2.30), rw6 - Inches(0.60), Inches(0.01), fill_color=DIVIDER)
    add_rich_lines(s6, rx6 + Inches(0.30), Inches(2.50), rw6 - Inches(0.60), Inches(3.95), [
        {"lead": "第一层 · 选股分散防抱团\n", "lead_color": INK,
         "text": "前 50 只严格 2% 等权，叠加规模平衡因子，不暴露高波动微盘风险。", "space_after": 18},
        {"lead": "第二层 · 交易异常防护\n", "lead_color": INK,
         "text": "剔除上市不足 60 日新股、ST 与停牌股；涨跌停受阻订单顺延、绝不透支现金。", "space_after": 18},
        {"lead": "第三层 · 产品双阈值风控\n", "lead_color": CLAY,
         "text": "绝对净值 0.85 预警 / 0.80 止损；高水位回撤 -18% / -22%，兼顾安全垫防误平。", "space_after": 0},
    ], default_size=15, line_spacing=1.30)
    add_note(s6, "讲解风控设计：历史回测最大回撤-16.7%发生在2023年5月至12月，5个月修复，远浅于沪深300的-24.8%；同时说明绝对净值0.85/0.80与高水位回撤-18%/-22%的双重防误平设计。")

    # =========================================================================
    # P07: 深度思考
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s7, "02 策略介绍  /  深度思考", "高频信号并非无效，而是周度调仓频率错配", 7)

    gw7 = Inches(6.75)
    add_picture_fit(s7, FIG_DIR / "04_cost_erosion_waterfall.png",
                    M_LEFT, Inches(1.56), gw7, Inches(5.10))

    rx7 = M_LEFT + gw7 + Inches(0.42)
    rw7 = CONTENT_W - gw7 - Inches(0.42)
    insights = [
        ("01", "成本吞噬 37.2 个百分点", "5 日调仓下高频排名剧烈跳变，51.2% 单边换手磨平正收益。", CLAY),
        ("02", "价值核心被稀释", "混入 50% 量价信号后 BP/EP 暴露下降约四分之一且伴负残差。", INK),
        ("03", "降频即可显著缓释", "120 组网格证实调仓拉长至 20 日，样本外净年化回升至 10.4%。", INK),
        ("04", "坚守研究纪律", "不根据样本外反推最优参数，该规律留待未来新样本盲测验证。", INK),
    ]
    for i, (num, ititle, idesc, ncol) in enumerate(insights):
        y = Inches(1.60) + i * Inches(1.28)
        add_textbox(s7, rx7, y, Inches(0.56), Inches(0.45),
                    text=num, font_size=22, bold=True, color=ncol, serif=True)
        add_textbox(s7, rx7 + Inches(0.60), y + Inches(0.02), rw7 - Inches(0.60), Inches(0.36),
                    text=ititle, font_size=17, bold=True, color=INK, serif=True)
        add_textbox(s7, rx7 + Inches(0.60), y + Inches(0.42), rw7 - Inches(0.60), Inches(0.56),
                    text=idesc, font_size=14, color=STONE, line_spacing=1.25)
        if i < 3:
            add_rect(s7, rx7, y + Inches(1.12), rw7, Inches(0.01), fill_color=DIVIDER)

    add_note(s7, "这是最能体现团队研究深度的页面：用瀑布图直观讲清Research为何亏损，点出‘频率错配’机制与20日降频修复证据，同时强调不事后调参的学术诚信。")

    # =========================================================================
    # P08: 业绩概览（超大衬线 KPI + 细线分隔）
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s8, "03 产品介绍  /  业绩概览", "计成本年化 10.78%，穿越震荡持续跑赢基准", 8)

    kpis = [
        ("计成本年化收益", f"{b_full['年化收益']*100:.2f}%", f"同期沪深300 仅 {h_full['年化收益']*100:.2f}%", CLAY),
        ("全样本累计收益", f"+{b_full['累计收益']*100:.2f}%", f"净值 {nav_df['baseline'].iloc[-1]:.3f} ｜ 指数 +{h_full['累计收益']*100:.2f}%", INK),
        ("全样本夏普比率", f"{b_full['夏普']:.2f}", f"验证期 {b_val['夏普']:.2f} ｜ 信息比率 {ir_base:.2f}", INK),
        ("全样本最大回撤", f"{b_full['最大回撤']*100:.1f}%", "较沪深300 浅 8.1 个百分点", INK),
    ]
    kw = CONTENT_W / 4
    for i, (ktitle, kval, ksub, kcol) in enumerate(kpis):
        x = M_LEFT + i * kw
        pad_l = Inches(0.04) if i == 0 else Inches(0.24)
        add_textbox(s8, x + pad_l, Inches(1.66), kw - pad_l - Inches(0.14), Inches(0.32),
                    text=ktitle, font_size=14, bold=True, color=MUTED)
        add_textbox(s8, x + pad_l, Inches(2.08), kw - pad_l - Inches(0.14), Inches(0.88),
                    text=kval, font_size=36, bold=True, color=kcol, serif=True, word_wrap=False)
        add_textbox(s8, x + pad_l, Inches(3.12), kw - pad_l - Inches(0.10), Inches(0.48),
                    text=ksub, font_size=13, color=STONE, line_spacing=1.22, word_wrap=False)
        if i < 3:
            add_rect(s8, x + kw, Inches(1.74), Inches(0.012), Inches(1.92), fill_color=DIVIDER)

    add_rect(s8, M_LEFT, Inches(3.96), CONTENT_W, Inches(0.01), fill_color=DIVIDER)

    hw8 = (CONTENT_W - Inches(0.36)) / 2
    add_round_rect(s8, M_LEFT, Inches(4.26), hw8, Inches(2.38), fill_color=BG_OAT, radius=0.03)
    add_textbox(s8, M_LEFT + Inches(0.28), Inches(4.52), hw8 - Inches(0.56), Inches(0.38),
                text="分阶段稳健性 · 验证期与样本外双双领先", font_size=18, bold=True, color=INK, serif=True)
    add_rect(s8, M_LEFT + Inches(0.28), Inches(4.98), hw8 - Inches(0.56), Inches(0.01), fill_color=DIVIDER)
    add_rich_lines(s8, M_LEFT + Inches(0.28), Inches(5.16), hw8 - Inches(0.56), Inches(1.30), [
        {"lead": "验证期 2023–2024：", "lead_color": INK,
         "text": f"累计 +{b_val['累计收益']*100:.2f}%，大幅跑赢沪深300 {h_val['累计收益']*100:.2f}%。", "space_after": 10},
        {"lead": "样本外 2025–2026.10：", "lead_color": CLAY,
         "text": f"无缝衔接 +{oos_base_seamless:.2f}%，领先指数 +{oos_hs_seamless:.2f}% 超 12 pct。", "space_after": 0},
    ], default_size=15, line_spacing=1.26)

    rx8 = M_LEFT + hw8 + Inches(0.36)
    add_round_rect(s8, rx8, Inches(4.26), hw8, Inches(2.38), fill_color=BG_OAT, radius=0.03)
    add_textbox(s8, rx8 + Inches(0.28), Inches(4.52), hw8 - Inches(0.56), Inches(0.38),
                text="实盘成本与口径透明度", font_size=18, bold=True, color=INK, serif=True)
    add_rect(s8, rx8 + Inches(0.28), Inches(4.98), hw8 - Inches(0.56), Inches(0.01), fill_color=DIVIDER)
    add_rich_lines(s8, rx8 + Inches(0.28), Inches(5.16), hw8 - Inches(0.56), Inches(1.30), [
        {"lead": "保守扣费：", "lead_color": INK,
         "text": "含双边万3 佣金、全样本千1 印花税与双边千1 滑点，现金零计息。", "space_after": 10},
        {"lead": "对照表现：", "lead_color": INK,
         "text": f"同期 Research 计费后累计 {r_full['累计收益']*100:.2f}%，印证价值主线稳健。", "space_after": 0},
    ], default_size=15, line_spacing=1.26)
    add_note(s8, "用四个核心数字一页打穿产品业绩：年化10.78%、累计+45.38%、夏普0.67、最大回撤-16.7%，并交代验证期与样本外均保持双位数超额。")

    # =========================================================================
    # P09: 净值走势
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s9, "03 产品介绍  /  净值走势", "2023 年以来稳健上行，与指数持续拉开剪刀差", 9)

    gw9 = Inches(7.70)
    add_picture_fit(s9, FIG_DIR / "01_nav_curve.png", M_LEFT, Inches(1.56), gw9, Inches(5.12))

    rx9 = M_LEFT + gw9 + Inches(0.38)
    rw9 = CONTENT_W - gw9 - Inches(0.38)
    nav_notes = [
        ("熊市抗跌", "2023 至 2024 年中市场调整期，价值高股息提供强防御垫，回撤显著浅于指数。", INK),
        ("震荡修复快", "2024 年 9 月起迅速站上 1.25 平台，2025–2026 年稳步抬升至 1.454。", INK),
        (f"月度胜率 {win_rate:.1f}%", f"{n_months} 个自然月中 {pos_months} 个月录得正收益，最差单月 {worst_month:.1f}% 优于基准。", CLAY),
    ]
    for i, (ntitle, ndesc, ncol) in enumerate(nav_notes):
        y = Inches(1.74) + i * Inches(1.66)
        add_textbox(s9, rx9, y, rw9, Inches(0.38),
                    text=ntitle, font_size=19, bold=True, color=ncol, serif=True)
        add_textbox(s9, rx9, y + Inches(0.46), rw9, Inches(0.86),
                    text=ndesc, font_size=15, color=STONE, line_spacing=1.32)
        if i < 2:
            add_rect(s9, rx9, y + Inches(1.44), rw9, Inches(0.01), fill_color=DIVIDER)

    add_note(s9, "配合净值三线图讲解：陶土橙Baseline稳步向上，暖石虚线沪深300原地踏步，暖沙Research被交易成本拖累下行，视觉对比一目了然。")

    # =========================================================================
    # P10: 产品与费率
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s10, "03 产品介绍  /  产品与费率", "匹配不同资金属性，投资者到手年化 7.6%–8.9%", 10)

    lw10 = Inches(5.90)
    add_round_rect(s10, M_LEFT, Inches(1.54), lw10, Inches(1.56), fill_color=BG_OAT, radius=0.03)
    add_rich_lines(s10, M_LEFT + Inches(0.24), Inches(1.70), lw10 - Inches(0.48), Inches(1.26), [
        {"lead": "产品形态：", "lead_color": INK, "text": "私募基金 / 专户 ｜ R3 中风险 ｜ 100 万元起投", "size": 14, "space_after": 8},
        {"lead": "申赎机制：", "lead_color": INK, "text": "6 个月封闭 + 月度开放，匹配 5 日调仓减拖累", "size": 14, "space_after": 8},
        {"lead": "客户定位：", "lead_color": INK, "text": "高净值个人、家族办公室、FOF 与 MOM 机构", "size": 14, "space_after": 0},
    ], line_spacing=1.2)

    fee_headers = ["方案", "固定费 + 分成", "到手年化", "夏普", "最大回撤"]
    fee_rows = []
    for _, row in fee_df.iterrows():
        pid = row["plan_id"]
        if pid == "Gross":
            continue
        short_map = {
            "A": ("A 标准份额", "1.2% + 20%高水位"),
            "B": ("B 超额计提", "1.2% + 20%超额"),
            "C": ("C 机构份额", "0.75% + 15%超额"),
            "D": ("D 纯管理费", "1.7% + 无分成"),
        }
        nm, desc = short_map.get(pid, (row["plan_name"], ""))
        fee_rows.append([
            nm, desc, f"{row['ann_return']*100:.2f}%", f"{row['sharpe']:.2f}", f"{row['max_drawdown']*100:.2f}%"
        ])
    add_warm_three_line_table(
        s10, M_LEFT, Inches(3.34), lw10, Inches(3.38),
        fee_headers, fee_rows, col_widths=[1.22, 2.02, 0.90, 0.72, 1.04],
        aligns=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT],
        font_size=13, highlight_row=2,
    )

    rx10 = M_LEFT + lw10 + Inches(0.30)
    add_picture_fit(s10, FIG_DIR / "12_fee_net_nav.png",
                    rx10, Inches(1.52), CONTENT_W - lw10 - Inches(0.30), Inches(5.22))
    add_note(s10, "介绍产品定位与四档费率：高净值可选A/B档，机构客户推荐C档（0.75%固定费+15%超额提成，到手年化达8.48%、信息比率0.68），实现管理人与持有人利益对齐。")

    # =========================================================================
    # P11: 资金容量
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s11, "03 产品介绍  /  资金容量", "流动性硬约束稳健承数亿，理论半衰约 81 亿", 11)

    gw11 = Inches(7.15)
    add_picture_fit(s11, FIG_DIR / "11_capacity_curve.png", M_LEFT, Inches(1.54), gw11, Inches(5.16))

    rx11 = M_LEFT + gw11 + Inches(0.34)
    rw11 = CONTENT_W - gw11 - Inches(0.34)
    liq = data["prod"]["liquidity_profile"][0]
    y08_10y = data["prod"]["capacity_impact"]["y08_milestones"]["10亿"]
    add_round_rect(s11, rx11, Inches(1.50), rw11, Inches(5.28), fill_color=BG_OAT, radius=0.03)
    add_textbox(s11, rx11 + Inches(0.28), Inches(1.74), rw11 - Inches(0.56), Inches(0.36),
                text="三口径容量评估", font_size=19, bold=True, color=INK, serif=True)
    add_rect(s11, rx11 + Inches(0.28), Inches(2.18), rw11 - Inches(0.56), Inches(0.01), fill_color=DIVIDER)
    add_rich_lines(s11, rx11 + Inches(0.28), Inches(2.34), rw11 - Inches(0.56), Inches(4.25), [
        {"lead": "大盘流动性底座\n", "lead_color": INK,
         "text": f"持仓 20 日均成交额中位数 {liq['held_adv20_median_yi']:.2f} 亿，最新一期升至 {liq['latest_adv20_median_yi']:.2f} 亿。", "space_after": 8},
        {"lead": "5% 参与率硬约束\n", "lead_color": INK,
         "text": "1 日调仓可承 2.58–5.36 亿，3 日拆单线性扩至 7.75–16.09 亿。", "space_after": 8},
        {"lead": "10 亿元假设情景\n", "lead_color": INK,
         "text": f"冲击拖累仅约 {y08_10y['baseline_drag_ann']*100:.1f}%，净年化 {y08_10y['baseline_net_ann']*100:.2f}%；42/185 期瓶颈股需延窗。", "space_after": 8},
        {"lead": f"理论半衰约 {cap_half:.1f} 亿\n", "lead_color": CLAY,
         "text": "平方根冲击下超额减半容量达 80.9 亿元，Research 因高换手归零。", "space_after": 0},
    ], default_size=14, line_spacing=1.18)
    add_note(s11, "用人话讲清容量两个口径：日常硬约束看短板个股大约几亿到十亿级别，而整体阿尔法半衰理论容量在81亿元左右；反观Research因换手过高容量归零。")

    # =========================================================================
    # P12: 雪球实盘
    # =========================================================================
    s12 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s12, "03 产品介绍  /  雪球实盘", "雪球公开组合 ZH3689205，30 只蓝筹满仓跟踪", 12)

    lw12 = Inches(6.05)
    add_picture_fit(s12, FIG_DIR / "13_latest_industry_dist.png", M_LEFT, Inches(1.52), lw12, Inches(3.54))
    add_round_rect(s12, M_LEFT, Inches(5.18), lw12, Inches(1.54), fill_color=BG_OAT, radius=0.04)
    add_rich_lines(s12, M_LEFT + Inches(0.24), Inches(5.34), lw12 - Inches(0.48), Inches(1.24), [
        {"lead": "最新信号分布：", "lead_color": INK,
         "text": "银行 32% + 非银金融 28% + 建筑装饰 14% 主导低估值配置。", "size": 14, "space_after": 8},
        {"lead": "雪球平台适配：", "lead_color": CLAY,
         "text": "受限于 30 只与整数权重规则，取前 10 名各 4%、后 20 名各 3% 满仓。", "size": 14, "space_after": 0},
    ], line_spacing=1.20)

    rx12 = M_LEFT + lw12 + Inches(0.35)
    rw12 = CONTENT_W - lw12 - Inches(0.35)
    shot_files = sorted(
        p for p in XQ_SHOTS.glob("*") if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ) if XQ_SHOTS.exists() else []
    add_round_rect(s12, rx12, Inches(1.54), rw12, Inches(4.06),
                   fill_color=BG_PAPER, line_color=DIVIDER, line_pt=0.75, radius=0.03)
    if shot_files:
        add_picture_fit(s12, shot_files[0], rx12 + Inches(0.10), Inches(1.64), rw12 - Inches(0.20), Inches(3.86))
    else:
        add_rich_lines(s12, rx12 + Inches(0.36), Inches(2.90), rw12 - Inches(0.72), Inches(1.40), [
            {"runs": [("雪球实盘净值截图 · 审核成交后接入", True, INK, 16, True)],
             "align": PP_ALIGN.CENTER, "space_after": 10},
            {"runs": [("组合已创建并挂单，放图至 screenshots/ 重编即可", False, MUTED, 13, False)],
             "align": PP_ALIGN.CENTER, "space_after": 0},
        ], valign=MSO_ANCHOR.MIDDLE)

    # 底部深墨黑胶囊链接条
    add_round_rect(s12, rx12, Inches(5.78), rw12, Inches(0.92), fill_color=INK, radius=0.14)
    add_rich_lines(s12, rx12 + Inches(0.26), Inches(5.93), rw12 - Inches(0.52), Inches(0.66), [
        {"runs": [("雪球公开组合  ", True, TERRA, 14, False), ("ZH3689205", True, BG_CANVAS, 15, True)], "space_after": 4},
        {"runs": [("https://www.xueqiu.com/P/ZH3689205", False, BG_CANVAS, 14, False)], "space_after": 0},
    ], line_spacing=1.18)
    add_note(s12, "展示雪球实盘已建组合ZH3689205：解释为何采用30只4%/3%满仓（实测平台上限30只+整数百分比），并说明当前行业集中于银行与基建等高BP/EP蓝筹。")

    # =========================================================================
    # P13: 总结展望（对称两栏编辑风布局）
    # =========================================================================
    s13 = prs.slides.add_slide(blank_layout)
    add_editorial_chrome(s13, "04 总结致谢  /  总结展望", "稳健可落地的价值产品，诚实面对数据与平台边界", 13)

    col_w13 = Inches(5.45)
    lx13 = M_LEFT
    rx13 = M_LEFT + col_w13 + Inches(0.83)

    # 中央垂直发丝分割线
    add_rect(s13, M_LEFT + col_w13 + Inches(0.41), Inches(1.62), Inches(0.012), Inches(5.05), fill_color=DIVIDER)

    add_textbox(s13, lx13, Inches(1.62), col_w13, Inches(0.42),
                text="三大核心交付结论", font_size=20, bold=True, color=INK, serif=True)
    add_rect(s13, lx13, Inches(2.12), col_w13, Inches(0.015), fill_color=INK)

    left_pts = [
        ("01", "策略稳健可落地", f"Baseline 计成本年化 {b_full['年化收益']*100:.2f}%、夏普 {b_full['夏普']:.2f}、最大回撤 {b_full['最大回撤']*100:.1f}%，长期跑赢沪深300。"),
        ("02", "原创与机理闭环", "提出无量纲 new012 改善尺度敏感性，并用频率错配拆解高频量价损耗之谜。"),
        ("03", "产品与实盘接轨", "完成三口径容量评估、四档费率净值测算，并上线雪球模拟组合 ZH3689205。"),
    ]
    for i, (num, ptitle, pdesc) in enumerate(left_pts):
        y = Inches(2.40) + i * Inches(1.48)
        add_textbox(s13, lx13, y, Inches(0.55), Inches(0.42),
                    text=num, font_size=22, bold=True, color=INK, serif=True)
        add_textbox(s13, lx13 + Inches(0.58), y + Inches(0.02), col_w13 - Inches(0.58), Inches(0.36),
                    text=ptitle, font_size=17, bold=True, color=INK, serif=True)
        add_textbox(s13, lx13 + Inches(0.58), y + Inches(0.44), col_w13 - Inches(0.58), Inches(0.76),
                    text=pdesc, font_size=14, color=STONE, line_spacing=1.30)

    add_textbox(s13, rx13, Inches(1.62), col_w13, Inches(0.42),
                text="诚实边界与未来演进", font_size=20, bold=True, color=CLAY, serif=True)
    add_rect(s13, rx13, Inches(2.12), col_w13, Inches(0.015), fill_color=CLAY)

    right_pts = [
        ("01", "数据底层局限", "流通市值由成交额与换手率代理，缺财报精确发布时间戳；未来拟接入商业 PIT 库。"),
        ("02", "行业集中度提示", "最新持仓金融与建筑占比 74%，实盘产品可增设单行业权重偏离上限约束。"),
        ("03", "严格前瞻跟踪", "持续运行雪球模拟盘，并在未来新样本上盲测 20 日降频与 new012 复合方案。"),
    ]
    for i, (num, ptitle, pdesc) in enumerate(right_pts):
        y = Inches(2.40) + i * Inches(1.48)
        add_textbox(s13, rx13, y, Inches(0.55), Inches(0.42),
                    text=num, font_size=22, bold=True, color=CLAY, serif=True)
        add_textbox(s13, rx13 + Inches(0.58), y + Inches(0.02), col_w13 - Inches(0.58), Inches(0.36),
                    text=ptitle, font_size=17, bold=True, color=INK, serif=True)
        add_textbox(s13, rx13 + Inches(0.58), y + Inches(0.44), col_w13 - Inches(0.58), Inches(0.76),
                    text=pdesc, font_size=14, color=STONE, line_spacing=1.30)

    add_note(s13, "简洁收束全片：左侧讲三大交付成果，右侧坦诚交代市值代理、行业集中度等局限与下一步优化路线。")

    # =========================================================================
    # P14: 深墨黑 #141413 封底
    # =========================================================================
    s14 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s14, INK)

    # 左侧陶土星芒符号点缀
    draw_back_starburst(s14, 1.95, 3.15)

    tx14 = Inches(3.25)
    tw14 = Inches(9.20)
    add_textbox(s14, tx14, Inches(2.22), tw14, Inches(0.88),
                text="感谢聆听 · 欢迎批评指正", font_size=40, bold=True, color=BG_CANVAS, serif=True, word_wrap=False)
    add_textbox(s14, tx14, Inches(3.22), tw14, Inches(0.48),
                text="沪深300 价值精选量化策略  ｜  答辩交流环节", font_size=20, color=DARK_MUTED, serif=False)

    add_rect(s14, tx14, Inches(4.06), tw14, Inches(0.012), fill_color=RGBColor(0x36, 0x35, 0x31))

    add_rich_lines(s14, tx14, Inches(4.38), tw14, Inches(1.50), [
        {"runs": [("雪球实盘跟踪  ｜  ", True, TERRA, 15, False),
                  ("https://www.xueqiu.com/P/ZH3689205  ·  ZH3689205", False, BG_CANVAS, 15, False)], "space_after": 12},
        {"runs": [("项目代码仓库  ｜  ", True, TERRA, 15, False),
                  ("【待填：GitHub 仓库链接】", False, BG_CANVAS, 15, False)], "space_after": 12},
        {"runs": [("技术细节备查  ｜  ", True, DARK_MUTED, 14, False),
                  ("完整数学推导、120 组敏感性网格与子区间口径详见 30 页书面技术报告", False, DARK_MUTED, 14, False)], "space_after": 0},
    ])

    add_textbox(s14, SLIDE_W - M_RIGHT - Inches(1.4), Inches(6.85), Inches(1.4), Inches(0.28),
                text="14 / 14", font_size=12, color=DARK_MUTED, align=PP_ALIGN.RIGHT)
    add_note(s14, "致谢收尾，引导进入老师和同学的自由提问与答辩环节。")

    DECK_DIR.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT_PPTX))
    print(f"Saved PPTX: {OUT_PPTX} (slides={len(prs.slides)})")


if __name__ == "__main__":
    build_deck()
