# Exporters 实现

## 接口与调用

所有 exporter 继承 `BaseExporter`，实现以下接口：

```python
def export(
    self,
    transcript: StoryTranscript,
    outfile: str | Path,
    *,
    language: str,
) -> None:
    ...
```

`language` 必须通过关键字传入。输出成功后返回 `None`；数据或文件访问错误按实际异常传播。调用方负责准备输出父目录。

```python
from pathlib import Path

from exporters import Exporters
from models.story_transcript import DialogueEntry, DialogueTranslation, StoryTranscript


transcript = StoryTranscript(supported_languages=["jp", "sc"])
chapter = transcript.add_chapter("example.ks")
chapter.entries.append(DialogueEntry(
    original_speaker="美羽",
    translations={
        "jp": DialogueTranslation(speaker_alias="", text="こんにちは。"),
        "sc": DialogueTranslation(speaker_alias="", text="你好。"),
    },
))

output_dir = Path("output")
output_dir.mkdir(exist_ok=True)
Exporters["txt"].clazz().export(transcript, output_dir / "sample.txt", language="sc")
Exporters["pdf"].clazz().export(transcript, output_dir / "sample.pdf", language="jp")
```

当前两个实现位于 [txt_exporter.py](../exporters/txt_exporter.py) 和 [pdf_exporter.py](../exporters/pdf_exporter.py)。它们只读取剧情对象；同一对象可多次导出。

## 注册机制

导入 `exporters` 时，按文件名排序加载目录内的 `*_exporter.py`。实现类通过装饰器写入 `Exporters`：

```python
@registry(name="txt", description="纯文本")
class TxtExporter(BaseExporter):
    ...
```

`ExporterMeta` 包含 `name`、`description` 和 `clazz`，没有配置构造器。当前注册键为 `txt`、`pdf`。

新格式使用 `xxx_exporter.py` 文件名及唯一注册名；共同帮助模块不要使用此后缀。需要纸张等额外参数时再设计相应配置，当前接口仅有剧情对象、路径和语言。

## 语言与说话人规则

两个实现都直接查找翻译：

```python
translation = entry.translations.get(language)
if translation is None:
    translation = entry.translations["jp"]

speaker = translation.speaker_alias or entry.original_speaker
text = translation.text
```

规则如下：

1. 目标语言存在时使用其内容，包括空正文。
2. 缺少目标语言时使用日文，因此记录应提供 `jp` 条目。
3. 所选翻译的别名为空时，显示原始说话人。
4. 两个名字均为空时显示为旁白。

判断缺失使用 `is None`，不按正文是否为空判断。补全只作用于局部变量，不回写 `speaker_alias` 或 `translations`。

`supported_languages` 供调用方展示和选择语言。当前 exporter 不额外验证该列表；PDF 字体表配置了 `jp/en/sc/tc` 四种语言。调用方应使用这四个代码，并优先选择记录声明的语言。

## TXT 格式

TXT 使用 UTF-8 编码。章节编号从 1 开始，来自记录中的章节顺序：

```text
【第1章】开始
【美羽】你好。
这是一条旁白。
【第1章】结束



```

实现逐章节写入开始标记、正文和结束标记。结束标记后写四个换行字符，其中第一个结束当前行。空章节也保留开始、结束标记。

文件以 `newline=""` 打开，避免 Windows 自动换行转换把原始 `\r\n` 变成 `\r\r\n`。正文不会 `strip()`，原始正文的换行保留；格式标记使用 `\n`。

无章节的剧情对象会产生空 TXT 文件。

## PDF 排版

PDF 直接遍历章节和台词，不通过 TXT 标记或正则重新识别结构。正文中出现 `【名字】` 或章节样式文字时，仍作为该条正文处理。

当前布局：

| 设置 | 值 |
| --- | --- |
| 纸张 | A4 |
| 四边页边距 | 20 mm |
| 说话人列 | 45 mm |
| 正文列 | 剩余宽度 |
| 正文与说话人字号 | 12 pt |
| 章节字号 | 正文字号的 1.6 倍 |
| 章节分页 | 首章直接开始，之后每章先分页 |

英文标题使用 `[Chapter N]`，其他语言使用 `【第 N 章】`；英文说话人使用方括号，其他语言使用 `【】`。空章节仍显示标题。

ReportLab 的 `Paragraph` 会解释类似 XML 的标记，因此 `_paragraph_text()` 先转义正文中的 `<`、`>`、`&`，再将各种换行统一转换为 `<br/>`。原始数据不会被改写。

### 字体与日语回退

字体及样式复用 [旧 PDF 模块](../utils/pdf_builder.py) 的辅助函数：

| 语言 | 字体系列 |
| --- | --- |
| `jp` | Source Han Serif JP |
| `en` | Source Serif 4 |
| `sc` | Source Han Serif CN |
| `tc` | Source Han Serif TW |

字体文件从工作目录下的 `fonts/` 查找。英文导出发生日语回退时，正文和说话人使用日文字体；英文翻译存在但别名为空时，原始说话人使用日文字体，正文继续使用英文字体。

日文字体及样式按需初始化。这个处理针对当前语言回退和原始说话人场景，没有实现任意字符的自动字体匹配。

### 旧接口兼容

`utils.pdf_builder.build_pdf(raw_text, language, outfile)` 仍然保留，供另外四个 handler 使用。旧实现解析字符串，新的 PDF exporter 消费剧情对象，两个入口当前共存。

修改共享的字体或样式辅助函数时，需要同时检查两个入口。新增格式无需改动 Dracu 状态机；扩展步骤和验收要求见 [开发规范](development.md)。
