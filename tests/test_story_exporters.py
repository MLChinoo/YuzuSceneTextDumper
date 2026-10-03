import copy
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reportlab.platypus import PageBreak, Table

from configs.dracu_config import DracuConfig
from exporters import Exporters
from handlers.dracu_handler import DracuHandler
from models.story_transcript import DialogueEntry, DialogueTranslation, StoryTranscript


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.transcript = StoryTranscript(supported_languages=["jp", "en", "sc", "tc"])
        chapter = self.transcript.add_chapter("sample.ks")
        chapter.entries.extend([
            DialogueEntry("原始名", {
                "jp": DialogueTranslation("", "日文"),
                "en": DialogueTranslation("Alice", "English"),
                "sc": DialogueTranslation("", "简中"),
                "tc": DialogueTranslation("愛莉", "繁中"),
            }),
            DialogueEntry("", {"jp": DialogueTranslation("", "【普通正文】<b> & >\n第二行\r\n第三行")}),
            DialogueEntry("原始名", {
                "jp": DialogueTranslation("", "日语回退"),
                "sc": DialogueTranslation("", ""),
            }),
        ])
        self.transcript.add_chapter("sample.ks")

    def test_registry(self):
        self.assertEqual(set(Exporters), {"txt", "pdf"})

    def test_txt_languages_fallback_empty_text_and_unchanged_data(self):
        before = copy.deepcopy(self.transcript)
        with tempfile.TemporaryDirectory() as directory:
            for language, first_line in {
                "jp": "【原始名】日文",
                "en": "【Alice】English",
                "sc": "【原始名】简中",
                "tc": "【愛莉】繁中",
            }.items():
                with self.subTest(language=language):
                    output = Path(directory) / f"{language}.txt"
                    Exporters["txt"].clazz().export(self.transcript, output, language=language)
                    last_text = "" if language == "sc" else "日语回退"
                    expected = (
                        f"【第1章】开始\n{first_line}\n"
                        "【普通正文】<b> & >\n第二行\n第三行\n"
                        f"【原始名】{last_text}\n【第1章】结束\n\n\n\n"
                        "【第2章】开始\n【第2章】结束\n\n\n\n"
                    )
                    self.assertEqual(output.read_text(encoding="UTF-8"), expected)
                    self.assertNotIn(b"\r\r\n", output.read_bytes())
        self.assertEqual(self.transcript, before)

    def test_pdf_reads_structure_escapes_text_and_preserves_data(self):
        before = copy.deepcopy(self.transcript)
        for language, first_speaker in {
            "jp": "【原始名】", "en": "[Alice]", "sc": "【原始名】", "tc": "【愛莉】",
        }.items():
            with self.subTest(language=language), \
                    patch("exporters.pdf_exporter._register_fonts", side_effect=lambda language:
                          ("Times-Roman", "Times-Bold") if language == "jp" else ("Helvetica", "Helvetica-Bold")), \
                    patch("exporters.pdf_exporter.SimpleDocTemplate") as document:
                Exporters["pdf"].clazz().export(self.transcript, "unused.pdf", language=language)
                elements = document.return_value.build.call_args.args[0]
                tables = [element for element in elements if isinstance(element, Table)]
                self.assertEqual(len(tables), 5)
                self.assertEqual(sum(isinstance(element, PageBreak) for element in elements), 1)
                self.assertEqual(tables[1]._cellvalues[0][0].getPlainText(), first_speaker)
                narrator = tables[2]._cellvalues[0]
                self.assertEqual(narrator[0].getPlainText(), "")
                self.assertEqual(
                    narrator[1].text,
                    "【普通正文】&lt;b&gt; &amp; &gt;<br/>第二行<br/>第三行",
                )
                last_body = tables[3]._cellvalues[0][1].getPlainText()
                self.assertEqual(last_body, "" if language == "sc" else "日语回退")
                if language == "en":
                    self.assertEqual(tables[1]._cellvalues[0][1].style.fontName, "Helvetica")
                    self.assertEqual(narrator[1].style.fontName, "Times-Roman")
                    self.assertEqual(tables[3]._cellvalues[0][0].style.fontName, "Times-Bold")
        self.assertEqual(self.transcript, before)

    def test_empty_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "empty.txt"
            Exporters["txt"].clazz().export(StoryTranscript(["jp"]), output, language="jp")
            self.assertEqual(output.read_bytes(), b"")


class DracuTranscriptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        flag_file = self.root / "flags.tjs"
        flag_file.write_text("fixture", encoding="UTF-16")
        flags = json.dumps({"flagkeys": ["miu"], "flags": {"miu": [["choice", 2, 7]]}})
        self.parser = patch("utils.parser.scnchartdata_tjs_to_json", return_value=flags)
        self.parser.start()
        self.addCleanup(self.parser.stop)
        self.inputs = patch("builtins.input", return_value="2")
        self.inputs.start()
        self.addCleanup(self.inputs.stop)
        self.config = DracuConfig(
            root_dir=str(self.root), scnchartdata_filepath=str(flag_file),
            head_scn="a.ks", head_label="*choice", skip_text=True,
            output_txt_filepath=str(self.root / "unused.txt"),
            output_pdf_filepath=str(self.root / "unused.pdf"),
        )
        self.text = ["原始名", [["", "日文"], ["Alias", "English"], ["", "简中"], ["別名", "繁中"]]]

    def write_scripts(self, *, failing_exp=False):
        def scene(label, **fields):
            return {"label": label, "firstLine": 1, "title": label, **fields}

        a_scenes = [
            scene("*choice", preevals=[["f.route_jump", "miu"]], selects=[{
                "selidx": 2, "text": "选择", "language": [], "storage": "", "target": "*text",
                "exp": 'throw new Error("fixture");' if failing_exp else 'SetBranchFlags("choice", 2);',
            }]),
            scene("*text", texts=[self.text], nexts=[{
                "type": 0, "eval": 'f.miu === 7 && f.route_jump === "miu"',
                "exp": "delete f.route_jump;", "storage": "b.ks", "target": "*return",
            }]),
            scene("*end", texts=[["", [["", "结尾旁白"]]]], nexts=[{"type": 1}]),
        ]
        b_scenes = [scene("*return", nexts=[{
            "type": 0, "eval": 'typeof f.route_jump === "undefined"',
            "storage": "a.ks", "target": "*end",
        }])]
        for storage, scenes in (("a.ks", a_scenes), ("b.ks", b_scenes)):
            (self.root / f"{storage}.json").write_text(
                json.dumps({"name": storage, "scenes": scenes}), encoding="UTF-8",
            )

    def test_multilingual_return_repeated_empty_chapters_and_no_output(self):
        self.write_scripts()
        transcript = DracuHandler().handle(self.config)
        self.assertEqual(transcript.supported_languages, ["jp", "en", "sc", "tc"])
        self.assertEqual([chapter.storage for chapter in transcript.chapters], ["a.ks", "b.ks", "a.ks"])
        self.assertEqual([len(chapter.entries) for chapter in transcript.chapters], [1, 0, 1])
        entry = transcript.chapters[0].entries[0]
        self.assertEqual(entry.original_speaker, "原始名")
        self.assertEqual(entry.translations["jp"].speaker_alias, "")
        self.assertEqual(entry.translations["sc"].speaker_alias, "")
        self.assertEqual(entry.translations["tc"].text, "繁中")
        self.assertFalse(Path(self.config.output_txt_filepath).exists())
        self.assertFalse(Path(self.config.output_pdf_filepath).exists())

    def test_jp_only(self):
        self.text[1] = self.text[1][:1]
        self.write_scripts()
        transcript = DracuHandler().handle(self.config)
        self.assertEqual(transcript.supported_languages, ["jp"])
        self.assertEqual(set(transcript.chapters[0].entries[0].translations), {"jp"})

    def test_execution_failure_closes_runtime_and_does_not_export(self):
        self.write_scripts(failing_exp=True)
        from py_mini_racer import MiniRacer

        closed = []
        original_close = MiniRacer.close

        def close(runtime):
            closed.append(runtime)
            original_close(runtime)

        with patch.object(MiniRacer, "close", close):
            with self.assertRaisesRegex(RuntimeError, "执行脚本失败"):
                DracuHandler().handle(self.config)
        self.assertEqual(len(closed), 1)
        self.assertFalse(Path(self.config.output_txt_filepath).exists())

    def test_end_before_any_chapter(self):
        transcript = DracuHandler().handle(self.config.model_copy(update={"head_scn": "start.ks"}))
        self.assertEqual(transcript, StoryTranscript(["jp"]))


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
