# 开发规范

## 职责与兼容性

- 游戏输入结构、分支执行和路线选择放在 handler。
- 剧情模型保存原始内容，语言回退、说话人补全和格式标记放在 exporter。
- exporter 只读剧情对象，不追加翻译、不回写别名、不重新运行 handler。
- Dracu 使用新的返回对象接口；其余 handler 仍使用旧输出配置与 PDF 接口。公共字段和旧辅助函数在仍有调用者时保留。
- 每个 handler 的状态机保持独立。修复一个游戏时，先确认该行为是否适用于其他游戏，再决定迁移范围。

接口调整应同步更新示例和文档。`handle()` 的返回类型差异、语言回退及章节划分属于外部可观察行为。

## 代码约定

使用 Python 3.12，源文件采用 UTF-8。变量与函数使用 `snake_case`，类使用 `PascalCase`，名称应说明数据角色，例如 `selected_transition`、`original_speaker`。

运行配置使用 Pydantic；剧情数据使用 dataclass。可变列表默认值使用 `field(default_factory=list)`。小型功能直接实现，有重复职责和真实扩展需求时再增加公共抽象。

针对已知输入结构访问字段。额外检查应解决具体数据歧义或实际失败，不重复检查刚通过字典索引取得的同一个标签，也不为自然异常再建立一套位置追踪状态。

Python 值传入 JavaScript 时使用 `json.dumps()`，让字符串转义和布尔值等字面量正确：

```python
ctx.eval(f"Object.assign(this, {json.dumps(runtime_options)});")
execute_script(f"{expression} = {json.dumps(value)};")
```

来自脚本的 `eval`、`exp` 以及赋值目标本身按代码处理，不能整体序列化成字符串。不要在选中跳转之前执行 `exp`；失败后也不继续推进到下一位置。

## 新增 exporter

1. 新建 `exporters/<format>_exporter.py`，继承 `BaseExporter`。
2. 使用 `exporters.registry` 注册唯一名称及描述。
3. 实现 `export(transcript, outfile, *, language)`，沿用语言回退和别名补全规则。
4. 根据格式读取章节与条目；在调用方决定路径和是否导出。
5. 添加针对格式实际行为的测试，更新文档索引和调用示例。

注册会在模块导入时发生。模块顶层只定义类型、函数、常量和注册信息，不在导入时生成文件或执行游戏流程。

未来新增 JSON 等格式时，先确定序列化与重新加载的接口，再实现对应功能；当前项目只提供 TXT、PDF exporter。

## 新增或迁移 handler

配置类继承 `BaseConfig`，实现 `_check_valid()`。handler 继承 `BaseHandler`，通过 `handlers.registry` 关联配置类，在 `_handle()` 中实现游戏适配。

采用新接口的 handler 应返回 `StoryTranscript`，保留各语言原始内容，并停止内部文件导出。调用入口负责判断返回值和调用 exporter。

迁移旧 handler 时先核对其原始结构。例如 Senren 的语言数组位于 `text[2]`，Dracu 等位于 `text[1]`，不能机械复制索引。也要分别保留其起始位置、脚本函数和跳转规则。

当前 handlers 会导入目录中除 `__init__.py` 外的全部 Python 文件；exporters 只自动导入 `*_exporter.py`。不要把依赖运行入口或有外部副作用的模块放入这些自动加载范围。

## 日志与资源

新实现使用模块 logger 和参数化消息：

```python
logger = logging.getLogger(__name__)
logger.debug("跳转条件：%s，结果：%s", expression, result)
```

INFO 描述场景进入、选项和导出进度，DEBUG 描述求值结果及附加字段。选择提示继续使用 `input()`。Dracu 当前在 handler 内调用 `logging.basicConfig()`；其他 handler 的 `print()` 尚未统一迁移。

场景读取完成后关闭文件；MiniRacer 使用上下文管理器；文件写入使用 `with`。条件和代码执行错误保持失败传播，不用吞掉异常的方式继续流程。

## 自动测试

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
```

测试使用标准库 `unittest`，目前集中在 [test_story_exporters.py](../tests/test_story_exporters.py)：

| 范围 | 已覆盖的行为 |
| --- | --- |
| Dracu | 返回多语言对象、日语流程、重复及空章节、异常关闭运行时、运行本身不写产物 |
| 注册 | 两个 exporter 的自动发现 |
| TXT | 四语言选择、日语回退、空正文、别名补全、正文换行、空记录 |
| PDF | 直接使用结构、文本转义、章节分页、英文回退字体 |
| 复用 | 多次导出后剧情对象保持不变 |

测试中的分支数据转换被替换为固定数据，PDF 文档构建使用 mock；这套测试不能替代真实 TJS 样本转换检查或 PDF 视觉验收。MiniRacer 在 Dracu 流程测试中实际执行脚本。

按修改的风险选择验证范围：文档和简单命名调整优先做一致性检查；数据结构、状态机和导出规则变化应验证可观察行为。测试应覆盖顺序、副作用、回退等语义，不只重复实现中的每一步。

改变状态机时，对比修改前后的条件求值顺序、选中项、`exp` 执行顺序和正文输出。修改共享配置或辅助函数时，再验证旧 handler 的兼容性。

## PDF 视觉验收

修改字体、样式或布局后，生成四语言样本，包含多行正文、旁白、空别名、仅日语台词、特殊字符、重复章节和空章节。

可以使用 Poppler 渲染检查：

```powershell
pdftoppm -r 120 -png output/sample.pdf output/sample
```

逐页确认没有缺字方框、裁切、重叠或错误分页；确认 `<`、`>`、`&` 按正文显示。英文字体下的日语回退和原始说话人需要单独检查。文本抽取和 mock 测试无法判断最终排版。

验收临时样本集中放在临时目录，完成后清理；不要将生成的文件混入代码提交。

## 文档与提交

技术文档放在 `docs/`，用相对链接关联源码和其他文档。已实现行为、旧接口兼容状态和未来扩展建议应明确区分；不把某个 handler 的实现写成所有游戏的通用规则。

提交前检查改动范围和空白问题：

```powershell
git status --short
git diff --check
```

本轮后续工作在 `reborn` 分支进行；仅在明确要求提交时提交 Git。提交包含本次功能及相应文档、测试，不包含 `.idea/`、虚拟环境和验收临时产物。
