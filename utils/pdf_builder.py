"""
Usage:
    from pdf_builder import build_pdf
    build_pdf(raw_text, language="tw", outfile="output.pdf")
"""
import re
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    PageBreak, Spacer
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet


FONT_FILES = {
    "en": {
        "regular":  "fonts/SourceSerif4-Regular.ttf",
        "semibold": "fonts/SourceSerif4-Semibold.ttf",
    },
    "cn": {
        "regular":  "fonts/SourceHanSerifCN-Regular.ttf",
        "semibold": "fonts/SourceHanSerifCN-SemiBold.ttf",
    },
    "tw": {
        "regular":  "fonts/SourceHanSerifTW-Regular.ttf",
        "semibold": "fonts/SourceHanSerifTW-SemiBold.ttf",
    },
    "jp": {
        "regular":  "fonts/SourceHanSerifJP-Regular.ttf",
        "semibold": "fonts/SourceHanSerifJP-SemiBold.ttf",
    },
}

_chapter_re = re.compile(r"^【第(\d+)章】开始$")
_chapter_end_re = re.compile(r"^【第\d+章】结束$")
_speaker_re = re.compile(r"^【([^】]+)】(.*)$")


def _register_fonts(lang: str):
    files = FONT_FILES[lang]
    reg_name = f"{lang}-regular"
    bold_name = f"{lang}-semibold"

    if reg_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(reg_name, files["regular"]))
        pdfmetrics.registerFont(TTFont(bold_name, files["semibold"]))
    return reg_name, bold_name


def _build_styles(reg_name, bold_name, base_font_size=12):
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="Body",
        fontName=reg_name,
        fontSize=base_font_size,
        leading=base_font_size * 1.35,
    ))
    styles.add(ParagraphStyle(
        name="Speaker",
        fontName=bold_name,
        fontSize=base_font_size,
        leading=base_font_size * 1.35,
    ))
    styles.add(ParagraphStyle(
        name="Chapter",
        fontName=bold_name,
        fontSize=base_font_size * 1.6,  # 放大字号
        leading=base_font_size * 1.6 * 1.3,
        spaceAfter=base_font_size,
    ))
    return styles


def build_pdf(raw_text: str, language: str, outfile: str):
    assert language in FONT_FILES, f"Unsupported language: {language}"
    reg_font, bold_font = _register_fonts(language)
    styles = _build_styles(reg_font, bold_font)

    doc = SimpleDocTemplate(
        outfile,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    elements = []
    first_chapter = True  # 用于处理首章前不分页
    col_widths = [45 * mm, None]  # 说话人列固定宽度，其余自适应

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # 1. 章节结束：直接跳过
        if _chapter_end_re.match(line):
            first_chapter = False
            continue

        # 2. 章节开始
        chap_m = _chapter_re.match(line)
        if chap_m:
            chap_num = chap_m.group(1)
            if not first_chapter:
                elements.append(PageBreak())
            first_chapter = False

            if language == "en":
                chap_label = f"[Chapter {chap_num}]"
            else:
                chap_label = f"【第 {chap_num} 章】"
            p = Paragraph(chap_label, styles["Chapter"])
            row = [p, Paragraph("", styles["Body"])]
            elements.append(Table([row], colWidths=col_widths, style=[]))
            elements.append(Spacer(1, 4))
            continue

        # 3. 说话人 + 台词
        spk_m = _speaker_re.match(line)
        if spk_m:
            speaker, speech = spk_m.groups()
            if language == "en":
                speaker = f"[{speaker}]"
            else:
                speaker = f"【{speaker}】"
            row = [
                Paragraph(speaker, styles["Speaker"]),
                Paragraph(speech.lstrip(), styles["Body"]),
            ]
        else:  # 旁白
            row = [
                Paragraph("", styles["Speaker"]),
                Paragraph(line, styles["Body"]),
            ]

        tbl = Table([row], colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(tbl)

    doc.build(elements)


if __name__ == "__main__":
    SAMPLE_TEXT = """
【第1章】开始
日文：
【JP】「いろはにほへと ちりぬるを」
英文：
【EN】“The quick brown fox jumps over the lazy dog.”
简中：
【SC】“创新科技，服务中国”
繁中：
【TC】「寬恕是人類美德的表現」

【第1章】结束
【第2章】开始
……………………"""
    Path("output").mkdir(exist_ok=True)
    build_pdf(SAMPLE_TEXT, language="tw", outfile="output/sample_tw.pdf")
    build_pdf(SAMPLE_TEXT, language="en", outfile="output/sample_en.pdf")
    build_pdf(SAMPLE_TEXT, language="cn", outfile="output/sample_cn.pdf")
    build_pdf(SAMPLE_TEXT, language="jp", outfile="output/sample_jp.pdf")

