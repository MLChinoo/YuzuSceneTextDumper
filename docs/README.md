# YuzuSceneTextDumper 文档

本项目根据反编译后的场景 JSON 和分支数据运行剧情流程，读取用户选择，提取本次流程实际经过的剧情文本。不同游戏由各自的 handler 适配。

Dracu 已采用多语言剧情对象与独立 exporter：一次运行产生 `StoryTranscript`，随后可以重复导出不同语言的 TXT、PDF。其余 handler 仍使用原有的文件输出流程。

## 阅读顺序

| 文档 | 内容 |
| --- | --- |
| [使用指南](getting-started.md) | 环境、输入文件、运行示例、配置和输出位置 |
| [架构与数据模型](architecture.md) | 模块职责、注册机制、章节与台词结构、多语言语义 |
| [Dracu 运行原理](dracu-runtime.md) | 场景遍历、分支状态、`preevals`、选择和跳转 |
| [Exporters 实现](exporters.md) | 导出接口、语言回退、TXT 格式、PDF 排版与字体 |
| [开发规范](development.md) | 扩展方式、代码约定、测试和兼容性要求 |

初次运行先阅读使用指南；修改剧情流程先阅读 Dracu 运行原理；新增输出格式先阅读 Exporters 实现。

## 当前适配状态

| 注册名称 | 游戏 | `handle()` 返回值 | 输出方式 |
| --- | --- | --- | --- |
| `dracu` | DRACU-RIOT! Steam 版 | `StoryTranscript` | 调用方选择 exporter 和语言 |
| `senren` | 千恋＊万花 Steam 版 | `None` | handler 内写 TXT 并生成 PDF |
| `tenshi` | 天使☆嚣嚣 RE-BOOT! Hikari Field 版 | `None` | handler 内写 TXT 并生成 PDF |
| `sanoba` | 魔女的夜宴 Steam 版 | `None` | handler 内写 TXT 并生成 PDF |
| `lllj` | Limelight Lemonade Jam | `None` | handler 内写 TXT 并生成 PDF |

当前 `sanoba` 注册使用 `TenshiConfig`。这张表描述实际代码，不代表这些 handler 的状态机或配置已经统一。

## 项目目录

```text
configs/       输入位置、运行开关和各游戏配置
handlers/      各游戏的场景遍历与脚本执行
models/        多语言剧情数据模型
exporters/     从剧情对象生成 TXT、PDF
utils/         分支数据转换、语言映射、旧 PDF 实现
fonts/         PDF 使用的字体
tests/         剧情对象与 exporters 的自动测试
docs/          使用与开发文档
example_1.py   交互选择游戏；兼容新旧输出流程
example_2.py   Senren 的旧调用示例
```

文档中的接口和行为以当前工作树为准。当前没有 JSON exporter、剧情对象加载器、所有路线批量遍历或完整的 TJS 引擎实现。
