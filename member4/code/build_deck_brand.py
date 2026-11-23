# -*- coding: utf-8 -*-
"""
组员4：Anthropic brand-guidelines + competitive-analysis 双技能版 14 页路演 PPT
严格遵循：
1. brand-guidelines：
   - 主色：Dark #141413 / Light #FAF9F5 / Mid Gray #B0AEA5 / Light Gray #E8E6DC
   - 三强调色循环：Orange #D97757 / Blue #6A9BCC / Green #788C5D
   - 字体配对：标题 Sans-serif (Poppins/Arial + 黑体-简)，正文 Serif (Lora/Georgia + 宋体-简)
2. competitive-analysis：
   - 洞察式标题（Insight Headlines）
   - 行业关键指标（Step 0）、2x2 竞争定位矩阵（Step 5）、●●●+实值同业对比表（Step 7）
   - 目标产品档案（Step 3）、牛/基准/熊情景与量化信号（Step 9）、护城河评估表（Step 9）
   - 正文/表格 >= 14pt，左文右数，浅灰表头，零投影
输出：
- member4/deck/路演_Skill版.pptx（不覆盖原 路演.pptx，方便并排对比）
复现命令（在 member4 目录）：
    .venv/bin/python code/build_deck_brand.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from paths import M3_RES, MEMBER4_DIR

RES_DIR = MEMBER4_DIR / "results"
FIG_DIR = MEMBER4_DIR / "figures" / "slide_brand"
DECK_DIR = MEMBER4_DIR / "deck"
OUT_PPTX = DECK_DIR / "路演_Skill版.pptx"

# ---------------------------------------------------------------------------
# Anthropic Official brand-guidelines Constants (16:9)
# ---------------------------------------------------------------------------
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
M_LEFT = Inches(0.75)
M_RIGHT = Inches(0.75)
CONTENT_W = SLIDE_W - M_LEFT - M_RIGHT  # 11.833 in

# Typography per brand-guidelines: Headings Sans (Poppins/Arial), Body Serif (Lora/Georgia)
FONT_HEAD_EN = "Arial"
FONT_HEAD_CN = "黑体-简"
FONT_BODY_EN = "Georgia"
FONT_BODY_CN = "宋体-简"

# Official Anthropic brand-guidelines Palette
DARK = RGBColor(0x14, 0x14, 0x13)          # #141413 Primary dark
DARK_CARD = RGBColor(0x22, 0x21, 0x1F)     # Subtle card on dark canvas
DARK_LINE = RGBColor(0x36, 0x35, 0x31)     # Hairline on dark canvas
LIGHT = RGBColor(0xFA, 0xF9, 0xF5)         # #FAF9F5 Light background / light text
MID_GRAY = RGBColor(0xB0, 0xAE, 0xA5)      # #B0AEA5 Secondary elements
LIGHT_GRAY = RGBColor(0xE8, 0xE6, 0xDC)    # #E8E6DC Subtle backgrounds / table headers
LIGHT_CARD = RGBColor(0xF2, 0xF0, 0xE8)    # Softer card surface
BORDER = RGBColor(0xDC, 0xD9, 0xCE)        # Thin divider
TEXT_SUB = RGBColor(0x59, 0x57, 0x51)      # Secondary body ink

ORANGE = RGBColor(0xD9, 0x77, 0x57)        # #D97757 Primary accent
ORANGE_DEEP = RGBColor(0xC0, 0x5E, 0x3D)   # High-contrast text on light
ORANGE_TINT = RGBColor(0xF5, 0xE4, 0xDC)   # Soft orange pill fill

BLUE = RGBColor(0x6A, 0x9B, 0xCC)          # #6A9BCC Secondary accent
BLUE_DEEP = RGBColor(0x45, 0x74, 0xA4)     # High-contrast blue text
BLUE_TINT = RGBColor(0xE6, 0xEF, 0xF7)     # Soft blue pill fill

GREEN = RGBColor(0x78, 0x8C, 0x5D)         # #788C5D Tertiary accent
GREEN_DEEP = RGBColor(0x55, 0x69, 0x3D)    # High-contrast green text
GREEN_TINT = RGBColor(0xEA, 0xF0, 0xE3)    # Soft green pill fill


def load_data() -> dict:
    with open(RES_DIR / "product_summary.json", "r", encoding="utf-8") as f:
        prod = json.load(f)
    with open(RES_DIR / "xueqiu_summary.json", "r", encoding="utf-8") as f:
        xq = json.load(f)
    fee_df = pd.read_csv(RES_DIR / "fee_analysis.csv")
    cap_df = pd.read_csv(RES_DIR / "capacity_constraints.csv")
    metrics_df = pd.read_csv(M3_RES / "metrics.csv")
    nav_df = pd.read_csv(M3_RES / "nav.csv", index_col=0)
    turn_df = pd.read_csv(M3_RES / "turnover.csv", index_col=0)
    monthly_df = pd.read_csv(M3_RES / "monthly_returns.csv", index_col=0)
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
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _set_font(run, size: float, bold: bool = False, color: RGBColor = DARK, heading: bool = False):
    en_font = FONT_HEAD_EN if heading else FONT_BODY_EN
    cn_font = FONT_HEAD_CN if heading else FONT_BODY_CN
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


def add_rect(slide, x, y, w, h, fill_color: RGBColor | None = None,
             line_color: RGBColor | None = None, line_pt: float = 0.75):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
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


def add_round_rect(slide, x, y, w, h, fill_color: RGBColor | None = None,
                   line_color: RGBColor | None = None, line_pt: float = 0.75, radius: float = 0.04):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
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


def add_circle(slide, cx, cy, dia, fill_color: RGBColor,
               line_color: RGBColor | None = None, line_pt: float = 0.75):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, cx - dia // 2, cy - dia // 2, dia, dia)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill_color
    if line_color is not None:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_pt)
    else:
        shp.line.fill.background()
    return clear_shadow(shp)


def add_line(slide, x1, y1, x2, y2, color: RGBColor = BORDER, width_pt: float = 1.0):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    conn.line.color.rgb = color
    conn.line.width = Pt(width_pt)
    return clear_shadow(conn)


def add_textbox(slide, x, y, w, h, text: str = "", font_size: float = 14.5,
                bold: bool = False, color: RGBColor = DARK, align=PP_ALIGN.LEFT,
                heading: bool = False, line_spacing: float = 1.25,
                anchor=MSO_ANCHOR.TOP, word_wrap: bool = True):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = word_wrap
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(2)
    tf.margin_right = Pt(2)
    tf.margin_top = Pt(1)
    tf.margin_bottom = Pt(1)
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    if text:
        run = p.add_run()
        run.text = text
        _set_font(run, font_size, bold=bold, color=color, heading=heading)
    return tb


def add_rich_lines(slide, x, y, w, h, lines: Iterable[dict],
                   default_size: float = 14.5, default_color: RGBColor = TEXT_SUB,
                   line_spacing: float = 1.28, default_heading: bool = False):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(2)
    tf.margin_right = Pt(2)
    tf.margin_top = Pt(1)
    tf.margin_bottom = Pt(1)
    for idx, item in enumerate(lines):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = item.get("align", PP_ALIGN.LEFT)
        p.line_spacing = item.get("line_spacing", line_spacing)
        p.space_after = Pt(item.get("space_after", 8))
        lead = item.get("lead")
        if lead:
            r0 = p.add_run()
            r0.text = lead
            _set_font(
                r0,
                item.get("lead_size", item.get("size", default_size)),
                bold=item.get("lead_bold", True),
                color=item.get("lead_color", DARK),
                heading=item.get("lead_heading", True),
            )
        txt = item.get("text", "")
        if txt:
            r1 = p.add_run()
            r1.text = txt
            _set_font(
                r1,
                item.get("size", default_size),
                bold=item.get("bold", False),
                color=item.get("color", default_color),
                heading=item.get("heading", default_heading),
            )
    return tb


def add_pill(slide, x, y, w, h, text: str, fill_color: RGBColor, text_color: RGBColor,
             font_size: float = 11.5, bold: bool = True, line_color: RGBColor | None = None):
    shp = add_round_rect(slide, x, y, w, h, fill_color=fill_color,
                         line_color=line_color, line_pt=0.75, radius=0.5)
    tf = shp.text_frame
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Pt(6)
    tf.margin_right = Pt(6)
    tf.margin_top = Pt(1)
    tf.margin_bottom = Pt(1)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    _set_font(run, font_size, bold=bold, color=text_color, heading=True)
    return shp


def add_picture_fit(slide, img_path: Path, box_x, box_y, box_w, box_h):
    with Image.open(img_path) as im:
        iw, ih = im.size
    ratio = iw / ih
    box_ratio = box_w / box_h
    if ratio >= box_ratio:
        w = box_w
        h = int(box_w / ratio)
        x = box_x
        y = box_y + (box_h - h) // 2
    else:
        h = box_h
        w = int(box_h * ratio)
        x = box_x + (box_w - w) // 2
        y = box_y
    return slide.shapes.add_picture(str(img_path), x, y, width=w, height=h)


def _set_cell_border(cell, border_color: str = "DCD9CE", top_w: int = 0, bottom_w: int = 6350):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        for old in tcPr.findall(qn(tag)):
            tcPr.remove(old)
    # Remove left/right vertical borders cleanly
    for tag in ("a:lnL", "a:lnR"):
        ln = OxmlElement(tag)
        ln.set("w", "0")
        ln.append(OxmlElement("a:noFill"))
        tcPr.append(ln)
    for tag, w_val in (("a:lnT", top_w), ("a:lnB", bottom_w)):
        ln = OxmlElement(tag)
        ln.set("w", str(w_val))
        if w_val > 0:
            sf = OxmlElement("a:solidFill")
            clr = OxmlElement("a:srgbClr")
            clr.set("val", border_color)
            sf.append(clr)
            ln.append(sf)
        else:
            ln.append(OxmlElement("a:noFill"))
        tcPr.append(ln)


def add_styled_table(slide, x, y, w, h, headers: list[str], rows: list[list[str]],
                     col_widths: list[float] | None = None,
                     alignments: list | None = None,
                     highlight_row: int | None = None,
                     highlight_fill: RGBColor = ORANGE_TINT,
                     font_size: float = 14.0,
                     dark_mode: bool = False):
    """Build a crisp competitive-analysis standard table (light gray header, >=14pt, left text / right numbers)."""
    n_rows = len(rows) + 1
    n_cols = len(headers)
    tbl_shape = slide.shapes.add_table(n_rows, n_cols, x, y, w, h)
    tbl = tbl_shape.table
    tbl.first_row = False
    tbl.horz_banding = False
    tbl.vert_banding = False

    if col_widths:
        total = sum(col_widths)
        for ci, cw in enumerate(col_widths):
            tbl.columns[ci].width = int(w * (cw / total))

    hdr_fill = DARK_CARD if dark_mode else LIGHT_GRAY
    hdr_txt = LIGHT if dark_mode else DARK
    body_txt = LIGHT if dark_mode else DARK
    border_hex = "363531" if dark_mode else "DCD9CE"
    top_hex = "B0AEA5" if dark_mode else "141413"

    for ci, htext in enumerate(headers):
        cell = tbl.cell(0, ci)
        cell.fill.solid()
        cell.fill.fore_color.rgb = hdr_fill
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = Inches(0.11)
        cell.margin_right = Inches(0.11)
        cell.margin_top = Inches(0.06)
        cell.margin_bottom = Inches(0.06)
        _set_cell_border(cell, border_color=top_hex, top_w=12700, bottom_w=9525)
        p = cell.text_frame.paragraphs[0]
        p.alignment = alignments[ci] if alignments else PP_ALIGN.LEFT
        run = p.add_run()
        run.text = htext
        _set_font(run, font_size, bold=True, color=hdr_txt, heading=True)

    for ri, row in enumerate(rows):
        is_hl = (highlight_row is not None and ri == highlight_row)
        is_last = (ri == len(rows) - 1)
        for ci, val in enumerate(row):
            cell = tbl.cell(ri + 1, ci)
            if is_hl:
                cell.fill.solid()
                cell.fill.fore_color.rgb = highlight_fill
            elif dark_mode:
                cell.fill.solid()
                cell.fill.fore_color.rgb = DARK if ri % 2 == 0 else RGBColor(0x1B, 0x1A, 0x18)
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT if ri % 2 == 0 else RGBColor(0xF5, 0xF4, 0xEE)

            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.11)
            cell.margin_right = Inches(0.11)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.05)
            _set_cell_border(
                cell,
                border_color=top_hex if is_last else border_hex,
                top_w=0,
                bottom_w=12700 if is_last else 6350,
            )
            p = cell.text_frame.paragraphs[0]
            p.alignment = alignments[ci] if alignments else PP_ALIGN.LEFT

            # Smart accent coloring for rating dots / strong / weak / highlighted row
            txt_col = body_txt
            is_bold = is_hl or (ci == 0)
            if val.startswith("●●●") or val in ("强", "极强", "主推"):
                txt_col = ORANGE_DEEP if not dark_mode else ORANGE
                is_bold = True
            elif val.startswith("●●○") or val == "中":
                txt_col = BLUE_DEEP if not dark_mode else BLUE
            elif val.startswith("●○○") or val == "弱":
                txt_col = MID_GRAY
            elif is_hl and not dark_mode and ci > 0:
                txt_col = DARK

            if val.startswith(("●●●", "●●○", "●○○")):
                # Render rating circles in pure Latin Arial so dot sizes stay 100% uniform next to CJK text
                r_dot = p.add_run()
                r_dot.text = val[:3]
                _set_font(r_dot, font_size - 1.0, bold=False, color=txt_col, heading=True)
                rPr = r_dot._r.get_or_add_rPr()
                for tag in ("a:latin", "a:ea", "a:cs"):
                    el = rPr.find(qn(tag))
                    if el is not None:
                        el.set("typeface", "Arial")
                r_rest = p.add_run()
                r_rest.text = val[3:]
                _set_font(r_rest, font_size, bold=is_bold, color=txt_col, heading=(ci == 0 or is_bold))
            else:
                run = p.add_run()
                run.text = val
                _set_font(run, font_size, bold=is_bold, color=txt_col, heading=(ci == 0 or is_bold))
    return tbl_shape


def add_brand_chrome(slide, section_tag: str, headline: str, page_num: int,
                     accent: RGBColor = ORANGE, dark: bool = False):
    """Consistent Anthropic brand-guidelines header: 3-dot accent bar + section tag + insight headline."""
    set_slide_bg(slide, DARK if dark else LIGHT)

    # Top thin 3-color brand micro-bar on left edge (Orange / Blue / Green signature)
    bar_y = Inches(0.32)
    add_rect(slide, M_LEFT, bar_y, Inches(0.26), Inches(0.055), fill_color=ORANGE)
    add_rect(slide, M_LEFT + Inches(0.30), bar_y, Inches(0.18), Inches(0.055), fill_color=BLUE)
    add_rect(slide, M_LEFT + Inches(0.52), bar_y, Inches(0.12), Inches(0.055), fill_color=GREEN)

    # Section breadcrumb & page number
    add_textbox(slide, M_LEFT + Inches(0.76), Inches(0.24), Inches(7.2), Inches(0.28),
                text=section_tag, font_size=11.5, bold=True,
                color=MID_GRAY if dark else TEXT_SUB, heading=True)
    add_textbox(slide, SLIDE_W - M_RIGHT - Inches(1.2), Inches(0.24), Inches(1.2), Inches(0.28),
                text=f"{page_num:02d} / 14", font_size=11.5, bold=True,
                color=MID_GRAY, align=PP_ALIGN.RIGHT, heading=True)

    # Hairline rule under header strip
    add_rect(slide, M_LEFT, Inches(0.56), CONTENT_W, Inches(0.012),
             fill_color=DARK_LINE if dark else BORDER)

    # Insight Headline (26pt bold Sans per brand-guidelines + competitive-analysis)
    add_textbox(slide, M_LEFT, Inches(0.68), CONTENT_W, Inches(0.64),
                text=headline, font_size=26, bold=True,
                color=LIGHT if dark else DARK, heading=True, line_spacing=1.15)


def add_note(slide, text: str):
    slide.notes_slide.notes_text_frame.text = text


def draw_cover_art(slide):
    """Right-side Anthropic 3-accent geometric constellation on dark #141413 cover."""
    cx, cy = Inches(10.55), Inches(3.85)
    # Subtle concentric rings
    add_circle(slide, cx, cy, Inches(3.70), fill_color=DARK, line_color=DARK_LINE, line_pt=1.0)
    add_circle(slide, cx, cy, Inches(2.45), fill_color=DARK, line_color=RGBColor(0x4A, 0x48, 0x42), line_pt=1.0)

    nodes = [
        (cx - Inches(1.55), cy - Inches(0.95), Inches(0.54), ORANGE),
        (cx + Inches(1.20), cy - Inches(1.30), Inches(0.46), BLUE),
        (cx + Inches(1.65), cy + Inches(0.45), Inches(0.50), GREEN),
        (cx - Inches(0.15), cy + Inches(1.55), Inches(0.44), ORANGE),
        (cx - Inches(1.60), cy + Inches(0.75), Inches(0.38), BLUE),
        (cx + Inches(0.15), cy - Inches(0.05), Inches(0.62), LIGHT),
    ]
    # Connecting lines
    edges = [(0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]
    for i, j in edges:
        col = ORANGE if 5 in (i, j) and (i == 0 or j == 0) else (BLUE if (i == 1 or j == 1) else DARK_LINE)
        add_line(slide, nodes[i][0], nodes[i][1], nodes[j][0], nodes[j][1], color=col, width_pt=1.2)

    for nx, ny, ndia, ncol in nodes[:-1]:
        add_circle(slide, nx, ny, ndia, fill_color=ncol, line_color=DARK, line_pt=2.0)
    # Center anchor ring + dot
    add_circle(slide, nodes[5][0], nodes[5][1], Inches(0.84), fill_color=DARK, line_color=ORANGE, line_pt=1.6)
    add_circle(slide, nodes[5][0], nodes[5][1], Inches(0.42), fill_color=LIGHT)


def build_deck():
    data = load_data()
    fee_df = data["fee"].set_index("plan_id")
    nav_df = data["nav"]
    turn_df = data["turn"]
    metrics_df = data["metrics"]
    monthly_df = data["monthly"]

    b_full = metrics_df[(metrics_df["区间"].str.contains("全样本")) & (metrics_df["组合"] == "baseline")].iloc[0]
    b_val = metrics_df[(metrics_df["区间"].str.contains("验证期")) & (metrics_df["组合"] == "baseline")].iloc[0]
    h_full = metrics_df[(metrics_df["区间"].str.contains("全样本")) & (metrics_df["组合"] == "hs300")].iloc[0]
    h_val = metrics_df[(metrics_df["区间"].str.contains("验证期")) & (metrics_df["组合"] == "hs300")].iloc[0]
    r_full = metrics_df[(metrics_df["区间"].str.contains("全样本")) & (metrics_df["组合"] == "research")].iloc[0]

    oos_base = (nav_df.loc["2026-10-30", "baseline"] / nav_df.loc["2024-12-31", "baseline"] - 1.0) * 100
    oos_res = (nav_df.loc["2026-10-30", "research"] / nav_df.loc["2024-12-31", "research"] - 1.0) * 100
    oos_hs = (nav_df.loc["2026-10-30", "hs300"] / nav_df.loc["2024-12-31", "hs300"] - 1.0) * 100
    b_turn = turn_df["baseline_turnover"].mean() * 100
    r_turn = turn_df["research_turnover"].mean() * 100
    ir_base = float(fee_df.loc["Gross", "info_ratio"])
    cap_half = data["prod"]["capacity_impact"]["half_excess_capacities"]["Y_0.8"]["baseline_half_excess_aum_yi"]

    n_months = len(monthly_df)
    pos_months = int((monthly_df["baseline"] > 0).sum())
    win_rate = pos_months / n_months * 100
    worst_month = float(monthly_df["baseline"].min()) * 100

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # =========================================================================
    # P01: DARK FLAGSHIP COVER (Anthropic brand-guidelines #141413 Hero)
    # =========================================================================
    s1 = prs.slides.add_slide(blank)
    set_slide_bg(s1, DARK)
    draw_cover_art(s1)

    # Top 3-color brand ribbon
    add_rect(s1, M_LEFT, Inches(0.62), Inches(0.60), Inches(0.08), fill_color=ORANGE)
    add_rect(s1, M_LEFT + Inches(0.68), Inches(0.62), Inches(0.42), Inches(0.08), fill_color=BLUE)
    add_rect(s1, M_LEFT + Inches(1.18), Inches(0.62), Inches(0.28), Inches(0.08), fill_color=GREEN)

    add_textbox(s1, M_LEFT, Inches(0.88), Inches(7.5), Inches(0.32),
                text="QUANTITATIVE EQUITY  ·  PRODUCT & COMPETITIVE ROADSHOW",
                font_size=11.5, bold=True, color=MID_GRAY, heading=True)

    add_textbox(s1, M_LEFT, Inches(1.52), Inches(8.1), Inches(1.85),
                text="沪深300 价值精选\n量化策略与产品化方案",
                font_size=44, bold=True, color=LIGHT, heading=True, line_spacing=1.18)

    add_textbox(s1, M_LEFT, Inches(3.78), Inches(7.8), Inches(0.65),
                text="低换手价值主线、高频交易摩擦实证与机构产品化全链路评估",
                font_size=17, color=MID_GRAY, heading=False, line_spacing=1.30)

    # 3-Accent Hero Pills
    add_pill(s1, M_LEFT, Inches(5.05), Inches(2.55), Inches(0.46),
             "计成本年化 +10.78%", fill_color=ORANGE, text_color=LIGHT, font_size=13.5)
    add_pill(s1, M_LEFT + Inches(2.75), Inches(5.05), Inches(2.45), Inches(0.46),
             "理论半衰容量 80.9 亿", fill_color=DARK_CARD, text_color=BLUE,
             font_size=13.5, line_color=BLUE)
    add_pill(s1, M_LEFT + Inches(5.40), Inches(5.05), Inches(2.45), Inches(0.46),
             "雪球实盘 ZH3689205", fill_color=DARK_CARD, text_color=GREEN,
             font_size=13.5, line_color=GREEN)

    # Bottom hairline & team placeholder
    add_rect(s1, M_LEFT, Inches(6.28), Inches(8.2), Inches(0.012), fill_color=DARK_LINE)
    add_textbox(s1, M_LEFT, Inches(6.46), Inches(8.2), Inches(0.40),
                text="量化投资课程期末大作业   ｜   汇报团队：【待填：四位组员姓名】   ｜   2026 年 11 月",
                font_size=13, color=MID_GRAY, heading=False)
    add_note(s1, "封面开场：介绍策略定位、核心业绩与雪球实盘组合 ZH3689205。")

    # =========================================================================
    # P02: 团队介绍与四段流水线（3-Accent Cycle: Orange -> Blue -> Green -> Dark）
    # =========================================================================
    s2 = prs.slides.add_slide(blank)
    add_brand_chrome(s2, "01 团队介绍  /  全链路协同", "四段式只读流水线：从真时点数据到实盘产品化闭环", 2)

    roles = [
        ("01", "组员 1 · 数据治理", "动态成分池与防前视底座",
         "按月构建 520 只沪深300历史成分池，45 天行业与 90 天估值时效约束，全链路无幸存者偏差。",
         "交付：921日清洗面板", ORANGE, ORANGE_TINT, ORANGE_DEEP),
        ("02", "组员 2 · 因子信号", "价值主线锁定与理论创新",
         "确立 BP+EP+Small 等权主线；发现 Alpha012 价格尺度偏差，提出无量纲改进因子 new012。",
         "交付：120组换手诊断", BLUE, BLUE_TINT, BLUE_DEEP),
        ("03", "组员 3 · 回测归因", "账户级开盘撮合与归因",
         "用开盘价跳空判定一字板，计入万3佣金+千1税+千1滑点；完成 Fama-MacBeth 收益分解。",
         "交付：185期撮合账本", GREEN, GREEN_TINT, GREEN_DEEP),
        ("04", "组员 4 · 产品落地", "容量费率测算与实盘汇报",
         "完成三口径容量评估、四档费率高水位核算、雪球实盘 ZH3689205 建仓及报告路演整合。",
         "交付：30页报告+实盘", DARK, LIGHT_GRAY, DARK),
    ]
    gap = Inches(0.24)
    cw2 = (CONTENT_W - gap * 3) / 4
    for i, (num, rtitle, rsub, rdesc, rdeliv, acc, tint, txt_acc) in enumerate(roles):
        x = M_LEFT + i * (cw2 + gap)
        y = Inches(1.58)
        h = Inches(4.55)
        add_round_rect(s2, x, y, cw2, h, fill_color=LIGHT_CARD, line_color=BORDER, line_pt=0.75, radius=0.03)
        # Brand top accent bar
        add_rect(s2, x, y, cw2, Inches(0.08), fill_color=acc)
        add_textbox(s2, x + Inches(0.22), y + Inches(0.24), cw2 - Inches(0.44), Inches(0.42),
                    text=num, font_size=26, bold=True, color=acc, heading=True)
        add_textbox(s2, x + Inches(0.22), y + Inches(0.74), cw2 - Inches(0.44), Inches(0.38),
                    text=rtitle, font_size=17, bold=True, color=DARK, heading=True)
        add_textbox(s2, x + Inches(0.22), y + Inches(1.14), cw2 - Inches(0.44), Inches(0.36),
                    text=rsub, font_size=14, bold=True, color=txt_acc, heading=True)
        add_rect(s2, x + Inches(0.22), y + Inches(1.58), cw2 - Inches(0.44), Inches(0.01), fill_color=BORDER)
        add_textbox(s2, x + Inches(0.22), y + Inches(1.74), cw2 - Inches(0.44), Inches(1.85),
                    text=rdesc, font_size=14, color=TEXT_SUB, line_spacing=1.35)
        add_pill(s2, x + Inches(0.22), y + h - Inches(0.62), cw2 - Inches(0.44), Inches(0.40),
                 rdeliv, fill_color=tint, text_color=txt_acc, font_size=12.5)

    # Bottom governance ribbon
    add_round_rect(s2, M_LEFT, Inches(6.34), CONTENT_W, Inches(0.62), fill_color=LIGHT_GRAY, radius=0.08)
    add_textbox(s2, M_LEFT + Inches(0.28), Inches(6.46), CONTENT_W - Inches(0.56), Inches(0.38),
                text="跨组工程纪律：上游目录严格只读交接  ·  下游 185 期换手率双向对账误差 ≤ 0.015%  ·  不回避负结果、不事后改参美化",
                font_size=14, bold=True, color=DARK, align=PP_ALIGN.CENTER, heading=True)
    add_note(s2, "展示四人工程化分工与只读交接机制。")

    # =========================================================================
    # P03: 策略核心思想 + 行业核心指标（competitive-analysis Step 0）
    # =========================================================================
    s3 = prs.slides.add_slide(blank)
    add_brand_chrome(s3, "02 策略介绍  /  核心思想与标尺", "以低换手大盘价值为锚，瞄准稳健超额与成本效率", 3)

    # Left: Dual-Track Strategy Philosophy
    lw3 = Inches(5.65)
    add_round_rect(s3, M_LEFT, Inches(1.56), lw3, Inches(2.52), fill_color=LIGHT_CARD, line_color=ORANGE, line_pt=1.0, radius=0.03)
    add_pill(s3, M_LEFT + Inches(0.24), Inches(1.78), Inches(2.05), Inches(0.34),
             "正式交付 · Baseline", fill_color=ORANGE, text_color=LIGHT, font_size=12)
    add_textbox(s3, M_LEFT + Inches(0.24), Inches(2.22), lw3 - Inches(0.48), Inches(0.38),
                text="沪深300 价值与规模平衡三因子等权", font_size=18, bold=True, color=DARK, heading=True)
    add_textbox(s3, M_LEFT + Inches(0.24), Inches(2.68), lw3 - Inches(0.48), Inches(1.25),
                text="BP、EP 与小市值代理三因子等权打分，每 5 交易日等权持有前 50 只（单票 2%）。刻意保留价值行业配置，严守低换手与大盘高流动性。",
                font_size=14.5, color=TEXT_SUB, line_spacing=1.34)

    add_round_rect(s3, M_LEFT, Inches(4.32), lw3, Inches(2.52), fill_color=LIGHT_GRAY, line_color=BORDER, line_pt=0.75, radius=0.03)
    add_pill(s3, M_LEFT + Inches(0.24), Inches(4.54), Inches(2.15), Inches(0.34),
             "科学对照 · Research", fill_color=MID_GRAY, text_color=LIGHT, font_size=12)
    add_textbox(s3, M_LEFT + Inches(0.24), Inches(4.98), lw3 - Inches(0.48), Inches(0.38),
                text="混入 50% 短周期量价信号 · 不交付", font_size=18, bold=True, color=DARK, heading=True)
    add_textbox(s3, M_LEFT + Inches(0.24), Inches(5.44), lw3 - Inches(0.48), Inches(1.25),
                text="在原模型基础上将 50% 权重替换为 Alpha006 与 Alpha033，用于真实检验短周期因子在周度调仓下的换手冲击，保留作为负面反例。",
                font_size=14.5, color=TEXT_SUB, line_spacing=1.34)

    # Right: Industry-Defining Metrics (Step 0)
    rx3 = M_LEFT + lw3 + Inches(0.38)
    rw3 = CONTENT_W - lw3 - Inches(0.38)
    add_textbox(s3, rx3, Inches(1.56), rw3, Inches(0.38),
                text="量化权益产品评估的 5 大行业核心标尺", font_size=18, bold=True, color=DARK, heading=True)

    metrics_rows = [
        ["净年化收益率", "衡量扣费后长期复利能力", "10.78%"],
        ["夏普与信息比率", "检验单位风险与超额质量", "0.67 / 0.82"],
        ["最大回撤与修复", "决定持有人真实拿得住", "-16.7% · 5月"],
        ["单边平均换手率", "直指实盘交易摩擦与冲击", "5.9%"],
        ["流动性承载容量", "决定机构可配置资金上限", "数亿硬约束"],
    ]
    add_styled_table(
        s3, rx3, Inches(2.06), rw3, Inches(4.78),
        headers=["行业标尺", "投资人核心关注", "Baseline"],
        rows=metrics_rows,
        col_widths=[1.95, 2.40, 1.65],
        alignments=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.RIGHT],
        font_size=14.0,
    )
    add_note(s3, "阐明核心策略思想，并定义机构评审量化权益产品的 5 大核心标尺。")

    # =========================================================================
    # P04: 因子体系与理论创新（3-Accent Cards + new012 Chart）
    # =========================================================================
    s4 = prs.slides.add_slide(blank)
    add_brand_chrome(s4, "02 策略介绍  /  因子与创新", "经典价值提供压舱石，比例化改进 new012 三期全面胜出", 4)

    lw4 = Inches(5.25)
    pillars = [
        ("BP 账面市值比", "低估值安全边际", "捕捉净资产折价蓝筹，熊市与震荡市提供核心防御垫，日均正向归因贡献最高。", ORANGE),
        ("EP 盈利收益率", "当期盈利真实支撑", "严格过滤亏损与伪低估陷阱，确保低市净率背后具备现金流与盈利兑现能力。", BLUE),
        ("Small 规模平衡", "防止超大盘过度扎堆", "在沪深300大盘池内部做温和均衡，不向高波动微盘股下沉，维持优异流动性。", GREEN),
    ]
    for i, (ptitle, psub, pdesc, acc) in enumerate(pillars):
        y = Inches(1.56) + i * Inches(1.78)
        add_round_rect(s4, M_LEFT, y, lw4, Inches(1.58), fill_color=LIGHT_CARD, line_color=BORDER, line_pt=0.75, radius=0.03)
        add_rect(s4, M_LEFT, y, Inches(0.09), Inches(1.58), fill_color=acc)
        add_textbox(s4, M_LEFT + Inches(0.26), y + Inches(0.16), lw4 - Inches(0.44), Inches(0.36),
                    text=f"{ptitle}  ·  {psub}", font_size=16, bold=True, color=DARK, heading=True)
        add_textbox(s4, M_LEFT + Inches(0.26), y + Inches(0.58), lw4 - Inches(0.44), Inches(0.88),
                    text=pdesc, font_size=14, color=TEXT_SUB, line_spacing=1.30)

    # Right: new012 chart + key callout
    rx4 = M_LEFT + lw4 + Inches(0.38)
    rw4 = CONTENT_W - lw4 - Inches(0.38)
    add_picture_fit(s4, FIG_DIR / "08_new012_vs_alpha012_ic.png", rx4, Inches(1.52), rw4, Inches(4.32))
    add_round_rect(s4, rx4, Inches(5.96), rw4, Inches(0.92), fill_color=BLUE_TINT, line_color=BLUE, line_pt=0.8, radius=0.04)
    add_rich_lines(s4, rx4 + Inches(0.22), Inches(6.08), rw4 - Inches(0.44), Inches(0.72), [
        {"lead": "原创理论改进（v3.0 储备）：", "lead_color": BLUE_DEEP, "size": 14,
         "text": "用日收益率替代绝对价差消除尺度偏差，样本外 5 日 IC 达 0.0156；严守纪律未事后改写主模型。", "space_after": 0},
    ], default_color=DARK, line_spacing=1.25)
    add_note(s4, "介绍三因子分工与无量纲比例化改进因子 new012_return 的三期 IC 提升。")

    # =========================================================================
    # P05: 2x2 竞争定位矩阵（competitive-analysis Step 5 招牌页！）
    # =========================================================================
    s5 = prs.slides.add_slide(blank)
    add_brand_chrome(s5, "02 策略介绍  /  竞争定位", "在沪深300赛道中，Baseline 占据低换手与高夏普稀缺象限", 5)

    gw5 = Inches(7.35)
    add_picture_fit(s5, FIG_DIR / "02_positioning_2x2.png", M_LEFT, Inches(1.52), gw5, Inches(5.32))

    rx5 = M_LEFT + gw5 + Inches(0.35)
    rw5 = CONTENT_W - gw5 - Inches(0.35)
    pos_cards = [
        ("黄金象限 · Baseline", ORANGE, ORANGE_TINT, ORANGE_DEEP,
         "以 5.9% 极低单边换手拿到 0.67 夏普与 +10.78% 净年化，在收益与摩擦间取得罕见平衡。"),
        ("被动基准 · 沪深300", BLUE, BLUE_TINT, BLUE_DEEP,
         "换手趋近于零但缺乏选股阿尔法，过去 3.8 年原地踏步（+0.12%），回撤深达 -24.8%。"),
        ("损耗反例 · Research", GREEN, GREEN_TINT, GREEN_DEEP,
         "5 日调仓陷入 51.2% 高换手泥潭；诊断证实拉长至 20 日可沿绿线显著修复。"),
    ]
    for i, (ctitle, acc, tint, txt_acc, cdesc) in enumerate(pos_cards):
        y = Inches(1.56) + i * Inches(1.80)
        add_round_rect(s5, rx5, y, rw5, Inches(1.60), fill_color=LIGHT_CARD, line_color=BORDER, line_pt=0.75, radius=0.03)
        add_pill(s5, rx5 + Inches(0.20), y + Inches(0.18), Inches(2.20), Inches(0.32),
                 ctitle, fill_color=tint, text_color=txt_acc, font_size=12.5)
        add_textbox(s5, rx5 + Inches(0.20), y + Inches(0.58), rw5 - Inches(0.40), Inches(0.92),
                    text=cdesc, font_size=14, color=TEXT_SUB, line_spacing=1.30)
    add_note(s5, "使用 competitive-analysis 2x2 定位矩阵直观展示 Baseline 的稀缺竞争位置。")

    # =========================================================================
    # P06: 同业横向量化对比表（competitive-analysis Step 7: ●●● + Actuals！）
    # =========================================================================
    s6 = prs.slides.add_slide(blank)
    add_brand_chrome(s6, "02 策略介绍  /  横向对比", "实盘约束横向对比：Baseline 在收益、回撤与换手全面占优", 6)

    comp_rows = [
        ["全样本累计收益", f"●●● +{b_full['累计收益']*100:.2f}%", f"●○○ {r_full['累计收益']*100:.2f}%", f"●●○ +{h_full['累计收益']*100:.2f}%"],
        ["计成本年化收益", f"●●● {b_full['年化收益']*100:.2f}%", f"●○○ {r_full['年化收益']*100:.2f}%", f"●●○ {h_full['年化收益']*100:.2f}%"],
        ["样本外无缝累计", f"●●● +{oos_base:.2f}%", f"●○○ {oos_res:.2f}%", f"●●○ +{oos_hs:.2f}%"],
        ["全样本夏普比率", f"●●● {b_full['夏普']:.2f}", f"●○○ {r_full['夏普']:.2f}", f"●●○ {h_full['夏普']:.2f}"],
        ["全样本最大回撤", f"●●● {b_full['最大回撤']*100:.2f}%", f"●○○ {r_full['最大回撤']*100:.2f}%", f"●○○ {h_full['最大回撤']*100:.2f}%"],
        ["单边平均换手率", f"●●● {b_turn:.1f}%", f"●○○ {r_turn:.1f}%", "●●● 被动指数"],
        ["5% 参与率 3日容量", "●●● 7.8–16.1 亿", "●○○ 3.9–7.1 亿", "●●● 指数级"],
    ]
    add_styled_table(
        s6, M_LEFT, Inches(1.54), CONTENT_W, Inches(4.55),
        headers=["核心评估维度", "Baseline · 正式交付", "Research · 量价对照", "沪深300 · 市场基准"],
        rows=comp_rows,
        col_widths=[2.7, 3.1, 3.0, 3.0],
        alignments=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.LEFT],
        font_size=14.0,
    )

    # Bottom 3 Engineering Moat Pills
    add_round_rect(s6, M_LEFT, Inches(6.28), CONTENT_W, Inches(0.64), fill_color=LIGHT_GRAY, radius=0.08)
    add_textbox(s6, M_LEFT + Inches(0.24), Inches(6.42), CONTENT_W - Inches(0.48), Inches(0.38),
                text="评级口径：●●● 显著领先  ｜  ●●○ 行业中性  ｜  ●○○ 明显承压  ·  全样本 921 交易日，样本外无缝衔接",
                font_size=14, bold=True, color=DARK, align=PP_ALIGN.CENTER, heading=True)
    add_note(s6, "采用 competitive-analysis 标准的评级+实值矩阵，横向对标主策略、对照组与沪深300基准。")

    # =========================================================================
    # P07: 深度思考——成本侵蚀瀑布图
    # =========================================================================
    s7 = prs.slides.add_slide(blank)
    add_brand_chrome(s7, "02 策略介绍  /  深度思考", "高频量价并非无效，而是与 5 日周度调仓发生频率错配", 7)

    gw7 = Inches(6.75)
    add_picture_fit(s7, FIG_DIR / "04_cost_erosion_waterfall.png", M_LEFT, Inches(1.56), gw7, Inches(5.25))

    rx7 = M_LEFT + gw7 + Inches(0.38)
    rw7 = CONTENT_W - gw7 - Inches(0.38)
    lessons = [
        ("01", "交易成本吞噬 37.2 pct", ORANGE,
         "Research 单边换手高达 51.2%，达 Baseline 的 8.7 倍，双边摩擦将 1.307 理想净值拖垮至 0.935。"),
        ("02", "价值核心暴露被稀释 1/4", BLUE,
         "Fama-MacBeth 归因证实 BP/EP 暴露降至 1.12/1.10，且叠加负特异选股残差（-0.83 bp/日）。"),
        ("03", "20 日降频即可显著修复", GREEN,
         "120 组网格证实调仓拉长至 20 日后，样本外 10bp 净年化回升至 10.4%，留待前瞻盲测。"),
    ]
    for i, (num, ltitle, acc, ldesc) in enumerate(lessons):
        y = Inches(1.58) + i * Inches(1.78)
        add_round_rect(s7, rx7, y, rw7, Inches(1.58), fill_color=LIGHT_CARD, line_color=BORDER, line_pt=0.75, radius=0.03)
        add_rect(s7, rx7, y, Inches(0.08), Inches(1.58), fill_color=acc)
        add_textbox(s7, rx7 + Inches(0.24), y + Inches(0.16), Inches(0.55), Inches(0.38),
                    text=num, font_size=20, bold=True, color=acc, heading=True)
        add_textbox(s7, rx7 + Inches(0.80), y + Inches(0.18), rw7 - Inches(1.00), Inches(0.36),
                    text=ltitle, font_size=16.5, bold=True, color=DARK, heading=True)
        add_textbox(s7, rx7 + Inches(0.24), y + Inches(0.62), rw7 - Inches(0.44), Inches(0.86),
                    text=ldesc, font_size=14, color=TEXT_SUB, line_spacing=1.28)
    add_note(s7, "用瀑布图定量拆解 Research 亏损原因：换手损耗 + 价值稀释，并给出 20 日降频修复的网格证据。")

    # =========================================================================
    # P08: 产品业绩概览（Step 3 Target Profile + 4-KPI Strip）
    # =========================================================================
    s8 = prs.slides.add_slide(blank)
    add_brand_chrome(s8, "03 产品介绍  /  核心业绩", "计成本年化 10.78% 穿越震荡，样本外领先指数超 12 pct", 8)

    kpis = [
        ("计成本年化收益", f"{b_full['年化收益']*100:.2f}%", f"同期沪深300 仅 {h_full['年化收益']*100:.2f}%", ORANGE),
        ("全样本累计收益", f"+{b_full['累计收益']*100:.2f}%", f"净值 {nav_df['baseline'].iloc[-1]:.3f} ｜ 指数 +0.12%", BLUE),
        ("全样本夏普 / IR", f"{b_full['夏普']:.2f} / {ir_base:.2f}", f"验证期夏普 {b_val['夏普']:.2f}", GREEN),
        ("全样本最大回撤", f"{b_full['最大回撤']*100:.1f}%", "较沪深300 浅 8.1 pct", DARK),
    ]
    kgap = Inches(0.22)
    kw8 = (CONTENT_W - kgap * 3) / 4
    for i, (ktitle, kval, ksub, acc) in enumerate(kpis):
        x = M_LEFT + i * (kw8 + kgap)
        y = Inches(1.56)
        add_round_rect(s8, x, y, kw8, Inches(1.88), fill_color=LIGHT_CARD, line_color=BORDER, line_pt=0.75, radius=0.04)
        add_rect(s8, x, y, kw8, Inches(0.08), fill_color=acc)
        add_textbox(s8, x + Inches(0.20), y + Inches(0.22), kw8 - Inches(0.40), Inches(0.30),
                    text=ktitle, font_size=13.5, bold=True, color=TEXT_SUB, heading=True)
        add_textbox(s8, x + Inches(0.20), y + Inches(0.58), kw8 - Inches(0.40), Inches(0.72),
                    text=kval, font_size=31, bold=True, color=acc, heading=True, word_wrap=False)
        add_textbox(s8, x + Inches(0.20), y + Inches(1.38), kw8 - Inches(0.40), Inches(0.34),
                    text=ksub, font_size=13.5, color=TEXT_SUB, word_wrap=False)

    # Bottom two structured tables (Target Profile)
    hw8 = (CONTENT_W - Inches(0.34)) / 2
    add_textbox(s8, M_LEFT, Inches(3.72), hw8, Inches(0.34),
                text="分阶段业绩一致性（无缝衔接）", font_size=17, bold=True, color=DARK, heading=True)
    add_styled_table(
        s8, M_LEFT, Inches(4.12), hw8, Inches(2.74),
        headers=["回测阶段", "Baseline", "沪深300", "超额"],
        rows=[
            ["全样本 3.8年 (921日)", f"+{b_full['累计收益']*100:.2f}%", f"+{h_full['累计收益']*100:.2f}%", "+45.26 pct"],
            ["验证期 2023–2024", f"+{b_val['累计收益']*100:.2f}%", f"{h_val['累计收益']*100:.2f}%", "+30.20 pct"],
            ["样本外 2025–2026.10", f"+{oos_base:.2f}%", f"+{oos_hs:.2f}%", f"+{oos_base - oos_hs:.2f} pct"],
        ],
        col_widths=[2.35, 1.25, 1.15, 1.25],
        alignments=[PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT],
        highlight_row=2,
        highlight_fill=ORANGE_TINT,
        font_size=14.0,
    )

    rx8 = M_LEFT + hw8 + Inches(0.34)
    add_textbox(s8, rx8, Inches(3.72), hw8, Inches(0.34),
                text="实盘约束与保守假设参数", font_size=17, bold=True, color=DARK, heading=True)
    add_styled_table(
        s8, rx8, Inches(4.12), hw8, Inches(2.74),
        headers=["执行要素", "设定标准"],
        rows=[
            ["交易成本", "双边万3佣金 + 千1卖出印花税 + 双边千1滑点"],
            ["撮合规则", "T日收盘信号、T+1开盘执行，现金零计息不透支"],
            ["防前视校验", "开盘跳空判定一字板，出池/ST允许非跌停退出"],
        ],
        col_widths=[1.55, 4.45],
        alignments=[PP_ALIGN.LEFT, PP_ALIGN.LEFT],
        font_size=14.0,
    )
    add_note(s8, "目标策略档案页：4 大 KPI + 分阶段一致性 + 保守实盘参数。")

    # =========================================================================
    # P09: 净值走势与水下回撤双图并览
    # =========================================================================
    s9 = prs.slides.add_slide(blank)
    add_brand_chrome(s9, "03 产品介绍  /  净值与回撤", "净值稳步攀升至 1.454，最大回撤 -16.7% 仅 5 个月收复", 9)

    half_w9 = (CONTENT_W - Inches(0.32)) / 2
    add_textbox(s9, M_LEFT, Inches(1.48), half_w9, Inches(0.32),
                text="累计单位净值曲线（计交易成本）", font_size=16, bold=True, color=DARK, heading=True)
    add_picture_fit(s9, FIG_DIR / "01_nav_curve.png", M_LEFT, Inches(1.82), half_w9, Inches(4.20))

    rx9 = M_LEFT + half_w9 + Inches(0.32)
    add_textbox(s9, rx9, Inches(1.48), half_w9, Inches(0.32),
                text="动态水下回撤对比", font_size=16, bold=True, color=DARK, heading=True)
    add_picture_fit(s9, FIG_DIR / "03_drawdown_underwater.png", rx9, Inches(1.82), half_w9, Inches(4.20))

    # Bottom 3-metric synthesis bar
    add_round_rect(s9, M_LEFT, Inches(6.22), CONTENT_W, Inches(0.66), fill_color=LIGHT_GRAY, radius=0.08)
    add_textbox(s9, M_LEFT + Inches(0.24), Inches(6.36), CONTENT_W - Inches(0.48), Inches(0.38),
                text=f"持有体验优势：月度胜率 {win_rate:.1f}% · {pos_months}/{n_months} 月正收益，最差单月 {worst_month:.1f}% 优于基准，历史谷底 0.9396 远高于止损线",
                font_size=14, bold=True, color=DARK, align=PP_ALIGN.CENTER, heading=True)
    add_note(s9, "双图并列对比净值剪刀差与回撤修复速度，突出持有人真实体验。")

    # =========================================================================
    # P10: 资金容量三口径评估
    # =========================================================================
    s10 = prs.slides.add_slide(blank)
    add_brand_chrome(s10, "03 产品介绍  /  资金容量", "大盘蓝筹底座稳承数亿硬约束，理论半衰容量达 80.9 亿", 10)

    gw10 = Inches(7.10)
    add_picture_fit(s10, FIG_DIR / "11_capacity_curve.png", M_LEFT, Inches(1.52), gw10, Inches(5.35))

    rx10 = M_LEFT + gw10 + Inches(0.35)
    rw10 = CONTENT_W - gw10 - Inches(0.35)
    cap_cards = [
        ("大盘流动性底座", GREEN, GREEN_TINT, GREEN_DEEP,
         "全 185 期持仓股 ADV20 中位数 4.49 亿元，最新一期升至 5.05 亿元（P10 达 2.06 亿）。"),
        ("5% 参与率硬约束", BLUE, BLUE_TINT, BLUE_DEEP,
         "1 日调仓可承 2.58–5.36 亿，3 日拆单线性扩至 7.75–16.09 亿；5 日清仓 5.67–11.28 亿。"),
        ("10 亿情景与理论上限", ORANGE, ORANGE_TINT, ORANGE_DEEP,
         f"10 亿假设情景下冲击拖累约 1.9%，净年化仍达 8.86%（42/185 期需延窗）；理论半衰容量 {cap_half:.1f} 亿。"),
    ]
    for i, (ctitle, acc, tint, txt_acc, cdesc) in enumerate(cap_cards):
        y = Inches(1.56) + i * Inches(1.80)
        add_round_rect(s10, rx10, y, rw10, Inches(1.60), fill_color=LIGHT_CARD, line_color=BORDER, line_pt=0.75, radius=0.03)
        add_pill(s10, rx10 + Inches(0.20), y + Inches(0.16), Inches(2.25), Inches(0.32),
                 ctitle, fill_color=tint, text_color=txt_acc, font_size=12.5)
        add_textbox(s10, rx10 + Inches(0.20), y + Inches(0.56), rw10 - Inches(0.40), Inches(0.94),
                    text=cdesc, font_size=14, color=TEXT_SUB, line_spacing=1.30)
    add_note(s10, "三口径诚实披露容量边界：流动性硬约束、10亿假设情景与80.9亿理论半衰容量。")

    # =========================================================================
    # P11: 产品要素与四档费率净值测算
    # =========================================================================
    s11 = prs.slides.add_slide(blank)
    add_brand_chrome(s11, "03 产品介绍  /  产品与费率", "主推 C 档机构超额份额，扣费后净年化 8.48%、IR 达 0.68", 11)

    gw11 = Inches(6.05)
    add_picture_fit(s11, FIG_DIR / "12_fee_net_nav.png", M_LEFT, Inches(1.54), gw11, Inches(4.52))
    # Compact product element strip under chart
    add_round_rect(s11, M_LEFT, Inches(6.22), gw11, Inches(0.66), fill_color=LIGHT_GRAY, radius=0.08)
    add_textbox(s11, M_LEFT + Inches(0.16), Inches(6.36), gw11 - Inches(0.32), Inches(0.38),
                text="私募基金 / 机构专户  ·  R3 中风险  ·  100 万起投  ·  月度开放",
                font_size=13.5, bold=True, color=DARK, align=PP_ALIGN.CENTER, heading=True)

    rx11 = M_LEFT + gw11 + Inches(0.32)
    rw11 = CONTENT_W - gw11 - Inches(0.32)
    add_textbox(s11, rx11, Inches(1.54), rw11, Inches(0.36),
                text="四档费率逐日高水位净值对比", font_size=17, bold=True, color=DARK, heading=True)

    fee_rows = [
        ["A 标准", "1.0%+0.2%", "绝对 20%", f"{fee_df.loc['A', 'ann_return']*100:.2f}%", f"{fee_df.loc['A', 'info_ratio']:.2f}"],
        ["B 超额", "1.0%+0.2%", "超额 20%", f"{fee_df.loc['B', 'ann_return']*100:.2f}%", f"{fee_df.loc['B', 'info_ratio']:.2f}"],
        ["C 机构 ★", "0.6%+0.15%", "超额 15%", f"{fee_df.loc['C', 'ann_return']*100:.2f}%", f"{fee_df.loc['C', 'info_ratio']:.2f}"],
        ["D 纯管理", "1.5%+0.2%", "无提成", f"{fee_df.loc['D', 'ann_return']*100:.2f}%", f"{fee_df.loc['D', 'info_ratio']:.2f}"],
    ]
    add_styled_table(
        s11, rx11, Inches(1.98), rw11, Inches(3.20),
        headers=["方案", "固定费", "业绩报酬", "净年化", "IR"],
        rows=fee_rows,
        col_widths=[1.12, 1.50, 1.08, 0.92, 0.63],
        alignments=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT],
        highlight_row=2,
        highlight_fill=BLUE_TINT,
        font_size=14.0,
    )

    add_round_rect(s11, rx11, Inches(5.38), rw11, Inches(1.56), fill_color=LIGHT_CARD, line_color=BLUE, line_pt=1.0, radius=0.04)
    add_rich_lines(s11, rx11 + Inches(0.22), Inches(5.52), rw11 - Inches(0.44), Inches(1.30), [
        {"lead": "为何主推 C 档机构超额份额？\n", "lead_color": BLUE_DEEP, "size": 15,
         "text": "仅对跑赢沪深300的真 Alpha 计提 15%，拒绝分享市场 Beta；总费率拖累压缩至 2.30%/年，兼顾机构持有人到手收益与管理人长期激励对齐。", "space_after": 0},
    ], default_size=14, default_color=TEXT_SUB, line_spacing=1.28)
    add_note(s11, "展示四档费率净值曲线与对比表，阐明主推 C 档机构超额份额的商业逻辑。")

    # =========================================================================
    # P12: 情景推演与量化风控信号（competitive-analysis Step 9 Bull/Base/Bear！）
    # =========================================================================
    s12 = prs.slides.add_slide(blank)
    add_brand_chrome(s12, "03 产品介绍  /  情景与风控", "三层风控叠加情景预案，用量化阈值守住净值底线", 12)

    add_textbox(s12, M_LEFT, Inches(1.48), CONTENT_W, Inches(0.36),
                text="未来市场风格情景推演（Bull / Base / Bear）", font_size=17.5, bold=True, color=DARK, heading=True)

    scen_rows = [
        ["乐观情景 Bull", "30%", "年化 12%–16%", "宏观企稳与高股息重估共振，低估值银行基建戴维斯双击，超额扩大"],
        ["基准情景 Base", "50%", "年化 8%–11%", "指数宽幅震荡、风格均衡轮动，低换手价值稳步复利兑现历史超额中枢"],
        ["压力情景 Bear", "20%", "阶段回撤 12%–18%", "成长主题极致抱团压制价值风格，或金融板块基本面承压引发相对跑输"],
    ]
    add_styled_table(
        s12, M_LEFT, Inches(1.90), CONTENT_W, Inches(2.58),
        headers=["情景假设", "主观概率", "预期策略表现", "核心驱动与风格环境"],
        rows=scen_rows,
        col_widths=[1.85, 1.25, 2.15, 6.58],
        alignments=[PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.LEFT, PP_ALIGN.LEFT],
        highlight_row=1,
        highlight_fill=BLUE_TINT,
        font_size=14.0,
    )

    # Bottom 3 Quantified Signpost & Risk Defense Cards
    add_textbox(s12, M_LEFT, Inches(4.70), CONTENT_W, Inches(0.36),
                text="三层量化预警与止损信号（Quantified Signposts）", font_size=17.5, bold=True, color=DARK, heading=True)

    sgap = Inches(0.24)
    sw12 = (CONTENT_W - sgap * 2) / 3
    signposts = [
        ("绝对净值双线", "0.85 预警 / 0.80 止损", ORANGE, ORANGE_TINT, ORANGE_DEEP,
         "回测历史最低净值 0.9396；触及 0.85 降仓至 50%，触及 0.80 触发硬止损保护本金。"),
        ("高水位回撤线", "-18% 预警 / -22% 强控", GREEN, GREEN_TINT, GREEN_DEEP,
         "历史最大回撤仅 -16.7%；双轨阈值避开正常价值波动，严防底部误强平。"),
        ("集中度与换手监控", "金融 > 75% 或换手 > 15%", BLUE, BLUE_TINT, BLUE_DEEP,
         "单票严格 2% 上限；实时跟踪行业权重漂移与异常换手，必要时触发组合风险复核。"),
    ]
    for i, (stitle, strigger, acc, tint, txt_acc, sdesc) in enumerate(signposts):
        x = M_LEFT + i * (sw12 + sgap)
        y = Inches(5.12)
        add_round_rect(s12, x, y, sw12, Inches(1.86), fill_color=LIGHT_CARD, line_color=BORDER, line_pt=0.75, radius=0.04)
        add_rect(s12, x, y, sw12, Inches(0.07), fill_color=acc)
        add_textbox(s12, x + Inches(0.20), y + Inches(0.18), sw12 - Inches(0.40), Inches(0.32),
                    text=stitle, font_size=15.5, bold=True, color=DARK, heading=True)
        add_pill(s12, x + Inches(0.20), y + Inches(0.54), sw12 - Inches(0.40), Inches(0.34),
                 strigger, fill_color=tint, text_color=txt_acc, font_size=12.5)
        add_textbox(s12, x + Inches(0.20), y + Inches(0.96), sw12 - Inches(0.40), Inches(0.82),
                    text=sdesc, font_size=13.5, color=TEXT_SUB, line_spacing=1.24)
    add_note(s12, "采用 competitive-analysis Step 9 情景推演与量化风控阈值，展示严谨的风控预案。")

    # =========================================================================
    # P13: 雪球公开模拟盘实盘落地（ZH3689205）
    # =========================================================================
    s13 = prs.slides.add_slide(blank)
    add_brand_chrome(s13, "03 产品介绍  /  实盘跟踪", "雪球公开组合 ZH3689205 已上线运行，30 只满仓映射蓝筹价值", 13)

    gw13 = Inches(6.45)
    add_picture_fit(s13, FIG_DIR / "13_latest_industry_dist.png", M_LEFT, Inches(1.54), gw13, Inches(5.32))

    rx13 = M_LEFT + gw13 + Inches(0.38)
    rw13 = CONTENT_W - gw13 - Inches(0.38)

    # Top live badge card
    add_round_rect(s13, rx13, Inches(1.56), rw13, Inches(1.42), fill_color=DARK, radius=0.04)
    add_pill(s13, rx13 + Inches(0.24), Inches(1.74), Inches(1.75), Inches(0.32),
             "LIVE TRACKING", fill_color=ORANGE, text_color=LIGHT, font_size=11.5)
    add_textbox(s13, rx13 + Inches(0.24), Inches(2.14), rw13 - Inches(0.48), Inches(0.44),
                text="雪球组合代码：ZH3689205", font_size=21, bold=True, color=LIGHT, heading=True)
    add_textbox(s13, rx13 + Inches(0.24), Inches(2.58), rw13 - Inches(0.48), Inches(0.30),
                text="xueqiu.com/P/ZH3689205  ·  2026-11-18 建仓", font_size=13, color=MID_GRAY, heading=True)

    # Structured spec table
    add_styled_table(
        s13, rx13, Inches(3.20), rw13, Inches(3.66),
        headers=["实盘跟踪维度", "落地口径与最新状态"],
        rows=[
            ["信号基准日", "2026-10-30（50只完整策略同源排序）"],
            ["平台上限适配", "雪球上限30只整数权重：前10只4%+后20只3%"],
            ["主仓板块结构", "银行 32%、非银金融 28%、建筑装饰 14%"],
            ["近8期实测换手", "周度均值 7.50%，每期仅微调 1–5 只股票"],
            ["运行审计纪律", "每5交易日收盘出信号，次日开盘公开调仓"],
        ],
        col_widths=[1.75, 3.25],
        alignments=[PP_ALIGN.LEFT, PP_ALIGN.LEFT],
        font_size=14.0,
    )
    add_note(s13, "展示雪球实盘 ZH3689205 的落地细节、30只整数权重适配与近8期低换手审计。")

    # =========================================================================
    # P14: 护城河评估、坦诚局限与致谢（Dark #141413 Flagship Closing!）
    # =========================================================================
    s14 = prs.slides.add_slide(blank)
    add_brand_chrome(s14, "04 总结与致谢  /  护城河与展望", "四维护城河铸就稳健底色，坦诚面对局限并开启 v3.0 演进", 14, dark=True)

    # Left: Moat Assessment Table (competitive-analysis Step 9!)
    lw14 = Inches(6.55)
    add_textbox(s14, M_LEFT, Inches(1.48), lw14, Inches(0.36),
                text="策略核心护城河评估（Moat Assessment）", font_size=17, bold=True, color=LIGHT, heading=True)
    moat_rows = [
        ["真时点数据治理", "强", "520 只动态成分池 + 行业/估值时效硬约束"],
        ["无前视开盘撮合", "强", "开盘跳空判定一字板，出池/ST允许正常退出"],
        ["低换手成本护城河", "强", "5.9% 单边换手，仅为量价对照的 1/8.7"],
        ["大盘流动性容量", "中", "数亿硬约束稳健，理论半衰容量达 80.9 亿"],
    ]
    add_styled_table(
        s14, M_LEFT, Inches(1.90), lw14, Inches(3.25),
        headers=["护城河维度", "评级", "可验证核心依据"],
        rows=moat_rows,
        col_widths=[2.05, 0.75, 3.75],
        alignments=[PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.LEFT],
        font_size=14.0,
        dark_mode=True,
    )

    # Right: Honest Limitations & v3.0 Roadmap
    rx14 = M_LEFT + lw14 + Inches(0.38)
    rw14 = CONTENT_W - lw14 - Inches(0.38)
    add_textbox(s14, rx14, Inches(1.48), rw14, Inches(0.36),
                text="三项坦诚局限与 v3.0 演进路线", font_size=17, bold=True, color=LIGHT, heading=True)
    add_round_rect(s14, rx14, Inches(1.90), rw14, Inches(3.25), fill_color=DARK_CARD, line_color=DARK_LINE, line_pt=0.8, radius=0.04)
    lims = [
        ("01  行业集中度约束", ORANGE, "最新金融基建占比 74%，下阶段引入软行业偏离上限测试。"),
        ("02  PIT 财报与精确市值", BLUE, "接入真实公告日时间戳与精确流通股本，消除代理噪声。"),
        ("03  new012 因子盲测", GREEN, "在未来前瞻样本上独立验证 20 日降频与无量纲改进因子。"),
    ]
    for i, (lt, lc, ld) in enumerate(lims):
        ly = Inches(2.06) + i * Inches(1.00)
        add_textbox(s14, rx14 + Inches(0.24), ly, rw14 - Inches(0.48), Inches(0.30),
                    text=lt, font_size=14.5, bold=True, color=lc, heading=True)
        add_textbox(s14, rx14 + Inches(0.24), ly + Inches(0.30), rw14 - Inches(0.48), Inches(0.58),
                    text=ld, font_size=13.5, color=MID_GRAY, line_spacing=1.22)

    # Bottom Dark Closing Banner
    add_rect(s14, M_LEFT, Inches(5.48), CONTENT_W, Inches(0.014), fill_color=DARK_LINE)
    add_textbox(s14, M_LEFT, Inches(5.72), Inches(7.5), Inches(0.62),
                text="感谢聆听  ·  欢迎各位老师与同学批评指正",
                font_size=26, bold=True, color=LIGHT, heading=True)
    add_textbox(s14, M_LEFT, Inches(6.42), Inches(7.8), Inches(0.38),
                text="完整公式推导、120 组敏感性网格与代码复现指南详见 30 页终版技术报告",
                font_size=14, color=MID_GRAY)

    # Right Q&A Pills
    add_pill(s14, SLIDE_W - M_RIGHT - Inches(3.55), Inches(5.86), Inches(1.65), Inches(0.48),
             "进入答辩 Q&A", fill_color=ORANGE, text_color=LIGHT, font_size=13.5)
    add_pill(s14, SLIDE_W - M_RIGHT - Inches(1.75), Inches(5.86), Inches(1.75), Inches(0.48),
             "ZH3689205", fill_color=DARK_CARD, text_color=GREEN, font_size=13.5, line_color=GREEN)

    add_note(s14, "收尾总结四大护城河与三项坦诚局限，邀请评委进入答辩 Q&A。")

    OUT_PPTX.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT_PPTX))
    print(f"[brand deck] saved {OUT_PPTX} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build_deck()
