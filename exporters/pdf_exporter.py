import logging
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from exporters import BaseExporter, registry
from models.story_transcript import StoryTranscript
from utils.pdf_builder import _build_styles, _register_fonts


logger = logging.getLogger(__name__)


def _paragraph_text(text: str) -> str:
    return escape(text).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")


@registry(name="pdf", description="PDF 文档")
class PdfExporter(BaseExporter):
    def export(
        self,
        transcript: StoryTranscript,
        outfile: str | Path,
        *,
        language: str,
    ) -> None:
        outfile = Path(outfile)
        outfile.parent.mkdir(parents=True, exist_ok=True)
        logger.info("正在生成pdf：%s，耗时可能较长......", outfile)
        regular_font, bold_font = _register_fonts(language)
        styles = _build_styles(regular_font, bold_font)
        document = SimpleDocTemplate(
            str(outfile),
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )
        elements = []
        column_widths = [45 * mm, None]
        japanese_styles = None

        for number, chapter in enumerate(transcript.chapters, start=1):
            if number > 1:
                elements.append(PageBreak())
            chapter_label = f"[Chapter {number}]" if language == "en" else f"【第 {number} 章】"
            elements.append(Table([
                [Paragraph(chapter_label, styles["Chapter"]), Paragraph("", styles["Body"])],
            ], colWidths=column_widths, style=[]))
            elements.append(Spacer(1, 4))

            for entry in chapter.entries:
                translation = entry.translations.get(language)
                fallback_to_japanese = translation is None
                if translation is None:
                    translation = entry.translations["jp"]
                speaker = translation.speaker_alias or entry.original_speaker
                speaker_style = styles["Speaker"]
                body_style = styles["Body"]
                # 英文字体不包含日文；回退台词和原始说话人使用日文字体。
                if language == "en" and (fallback_to_japanese or not translation.speaker_alias):
                    if japanese_styles is None:
                        japanese_styles = _build_styles(*_register_fonts("jp"))
                    speaker_style = japanese_styles["Speaker"]
                    if fallback_to_japanese:
                        body_style = japanese_styles["Body"]
                if speaker:
                    speaker = f"[{speaker}]" if language == "en" else f"【{speaker}】"
                row = [
                    Paragraph(_paragraph_text(speaker), speaker_style),
                    Paragraph(_paragraph_text(translation.text), body_style),
                ]
                table = Table([row], colWidths=column_widths)
                table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                elements.append(table)

        document.build(elements)
        logger.info("成功生成pdf.")
