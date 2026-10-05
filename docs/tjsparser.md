# TjsParser 接入

最后核对：2026-10-06。适用范围：五个现有 handler 加载的明文 scnchartdata.tjs / x_scnchartdata.tjs 等计分表。源码依据：[MLChinoo/TjsParser](https://github.com/MLChinoo/TjsParser)。仅使用用户提供的 DLL，没有重新构建，也未执行代码测试。

## 运行环境与入口

- Python 依赖：requirements.txt 中的 `pythonnet==3.0.5`。
- 程序集：`binaries/TjsParser.dll`，当前文件元数据显示目标为 `.NETCoreApp,Version=v8.0`。
- 运行时：与 Python 进程位数匹配的 .NET 8 Runtime；不需要 SDK 或构建工具。
- `binaries/TjsParser.runtimeconfig.json` 指定 .NET 8 框架，补丁版本按宿主默认策略选择。

[utils/parser.py](../utils/parser.py) 在导入 clr 之前调用 pythonnet.load 选择 CoreCLR，再以相对于项目文件的绝对路径 AddReference；不依赖启动时的工作目录。调用约束来自 [pythonnet 官方文档](https://pythonnet.github.io/pythonnet/python.html#loading-a-runtime)。

统一 Python 接口直接返回完整的 flags：

```python
branch_flags = utils.parser.load_branch_flags(config.scnchartdata_filepath)
flag_names = list(branch_flags)
ctx.eval(f"var flags = {json.dumps(branch_flags)};")
```

底层调用 Parser.ParseFile，ParseOptions.RootMode 设为 Expression。编码读取交给库的 SourceLoader，不再由 handler 固定 UTF-16，也没有另外设置 EncodingHint。

## 从 AST 直接提取规则

接口依据：[Parser.cs](https://github.com/MLChinoo/TjsParser/blob/master/src/TjsParser/Parser.cs)、[ParseModel.cs](https://github.com/MLChinoo/TjsParser/blob/master/src/TjsParser/Parsing/ParseModel.cs)、[SyntaxModel.cs](https://github.com/MLChinoo/TjsParser/blob/master/src/TjsParser/Syntax/SyntaxModel.cs)。

ParseFile 返回 ParseResult，其 Document 是 AST，不是执行脚本得到的 Dictionary。项目检查 Success，解析错误时抛出包含诊断代码、行列及消息的 ValueError。成功后的提取路径是：

```text
Document.Expression.Entries
  → 根字典中 key 为 flags 的 entry.Value
  → 每个派生字段的 entry.Value.Elements
  → 每条规则的三个元素：选择键、选项值、贡献值
  → 最终 flags 字典
```

没有 AST → JSON → Python 的中间过程，也不先还原整份 scnchartdata。TjsParser 仍解析整个文件的语法，但 Python 仅提取 flags 子树的数据。

例如：

```tjs
(const) %[
    "flagkeys" => (const) ["miu_flag"],
    "flags" => (const) %[
        "miu_flag" => (const) [(const) ["choice", 1, 8]]
    ],
    "optional" => void
]
```

函数仅返回：

```python
{"miu_flag": [["choice", 1, 8]]}
```

handler 用 flags 的键生成日志字段列表，不再读取或比较原表中的 flagkeys。这是在原先两者顺序相等约束下进行的简化；不能据此认为原引擎的 flagkeys 在所有用途下都没有意义。

## 适用结构与边界

flags 必须是字典，每个值为规则数组，每条规则为 `[字符串选择键, 整数选项值, 整数贡献值]`。完整保留所有派生字段、规则顺序及贡献；空规则数组仍保留。整数来自 LiteralExpression.Value，前缀正负号从 UnaryExpression 的操作符及整数操作数读取。

字典条目和数组元素直接从 AST 读取，因此普通及 `(const)` 形式都可使用。常量修饰的不可变约束没有复制到 Python 容器中。字典同键后值覆盖前值，最终 dict 不保留每条重复条目；调查重复键或重建源码时应使用原始 AST。

不支持在 flags 数据中执行函数、标识符引用、任意算术表达式或恢复宿主对象。没有通用 `_to_python` 求值/还原函数；items、注释、其他元数据不进入最终 flags。缺少根 flags 项会抛出 KeyError。

这里只接入明文 ParseFile，没有接入 KBAD 二进制读取，也没有反编译 TJS2100 字节码。不同文件格式需单独确认库接口。

## 与原游戏数据加载的差异

五个 handler 原有的计分算法和场景推进方式保留。原游戏 Scripts.evalStorage 会求值，并可能通过 ScnChartInfo 组合追加资源；本项目只从指定单个文件的 AST 提取 flags，没有自动执行启动脚本、枚举追加文件或恢复游戏存档。

相关机制参见 [DR 数据加载与追加合并](dracu-scnchart.md#10-数据加载与追加合并)。扩展规则结构或文件格式时，必须同步更新本文及对应运行机理记录。
