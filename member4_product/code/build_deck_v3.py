# -*- coding: utf-8 -*-
"""
组员4 路演 PPT 自动构建脚本（v4.0 Anthropic 杂志编辑风重构版）
- 主路演 15 页（路演_v3.pptx / .pdf）：彻底告别“圆角盒 + 粗彩条”AI 模板感，采用纯瑞士编辑网格：
  * 暖象牙白画布 (#FAF9F5) + 柔和暖燕麦章节页 (#F0EEE6)，零深色整页、零冷蓝、零投影
  * 极细 0.75pt 发丝线 + 短陶土/橄榄细锚线 + 无框超大号衬线数据条 (Stat Strip)
  * 全篇深度 humanizer 去 AI 味，精简克制、像真人研究员写出来的路演
  * 原生 OOXML 页间 Fade 转场 + 按演讲顺序分步淡入动画 (350ms)
- 独立技术备查 5 页（技术备查_v3.pptx / .pdf）：同视觉语言，供答辩后单独打印递交老师
运行命令：
    .venv/bin/python code/build_deck_v3.py
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd
from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

import paths as P

M3_RES = P.resolve_member3_dir("v3") / "results"
M4_RES = P.MEMBER4_DIR / "results"
M4_XQ = P.MEMBER4_DIR / "xueqiu"
FIG_DIR = P.MEMBER4_DIR / "figures" / "slide_v3_brand"
DECK_DIR = P.MEMBER4_DIR / "deck"
PREVIEW_DIR = DECK_DIR / "preview_v3"
PREVIEW_APP_DIR = DECK_DIR / "preview_appendix"
DECK_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_APP_DIR.mkdir(parents=True, exist_ok=True)

OUT_PPTX = DECK_DIR / "路演_v3.pptx"
OUT_PDF = DECK_DIR / "路演_v3.pdf"
APP_PPTX = DECK_DIR / "技术备查_v3.pptx"
APP_PDF = DECK_DIR / "技术备查_v3.pdf"

MAIN_TOTAL = 15
APP_TOTAL = 5

# ---------------------------------------------------------------------------
# Anthropic Editorial Palette (Warm Ivory Paper + Swiss Hairlines + Earth Accents)
# ---------------------------------------------------------------------------
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

BG_IVORY = RGBColor(0xFA, 0xF9, 0xF5)     # #FAF9F5 主画布暖象牙白
BG_OAT = RGBColor(0xF0, 0xEE, 0xE6)       # #F0EEE6 章节页柔和燕麦底
BG_BAND = RGBColor(0xF4, 0xF2, 0xEA)      # #F4F2EA 极轻底纹带
BG_HEADER = RGBColor(0xEB, 0xE8, 0xDF)    # #EBE8DF 极轻表头底
BG_PAPER = RGBColor(0xFF, 0xFF, 0xFF)     # #FFFFFF 表格斑马亮行

INK = RGBColor(0x14, 0x14, 0x13)          # #141413 主炭墨
STONE = RGBColor(0x52, 0x50, 0x4A)        # #52504A 次正文石墨
MUTED = RGBColor(0x86, 0x82, 0x79)        # #868279 轻灰注记
GHOST = RGBColor(0xD8, 0xD4, 0xC8)        # #D8D4C8 章节超大号水印数字
HAIRLINE = RGBColor(0xD6, 0xD3, 0xC8)     # #D6D3C8 极细发丝分割线

TERRA = RGBColor(0xD9, 0x77, 0x57)        # #D97757 陶土橙
TERRA_DEEP = RGBColor(0xB8, 0x55, 0x35)   # #B85535 深陶土文字
TERRA_SOFT = RGBColor(0xF5, 0xE7, 0xDF)   # #F5E7DF 极淡陶土底纹

SAGE = RGBColor(0x6B, 0x80, 0x58)         # #6B8058 鼠尾草绿
SAGE_DEEP = RGBColor(0x4D, 0x60, 0x3C)    # #4D603C 深橄榄文字
SAGE_SOFT = RGBColor(0xEC, 0xF0, 0xE5)    # #ECF0E5 极淡橄榄底纹

OCHRE = RGBColor(0xB4, 0x84, 0x4C)        # #B4844C 暖赭石
OCHRE_DEEP = RGBColor(0x88, 0x5E, 0x2E)   # #885E2E 深古铜文字

BRICK = RGBColor(0xA6, 0x3D, 0x33)        # #A63D33 砖红反例警示

FONT_HEAD_EN = "Arial"
FONT_HEAD_CN = "黑体-简"
FONT_BODY_EN = "Georgia"
FONT_BODY_CN = "宋体-简"

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


# ---------------------------------------------------------------------------
# 原生 OOXML 页间淡入转场 & 按演讲顺序分步渐显动画
# ---------------------------------------------------------------------------
def add_fade_transition(slide, spd: str = "med"):
    sld = slide._element
    for old in sld.findall(f"{{{P_NS}}}transition"):
        sld.remove(old)
    trans = etree.Element(f"{{{P_NS}}}transition", spd=spd, advClick="1")
    etree.SubElement(trans, f"{{{P_NS}}}fade")
    clr_map = sld.find(f"{{{P_NS}}}clrMapOvr")
    c_sld = sld.find(f"{{{P_NS}}}cSld")
    anchor = clr_map if clr_map is not None else c_sld
    if anchor is not None:
        anchor.addnext(trans)
    else:
        sld.append(trans)


def add_click_builds(slide, click_groups: list[list[tuple[list[int], int]]], dur_ms: int = 350):
    valid_clicks: list[list[tuple[list[int], int]]] = []
    for click in click_groups:
        sub = [(ids, d) for ids, d in click if ids]
        if sub:
            valid_clicks.append(sub)
    if not valid_clicks:
        return

    sld = slide._element
    for old in sld.findall(f"{{{P_NS}}}timing"):
        sld.remove(old)

    next_id = [1]

    def alloc_id() -> str:
        val = str(next_id[0])
        next_id[0] += 1
        return val

    timing = etree.Element(f"{{{P_NS}}}timing")
    tn_lst = etree.SubElement(timing, f"{{{P_NS}}}tnLst")
    root_par = etree.SubElement(tn_lst, f"{{{P_NS}}}par")
    root_ctn = etree.SubElement(root_par, f"{{{P_NS}}}cTn", id=alloc_id(), dur="indefinite", restart="never", nodeType="tmRoot")
    root_children = etree.SubElement(root_ctn, f"{{{P_NS}}}childTnLst")

    seq = etree.SubElement(root_children, f"{{{P_NS}}}seq", concurrent="1", nextAc="seek")
    seq_ctn = etree.SubElement(seq, f"{{{P_NS}}}cTn", id=alloc_id(), dur="indefinite", nodeType="mainSeq")
    seq_children = etree.SubElement(seq_ctn, f"{{{P_NS}}}childTnLst")

    animated_spids: list[int] = []
    seen_spids: set[int] = set()

    for click in valid_clicks:
        c_par = etree.SubElement(seq_children, f"{{{P_NS}}}par")
        c_ctn = etree.SubElement(c_par, f"{{{P_NS}}}cTn", id=alloc_id(), fill="hold")
        c_st = etree.SubElement(c_ctn, f"{{{P_NS}}}stCondLst")
        etree.SubElement(c_st, f"{{{P_NS}}}cond", delay="indefinite")
        c_children = etree.SubElement(c_ctn, f"{{{P_NS}}}childTnLst")

        w_par = etree.SubElement(c_children, f"{{{P_NS}}}par")
        w_ctn = etree.SubElement(w_par, f"{{{P_NS}}}cTn", id=alloc_id(), fill="hold")
        w_st = etree.SubElement(w_ctn, f"{{{P_NS}}}stCondLst")
        etree.SubElement(w_st, f"{{{P_NS}}}cond", delay="0")
        w_children = etree.SubElement(w_ctn, f"{{{P_NS}}}childTnLst")

        is_first_in_click = True
        for spids, delay_ms in click:
            for spid in spids:
                if spid in seen_spids:
                    continue
                seen_spids.add(spid)
                animated_spids.append(spid)

                node_type = "clickEffect" if is_first_in_click else "withEffect"
                is_first_in_click = False

                e_par = etree.SubElement(w_children, f"{{{P_NS}}}par")
                e_ctn = etree.SubElement(
                    e_par, f"{{{P_NS}}}cTn",
                    id=alloc_id(), presetID="10", presetClass="entr", presetSubtype="0",
                    fill="hold", nodeType=node_type,
                )
                e_st = etree.SubElement(e_ctn, f"{{{P_NS}}}stCondLst")
                etree.SubElement(e_st, f"{{{P_NS}}}cond", delay=str(delay_ms))
                e_children = etree.SubElement(e_ctn, f"{{{P_NS}}}childTnLst")

                set_el = etree.SubElement(e_children, f"{{{P_NS}}}set")
                set_bhvr = etree.SubElement(set_el, f"{{{P_NS}}}cBhvr")
                set_ctn = etree.SubElement(set_bhvr, f"{{{P_NS}}}cTn", id=alloc_id(), dur="1", fill="hold")
                set_st = etree.SubElement(set_ctn, f"{{{P_NS}}}stCondLst")
                etree.SubElement(set_st, f"{{{P_NS}}}cond", delay="0")
                set_tgt = etree.SubElement(set_bhvr, f"{{{P_NS}}}tgtEl")
                etree.SubElement(set_tgt, f"{{{P_NS}}}spTgt", spid=str(spid))
                attr_lst = etree.SubElement(set_bhvr, f"{{{P_NS}}}attrNameLst")
                attr = etree.SubElement(attr_lst, f"{{{P_NS}}}attrName")
                attr.text = "style.visibility"
                to_el = etree.SubElement(set_el, f"{{{P_NS}}}to")
                etree.SubElement(to_el, f"{{{P_NS}}}strVal", val="visible")

                anim = etree.SubElement(e_children, f"{{{P_NS}}}animEffect", transition="in", filter="fade")
                anim_bhvr = etree.SubElement(anim, f"{{{P_NS}}}cBhvr")
                etree.SubElement(anim_bhvr, f"{{{P_NS}}}cTn", id=alloc_id(), dur=str(dur_ms))
                anim_tgt = etree.SubElement(anim_bhvr, f"{{{P_NS}}}tgtEl")
                etree.SubElement(anim_tgt, f"{{{P_NS}}}spTgt", spid=str(spid))

    prev_cond = etree.SubElement(seq, f"{{{P_NS}}}prevCondLst")
    p_cond = etree.SubElement(prev_cond, f"{{{P_NS}}}cond", evt="onPrev", delay="0")
    etree.SubElement(etree.SubElement(p_cond, f"{{{P_NS}}}tgtEl"), f"{{{P_NS}}}sldTgt")

    next_cond = etree.SubElement(seq, f"{{{P_NS}}}nextCondLst")
    n_cond = etree.SubElement(next_cond, f"{{{P_NS}}}cond", evt="onNext", delay="0")
    etree.SubElement(etree.SubElement(n_cond, f"{{{P_NS}}}tgtEl"), f"{{{P_NS}}}sldTgt")

    bld_lst = etree.SubElement(timing, f"{{{P_NS}}}bldLst")
    for spid in animated_spids:
        etree.SubElement(bld_lst, f"{{{P_NS}}}bldP", spid=str(spid), grpId="0", animBg="1")

    trans = sld.find(f"{{{P_NS}}}transition")
    clr_map = sld.find(f"{{{P_NS}}}clrMapOvr")
    c_sld = sld.find(f"{{{P_NS}}}cSld")
    anchor = trans if trans is not None else (clr_map if clr_map is not None else c_sld)
    if anchor is not None:
        anchor.addnext(timing)
    else:
        sld.append(timing)


def track_ids(slide, start_len: int) -> list[int]:
    return [sh.shape_id for sh in list(slide.shapes)[start_len:]]


# ---------------------------------------------------------------------------
# 杂志编辑风排版基元（零圆角塑料盒、零阴影、纯线条与字号层级）
# ---------------------------------------------------------------------------
def disable_shadow(sh):
    sh.shadow.inherit = False
    spPr = sh._element.spPr
    for el in list(spPr):
        if el.tag.endswith("effectLst"):
            spPr.remove(el)
    spPr.append(OxmlElement("a:effectLst"))
    style = sh._element.find(qn("p:style"))
    if style is not None:
        eff_ref = style.find(qn("a:effectRef"))
        if eff_ref is not None:
            eff_ref.set("idx", "0")


def set_bg(slide, color=BG_IVORY):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def set_font(run, size_pt: float, bold: bool = False, color=INK, is_heading: bool = False, force_serif: bool = False):
    if force_serif:
        en_font, cn_font = FONT_BODY_EN, FONT_BODY_CN
    else:
        en_font = FONT_HEAD_EN if is_heading else FONT_BODY_EN
        cn_font = FONT_HEAD_CN if is_heading else FONT_BODY_CN
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = en_font
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            rPr.append(el)
        el.set("typeface", cn_font)


def add_tb(slide, left, top, width, height, text="", size=13.0, bold=False, color=INK,
           align=PP_ALIGN.LEFT, line_spacing=1.28, is_heading: bool | None = None, force_serif: bool = False):
    if is_heading is None:
        is_heading = bold
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = Inches(0.01)
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    if text:
        r = p.add_run()
        r.text = text
        set_font(r, size, bold=bold, color=color, is_heading=is_heading, force_serif=force_serif)
    return tb


def add_rule(slide, left, top, width, thickness_in=0.012, color=HAIRLINE):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(thickness_in))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    disable_shadow(sh)
    return sh


def add_vrule(slide, left, top, height, thickness_in=0.012, color=HAIRLINE):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(thickness_in), Inches(height))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    disable_shadow(sh)
    return sh


def add_soft_rect(slide, left, top, width, height, fill_color=BG_BAND, border_color=None, dashed=False):
    """极克制无圆角平面色带（仅用于极轻底纹或虚线截图预留区，不做塑料卡片）"""
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill_color
    if border_color is not None:
        sh.line.color.rgb = border_color
        sh.line.width = Pt(1.0 if dashed else 0.75)
        if dashed:
            sh.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    else:
        sh.line.fill.background()
    disable_shadow(sh)
    return sh


def add_stat_item(slide, left, top, width, label: str, value: str, sub: str = "", accent=TERRA_DEEP,
                  val_size=30.0, top_rule=True):
    """无框大号衬线数字项（Anthropic / 杂志 Stat Strip，绝不套圆角塑料盒）"""
    if top_rule:
        add_rule(slide, left, top, width, 0.012, HAIRLINE)
        add_rule(slide, left, top, 0.42, 0.028, accent)
    add_tb(slide, left, top + 0.14, width, 0.28, label, size=10.5, bold=True, color=MUTED, is_heading=True)
    add_tb(slide, left, top + 0.44, width, 0.68, value, size=val_size, bold=True, color=accent, force_serif=True)
    if sub:
        sub_dy = 1.22 if val_size >= 32 else 1.12
        add_tb(slide, left, top + sub_dy, width, 0.42, sub, size=10.5, bold=False, color=STONE, line_spacing=1.25)


def add_editorial_note(slide, left, top, width, heading: str, body: str, accent=TERRA_DEEP,
                       head_size=12.2, body_size=11.3, with_top_rule=True):
    """无框编辑风短评块：一根细顶线 + 简短标题 + 平实短句"""
    if with_top_rule:
        add_rule(slide, left, top, width, 0.012, HAIRLINE)
        add_rule(slide, left, top, 0.36, 0.026, accent)
    y0 = top + (0.14 if with_top_rule else 0.0)
    add_tb(slide, left, y0, width, 0.32, heading, size=head_size, bold=True, color=INK, is_heading=True)
    add_tb(slide, left, y0 + 0.34, width, 1.40, body, size=body_size, bold=False, color=STONE, line_spacing=1.34)


def add_header(slide, kicker: str, title: str, page_no: int, total: int = MAIN_TOTAL, footer_text: str | None = None):
    set_bg(slide, BG_IVORY)
    add_fade_transition(slide, spd="med")
    add_tb(slide, 0.72, 0.36, 8.5, 0.28, kicker, size=10.5, bold=True, color=TERRA_DEEP, is_heading=True)
    add_tb(slide, 11.4, 0.36, 1.21, 0.28, f"{page_no:02d} / {total:02d}", size=10.2, bold=False, color=MUTED, align=PP_ALIGN.RIGHT, force_serif=True)
    add_tb(slide, 0.72, 0.68, 11.89, 0.56, title, size=22.5, bold=True, color=INK, is_heading=True)
    add_rule(slide, 0.72, 1.32, 11.89, 0.012, HAIRLINE)
    ft = footer_text if footer_text is not None else "沪深300 价值低波精选策略（M4）  ·  雪球模拟组合 ZH3689205"
    add_tb(slide, 0.72, 7.12, 11.89, 0.24, ft, size=9.2, color=MUTED)


def add_section_slide(slide, num_str: str, title: str, subtitle: str, toc_items: list[str],
                      page_no: int, total: int = MAIN_TOTAL, accent=TERRA_DEEP):
    """极简高级章节过渡页：柔和暖燕麦画布 + 超大轻衬线数字 + 短细线 + 克制目录"""
    set_bg(slide, BG_OAT)
    add_fade_transition(slide, spd="med")
    add_tb(slide, 0.72, 0.42, 6.0, 0.28, "沪深300 价值低波精选策略（M4）", size=10.2, color=MUTED, is_heading=True)
    add_tb(slide, 11.4, 0.42, 1.21, 0.28, f"{page_no:02d} / {total:02d}", size=10.2, color=MUTED, align=PP_ALIGN.RIGHT, force_serif=True)

    # 左下超大号轻衬线章节数字
    add_tb(slide, 0.68, 1.55, 3.6, 2.4, num_str, size=120, bold=False, color=GHOST, force_serif=True)

    # 右侧主章名与短锚线
    n1 = len(slide.shapes)
    add_rule(slide, 4.35, 2.30, 0.65, 0.038, accent)
    add_tb(slide, 4.35, 2.55, 8.0, 0.85, title, size=40, bold=True, color=INK, is_heading=True)
    add_tb(slide, 4.35, 3.52, 7.8, 0.55, subtitle, size=15.0, color=STONE, line_spacing=1.35)
    title_ids = track_ids(slide, n1)

    # 底部轻盈水平目录条
    n2 = len(slide.shapes)
    add_rule(slide, 4.35, 4.55, 7.9, 0.012, HAIRLINE)
    col_w = 7.9 / len(toc_items)
    for i, item in enumerate(toc_items):
        x = 4.35 + i * col_w
        add_tb(slide, x, 4.78, col_w - 0.15, 0.26, f"0{i+1}", size=9.8, bold=True, color=accent, force_serif=True)
        add_tb(slide, x, 5.04, col_w - 0.12, 0.45, item, size=12.0, bold=False, color=INK, is_heading=True)
    toc_ids = track_ids(slide, n2)
    add_click_builds(slide, [[(title_ids, 0)], [(toc_ids, 0)]])


def add_pic_fit(slide, img_path: Path, left, top, max_w, max_h):
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


def set_cell_borders(cell, top_hex=None, bottom_hex=None, sz_pt=0.6):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        old = tcPr.find(qn(tag))
        if old is not None:
            tcPr.remove(old)
    w_emu = str(int(sz_pt * 12700))
    for tag, col in (("a:lnL", None), ("a:lnR", None), ("a:lnT", top_hex), ("a:lnB", bottom_hex)):
        ln = OxmlElement(tag)
        ln.set("w", w_emu)
        if col:
            sf = OxmlElement("a:solidFill")
            srgb = OxmlElement("a:srgbClr")
            srgb.set("val", col)
            sf.append(srgb)
            ln.append(sf)
        else:
            ln.append(OxmlElement("a:noFill"))
        tcPr.append(ln)


def add_editorial_table(slide, left, top, width, height, headers: list[str], rows: list[list[str]],
                        font_size=9.8, highlight_rows: set[int] | None = None,
                        col_widths: list[float] | None = None, left_align_cols: set[int] | None = None):
    """无竖线、纯极细横线的投行/期刊级三线表"""
    tbl_shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(left), Inches(top), Inches(width), Inches(height))
    tbl = tbl_shape.table
    # 清除默认表格样式条纹
    tblPr = tbl._tbl.tblPr
    for attr in ("bandRow", "firstRow"):
        if attr in tblPr.attrib:
            del tblPr.attrib[attr]
    if col_widths:
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = Inches(cw)
    hi_set = highlight_rows or set()
    la_set = left_align_cols if left_align_cols is not None else {0}

    for c_i, h in enumerate(headers):
        cell = tbl.cell(0, c_i)
        cell.fill.solid()
        cell.fill.fore_color.rgb = BG_HEADER
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        set_cell_borders(cell, top_hex="141413", bottom_hex="868279", sz_pt=0.9)
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT if c_i in la_set else PP_ALIGN.CENTER
        r = p.add_run()
        r.text = h
        set_font(r, font_size, bold=True, color=INK, is_heading=True)

    n_rows = len(rows)
    for r_i, rdata in enumerate(rows, start=1):
        is_hi = (r_i - 1) in hi_set
        is_last = (r_i == n_rows)
        bg = TERRA_SOFT if is_hi else (BG_IVORY if r_i % 2 == 1 else BG_BAND)
        for c_i, val in enumerate(rdata):
            cell = tbl.cell(r_i, c_i)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            set_cell_borders(cell, bottom_hex=("141413" if is_last else "DCD9CE"), sz_pt=(0.9 if is_last else 0.5))
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c_i in la_set else PP_ALIGN.CENTER
            r = p.add_run()
            r.text = val
            set_font(r, font_size, bold=(is_hi or c_i == 0), color=(TERRA_DEEP if is_hi else INK), is_heading=(c_i == 0 and is_hi))
    return tbl_shape


def load_v3():
    m3 = pd.read_csv(M3_RES / "metrics_v3.csv")
    oi = pd.read_csv(M3_RES / "overnight_intraday_v3.csv")
    prod = json.loads((M4_RES / "product_summary_v3.json").read_text(encoding="utf-8"))
    fee_df = pd.read_csv(M4_RES / "fee_analysis_v3.csv")
    cap_s = pd.read_csv(M4_RES / "capacity_stress_v3.csv")
    xq_bt = pd.read_csv(M4_XQ / "xueqiu_30_tracking_backtest.csv")
    xq_ver = json.loads((M4_XQ / "xueqiu_screenshot_verified.json").read_text(encoding="utf-8"))
    live_1125 = json.loads((M4_XQ / "live_m4_20261125_audit.json").read_text(encoding="utf-8"))
    return dict(m3=m3, oi=oi, prod=prod, fee_df=fee_df, cap_s=cap_s, xq_bt=xq_bt, xq_ver=xq_ver, live_1125=live_1125)


def pct(x, signed=True, d=2):
    return f"{x*100:{'+' if signed else ''}.{d}f}%"


def export_pdf_and_pngs(pptx_path: Path, pdf_path: Path, out_dir: Path, preview_dir: Path):
    lo_env = {**os.environ, "HOME": "/tmp"}
    subprocess.run([
        "soffice", "-env:UserInstallation=file:///tmp/lo_deck", "--headless",
        "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx_path),
    ], env=lo_env, check=True)
    for old in preview_dir.glob("*.png"):
        old.unlink()
    subprocess.run(["pdftoppm", "-png", "-r", "120", str(pdf_path), str(preview_dir / "slide")], check=True)
    return sorted(preview_dir.glob("*.png"))


# =============================================================================
# 构建主路演 15 页（路演_v3.pptx）
# =============================================================================
def build_main_deck(D: dict):
    m3, oi, prod, fee_df = D["m3"], D["oi"], D["prod"], D["fee_df"]

    def gm(exp, mod, st="all", fee="net_10bp"):
        return m3[(m3["experiment"] == exp) & (m3["model"] == mod) & (m3["stage"] == st) & (m3["fee_scenario"] == fee)].iloc[0]

    def goi(exp, mod):
        return oi[(oi["experiment"] == exp) & (oi["model"] == mod)].iloc[0]

    hs_m4 = gm("hs300_clean", "M4")
    hs_m4_ht = gm("hs300_clean", "M4", "all", "net_histtax")
    hs_m4_val = gm("hs300_clean", "M4", "validation")
    hs_m4_seen = gm("hs300_clean", "M4", "seen")
    hs_m0b_gr = gm("hs300_full", "M0b", "all", "gross")
    hs_m0b_net = gm("hs300_full", "M0b", "all", "net_10bp")
    zz_m4 = gm("zz500", "M4")
    cap_hs = prod["cross_pool_capacity_highlight"]["hs300_M4"]
    fee_hs = fee_df[fee_df["series"] == "hs300_M4_net10bp"].set_index("plan_id")
    m0b_cost_pp = (hs_m0b_gr["cum_return"] - hs_m0b_net["cum_return"]) * 100

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # -------------------------------------------------------------------------
    # P01｜封面（极简大留白 + 无框 4 列数据条）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    set_bg(s, BG_IVORY)
    add_fade_transition(s, spd="med")
    add_rule(s, 0.72, 0.72, 0.65, 0.036, TERRA)
    add_tb(s, 0.72, 0.96, 10.0, 0.34, "《量化交易技术理论与实践》期末路演  ·  私募量化投研团队", size=12.0, bold=True, color=TERRA_DEEP, is_heading=True)
    add_tb(s, 0.72, 1.52, 11.8, 1.48, "沪深300 价值低波精选策略（M4）\n低换手防御型量化私募产品方案", size=36, bold=True, color=INK, line_spacing=1.18, is_heading=True)
    add_tb(s, 0.72, 3.16, 11.5, 0.42, "四因子等权（BP + EP + LowVol60 + LowTurn20） ·  每 5 交易日调仓  ·  沪深300 与中证500 双池验证", size=13.5, color=STONE)

    # Click 1: 无框 4 列大数字横条（突出年化收益率、夏普/回撤、双池年化、费后到手年化）
    n0 = len(s.shapes)
    add_rule(s, 0.72, 3.92, 11.89, 0.012, HAIRLINE)
    stats = [
        ("沪深300 M4 几何年化", pct(hs_m4["ann_geom"]), f"全期累计 {pct(hs_m4['cum_return'])}（含交易费·未扣产品费）", TERRA_DEEP),
        ("算术夏普 / 最大回撤", f"{hs_m4['sharpe_arith_rf0']:.2f} / -15.88%", f"单次单边换手 {pct(hs_m4['mean_half_turn'], False)} · 较指数浅 8.9pp", OCHRE_DEEP),
        ("中证500 跨池几何年化", pct(zz_m4["ann_geom"]), f"全期累计 {pct(zz_m4['cum_return'])} · 同规格居首", SAGE_DEEP),
        ("机构 C 档历史模拟费后", pct(fee_hs.loc["C", "ann_geom"]), "相对价格指数超额提成 · IR 0.73", INK),
    ]
    col_w = 11.89 / 4.0
    for i, (lbl, val, sub, col) in enumerate(stats):
        x = 0.72 + i * col_w
        if i > 0:
            add_vrule(s, x - 0.14, 4.14, 1.24, 0.010, HAIRLINE)
        add_tb(s, x, 4.10, col_w - 0.22, 0.28, lbl, size=10.2, bold=True, color=MUTED, is_heading=True)
        add_tb(s, x, 4.44, col_w - 0.22, 0.56, val, size=25.5, bold=True, color=col, force_serif=True)
        add_tb(s, x, 5.06, col_w - 0.22, 0.36, sub, size=9.9, color=STONE)
    add_rule(s, 0.72, 5.64, 11.89, 0.012, HAIRLINE)
    stat_ids = track_ids(s, n0)

    # 底部极简信息行（无底盒）
    add_tb(s, 0.72, 5.92, 11.89, 0.34, "李钰鹏 (2024104286)  ·  刘宇睿 (2024101054)  ·  张沐 (2024101056)  ·  张恒瑞 (2024101062)", size=12.0, bold=True, color=INK, is_heading=True)
    add_tb(s, 0.72, 6.32, 11.89, 0.32, "指导教师：肖亮海    |    雪球模拟组合：ZH3689205 (xueqiu.com/P/ZH3689205)    |    GitHub：github.com/z2823253773-p/csi300-quant-strategy", size=10.6, color=STONE)
    add_click_builds(s, [[(stat_ids, 0)]])

    # -------------------------------------------------------------------------
    # P02｜团队与分工（横向杂志编辑列表，零圆角白卡、零底部口号条）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "团队与分工", "四位成员按数据、因子、回测与产品顺序协作", 2)
    members = [
        ("01", "李钰鹏", "数据整理与校验", "双池动态成分数据底座",
         "搭建沪深300（520股）与中证500（1,107股）94 期月度动态成分库，整合个股行情、估值、复权与逐日 ST 状态，用 SHA-256 指纹锁定全部 21 份输入文件。", OCHRE_DEEP),
        ("02", "刘宇睿", "因子筛选与消融", "101 因子重筛与模型定型",
         "在双股票池运行 101 个候选公式并做训练期多重检验，设计 8 组控制变量实验确定简洁的四因子等权模型 M4，并定位排查 Alpha015 低覆盖约束问题。", TERRA_DEEP),
        ("03", "张沐", "回测与风险核查", "无前视撮合与行业回撤监控",
         "搭建开盘撮合账户引擎，完成 63 组账户零残差回测与双实现独立复算；核查每日申万行业暴露与水下回撤，量化产品三层风控防线。", SAGE_DEEP),
        ("04", "张恒瑞", "产品化与总整合", "容量、费率与模拟跟踪落地",
         "测算双池流动性容量与逐期超限率，设计四档高水位产品费率与雪球 30 股前 45 缓冲映射方案，统筹技术报告、路演与 GitHub 代码复现。", TERRA_DEEP),
    ]
    row_groups = []
    for i, (num, name, role, headline, desc, col) in enumerate(members):
        n0 = len(s.shapes)
        y = 1.62 + i * 1.32
        if i > 0:
            add_rule(s, 0.72, y - 0.14, 11.89, 0.010, HAIRLINE)
        add_tb(s, 0.72, y + 0.04, 0.90, 0.65, num, size=30, bold=False, color=col, force_serif=True)
        add_tb(s, 1.72, y + 0.06, 2.35, 0.36, name, size=16.5, bold=True, color=INK, is_heading=True)
        add_tb(s, 1.72, y + 0.48, 2.35, 0.30, role, size=11.5, bold=False, color=MUTED, is_heading=True)
        add_vrule(s, 4.25, y + 0.10, 0.88, 0.010, HAIRLINE)
        add_tb(s, 4.55, y + 0.04, 8.05, 0.34, headline, size=13.5, bold=True, color=INK, is_heading=True)
        add_tb(s, 4.55, y + 0.42, 8.05, 0.68, desc, size=11.8, color=STONE, line_spacing=1.34)
        row_groups.append((track_ids(s, n0), i * 100))
    add_rule(s, 0.72, 6.84, 11.89, 0.010, HAIRLINE)
    add_click_builds(s, [row_groups])

    # -------------------------------------------------------------------------
    # P03｜章节过渡页 · 01 策略架构
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_section_slide(
        s, "01", "策略架构",
        "为什么放弃高频量价，以及如何构建低换手防御组合",
        ["出发点与目标", "因子与交易规则", "演进与选型", "风控与回撤"],
        page_no=3, accent=TERRA_DEEP,
    )

    # -------------------------------------------------------------------------
    # P04｜出发点与目标（反差大数字视觉 + 底部无框三列，零圆角塑料盒！）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "01 策略架构", "为什么不做高频量价，转而追求低换手防御？", 4)

    # 上半区：左右两组超大反差数据直接铺在暖白纸面上
    n1 = len(s.shapes)
    # 左反差块：被动宽基大回撤
    add_tb(s, 0.72, 1.62, 5.55, 0.30, "现实一 · 被动持有宽基的回撤代价", size=12.0, bold=True, color=OCHRE_DEEP, is_heading=True)
    add_tb(s, 0.72, 2.02, 2.85, 0.90, "-24.8%", size=44, bold=True, color=STONE, force_serif=True)
    add_tb(s, 3.65, 2.24, 0.60, 0.45, "vs", size=16, bold=False, color=MUTED, align=PP_ALIGN.CENTER, force_serif=True)
    add_tb(s, 4.30, 2.02, 2.15, 0.90, "-15.9%", size=44, bold=True, color=TERRA_DEEP, force_serif=True)
    add_tb(s, 0.72, 2.98, 5.60, 0.96,
           "2023–2026 年沪深300 价格指数几乎原地踏步（-0.33%），期间最大回撤深达 -24.80%。同样扎根大盘成分池，M4 将回撤收窄 8.92 个百分点。",
           size=11.8, color=STONE, line_spacing=1.38)

    add_vrule(s, 6.62, 1.66, 2.25, 0.012, HAIRLINE)

    # 右反差块：高频量价交易摩擦
    add_tb(s, 6.95, 1.62, 5.65, 0.30, "现实二 · 高频量价的交易磨损（本组实测 M0b）", size=12.0, bold=True, color=BRICK, is_heading=True)
    add_tb(s, 6.95, 2.02, 2.95, 0.90, "-37.4pp", size=44, bold=True, color=BRICK, force_serif=True)
    add_tb(s, 9.95, 2.14, 2.65, 0.78, "毛收益 +28.54%\n扣费后 -8.88%", size=14.5, bold=True, color=INK, line_spacing=1.35, force_serif=True)
    add_tb(s, 6.95, 2.98, 5.65, 0.96,
           f"早期测试的 50% 高频量价模型（M0b）单次单边换手达 51.7%，双边成本直接吞掉 {m0b_cost_pp:.1f} 个百分点。小团队拼算力与短线换手很难跑赢摩擦。",
           size=11.8, color=STONE, line_spacing=1.38)
    top_ids = track_ids(s, n1)

    # 下半区：无框三列极细顶线目标
    n2 = len(s.shapes)
    add_tb(s, 0.72, 4.30, 11.89, 0.34, "因此我们把策略目标收敛为三件事", size=13.5, bold=True, color=INK, is_heading=True)
    tri_cols = [
        ("控回撤", "用低波动与低换手过滤情绪过热股，在震荡弱市里守住本金，不让一次大跌毁掉多年复利。", TERRA_DEEP),
        ("降磨损", "周频调仓配合排名缓冲带，把每次调仓平均单边换手压到 3% 以内，让纸面收益真正落袋。", SAGE_DEEP),
        ("能落地", "主战场放在高流动性的沪深300 成分池，并在中证500 做同规格验证，确保资金容量与规则透明。", OCHRE_DEEP),
    ]
    g_groups = []
    for i, (h, b, col) in enumerate(tri_cols):
        n_c = len(s.shapes)
        x = 0.72 + i * 4.10
        add_editorial_note(s, x, 4.78, 3.68, h, b, accent=col, head_size=14.5, body_size=11.8)
        g_groups.append((track_ids(s, n_c), i * 110))
    add_click_builds(s, [[(top_ids, 0)], g_groups])

    # -------------------------------------------------------------------------
    # P05｜因子与交易规则（清爽两栏建筑感网格）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "01 策略架构", "四因子直接等权（零调参）+ 前 75 名排名缓冲带", 5)

    # 左栏：选股打分（两块无框极轻暖色带）
    n1 = len(s.shapes)
    add_tb(s, 0.72, 1.56, 6.20, 0.36, "选股打分：25% × 4 直接等权", size=15.0, bold=True, color=INK, is_heading=True)
    add_soft_rect(s, 0.72, 2.08, 6.18, 2.12, fill_color=TERRA_SOFT)
    add_tb(s, 1.00, 2.26, 5.65, 0.34, "50%  价值双锚（不做行业中性化，保留价值风格）", size=12.8, bold=True, color=TERRA_DEEP, is_heading=True)
    add_tb(s, 1.00, 2.70, 5.65, 0.62, "BP（账面市值比 1/PB，25%）  锚定净资产安全边际，在弱市底部提供估值底。", size=11.8, color=INK, line_spacing=1.32)
    add_tb(s, 1.00, 3.40, 5.65, 0.62, "EP（盈利收益率 1/PE，25%）  只保留盈利为正标的，避开低估值亏损陷阱。", size=11.8, color=INK, line_spacing=1.32)

    add_soft_rect(s, 0.72, 4.44, 6.18, 2.24, fill_color=SAGE_SOFT)
    add_tb(s, 1.00, 4.62, 5.65, 0.34, "50%  低风险双因子（行业与市值双重中性化）", size=12.8, bold=True, color=SAGE_DEEP, is_heading=True)
    add_tb(s, 1.00, 5.06, 5.65, 0.62, "LowVol60（60日低波动，25%）  剔除暴涨暴跌题材股，平滑净值曲线。", size=11.8, color=INK, line_spacing=1.32)
    add_tb(s, 1.00, 5.76, 5.65, 0.72, "LowTurn20（20日低换手，25%）  远离筹码拥挤的高换手标的；计算滚动前先屏蔽停牌日，不前填停牌价。", size=11.8, color=INK, line_spacing=1.32)
    left_ids = track_ids(s, n1)

    # 右栏：极细横线分隔的交易规则 + 底部超大号无框结果数字
    n2 = len(s.shapes)
    add_tb(s, 7.35, 1.56, 5.25, 0.36, "交易与降换手规则", size=15.0, bold=True, color=INK, is_heading=True)
    rules = [
        ("每 5 交易日调仓", "周频节奏贴合价值与低波特征，避开日频噪声。"),
        ("Top 50 等权持有", "单股目标权重 2%，分散个股风险并保障流动性。"),
        ("前 75 名排名缓冲带", "老持仓维持前 75 名即保留，消除临界排名的来回换手。"),
        ("次日开盘撮合", "收盘算分、次日开盘按真实停牌与涨跌停规则成交。"),
    ]
    for i, (rh, rb) in enumerate(rules):
        y = 2.08 + i * 0.80
        add_rule(s, 7.35, y, 5.25, 0.010, HAIRLINE)
        add_tb(s, 7.35, y + 0.10, 2.05, 0.34, rh, size=12.0, bold=True, color=INK, is_heading=True)
        add_tb(s, 9.45, y + 0.10, 3.15, 0.62, rb, size=11.0, color=STONE, line_spacing=1.28)

    add_stat_item(s, 7.35, 5.24, 5.25, "降换手实测结果 · 每次调仓平均单边换手", "2.74%",
                  "折算年化单边约 137%（对比高频反例 M0b 单次 51.7%）", accent=TERRA_DEEP, val_size=34.0)
    right_ids = track_ids(s, n2)
    add_click_builds(s, [[(left_ids, 0)], [(right_ids, 0)]])

    # -------------------------------------------------------------------------
    # P06｜策略演进与选型（左图 + 右无框大数字条 + 简练选型说明）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "01 策略架构", "沪深300 净值演进：为什么定案简洁的四因子 M4？", 6)
    n1 = len(s.shapes)
    add_pic_fit(s, FIG_DIR / "01_hs300_ablation_nav.png", 0.58, 1.48, 8.20, 5.42)
    fig_ids = track_ids(s, n1)

    n2 = len(s.shapes)
    add_stat_item(s, 9.05, 1.62, 3.55, "沪深300 M4 年化 / 累计收益", f"{pct(hs_m4['ann_geom'])}",
                  f"全期 {pct(hs_m4['cum_return'])} · 较原始基准 M0a +15.02pp", accent=TERRA_DEEP, val_size=32.0)
    add_stat_item(s, 9.05, 3.24, 3.55, "算术夏普比率（Rf=0）", f"{hs_m4['sharpe_arith_rf0']:.3f}",
                  f"验证期 {pct(hs_m4_val['cum_return'])} · 后段 {pct(hs_m4_seen['cum_return'])}", accent=OCHRE_DEEP, val_size=32.0)
    stat_ids = track_ids(s, n2)

    n3 = len(s.shapes)
    add_editorial_note(
        s, 9.05, 4.92, 3.55, "双池选型权衡（含反例）",
        "沪深300 内五因子 M5（+60.79%）优于 M4，且历史留后段 M4（+12.21%）低于 M1（+14.07%）；但中证500 上 M4 全面优于 M5（+57.73% 对 +55.17%，回撤浅 3.75pp）。减少一个由 EP/BP 直接派生的比率因子，跨池表现更一致。",
        accent=SAGE_DEEP, head_size=12.5, body_size=10.8,
    )
    note_ids = track_ids(s, n3)
    add_click_builds(s, [[(fig_ids, 0)], [(stat_ids, 0)], [(note_ids, 0)]])

    # -------------------------------------------------------------------------
    # P07｜风险控制与回撤（左水下回撤图 + 右无框极细横线三层风控）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "01 策略架构", "回撤审计与拟议风控条款：最大回撤 -15.88%，最低净值 0.9926", 7)
    n1 = len(s.shapes)
    add_pic_fit(s, FIG_DIR / "04_drawdown_underwater_v3.png", 0.58, 1.48, 8.15, 5.42)
    fig_ids = track_ids(s, n1)

    n2 = len(s.shapes)
    layers = [
        ("01 事前选股与专户行业条款", "动态成分池消除幸存者偏差，剔除 ST、亏损及停牌异常股；针对金融持仓均值 42.4%（期末 50.0%），机构专户拟设单行业 ≤35% 上限。", OCHRE_DEEP, 1.54),
        ("02 事中执行与参与率约束", "次日开盘触限自动跳过不追高；大额资金在尾部低流动性调仓期采用多日 VWAP/TWAP 拆单控制 5% 成交参与率。", SAGE_DEEP, 3.06),
        ("03 拟议净值防线与回撤口径区分", "全期最低单位净值为 0.9926（2023-01-12）；最大回撤 -15.88% 对应净值由 2025-11-12 峰值 1.5999 回落至 2026-06-30 谷底 1.3458。拟设 0.85 预警线与 0.80 止损线（与 35% 行业上限同属拟议合同条款，未嵌入历史回测）。", TERRA_DEEP, 4.54),
    ]
    for h, b, col, y in layers:
        add_editorial_note(s, 8.98, y, 3.63, h, b, accent=col, head_size=12.4, body_size=10.8)
    add_tb(s, 8.98, 6.56, 3.63, 0.36, "申赎匹配：建议月度开放、6 个月锁定期。", size=10.6, bold=True, color=MUTED, is_heading=True)
    right_ids = track_ids(s, n2)
    add_click_builds(s, [[(fig_ids, 0)], [(right_ids, 0)]])

    # -------------------------------------------------------------------------
    # P08｜章节过渡页 · 02 产品方案
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_section_slide(
        s, "02", "产品方案",
        "双股票池业绩布局、同业对比与机构落地条款",
        ["双池业绩", "行业分布", "同业对比", "容量与费率", "跟踪与说明"],
        page_no=8, accent=SAGE_DEEP,
    )

    # -------------------------------------------------------------------------
    # P09｜双池业绩与产品定位（左极简 4 线净值图 + 右无框双线大数字对比）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "02 产品方案", "同一套零调参逻辑跑通双池：大盘旗舰底仓 + 中盘卫星延展", 9)
    n1 = len(s.shapes)
    add_pic_fit(s, FIG_DIR / "11_dual_pool_product_nav.png", 0.58, 1.48, 7.65, 5.42)
    fig_ids = track_ids(s, n1)

    n2 = len(s.shapes)
    add_stat_item(s, 8.55, 1.56, 4.05, "旗舰主线 · 沪深300 M4（年化）", pct(hs_m4["ann_geom"]),
                  f"全期 {pct(hs_m4['cum_return'])} · 较 M0a +15.0pp · 夏普 {hs_m4['sharpe_arith_rf0']:.2f}", accent=TERRA_DEEP, val_size=32.0)
    add_tb(s, 8.55, 3.16, 4.05, 0.85,
           "大盘蓝筹池容量约为中证500 的 2.5–3 倍（3–5 亿低超限可行），主打 FOF 与机构稳健底仓配置。",
           size=11.4, color=STONE, line_spacing=1.34)
    top_ids = track_ids(s, n2)

    n3 = len(s.shapes)
    add_stat_item(s, 8.55, 4.24, 4.05, "卫星延展 · 中证500 M4（年化）", pct(zz_m4["ann_geom"]),
                  f"全期 {pct(zz_m4['cum_return'])} · 较 M0a +27.9pp · 金融 22.3%", accent=SAGE_DEEP, val_size=32.0)
    add_tb(s, 8.55, 5.84, 4.05, 0.90,
           "零调参平移即居全池 8 模型之首，较原始基准 M0a 回撤收窄 5.61pp，适合 1–2.5 亿中小盘分散配置。",
           size=11.4, color=STONE, line_spacing=1.34)
    bot_ids = track_ids(s, n3)
    add_click_builds(s, [[(fig_ids, 0)], [(top_ids, 0)], [(bot_ids, 0)]])

    # -------------------------------------------------------------------------
    # P10｜持仓行业分布（上图 + 底部无框双栏极细顶线短注）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "02 产品方案", "持仓行业分布：沪深300 金融低于纯价值 M2，中证500 仅 22.3%", 10)
    n1 = len(s.shapes)
    add_pic_fit(s, FIG_DIR / "07_industry_exposure_v3.png", 0.58, 1.44, 12.15, 3.92)
    fig_ids = track_ids(s, n1)

    n2 = len(s.shapes)
    add_editorial_note(
        s, 0.72, 5.48, 5.72, "沪深300：低于纯价值 M2、高于 M1",
        f"M4 金融占比（全期 {pct(goi('hs300_clean','M4')['finance_weight_full_mean'], False, 1)} / 末期 {pct(goi('hs300_clean','M4')['finance_weight_latest'], False, 1)}）低于纯价值 M2（48.2% / 66.0%），略高于含小市值的 M1（38.8%）。非金融集中在建筑、交运与机械；“未分类” 11.8% 系申万 45 天时效剔除回填所致。",
        accent=TERRA_DEEP, head_size=12.0, body_size=10.8,
    )
    add_editorial_note(
        s, 6.88, 5.48, 5.72, "中证500：行业均衡，专户可设单行业上限",
        f"中证500 M4 金融占比仅 {pct(goi('zz500','M4')['finance_weight_full_mean'], False, 1)}（末期 {pct(goi('zz500','M4')['finance_weight_latest'], False, 1)}），均匀分布在机械设备（7.0%）、公用事业（6.4%）、钢铁（6.4%）与交通运输（6.1%）。机构专户还可叠加单行业 ≤35% 约束。",
        accent=SAGE_DEEP, head_size=12.0, body_size=10.8,
    )
    note_ids = track_ids(s, n2)
    add_click_builds(s, [[(fig_ids, 0)], [(note_ids, 0)]])

    # -------------------------------------------------------------------------
    # P11｜市场同业对比（2×2 定位图 + 无竖线三线表 + 底部克制结语）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "02 产品方案", "大盘权益策略类型定位对比：低换手规则透明与回撤控制的平衡", 11)
    n1 = len(s.shapes)
    add_pic_fit(s, FIG_DIR / "12_peer_positioning_2x2.png", 0.55, 1.46, 5.80, 5.38)
    fig_ids = track_ids(s, n1)

    n2 = len(s.shapes)
    add_editorial_table(s, 6.52, 1.52, 6.09, 4.26,
        ["对比维度", "被动沪深300\n指数 ETF", "中高频量价\n指增私募", "主动价值红利\n公募基金", "本产品：沪深300\n价值低波 M4"],
        [
            ["收益与选股机制", "完全复制市值\n加权宽基指数", "多周期高频量价\n与机器学习", "基金经理主观\n基本面深度选股", "四因子等权打分\n+前75名保留缓冲"],
            ["典型费率结构", "管理+托管约\n0.15%+0.05%", "行业惯例约\n1.0%+20% 提成", "固定管理+托管\n约 1.20%+0.20%", "机构C档 0.60%+0.15%\n+15% 超额高水位"],
            ["换手与摩擦特征", "极低（仅随指数\n定期样本调整）", "年化单边换手\n常达数十倍", "偏低\n（主观中长期持有）", "单次单边 2.74%\n（年化单边约1.39倍）"],
            ["主要适用局限", "弱市承受完整\n指数回撤(-24.8%)", "依赖算力投入且受\n盘口流动性约束", "风格持续性受投研\n人员变更影响", "强成长牛市弹性\n弱于高贝塔策略"],
            ["核心配置定位", "低成本纯贝塔\n工具型配置", "高弹性超额\n进取型配置", "主观精选价值\n配置型产品", "规则透明可复现\n稳健防御型底仓"],
        ], font_size=8.5, highlight_rows={4}, col_widths=[1.04, 1.22, 1.30, 1.24, 1.29], left_align_cols={0})
    tbl_ids = track_ids(s, n2)

    n3 = len(s.shapes)
    add_rule(s, 6.52, 5.96, 6.09, 0.012, HAIRLINE)
    add_rule(s, 6.52, 5.96, 0.40, 0.026, SAGE_DEEP)
    add_tb(s, 6.52, 6.12, 6.09, 0.72,
           "在被动宽基 ETF、中高频量化指增与主动价值公募之间，M4 定位为规则白盒可复现、低摩擦损耗的大盘防御底仓。",
           size=11.5, bold=True, color=INK, line_spacing=1.32, is_heading=True)
    sum_ids = track_ids(s, n3)
    add_click_builds(s, [[(fig_ids, 0)], [(tbl_ids, 0)], [(sum_ids, 0)]])

    # -------------------------------------------------------------------------
    # P12｜流动性与规模执行情景（上图 + 底部无框双栏极细顶线短注）
    # -------------------------------------------------------------------------
    cs_5 = D["cap_s"][(D["cap_s"]["pool"] == "hs300") & (D["cap_s"]["aum_yi"] == 5.0)].iloc[0]
    cs_10 = D["cap_s"][(D["cap_s"]["pool"] == "hs300") & (D["cap_s"]["aum_yi"] == 10.0)].iloc[0]
    cs_15 = D["cap_s"][(D["cap_s"]["pool"] == "hs300") & (D["cap_s"]["aum_yi"] == 15.0)].iloc[0]
    s = prs.slides.add_slide(blank)
    add_header(s, "02 产品方案", "双池容量与多规模执行情景：沪深300 P10 容量约为中证500 的 3 倍", 12)
    n1 = len(s.shapes)
    add_pic_fit(s, FIG_DIR / "08_dual_pool_capacity_v3.png", 0.58, 1.44, 12.15, 3.92)
    fig_ids = track_ids(s, n1)

    n2 = len(s.shapes)
    add_editorial_note(
        s, 0.72, 5.48, 5.72, "3 亿与 5 亿元执行情景尾部超限核查",
        f"沪深300 M4 的 1日/假设3日拆单/5日清仓 5% P10 为 {cap_hs['p10_1d_5pct_yi']:.2f} / {cap_hs['p10_3d_5pct_yi']:.2f} / {cap_hs['p10_5d_liq_yi']:.2f} 亿元。3 亿情景下 3日拆单与 5日清仓均 0 期超限（单日调仓 15/184 期超限）；5 亿情景下单日 {int(cs_5['breach_1d_5pct_cnt'])}/184 期、假设 3 日拆单 {int(cs_5['breach_3d_5pct_cnt'])}/184 期、5 日清仓 {int(cs_5['breach_5d_liq_cnt'])}/185 期（最长 {cs_5['max_liq_days_5pct']:.3f} 天）超限。",
        accent=TERRA_DEEP, head_size=11.8, body_size=10.4,
    )
    add_editorial_note(
        s, 6.88, 5.48, 5.72, "10 亿与 15 亿元情景及拆单口径说明",
        f"10 亿元情景下假设 3 日拆单与 5 日清仓超限分别为 {int(cs_10['breach_3d_5pct_cnt'])}/184 期与 {int(cs_10['breach_5d_liq_cnt'])}/185 期；15 亿元情景下升至 {int(cs_15['breach_3d_5pct_cnt'])}/184 期与 {int(cs_15['breach_5d_liq_cnt'])}/185 期。主回测采用次日开盘集中撮合，多日拆单属独立执行情景，首期宜控制在 3–6 亿低超限情景并配合尾部拆单。",
        accent=OCHRE_DEEP, head_size=11.8, body_size=10.4,
    )
    note_ids = track_ids(s, n2)
    add_click_builds(s, [[(fig_ids, 0)], [(note_ids, 0)]])

    # -------------------------------------------------------------------------
    # P13｜费率结构与到手净值（左图 + 右极简三线表 + 无框说明）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_header(s, "02 产品方案", "四档高水位费率模拟：机构 C 档历史模拟费后年化 +10.39%", 13)
    n1 = len(s.shapes)
    add_pic_fit(s, FIG_DIR / "09_fee_net_nav_v3.png", 0.58, 1.46, 7.60, 5.42)
    fig_ids = track_ids(s, n1)

    n2 = len(s.shapes)
    add_editorial_table(s, 8.38, 1.62, 4.23, 2.95,
        ["方案", "固定+提成", "费后年化", "夏普"],
        [
            ["策略净值", "未扣产品费", pct(fee_hs.loc["Gross", "ann_geom"]), f"{fee_hs.loc['Gross','sharpe_arith_rf0']:.2f}"],
            ["A 标准", "1.2%+绝对20%", pct(fee_hs.loc["A", "ann_geom"]), f"{fee_hs.loc['A','sharpe_arith_rf0']:.2f}"],
            ["B 超额", "1.2%+超额20%", pct(fee_hs.loc["B", "ann_geom"]), f"{fee_hs.loc['B','sharpe_arith_rf0']:.2f}"],
            ["C 机构", "0.75%+超额15%", pct(fee_hs.loc["C", "ann_geom"]), f"{fee_hs.loc['C','sharpe_arith_rf0']:.2f}"],
            ["D 纯管", "1.7%+0%提成", pct(fee_hs.loc["D", "ann_geom"]), f"{fee_hs.loc['D','sharpe_arith_rf0']:.2f}"],
        ], font_size=9.8, highlight_rows={3}, col_widths=[0.95, 1.48, 1.05, 0.75])
    tbl_ids = track_ids(s, n2)

    n3 = len(s.shapes)
    add_editorial_note(
        s, 8.38, 4.86, 4.23, "费后拖累与逐年高水位结晶机制",
        f"机构 C 档（相对沪深300价格指数超额按年度高水位计提 15%）年化总费率拖累为 {fee_hs.loc['C','ann_fee_drag']*100:.2f} 个百分点（IR 0.73）。A、B 档排序由逐年结晶时点决定：2023 年末指数下跌使 B 档提前结晶扣减 0.0321 元（A 档仅 0.0038 元），缩减了 2024 年上涨行情的复利本金基数。",
        accent=SAGE_DEEP, head_size=12.0, body_size=10.4,
    )
    note_ids = track_ids(s, n3)
    add_click_builds(s, [[(fig_ids, 0)], [(tbl_ids, 0)], [(note_ids, 0)]])

    # -------------------------------------------------------------------------
    # P14｜雪球模拟跟踪与口径说明（左嵌真实归档截图 + 右平实局限说明）
    # -------------------------------------------------------------------------
    xv = D["xq_ver"]
    ib_rec = xv["initial_build_record"]
    snap_rec = xv["latest_archived_snapshot"]
    l1125 = D["live_1125"]["hs300"]
    s = prs.slides.add_slide(blank)
    add_header(s, "02 产品方案", "雪球公开组合归档运行凭证与三项研究边界说明", 14)

    n1 = len(s.shapes)
    add_tb(s, 0.72, 1.52, 5.70, 0.32, f"雪球公开组合 {xv['portfolio_code']} 归档凭证（披露至 {snap_rec['snapshot_date']}）", size=13.5, bold=True, color=INK, is_heading=True)
    live_img = M4_XQ / snap_rec["composite_screenshot_relpath"]
    add_soft_rect(s, 0.72, 1.94, 5.70, 3.38, fill_color=BG_PAPER, border_color=HAIRLINE, dashed=False)
    add_pic_fit(s, live_img, 0.78, 2.00, 5.58, 3.26)
    add_tb(s, 0.72, 5.42, 5.70, 1.48,
           f"组合于 {ib_rec['rebalance_timestamp'][:10]} 按 M0a 30 股分层（4%×10+3%×20）建仓，截至 {snap_rec['snapshot_date']} 归档净值 {snap_rec['unit_nav']:.4f}（累计 {pct(snap_rec['cum_return'])}，同期沪深300 {pct(snap_rec['benchmark_return'])}）；{l1125['signal_date']} 拟议切换单单边换手 {l1125['zh3689205_one_way_turnover_pct']:.2f}%，M4 正式生效日以平台调仓回执为准。50 股主回测（+56.58%）、30 股前 45 缓冲历史映射（+77.63%，换手 3.15%）与平台模拟严格分列。",
           size=10.1, color=STONE, line_spacing=1.30)
    left_ids = track_ids(s, n1)

    n2 = len(s.shapes)
    add_tb(s, 6.92, 1.52, 5.68, 0.32, "方法学边界与后续改进路线", size=13.5, bold=True, color=INK, is_heading=True)
    notes = [
        ("1. 历史留后区间与分段表现边界",
         "2025–2026.10 已参与方案讨论，全文统一界定为“历史留后区间”而非纯盲测。沪深300 上 M4 相对 M1 的收益优势集中在验证期（+39.54% 对 +32.47%），历史留后段落后于 M1（+12.21% 对 +14.07%）。",
         TERRA_DEEP, 2.02),
        ("2. 后复权含分红与价格指数股息差",
         "组合按后复权计算（含现金分红再投资），相对沪深300价格指数（不含分红）累计收益差为 +56.90 个百分点；按 2.5%–3.0% 年股息率扣减 10–12pp 仅为情景参考，精确超额需接入同起点全收益指数重算。",
         OCHRE_DEEP, 3.68),
        ("3. 后续工程升级方向",
         "下一步拟接入带披露时间戳的季度财报 Point-in-Time 数据库补充质量因子，并在机构定制专户中落地申万一级单行业 ≤35% 上限与换手惩罚二次规划（QP）优化器。",
         SAGE_DEEP, 5.34),
    ]
    for h, b, col, y in notes:
        add_editorial_note(s, 6.92, y, 5.68, h, b, accent=col, head_size=12.4, body_size=11.2)
    right_ids = track_ids(s, n2)
    add_click_builds(s, [[(left_ids, 0)], [(right_ids, 0)]])

    # -------------------------------------------------------------------------
    # P15｜致谢与交流（柔和暖燕麦收尾页，呼应章节页质感）
    # -------------------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    set_bg(s, BG_OAT)
    add_fade_transition(s, spd="med")
    add_tb(s, 0.72, 0.42, 6.0, 0.28, "沪深300 价值低波精选策略（M4）", size=10.2, color=MUTED, is_heading=True)
    add_tb(s, 11.4, 0.42, 1.21, 0.28, f"15 / {MAIN_TOTAL:02d}", size=10.2, color=MUTED, align=PP_ALIGN.RIGHT, force_serif=True)

    add_tb(s, 0.72, 2.05, 11.89, 0.92, "感谢各位老师聆听", size=42, bold=True, color=INK, align=PP_ALIGN.CENTER, is_heading=True)
    add_rule(s, 6.26, 3.16, 0.80, 0.036, TERRA)
    add_tb(s, 0.72, 3.42, 11.89, 0.45, "欢迎批评指正与提问交流", size=16.0, color=STONE, align=PP_ALIGN.CENTER)

    n1 = len(s.shapes)
    add_rule(s, 2.00, 4.48, 9.33, 0.012, HAIRLINE)
    add_tb(s, 1.50, 4.74, 10.33, 0.34, "李钰鹏 (2024104286)  ·  刘宇睿 (2024101054)  ·  张沐 (2024101056)  ·  张恒瑞 (2024101062)", size=12.2, bold=True, color=INK, align=PP_ALIGN.CENTER, is_heading=True)
    add_tb(s, 1.50, 5.18, 10.33, 0.32, "指导教师：肖亮海    |    雪球模拟组合：https://www.xueqiu.com/P/ZH3689205", size=11.0, color=STONE, align=PP_ALIGN.CENTER)
    add_tb(s, 1.50, 5.56, 10.33, 0.32, "GitHub 复现仓库：https://github.com/z2823253773-p/csi300-quant-strategy", size=11.0, bold=True, color=SAGE_DEEP, align=PP_ALIGN.CENTER, is_heading=True)
    add_rule(s, 2.00, 6.12, 9.33, 0.012, HAIRLINE)
    add_click_builds(s, [[(track_ids(s, n1), 0)]])

    prs.save(str(OUT_PPTX))
    pngs = export_pdf_and_pngs(OUT_PPTX, OUT_PDF, DECK_DIR, PREVIEW_DIR)
    print(f"主路演 15 页已生成: {OUT_PPTX} | PDF: {OUT_PDF} | 预览图: {len(pngs)} 张")


# =============================================================================
# 构建独立 5 页技术备查文档（技术备查_v3.pptx / .pdf）
# =============================================================================
def build_appendix_deck(D: dict):
    m3, xq_bt = D["m3"], D["xq_bt"]

    def gm(exp, mod, st="all", fee="net_10bp"):
        return m3[(m3["experiment"] == exp) & (m3["model"] == mod) & (m3["stage"] == st) & (m3["fee_scenario"] == fee)].iloc[0]

    hs_m1 = gm("hs300_clean", "M1")
    hs_m1_015 = gm("hs300_full", "M1")

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]
    ft = "技术备查材料（独立附呈）  ·  沪深300 价值低波精选策略（M4）"

    # A1: 数据工程与防前视处理
    s = prs.slides.add_slide(blank)
    add_header(s, "技术备查 A1", "双股票池动态成分与开盘撮合：阻断四类隐蔽前视偏差", 1, APP_TOTAL, footer_text=ft)
    pillars = [
        ("01 分项署源与动态成分池", "Tushare 提供个股行情、估值、换手、复权与逐日 ST 状态；94 期月度动态成分（沪深300 共 520 股、中证500 共 1,107 股）、申万行业历史与双指数沿用核验后的历史输入，消除幸存者偏差。", OCHRE_DEEP),
        ("02 时效约束与停牌不前填", "剔除证监会行业事后回填，限定申万一级行业 45 天时效、估值 90 天龄期上限；所有因子在滚动计算前先屏蔽停牌日，禁止前向填充停牌价伪造低波信号。", TERRA_DEEP),
        ("03 开盘瞬间无前视撮合", "摒弃依赖收盘价的涨跌停判定；仅凭开盘交易状态、开盘报价与逐日 ST 标记（修复历史全局 ST 标记漏洞），按 19.5% / 4.5% / 9.5% 阈值实时判触限。", SAGE_DEEP),
    ]
    for i, (h, b, col) in enumerate(pillars):
        add_editorial_note(s, 0.72 + i * 4.10, 1.65, 3.68, h, b, accent=col, head_size=13.5, body_size=11.6)
    add_editorial_note(
        s, 0.72, 4.92, 5.72, "首日开盘进场口径对齐",
        "2023-01-09 基准同步改为开盘至收盘收益（+0.36%），沪深300 价格指数全期精确为 -0.33%，中证500 为 +3.94%。",
        accent=OCHRE_DEEP, head_size=12.4, body_size=11.2,
    )
    add_editorial_note(
        s, 6.88, 4.92, 5.72, "账本闭合与双实现独立复算",
        "63 组账户全程无负现金、账本残差 0.0；两套独立实现交叉复算，14 项核心账户精确对齐（另单列中证500 M0b 0.12pp 修订差）。",
        accent=SAGE_DEEP, head_size=12.4, body_size=11.2,
    )

    # A2: 101 候选因子重筛与改造 new012
    s = prs.slides.add_slide(blank)
    add_header(s, "技术备查 A2", "101 候选因子重筛与改造 new012：双池三段单因子 5 日 Rank IC", 2, APP_TOTAL, footer_text=ft)
    add_pic_fit(s, FIG_DIR / "05_factor_ic_and_new012.png", 0.58, 1.44, 12.15, 3.92)
    add_editorial_note(
        s, 0.72, 5.48, 5.72, "101 候选因子全量重筛",
        "两池各运行 101 个本地实现编号（只用训练期选因子并做 Holm 多重检验校正）；沪深300 入选 040/006/015（015 验证覆盖仅 52.4%），中证500 入选 040/013/044。",
        accent=OCHRE_DEEP, head_size=12.0, body_size=10.8,
    )
    add_editorial_note(
        s, 6.88, 5.48, 5.72, "改造 new012_amt_ema10 检验",
        "同步改进价差尺度、量能代理与 10 日平滑后，双池三段单因子 IC 均为正；但扣费组合层面仅沪深300 M3b 较 M2 增厚 +8.58pp，中证500 同配方为 -6.93pp。",
        accent=TERRA_DEEP, head_size=12.0, body_size=10.8,
    )

    # A3: Alpha015 低覆盖约束排查
    s = prs.slides.add_slide(blank)
    add_header(s, "技术备查 A3", "Alpha015 低覆盖约束排查：区分同池打分与入池过滤影响", 3, APP_TOTAL, footer_text=ft)
    add_pic_fit(s, FIG_DIR / "03_015_coverage_diagnosis.png", 0.58, 1.46, 8.20, 5.42)
    add_stat_item(s, 9.05, 1.58, 3.55, "95.1% 退出席位归因", "3,605 / 3,789", "M1(含015) 后续调仓退出，仅因 015 缺失", accent=BRICK, val_size=28.0)
    add_stat_item(s, 9.05, 3.20, 3.55, "解除 015 约束后跃升", f"{pct(hs_m1_015['cum_return'])} → {pct(hs_m1['cum_return'])}", "单次单边换手 41.91% → 2.35%", accent=SAGE_DEEP, val_size=22.0)
    add_editorial_note(
        s, 9.05, 4.90, 3.55, "解耦说明",
        "解除约束后毛收益由 +27.58% 升至 +53.41%，说明持股被迫变动与摩擦同时造成损耗。M3a(-1.83%) 对比 M1(含015)(-3.44%) 测打分增量（+1.62pp）；两套 M1 对比测覆盖约束影响。",
        accent=OCHRE_DEEP, head_size=12.2, body_size=10.8,
    )

    # A4: 雪球 30 只历史映射跟踪回测
    s = prs.slides.add_slide(blank)
    add_header(s, "技术备查 A4", "雪球模拟组合 30 只分层权重历史映射：独立前 45 缓冲压降换手超一半", 4, APP_TOTAL, footer_text=ft)
    add_pic_fit(s, FIG_DIR / "10_xueqiu_30_tracking_v3.png", 0.58, 1.44, 12.15, 3.92)
    xq_m4 = xq_bt[(xq_bt["base_model"] == "hs300_M4_clean") & (xq_bt["stage"] == "all") & (xq_bt["fee_scenario"] == "net_10bp")].set_index("mapping_scheme")
    add_editorial_note(
        s, 0.72, 5.48, 5.72, "独立前 45 缓冲的效果",
        f"雪球限 30 只且仅支持整数权重（前10×4%+后20×3%）；直接硬截断会使单次单边换手反弹至 {pct(xq_m4.loc['xq30_trunc_tiered','mean_half_turn'], False)}，独立设前 45 缓冲后压回 {pct(xq_m4.loc['xq30_buf45_tiered','mean_half_turn'], False)}，日相关 {xq_m4.loc['xq30_buf45_tiered','daily_corr_vs_top50']:.4f}、年化 TE {pct(xq_m4.loc['xq30_buf45_tiered','tracking_error_vs_top50'], False)}。",
        accent=TERRA_DEEP, head_size=12.0, body_size=10.8,
    )
    add_editorial_note(
        s, 6.88, 5.48, 5.72, "历史映射与模拟跟踪分列",
        "雪球 30 股的 +77.63% 属于历史映射回测，10 月末持仓属历史目标；团队以 50 只原策略（+56.58%，IR 0.8748）为正式对外主口径，11 月起模拟记录按启用日期分列。",
        accent=SAGE_DEEP, head_size=12.0, body_size=10.8,
    )

    # A5: 15 行双池完整消融与双印花税精确对账表
    s = prs.slides.add_slide(blank)
    add_header(s, "技术备查 A5", "双池完整消融与双印花税情景（固定 10bp vs 减半 5bp）对账表", 5, APP_TOTAL, footer_text=ft)
    rows_b = []
    specs = [
        ("hs300_clean", "M1", "沪深300(干净) M1"),
        ("hs300_clean", "M2", "沪深300(干净) M2"),
        ("hs300_clean", "M3b", "沪深300(干净) M3b"),
        ("hs300_clean", "M4", "沪深300(旗舰) M4"),
        ("hs300_clean", "M5", "沪深300(干净) M5"),
        ("hs300_full", "M0a", "沪深300(锚) M0a"),
        ("hs300_full", "M0b", "沪深300(反例) M0b"),
        ("zz500", "M0a", "中证500 M0a"),
        ("zz500", "M0b", "中证500 M0b"),
        ("zz500", "M1", "中证500 M1"),
        ("zz500", "M2", "中证500 M2"),
        ("zz500", "M3a", "中证500 M3a"),
        ("zz500", "M3b", "中证500 M3b"),
        ("zz500", "M4", "中证500(最优) M4"),
        ("zz500", "M5", "中证500 M5"),
    ]
    for exp, mod, lbl in specs:
        a = gm(exp, mod, "all", "net_10bp")
        ht = gm(exp, mod, "all", "net_histtax")
        gr = gm(exp, mod, "all", "gross")
        v = gm(exp, mod, "validation", "net_10bp")
        sn = gm(exp, mod, "seen", "net_10bp")
        rows_b.append([
            lbl, pct(gr["cum_return"]), pct(a["cum_return"]), pct(ht["cum_return"]),
            pct(v["cum_return"]), pct(sn["cum_return"]),
            f"{a['sharpe_arith_rf0']:.3f} / {a['geom_over_vol']:.3f}",
            pct(a["max_drawdown"], False), pct(a["mean_half_turn"], False),
        ])
    add_editorial_table(s, 0.72, 1.50, 11.89, 5.42,
        ["池与模型", "毛收益", "净(10bp)", "历史税(5bp)", "验证(23-24)", "后段(25-26)", "夏普/几何波比", "最大回撤", "单次换手"],
        rows_b, font_size=9.1, highlight_rows={3, 13},
        col_widths=[2.02, 1.12, 1.15, 1.22, 1.22, 1.22, 1.66, 1.14, 1.14])

    prs.save(str(APP_PPTX))
    pngs = export_pdf_and_pngs(APP_PPTX, APP_PDF, DECK_DIR, PREVIEW_APP_DIR)
    print(f"独立备查 5 页已生成: {APP_PPTX} | PDF: {APP_PDF} | 预览图: {len(pngs)} 张")


def main():
    D = load_v3()
    build_main_deck(D)
    build_appendix_deck(D)


if __name__ == "__main__":
    main()
