import logging
from pathlib import Path

from exporters import BaseExporter, registry
from models.story_transcript import StoryTranscript


logger = logging.getLogger(__name__)


@registry(name="txt", description="纯文本")
class TxtExporter(BaseExporter):
    def export(
        self,
        transcript: StoryTranscript,
        outfile: str | Path,
        *,
        language: str,
    ) -> None:
        outfile = Path(outfile)
        outfile.parent.mkdir(parents=True, exist_ok=True)
        logger.info("正在写入文本：%s", outfile)
        with outfile.open("w", encoding="UTF-8", newline="") as output:
            for number, chapter in enumerate(transcript.chapters, start=1):
                output.write(f"【第{number}章】开始\n")
                for entry in chapter.entries:
                    translation = entry.translations.get(language)
                    if translation is None:
                        translation = entry.translations["jp"]
                    speaker = translation.speaker_alias or entry.original_speaker
                    prefix = f"【{speaker}】" if speaker else ""
                    output.write(f"{prefix}{translation.text}\n")
                output.write(f"【第{number}章】结束\n\n\n\n")
