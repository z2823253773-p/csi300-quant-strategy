#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build REPORT_FINAL.docx and REPORT_FINAL.pdf from REPORT_FINAL.md."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import docx
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor
from pypdf import PdfReader

NAVY_HEX = "14284B"
ACCENT_HEX = "C23B22"
MUTED_HEX = "5A6472"
BORDER_LIGHT_HEX = "D0D7DE"
HEADER_BG_HEX = "F4F6F9"

NAVY = RGBColor(0x14, 0x28, 0x4B)
ACCENT = RGBColor(0xC2, 0x3B, 0x22)
MUTED = RGBColor(0x5A, 0x64, 0x72)
DARK_TEXT = RGBColor(0x1F, 0x23, 0x28)

FONT_CN_BODY = "Songti SC"
FONT_CN_HEAD = "PingFang SC"
FONT_EN = "Times New Roman"


def set_run_font(
    run,
    cn_font: str = FONT_CN_BODY,
    en_font: str = FONT_EN,
    size_pt: Optional[float] = None,
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    color: Optional[RGBColor] = None,
) -> None:
    """Apply East Asian and ASCII fonts plus optional typography attributes."""
    run.font.name = en_font
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), en_font)
    rFonts.set(qn("w:hAnsi"), en_font)
    rFonts.set(qn("w:cs"), en_font)
    rFonts.set(qn("w:eastAsia"), cn_font)
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def set_style_font(
    style,
    cn_font: str,
    en_font: str,
    size_pt: float,
    bold: bool = False,
    color: Optional[RGBColor] = None,
    line_spacing: Optional[float] = None,
    space_before: Optional[float] = None,
    space_after: Optional[float] = None,
) -> None:
    """Configure a Word style with East Asian/ASCII fonts and spacing."""
    style.font.name = en_font
    style.font.size = Pt(size_pt)
    style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color
    rPr = style._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), en_font)
    rFonts.set(qn("w:hAnsi"), en_font)
    rFonts.set(qn("w:cs"), en_font)
    rFonts.set(qn("w:eastAsia"), cn_font)

    pf = style.paragraph_format
    if line_spacing is not None:
        if line_spacing > 5:
            pf.line_spacing_rule = WD_LINE_SPACING.AT_LEAST
            pf.line_spacing = Pt(line_spacing)
        else:
            pf.line_spacing = line_spacing
    if space_before is not None:
        pf.space_before = Pt(space_before)
    if space_after is not None:
        pf.space_after = Pt(space_after)


def ensure_style(doc: Document, name: str, base_name: str = "Normal"):
    """Fetch an existing paragraph style or create one inheriting from base."""
    styles = doc.styles
    if name in styles:
        return styles[name]
    s = styles.add_style(name, docx.enum.style.WD_STYLE_TYPE.PARAGRAPH)
    if base_name in styles:
        s.base_style = styles[base_name]
    return s


def create_reference_docx(ref_path: Path) -> None:
    """Generate the pandoc reference.docx template matching PLAN 4 & 5.1."""
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.55)
    sec.bottom_margin = Cm(2.55)
    sec.left_margin = Cm(2.55)
    sec.right_margin = Cm(2.55)

    for sname in ["Normal", "Body Text", "First Paragraph", "Compact", "Block Text"]:
        st = ensure_style(doc, sname, "Normal")
        set_style_font(
            st,
            cn_font=FONT_CN_BODY,
            en_font=FONT_EN,
            size_pt=12.0,
            bold=False,
            color=DARK_TEXT,
            line_spacing=1.5,
            space_before=0.0,
            space_after=0.0,
        )
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    h1 = ensure_style(doc, "Heading 1", "Normal")
    set_style_font(
        h1,
        cn_font=FONT_CN_HEAD,
        en_font=FONT_EN,
        size_pt=15.0,
        bold=True,
        color=NAVY,
        line_spacing=1.25,
        space_before=8.0,
        space_after=2.0,
    )
    h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    h1.paragraph_format.keep_with_next = True

    h2 = ensure_style(doc, "Heading 2", "Normal")
    set_style_font(
        h2,
        cn_font=FONT_CN_HEAD,
        en_font=FONT_EN,
        size_pt=13.0,
        bold=True,
        color=NAVY,
        line_spacing=1.2,
        space_before=6.0,
        space_after=2.0,
    )
    h2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    h2.paragraph_format.keep_with_next = True

    h3 = ensure_style(doc, "Heading 3", "Normal")
    set_style_font(
        h3,
        cn_font=FONT_CN_HEAD,
        en_font=FONT_EN,
        size_pt=12.0,
        bold=True,
        color=NAVY,
        line_spacing=1.3,
        space_before=8.0,
        space_after=2.0,
    )
    h3.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    h3.paragraph_format.keep_with_next = True

    for cname in ["Caption", "Image Caption", "Table Caption"]:
        cs = ensure_style(doc, cname, "Normal")
        set_style_font(
            cs,
            cn_font=FONT_CN_HEAD if cname == "Table Caption" else FONT_CN_BODY,
            en_font=FONT_EN,
            size_pt=10.5,
            bold=(cname == "Table Caption"),
            color=NAVY if cname == "Table Caption" else MUTED,
            line_spacing=1.2,
            space_before=4.0,
            space_after=4.0,
        )
        cs.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    fn = ensure_style(doc, "Footnote Text", "Normal")
    set_style_font(
        fn,
        cn_font=FONT_CN_BODY,
        en_font=FONT_EN,
        size_pt=9.5,
        bold=False,
        color=MUTED,
        line_spacing=1.2,
        space_before=0.0,
        space_after=2.0,
    )
    fn.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    bq = ensure_style(doc, "Block Quote", "Normal")
    set_style_font(
        bq,
        cn_font=FONT_CN_BODY,
        en_font=FONT_EN,
        size_pt=11.0,
        bold=False,
        color=MUTED,
        line_spacing=1.35,
        space_before=4.0,
        space_after=6.0,
    )
    bq.paragraph_format.left_indent = Cm(0.8)

    for cf in ["CaptionedFigure", "Captioned Figure"]:
        cfs = ensure_style(doc, cf, "Normal")
        cfs.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        cfs.paragraph_format.line_spacing = 1.0
        cfs.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    ref_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(ref_path)


def parse_cover_and_prepare_md(
    md_text: str, report_dir: Path, member4_dir: Path
) -> Tuple[Dict[str, str], List[List[str]], str]:
    """Extract cover metadata and rewrite image paths for pandoc."""
    meta: Dict[str, str] = {}
    team_rows: List[List[str]] = []

    cover_match = re.search(
        r":::\s*\{\.cover-block\}\s*(.*?)\s*:::\s*(?:---\s*)?",
        md_text,
        flags=re.DOTALL,
    )
    body_md = md_text
    if cover_match:
        cover_raw = cover_match.group(1)
        body_md = md_text[cover_match.end():].lstrip()
        for line in cover_raw.splitlines():
            m = re.match(r"^\*\*(.+?)\*\*[：:]\s*(.+)$", line.strip())
            if m:
                meta[m.group(1).strip()] = m.group(2).strip()
            elif line.strip().startswith("|") and not re.match(r"^\|[\s\-|]+\|$", line.strip()):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if cells and cells[0] != "组员序号":
                    team_rows.append(cells)

    # Resolve image links: check existence; if missing, emit placeholder notice.
    def _img_repl(match: re.Match) -> str:
        alt = match.group(1)
        rel = match.group(2).strip()
        cand = (report_dir / rel).resolve()
        if cand.exists():
            return f"![{alt}]({cand})"
        # Check under member4/figures/report_v3/ or report/ by basename
        for sub_fig in ("report_v3", "report"):
            alt_cand = member4_dir / "figures" / sub_fig / Path(rel).name
            if alt_cand.exists():
                return f"![{alt}]({alt_cand.resolve()})"
        return f"\n> **【图表占位 — {alt}】**（待生成图像文件：`{rel}`）\n"

    body_md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _img_repl, body_md)

    # Auto-embed Xueqiu screenshots if present in member4/xueqiu/screenshots/
    xq_dir = member4_dir / "xueqiu" / "screenshots"
    xq_imgs = sorted(
        p for p in xq_dir.glob("*") if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ) if xq_dir.exists() else []
    if xq_imgs:
        xq_block = "\n\n".join(
            f"![雪球模拟组合实盘运行截图（{p.name}）]({p.resolve()})" for p in xq_imgs
        )
    else:
        xq_block = "> **【雪球实盘净值截图待接入】**（在雪球创建公开组合并运行后，将净值截图放入 `member4/xueqiu/screenshots/`，重新运行 `code/build_report.py` 即可自动嵌入此处。）"
    body_md = body_md.replace("<!-- XUEQIU_SCREENSHOT_PLACEHOLDER -->", xq_block)

    # Remove top-level horizontal rules "---" used solely as chapter separators so Word pages stay clean
    body_md = re.sub(r"\n---\s*\n", "\n\n", body_md)
    return meta, team_rows, body_md


def set_cell_margins(cell, top=40, bottom=40, left=90, right=90) -> None:
    """Set XML cell padding in twips/dxa."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = tcPr.find(qn("w:tcMar"))
    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)
    for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = tcMar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tcMar.append(node)
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")


def set_cell_shading(cell, fill_hex: str) -> None:
    """Apply background shading to a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    old = tcPr.find(qn("w:shd"))
    if old is not None:
        tcPr.remove(old)
    tcPr.append(shd)


def set_row_borders(row, top=None, bottom=None) -> None:
    """Set top/bottom borders on every cell of a row, clearing left/right/inside."""
    for cell in row.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        tcBorders = tcPr.find(qn("w:tcBorders"))
        if tcBorders is not None:
            tcPr.remove(tcBorders)
        tcBorders = OxmlElement("w:tcBorders")
        for edge, spec in [("top", top), ("bottom", bottom), ("left", None), ("right", None)]:
            el = OxmlElement(f"w:{edge}")
            if spec is None:
                el.set(qn("w:val"), "none")
            else:
                val, sz, color = spec
                el.set(qn("w:val"), val)
                el.set(qn("w:sz"), str(sz))
                el.set(qn("w:space"), "0")
                el.set(qn("w:color"), color)
            tcBorders.append(el)
        tcPr.append(tcBorders)


def style_three_line_table(table, font_size: float = 9.5, header_bg: str = HEADER_BG_HEX) -> None:
    """Apply academic three-line table formatting (#14284B rules, no vertical lines)."""
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    tblPr = table._tbl.tblPr
    total_w = 9015  # 15.9 cm in dxa
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is not None:
        tblPr.remove(tblW)
    tblPr.append(parse_xml(f'<w:tblW {nsdecls("w")} w:w="{total_w}" w:type="dxa"/>'))
    tblLayout = tblPr.find(qn("w:tblLayout"))
    if tblLayout is not None:
        tblPr.remove(tblLayout)
    tblLayout = parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>')
    tblPr.append(tblLayout)

    tblBorders = tblPr.find(qn("w:tblBorders"))
    if tblBorders is not None:
        tblPr.remove(tblBorders)
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="12" w:space="0" w:color="{NAVY_HEX}"/>'
        f'<w:bottom w:val="single" w:sz="12" w:space="0" w:color="{NAVY_HEX}"/>'
        f'<w:left w:val="none"/><w:right w:val="none"/>'
        f'<w:insideH w:val="none"/><w:insideV w:val="none"/>'
        f"</w:tblBorders>"
    )
    tblPr.append(tblBorders)

    # Compute content-aware column widths (dxa) so formulas/codes never clip
    n_cols = len(table.columns)
    col_scores = [4.0] * n_cols
    for r_idx, row in enumerate(table.rows):
        for c_idx in range(min(n_cols, len(row.cells))):
            txt = row.cells[c_idx].text.strip()
            # Count East Asian chars as ~1.8 width, ASCII as 1.0, math slightly wider
            w_score = sum(1.8 if ord(ch) > 127 else 1.0 for ch in txt)
            if r_idx == 0:
                w_score = max(w_score * 0.8, 5.0)
            col_scores[c_idx] = max(col_scores[c_idx], min(w_score, 48.0))
    sum_scores = sum(col_scores) or 1.0
    col_widths = [max(int(total_w * (s / sum_scores)), 720) for s in col_scores]
    diff_w = total_w - sum(col_widths)
    col_widths[col_widths.index(max(col_widths))] += diff_w

    tblGrid = table._tbl.find(qn("w:tblGrid"))
    if tblGrid is not None:
        for c_idx, gc in enumerate(tblGrid.findall(qn("w:gridCol"))):
            if c_idx < len(col_widths):
                gc.set(qn("w:w"), str(col_widths[c_idx]))

    n_rows = len(table.rows)
    for r_idx, row in enumerate(table.rows):
        trPr = row._tr.get_or_add_trPr()
        if trPr.find(qn("w:cantSplit")) is None:
            trPr.append(OxmlElement("w:cantSplit"))
        if r_idx == 0 and trPr.find(qn("w:tblHeader")) is None:
            trPr.append(OxmlElement("w:tblHeader"))

        top_b = ("single", 12, NAVY_HEX) if r_idx == 0 else None
        bot_b = (
            ("single", 6, NAVY_HEX)
            if r_idx == 0 and n_rows > 1
            else (("single", 12, NAVY_HEX) if r_idx == n_rows - 1 else None)
        )
        set_row_borders(row, top=top_b, bottom=bot_b)

        for c_idx, cell in enumerate(row.cells):
            tcPr = cell._tc.get_or_add_tcPr()
            tcW = tcPr.find(qn("w:tcW"))
            if tcW is not None:
                tcPr.remove(tcW)
            if c_idx < len(col_widths):
                tcPr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{col_widths[c_idx]}" w:type="dxa"/>'))
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell, top=28, bottom=28, left=60, right=60)
            if r_idx == 0 and header_bg:
                set_cell_shading(cell, header_bg)
            for p in cell.paragraphs:
                if p.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY or p.alignment is None:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(1)
                for run in p.runs:
                    set_run_font(
                        run,
                        cn_font=FONT_CN_HEAD if r_idx == 0 else FONT_CN_BODY,
                        en_font=FONT_EN,
                        size_pt=font_size,
                        bold=True if r_idx == 0 else run.bold,
                        color=NAVY if r_idx == 0 else DARK_TEXT,
                    )


def add_field(run, field_text: str) -> None:
    """Append a Word XML field (e.g. PAGE, NUMPAGES) to a run."""
    fld_begin = parse_xml(r'<w:fldChar %s w:fldCharType="begin"/>' % nsdecls("w"))
    instr = parse_xml(r'<w:instrText %s xml:space="preserve"> %s </w:instrText>' % (nsdecls("w"), field_text))
    fld_sep = parse_xml(r'<w:fldChar %s w:fldCharType="separate"/>' % nsdecls("w"))
    fld_end = parse_xml(r'<w:fldChar %s w:fldCharType="end"/>' % nsdecls("w"))
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(fld_end)


def configure_headers_footers(doc: Document) -> None:
    """Configure running header and page-number footer (hidden on cover page)."""
    for sec in doc.sections:
        sec.different_first_page_header_footer = True
        sec.top_margin = Cm(2.55)
        sec.bottom_margin = Cm(2.55)
        sec.left_margin = Cm(2.55)
        sec.right_margin = Cm(2.55)

        hdr = sec.header
        hp = hdr.paragraphs[0] if hdr.paragraphs else hdr.add_paragraph()
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hp.paragraph_format.space_after = Pt(2)
        hrun = hp.add_run("沪深300价值低波多因子量化策略研究与产品化设计")
        set_run_font(hrun, cn_font=FONT_CN_BODY, en_font=FONT_EN, size_pt=9.0, color=MUTED)
        pPr = hp._p.get_or_add_pPr()
        pBdr = parse_xml(
            f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="4" w:space="4" w:color="{BORDER_LIGHT_HEX}"/></w:pBdr>'
        )
        pPr.append(pBdr)

        ftr = sec.footer
        fp = ftr.paragraphs[0] if ftr.paragraphs else ftr.add_paragraph()
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.paragraph_format.space_before = Pt(2)
        pPr_f = fp._p.get_or_add_pPr()
        pBdr_f = parse_xml(
            f'<w:pBdr {nsdecls("w")}><w:top w:val="single" w:sz="4" w:space="4" w:color="{BORDER_LIGHT_HEX}"/></w:pBdr>'
        )
        pPr_f.append(pBdr_f)

        r1 = fp.add_run("第 ")
        set_run_font(r1, cn_font=FONT_CN_BODY, en_font=FONT_EN, size_pt=9.0, color=MUTED)
        r_pg = fp.add_run()
        set_run_font(r_pg, cn_font=FONT_CN_BODY, en_font=FONT_EN, size_pt=9.0, color=MUTED)
        add_field(r_pg, "PAGE")
        r2 = fp.add_run(" 页 / 共 ")
        set_run_font(r2, cn_font=FONT_CN_BODY, en_font=FONT_EN, size_pt=9.0, color=MUTED)
        r_num = fp.add_run()
        set_run_font(r_num, cn_font=FONT_CN_BODY, en_font=FONT_EN, size_pt=9.0, color=MUTED)
        add_field(r_num, "NUMPAGES")
        r3 = fp.add_run(" 页")
        set_run_font(r3, cn_font=FONT_CN_BODY, en_font=FONT_EN, size_pt=9.0, color=MUTED)


def make_paragraph_element(
    doc: Document,
    text: str = "",
    align: WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH.LEFT,
    cn_font: str = FONT_CN_BODY,
    en_font: str = FONT_EN,
    size_pt: float = 12.0,
    bold: bool = False,
    italic: bool = False,
    color: RGBColor = DARK_TEXT,
    space_before: float = 0.0,
    space_after: float = 4.0,
    line_spacing: float = 1.15,
) -> docx.text.paragraph.Paragraph:
    """Create a standalone paragraph attached to doc and return it."""
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    if text:
        r = p.add_run(text)
        set_run_font(
            r,
            cn_font=cn_font,
            en_font=en_font,
            size_pt=size_pt,
            bold=bold,
            italic=italic,
            color=color,
        )
    return p


def build_front_matter_elements(
    doc: Document,
    meta: Dict[str, str],
    team_rows: List[List[str]],
    toc_entries: List[Tuple[int, str, Optional[int]]],
) -> List[OxmlElement]:
    """Create cover page + TOC page XML elements (detached from end, ready to prepend)."""
    front_els: List[OxmlElement] = []

    def track_p(p):
        el = p._p
        el.getparent().remove(el)
        front_els.append(el)

    def track_tbl(t):
        el = t._tbl
        el.getparent().remove(el)
        front_els.append(el)

    # Top accent bar on cover
    p_bar = make_paragraph_element(doc, "", space_before=0, space_after=18)
    pPr = p_bar._p.get_or_add_pPr()
    pPr.append(
        parse_xml(
            f'<w:pBdr {nsdecls("w")}><w:top w:val="single" w:sz="36" w:space="6" w:color="{NAVY_HEX}"/></w:pBdr>'
        )
    )
    track_p(p_bar)

    course = meta.get("课程全称", "【待填：课程全称】")
    p_course = make_paragraph_element(
        doc,
        course,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        cn_font=FONT_CN_HEAD,
        size_pt=13.5,
        bold=True,
        color=MUTED,
        space_before=12,
        space_after=24,
    )
    track_p(p_course)

    title = meta.get("报告题目", "沪深300价值低波多因子量化策略研究与产品化设计")
    if title in ("沪深300价值精选量化多因子策略研究与产品化设计", "沪深300价值低波多因子量化策略研究与产品化设计"):
        title = title.replace("研究与产品化设计", "\n研究与产品化设计")
    p_title = make_paragraph_element(
        doc,
        title,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        cn_font=FONT_CN_HEAD,
        size_pt=22.0,
        bold=True,
        color=NAVY,
        space_before=6,
        space_after=10,
        line_spacing=1.25,
    )
    track_p(p_title)

    strat = meta.get("策略名称", "沪深300价值精选量化策略（CSI 300 Value-Select Quantitative Strategy）")
    p_sub = make_paragraph_element(
        doc,
        strat,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        cn_font=FONT_CN_BODY,
        size_pt=12.0,
        italic=False,
        color=RGBColor(0xA3, 0x8F, 0x6E),
        space_before=0,
        space_after=20,
    )
    pPr_sub = p_sub._p.get_or_add_pPr()
    pPr_sub.append(
        parse_xml(
            f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="12" w:space="12" w:color="{NAVY_HEX}"/></w:pBdr>'
        )
    )
    track_p(p_sub)

    p_team_lbl = make_paragraph_element(
        doc,
        "研究团队成员与职责分工",
        align=WD_ALIGN_PARAGRAPH.LEFT,
        cn_font=FONT_CN_HEAD,
        size_pt=11.5,
        bold=True,
        color=NAVY,
        space_before=16,
        space_after=6,
    )
    track_p(p_team_lbl)

    if team_rows:
        tbl = doc.add_table(rows=1 + len(team_rows), cols=5)
        headers = ["组员", "姓名", "学号", "核心模块与职责定位", "交付目录"]
        for c_i, h in enumerate(headers):
            tbl.rows[0].cells[c_i].text = h
        for r_i, rdata in enumerate(team_rows, start=1):
            for c_i in range(min(5, len(rdata))):
                tbl.rows[r_i].cells[c_i].text = rdata[c_i].replace("`", "")
        style_three_line_table(tbl, font_size=9.5, header_bg=HEADER_BG_HEX)
        # 显式列宽确保 10 位学号与姓名绝不折行
        col_widths_cm = [1.55, 1.65, 2.55, 6.45, 3.70]
        for row in tbl.rows:
            for c_i, w_cm in enumerate(col_widths_cm):
                row.cells[c_i].width = Cm(w_cm)
        track_tbl(tbl)

    # Additional cover metadata table/lines
    meta_keys = ["角色定位", "指导教师", "提交日期", "代码仓库", "雪球模拟组合"]
    p_sp = make_paragraph_element(doc, "", space_before=14, space_after=4)
    track_p(p_sp)
    for k in meta_keys:
        if k in meta:
            pm = doc.add_paragraph()
            pm.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pm.paragraph_format.space_before = Pt(3)
            pm.paragraph_format.space_after = Pt(3)
            pm.paragraph_format.line_spacing = 1.35
            rk = pm.add_run(f"{k}：")
            set_run_font(rk, cn_font=FONT_CN_HEAD, size_pt=11.0, bold=True, color=NAVY)
            val = meta[k]
            rv = pm.add_run(val)
            is_ph = "【待填" in val
            set_run_font(
                rv,
                cn_font=FONT_CN_BODY,
                size_pt=11.0,
                bold=is_ph,
                color=ACCENT if is_ph else DARK_TEXT,
            )
            track_p(pm)

    # TOC page (starts on new page cleanly without risking trailing blank page)
    p_toc_title = make_paragraph_element(
        doc,
        "目  录",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        cn_font=FONT_CN_HEAD,
        size_pt=15.0,
        bold=True,
        color=NAVY,
        space_before=0,
        space_after=8,
    )
    p_toc_title.paragraph_format.page_break_before = True
    track_p(p_toc_title)

    if toc_entries:
        toc_tbl = doc.add_table(rows=len(toc_entries), cols=2)
        toc_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        toc_tbl.autofit = False
        tblPr = toc_tbl._tbl.tblPr
        tblPr.append(parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>'))
        tblBorders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="single" w:sz="8" w:space="0" w:color="{NAVY_HEX}"/>'
            f'<w:bottom w:val="single" w:sz="8" w:space="0" w:color="{NAVY_HEX}"/>'
            f'<w:left w:val="none"/><w:right w:val="none"/>'
            f'<w:insideH w:val="dotted" w:sz="4" w:space="0" w:color="{BORDER_LIGHT_HEX}"/>'
            f'<w:insideV w:val="none"/>'
            f"</w:tblBorders>"
        )
        tblPr.append(tblBorders)
        for idx, (lvl, title_txt, pg_no) in enumerate(toc_entries):
            row = toc_tbl.rows[idx]
            c0, c1 = row.cells[0], row.cells[1]
            c0.width = Cm(14.9)
            c1.width = Cm(1.0)
            set_cell_margins(c0, top=6, bottom=6, left=20, right=10)
            set_cell_margins(c1, top=6, bottom=6, left=6, right=20)
            p0 = c0.paragraphs[0]
            p0.paragraph_format.space_before = Pt(0)
            p0.paragraph_format.space_after = Pt(0)
            p0.paragraph_format.line_spacing = 1.1
            p0.paragraph_format.left_indent = Cm(0.0 if lvl == 1 else 0.5)
            r0 = p0.add_run(title_txt)
            set_run_font(
                r0,
                cn_font=FONT_CN_HEAD if lvl == 1 else FONT_CN_BODY,
                size_pt=9.6 if lvl == 1 else 8.8,
                bold=(lvl == 1),
                color=NAVY if lvl == 1 else DARK_TEXT,
            )
            p1 = c1.paragraphs[0]
            p1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p1.paragraph_format.space_before = Pt(0)
            p1.paragraph_format.space_after = Pt(0)
            p1.paragraph_format.line_spacing = 1.1
            r1 = p1.add_run(str(pg_no) if pg_no is not None else "—")
            set_run_font(
                r1,
                cn_font=FONT_CN_BODY,
                size_pt=9.0,
                bold=(lvl == 1),
                color=NAVY if lvl == 1 else MUTED,
            )
        track_tbl(toc_tbl)

    return front_els


def highlight_placeholders_and_fonts(doc: Document) -> None:
    """Normalize run fonts across paragraphs and highlight 【待填：...】 markers."""
    for p in doc.paragraphs:
        sname = p.style.name if p.style else ""
        if sname.startswith("Heading"):
            lvl = 1 if sname == "Heading 1" else (2 if sname == "Heading 2" else 3)
            sz = 16.0 if lvl == 1 else (13.5 if lvl == 2 else 12.0)
            for run in p.runs:
                set_run_font(run, cn_font=FONT_CN_HEAD, size_pt=sz, bold=True, color=NAVY)
        elif sname in {"Caption", "Image Caption", "Table Caption"}:
            continue
        elif sname == "Footnote Text":
            for run in p.runs:
                set_run_font(run, cn_font=FONT_CN_BODY, size_pt=9.5, color=MUTED)
        else:
            for run in p.runs:
                if not run.text:
                    continue
                is_ph = "【待填" in run.text
                set_run_font(
                    run,
                    cn_font=FONT_CN_BODY,
                    en_font=FONT_EN,
                    size_pt=12.0 if sname != "Block Quote" else 11.0,
                    bold=True if is_ph else run.bold,
                    color=ACCENT if is_ph else (MUTED if sname == "Block Quote" else DARK_TEXT),
                )


def process_captions_and_tables(doc: Document) -> List[Tuple[int, str, Optional[int]]]:
    """
    Auto-number chapters, tables (表 X-Y above table), and figures (图 X-Y below figure);
    enforce three-line table style and fit figure widths; return TOC outline.
    """
    body = doc.element.body
    children = list(body)

    # Map XML element -> python-docx Paragraph or Table
    p_map = {p._p: p for p in doc.paragraphs}
    t_map = {t._tbl: t for t in doc.tables}

    chap = 0
    fig_idx = 0
    tbl_idx = 0
    toc_outline: List[Tuple[int, str, Optional[int]]] = []

    # First, style all tables
    for tbl in doc.tables:
        n_cols = len(tbl.columns)
        fs = 8.8 if n_cols >= 7 else (9.5 if n_cols >= 5 else 10.0)
        style_three_line_table(tbl, font_size=fs)

    # Walk children in sequence
    i = 0
    while i < len(children):
        el = children[i]
        if el in p_map:
            p = p_map[el]
            sname = p.style.name if p.style else ""
            txt = p.text.strip()

            if sname == "Heading 1" and txt:
                m_ch = re.search(r"第\s*(\d+)\s*章", txt)
                if m_ch:
                    chap = int(m_ch.group(1))
                else:
                    chap += 1
                if chap == 1:
                    p.paragraph_format.page_break_before = True
                fig_idx = 0
                tbl_idx = 0
                toc_outline.append((1, txt, None))
            elif sname == "Heading 2" and txt:
                toc_outline.append((2, txt, None))

            # Use left alignment in Chapter 9 bibliography to avoid stretched URL lines
            if chap == 9 and sname in {"Normal", "Body Text", "First Paragraph", "Compact"}:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT

            # Resize inline drawings so figures fit comfortably (max 14.2cm W x 6.4cm H)
            drawings = el.findall(".//" + qn("wp:extent"))
            if drawings:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.keep_with_next = True
                max_cx = int(Cm(11.2).emu)
                max_cy = int(Cm(3.8).emu)
                for ext in drawings:
                    cx = int(ext.get("cx", "0"))
                    cy = int(ext.get("cy", "0"))
                    if cx > 0 and cy > 0:
                        scale = min(max_cx / cx, max_cy / cy, 1.0)
                        new_cx = int(cx * scale)
                        new_cy = int(cy * scale)
                        ext.set("cx", str(new_cx))
                        ext.set("cy", str(new_cy))
                for a_ext in el.findall(".//" + qn("a:xfrm") + "/" + qn("a:ext")):
                    cx = int(a_ext.get("cx", "0"))
                    cy = int(a_ext.get("cy", "0"))
                    if cx > 0 and cy > 0:
                        scale = min(max_cx / cx, max_cy / cy, 1.0)
                        a_ext.set("cx", str(int(cx * scale)))
                        a_ext.set("cy", str(int(cy * scale)))

            # Ensure equations and blockquotes never clip under exact line spacing
            if sname == "Block Quote" or el.findall(".//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath"):
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                p.paragraph_format.line_spacing = 1.0

            # Format figure and table captions
            if sname in {"Image Caption", "Table Caption", "Caption"} and txt:
                # Check if previous element was an image paragraph or next/prev element is a table
                prev_has_img = (
                    i > 0
                    and children[i - 1] in p_map
                    and len(children[i - 1].findall(".//" + qn("wp:extent"))) > 0
                )
                next_is_tbl = i + 1 < len(children) and children[i + 1] in t_map
                prev_is_tbl = i > 0 and children[i - 1] in t_map

                if prev_has_img or (sname == "Image Caption" and not next_is_tbl and not prev_is_tbl):
                    fig_idx += 1
                    clean_cap = re.sub(r"^图\s*\d+[-–]\d+\s*", "", txt)
                    p.text = f"图 {chap}-{fig_idx}  {clean_cap}"
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(4)
                    for r in p.runs:
                        set_run_font(r, cn_font=FONT_CN_BODY, size_pt=10.0, bold=False, color=MUTED)
                elif sname == "Table Caption" or next_is_tbl or prev_is_tbl:
                    tbl_idx += 1
                    clean_cap = re.sub(r"^表\s*\d+[-–]\d+\s*", "", txt)
                    p.text = f"表 {chap}-{tbl_idx}  {clean_cap}"
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.space_before = Pt(4)
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.keep_with_next = True
                    for r in p.runs:
                        set_run_font(r, cn_font=FONT_CN_HEAD, size_pt=10.5, bold=True, color=NAVY)
                    if prev_is_tbl:
                        # Move table caption above the table
                        tbl_el = children[i - 1]
                        body.remove(el)
                        tbl_pos = list(body).index(tbl_el)
                        body.insert(tbl_pos, el)
                        children = list(body)
        i += 1

    return toc_outline


def resolve_toc_pages(pdf_path: Path, toc_outline: List[Tuple[int, str, Optional[int]]]) -> List[Tuple[int, str, Optional[int]]]:
    """Scan rendered PDF pages to map each heading in toc_outline to its physical page number."""
    reader = PdfReader(str(pdf_path))
    page_texts = [(idx + 1, (pg.extract_text() or "")) for idx, pg in enumerate(reader.pages)]

    resolved: List[Tuple[int, str, Optional[int]]] = []
    min_page = 3  # Cover is page 1, TOC is page 2
    for lvl, title, _ in toc_outline:
        # Normalize whitespace for matching
        norm_title = re.sub(r"\s+", "", title)
        found_pg = None
        for pg_no, txt in page_texts:
            if pg_no < min_page:
                continue
            norm_txt = re.sub(r"\s+", "", txt)
            if norm_title in norm_txt:
                found_pg = pg_no
                min_page = pg_no
                break
        resolved.append((lvl, title, found_pg))
    return resolved


def run_build(
    md_path: Path,
    ref_path: Path,
    docx_path: Path,
    pdf_path: Path,
    preview_dir: Path,
    min_pages: int = 20,
    max_pages: int = 30,
) -> int:
    """Full build pipeline: reference.docx -> pandoc -> 2-pass postprocess -> soffice PDF -> preview PNGs."""
    member4_dir = md_path.parent.parent
    create_reference_docx(ref_path)

    raw_md = md_path.read_text(encoding="utf-8")
    meta, team_rows, body_md = parse_cover_and_prepare_md(raw_md, md_path.parent, member4_dir)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_md = Path(tmpdir) / "body.md"
        tmp_docx = Path(tmpdir) / "raw.docx"
        tmp_md.write_text(body_md, encoding="utf-8")

        cmd_pandoc = [
            "pandoc",
            str(tmp_md),
            "--from=markdown+tex_math_dollars+table_captions+footnotes",
            "--to=docx",
            f"--reference-doc={ref_path}",
            f"--resource-path={md_path.parent}:{member4_dir}:{member4_dir / 'figures' / 'report_v3'}:{member4_dir / 'figures' / 'report'}",
            "-o",
            str(tmp_docx),
        ]
        subprocess.run(cmd_pandoc, check=True)

        # Pass 1: post-process without final TOC page numbers to measure actual PDF page numbers
        def _postprocess(toc_with_pages: Optional[List[Tuple[int, str, Optional[int]]]] = None) -> List[Tuple[int, str, Optional[int]]]:
            doc = Document(str(tmp_docx))
            highlight_placeholders_and_fonts(doc)
            outline = process_captions_and_tables(doc)
            configure_headers_footers(doc)

            toc_to_render = toc_with_pages if toc_with_pages is not None else outline
            front_els = build_front_matter_elements(doc, meta, team_rows, toc_to_render)
            body_el = doc.element.body
            for idx_el, fel in enumerate(front_els):
                body_el.insert(idx_el, fel)
            doc.save(str(docx_path))
            return outline

        outline_pass1 = _postprocess(None)

        # Convert pass-1 DOCX -> PDF to determine exact TOC page numbers
        out_dir = pdf_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        lo_env = {**os.environ, "HOME": "/tmp"}
        lo_cmd = [
            "soffice",
            "-env:UserInstallation=file:///tmp/lo_profile",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(docx_path),
        ]
        subprocess.run(lo_cmd, env=lo_env, check=True)
        generated_pdf = out_dir / f"{docx_path.stem}.pdf"
        if generated_pdf != pdf_path and generated_pdf.exists():
            shutil.move(str(generated_pdf), str(pdf_path))

        toc_resolved = resolve_toc_pages(pdf_path, outline_pass1)

        # Pass 2: rebuild DOCX with exact TOC page numbers and re-export PDF
        _postprocess(toc_resolved)
        subprocess.run(lo_cmd, env=lo_env, check=True)
        if generated_pdf != pdf_path and generated_pdf.exists():
            shutil.move(str(generated_pdf), str(pdf_path))

    # Inspect PDF pages and export preview PNGs
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    print(f"PDF generated: {pdf_path} ({total_pages} pages)")

    table_page = None
    figure_page = None
    for idx, page in enumerate(reader.pages, start=1):
        if idx <= 3:
            continue
        txt = page.extract_text() or ""
        if table_page is None and re.search(r"表\s*\d+-\d+", txt):
            table_page = idx
        elif figure_page is None and idx != table_page and re.search(r"图\s*\d+-\d+", txt):
            figure_page = idx

    preview_dir.mkdir(parents=True, exist_ok=True)
    for old_png in preview_dir.glob("*.png"):
        old_png.unlink()

    pages_to_render = [1, 2, 3]
    if table_page and table_page not in pages_to_render:
        pages_to_render.append(table_page)
    if figure_page and figure_page not in pages_to_render:
        pages_to_render.append(figure_page)

    for pno in pages_to_render:
        tag = (
            "cover" if pno == 1 else (
                "toc" if pno == 2 else (
                    "exec" if pno == 3 else (
                        "table" if pno == table_page else "figure"
                    )
                )
            )
        )
        prefix = preview_dir / f"preview_p{pno:02d}_{tag}"
        subprocess.run(
            ["pdftoppm", "-png", "-r", "150", "-f", str(pno), "-l", str(pno), "-singlefile", str(pdf_path), str(prefix)],
            check=True,
        )

    if total_pages < min_pages or total_pages > max_pages:
        print(f"WARNING: page count {total_pages} is outside [{min_pages}, {max_pages}]")
    else:
        print(f"OK: page count {total_pages} is within [{min_pages}, {max_pages}]")
    return total_pages


def main() -> None:
    root_m4 = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Build final technical report DOCX & PDF.")
    parser.add_argument("--md", default=str(root_m4 / "report" / "REPORT_FINAL.md"))
    parser.add_argument("--ref", default=str(root_m4 / "report" / "reference.docx"))
    parser.add_argument("--docx", default=str(root_m4 / "report" / "REPORT_FINAL.docx"))
    parser.add_argument("--pdf", default=str(root_m4 / "report" / "REPORT_FINAL.pdf"))
    parser.add_argument("--preview", default=str(root_m4 / "report" / "preview"))
    args = parser.parse_args()

    run_build(
        md_path=Path(args.md),
        ref_path=Path(args.ref),
        docx_path=Path(args.docx),
        pdf_path=Path(args.pdf),
        preview_dir=Path(args.preview),
    )


if __name__ == "__main__":
    main()
