# 使用指南

## 环境与输入

使用 Python 3.12，并在项目根目录执行以下 PowerShell 命令。当前代码包含同引号嵌套的 f-string，需要 Python 3.12 引入的语法支持。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

主要依赖包括 MiniRacer、Pydantic 和 ReportLab；依赖版本见 [requirements.txt](../requirements.txt)。

准备两类输入：

| 输入 | 配置字段 | 当前读取方式 |
| --- | --- | --- |
| 反编译后的场景 JSON 目录 | `root_dir` | UTF-8；按 `{storage}.json` 查找 |
| 路线加点等分支数据文件 | `scnchartdata_filepath` | UTF-16；转换为 JSON 后加载 |

例如脚本位置是 `example.ks`，目录中应存在 `example.ks.json`。Dracu 默认从 `★プロローグa（始まり）.ks` 的 `*prologue_A` 开始。

原始 SCN 的反编译在项目运行前完成，可以使用 FreeMote 的 `PsbDecompile.exe`。handler 的输入是反编译结果，运行时不会调用反编译工具。

PDF 字体配置使用 `fonts/...` 相对路径，因此运行程序时以项目根目录为工作目录。exporter 不创建父目录，由调用方准备输出目录。

## Dracu：运行一次，导出多次

将以下示例中的场景目录和分支数据路径替换为实际位置，在项目根目录运行：

```python
from pathlib import Path

from exporters import Exporters
from handlers import Handlers


source_dir = Path(r"C:\path\to\dracu_scns")
meta = Handlers["dracu"]
config = meta.build_config(
    root_dir=str(source_dir),
    scnchartdata_filepath=str(source_dir / "scnchartdata.tjs"),
    adult_enabled=True,
)

transcript = meta.clazz().handle(config)

output_dir = Path("output")
output_dir.mkdir(parents=True, exist_ok=True)

Exporters["txt"].clazz().export(
    transcript, output_dir / "story_sc.txt", language="sc",
)
Exporters["txt"].clazz().export(
    transcript, output_dir / "story_jp.txt", language="jp",
)
Exporters["pdf"].clazz().export(
    transcript, output_dir / "story_en.pdf", language="en",
)
```

运行时按提示输入选项序号。每次运行提取用户实际选中的路线；想得到其他路线，需要再次运行并作出相应选择。

`transcript.supported_languages` 声明本次记录包含的语言。四种语言代码是 `jp`、`en`、`sc`、`tc`。单条台词缺少目标语言时，exporter 回退到日文，详见 [导出规则](exporters.md)。

## 配置的作用

| 字段 | 对 Dracu 的作用 |
| --- | --- |
| `root_dir`、`scnchartdata_filepath` | 指定场景及分支数据 |
| `head_scn`、`head_label` | 指定流程起点 |
| `adult_enabled` | 设置脚本成人开关，并参与无条件跳转的版本配对 |
| `is_trial` | 初始化脚本中的 `IsTrial` |
| `clear_miu/azu/rio/eri/nic` | 初始化对应的 `f.sf.clear_*` 通关状态 |
| `check_in/out/mouth/face` | 初始化对应的脚本选项；成人总开关关闭时均为假 |
| `skip_flags` | 跳过场景进入时的加点日志，默认 `True` |
| `skip_text` | 跳过逐条正文日志，默认 `True`；不影响剧情收集 |
| `skip_confirm` | 跳过正文后的回车确认，默认 `True`；仅在显示正文时有作用 |

开启成人内容时，`check_in/check_out` 至少一个为真，`check_mouth/check_face` 至少一个为真。`handle()` 会通过配置的 `check_valid()` 检查这两组条件。

公共配置仍保留 `dialogue_language_id`、`output_txt_filepath` 和 `output_pdf_filepath`，供尚未迁移的 handler 使用。Dracu 已不读取这三个字段；导出语言和路径由 `export()` 参数决定。

## 示例入口与旧 handler

交互入口：

```powershell
New-Item -ItemType Directory -Path output -Force
.\.venv\Scripts\python.exe -B example_1.py
```

选择 Dracu 时，入口接收剧情对象，并默认导出简中到 `output/output.txt`。PDF 调用示例保留在入口中，默认注释。选择其他游戏时，入口沿用 handler 内部的输出行为。

旧 handler 的调用仍然有效，例如：

```python
from pathlib import Path

from handlers import Handlers


Path("output").mkdir(exist_ok=True)
meta = Handlers["senren"]
config = meta.build_config(
    root_dir=r"C:\path\to\senren_scns",
    scnchartdata_filepath=r"C:\path\to\scnchartdata.tjs",
    dialogue_language_id=2,
    output_txt_filepath="output/senren_sc.txt",
    output_pdf_filepath="output/senren_sc.pdf",
)
meta.clazz().handle(config)
```

旧配置的语言编号为 `0=jp`、`1=en`、`2=sc`、`3=tc`。旧 handler 返回 `None`，会自行写入 TXT 并调用旧 PDF 接口。

## 日志与检查

Dracu 使用 `logging`，默认 INFO 级别。想查看条件判断、执行结果和选项附加字段，可以在调用前配置：

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

日志用于跟踪流程，正文收集独立于日志级别。当前旧 handler 主要仍使用 `print()`。

自动测试命令及 PDF 验收方法见 [开发规范](development.md)。
