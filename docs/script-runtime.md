# 脚本数据与运行时

## 1. 机制所属层级

krkr / 吉里吉里是运行环境；TJS 是其脚本语言；KAG 基于 TJS 提供场景解析、标签、宏和存档等功能。游戏还可以注册插件、替换函数、扩展解析器。

`.ks` 是场景脚本，`.tjs` 可以是文本源码或字节码。本项目读取的 `.ks.json` 是 SCN 反编译数据，不是 TJS 或标准 KAG 规定的 JSON 格式。字段含义必须结合具体编译器、解析器和游戏资源确认。`scnchart.tjs` 中的扩展不能无条件推广到标准 KAG。

项目通过 MiniRacer 的 JavaScript 环境执行所需表达式，并补充少量游戏函数；它不是完整 TJS VM，也没有重建完整 KAG 播放器。

证据：各 [handler](../handlers/) 的运行时初始化；DR 的 `MakeScnChartMacro` 使用 `KAGParser` 并检查 `KAGParserEx.dll` 相关能力。

## 2. 反编译场景数据

以下是当前样本及 handler 使用的字段，不承诺所有游戏都有同一结构。

| 字段 | 当前用途 |
| --- | --- |
| 根级 `name` | 场景资源名，如 `xxx.ks`；项目读取 `xxx.ks.json` |
| 根级 `languages` | 日语之外的语言代码列表；DR 使用 `['jp']` 加此列表定义顺序 |
| `scenes` | 标签对应的场景集合 |
| `label`、`firstLine` | 标签名及源码位置；DR 未指定 target 时取最小 firstLine |
| `preevals`、`postevals` | 场景开始/末尾需执行的状态操作 |
| `texts` | 正文及多语言对话数据 |
| `selects` | 选择项，含 selidx、text、language、eval、exp、storage、target 等 |
| `nexts` | 自动跳转候选，可能含 eval、exp、storage、target、type |

当前 DR 实际读取的字段名是 **`languages`（复数）**。只在读取第一份脚本时追加其列表；没有此字段就保留 `['jp']`，不根据每行文本动态推断语言。语言代码为 `jp/en/cn/tw`，没有 `sc/tc` 映射。

数据观察：LLLJ 和千恋样本可无 languages；魔女样本有 `['cn','tw']`，天使样本有 `['en','cn','tw']`。这里只描述读取过的样本，不保证整个游戏统一。

证据：[DR handler](../handlers/dracu_handler.py)、[模型](../models/story_transcript.py)；本机 `yuzu_scns` 下各游戏 `.ks.json`。

## 3. 当前 DR 的场景执行顺序

自动跳转场景：

```text
进入标签 → preevals → 正文及内嵌表达式 → postevals
         → 选择跳转 → 选中项 exp → 更新 storage / target
```

选择场景：

```text
进入标签 → preevals → 判断选项 eval → 用户选择
         → postevals → 选中项 exp → 更新 storage / target
```

这是 **项目约定及当前实现顺序**，不能只根据字段名字宣称与所有原版场景的执行时机一致。尤其 postevals 在选中项 exp 之前执行，新游戏若有相互依赖，需要核对原版解析过程。

DR 的 execute_evals 接受字符串语句，或 `[expression, value]` 赋值对。赋值对生成 `expression = json.dumps(value);`；它不会把 value 当作待执行代码。

`eval` 用于判断候选是否成立，`exp` 用于在选中后执行副作用。例如：

```javascript
// eval：决定是否可选择/可跳转
CheckBranchFlags("miu_flag == 0xF")
// exp：记录本次选择，并重算相关状态
SetBranchFlags("某个选择标识", 2)
```

不得执行未选中候选的 exp。DR 的 exp 执行失败会抛出异常，位置不会继续推进。其他 handler 仍有捕获选择 exp 错误后在 finally 中推进的旧行为。

## 4. 跳转和结束规则

当前 DR 先过滤 `type == 1`，按 `(eval, storage, target, type)` 去重；同键后出现的内容覆盖先出现的内容，因此 exp 不参与区分。遍历保留的候选，首个成立的条件项优先；首个无条件项作为 fallback。条件均不成立且没有 fallback 时结束本次流程，不要求无条件项一定存在或一定只有一个。

空白 storage 回退到当前文件；target 缺失/为 None 时进入该文件最早的场景。到达 `start.ks` 也结束当前导出。后者是文本导出项目的边界，不表示原版 start.ks 不可执行。

**`type == 1` 等于“结束整个游戏”没有得到引擎证据确认。** 当前过滤及结束规则是用户针对现有语料认可的导出策略。标准 KAG 的 call/return 有调用者恢复语义；不能直接据此推定 SCN 中 type 数字的编码。若新游戏出现子场景调用、返回调用者或带目标的 type:1，需先确认对应解析器/字节码定义。

DR 的 `★本編－その１５_２.ks.json` 中，`*dummy2` 先检查角色条件，再 fallback 到 `*normal_end`；`*route_jump` 内的条件在正常路线进入路径下应有满足项。这是具体样本的流程分析，不是“所有条件分支一定有成立项”的普遍保证。

## 5. f / sf / tf、全局对象与上下文

标准 KAG 的全局别名：`f = kag.flags`、`sf = kag.sflags`、`tf = kag.tflags`。f 随普通存档保存/恢复；sf 用于跨普通读档保留的系统状态；tf 是不写入普通存档的临时状态。具体清理、持久化时机还受框架/游戏扩展影响。

**f、sf 在全局中是并列名称，其成员不是天然的全局字段，也不天然共享存储。** `f.someKey` 与裸 `someKey` 能否表示同一数据，要看当时的函数上下文及引擎逻辑。

TJS 的 `.checkIN` 不是 JS 中合法的独立成员访问；其省略对象写法依赖当前上下文/with 等语义。`incontextof` 可指定函数执行上下文；字符串后缀 `!` 可动态求值。不能把所有前导点都机械替换成 `f.`，例如 `.sf.clear_miu` 会错误变成 `f.sf.clear_miu`。

当前 DR 的适配：

```javascript
var sf = {};
var f = new Proxy(globalThis, {});
```

f 与 JS 全局字段共享读、写、删除；sf 仍是独立对象。SetBranchFlags 将选项值分别写入 f 和 sf，但任意 `f.x = ...` 不会自动同步 sf.x。对 CheckBranchFlags 的参数，正则移除省略对象的前导点，让 `.sf.clear_miu` 访问全局 sf。**这只是现有表达式子集的适配，不是 TJS 上下文规则的完整实现。** 正则未做字符串/注释的语法分析，也不支持任意 with 对象；新语料必须检查这些边界。

其他四个 handler 仍使用独立 f 对象、finalize 拷贝全局字段以及旧的 ` 空格+点 → f.` 替换；不能认为它们已经具备 DR 的同步及上下文适配。

证据：[KAG Initialize.tjs](https://raw.githubusercontent.com/krkrz/kag3/master/data/system/Initialize.tjs)、[KAG 变量说明](https://kirikirikag.sourceforge.net/contents/Var.html)、[TJS 表达式说明](https://krkrz.github.io/docs/tjs2/j/contents/expr_and_op.html)；各 handler。

## 6. JavaScript 兼容范围

| 表达式/结构 | 当前认识与处理 |
| --- | --- |
| 十六进制、算术、比较、三元、赋值、函数调用 | 常见样本可直接交给 JS；相同拼写不保证所有类型转换规则一致 |
| `miu_flag != 0xF` | JS 可直接比较；字段由当前运行时计分提供，无需改写十六进制 |
| `&&`、`||`、`!` | 当前分支条件可使用；TJS 与 JS 的返回值/字符串真假规则不完全一致 |
| `$38` 等数字字符字面量 | DR 的文本替换专门转换成字符，例如 38 对应 `&`；不全局重写任意 TJS 源码 |
| `void`、`%[...]`、`(const)`、`=>` | TJS 特有形式；计分表交给 TjsParser 生成 AST，再还原数据，不传给 JS 执行 |
| `incontextof`、后缀求值 `!`、后置 `if` | JS 不能原样执行；当前用相应游戏函数的简化实现代替 |
| Dictionary / Array API、kag、Storages 等对象 | 需要相应宿主/游戏实现，JS 环境不会自动提供 |

TJS 整数为 64 位；JS Number 与位运算精度模型不同，不能由 DR 小整数掩码成功推断任意大整数均兼容。TJS 的 true/false 与 JS 布尔类型也不能在严格比较上无条件视为相同。

MiniRacer 返回 JSUndefined，通常只表示 JS 执行结果为 undefined，不表示失败。状态语句和无 return 函数可正常产生该结果；条件表达式则需要可解释的真假结果。执行失败以异常为依据。

Python 值注入 JS 时，json.dumps 可正确序列化当前使用的字符串、布尔值、数字、列表及字典；不是任意 Python 对象/任意 TJS 类型的桥接层。特别不要用 str(value) 生成 JS 字面量。

证据：[TJS 基本类型](https://krkrz.github.io/krkr2doc/tjs2doc/contents/types.html)、[TJS token](https://krkrz.github.io/krkr2doc/tjs2doc/contents/token.html)、上述表达式文档；DR 的 execute_evals、resolve_text 和运行时函数。

## 7. 计分表加载：直接从 TjsParser AST 提取 flags

[load_branch_flags](../utils/parser.py) 通过 pythonnet 加载已有 `binaries/TjsParser.dll`，调用 Parser.ParseFile，以 Expression 模式生成 AST，再直接定位根字典的 flags 节点，提取每个派生字段的全部 `[选择键, 选项值, 贡献值]` 规则。旧的文本替换函数及通用 AST 数据还原函数均已删除，所有五个 handler 使用同一入口。

注释、字符串转义、字典分隔符及编码识别由 TjsParser 处理；项目不再手动去注释或全局替换字符。TjsParser 本身只解析，不执行脚本。项目只读取 flags 所需的字符串和整数数据，不还原 items、flagkeys 等其他字段。handler 的日志字段列表直接使用提取后的 flags 键顺序。

计分表加载仍不自动组合补丁/追加数据；配置中选择哪份表，就只读取哪份表。完整调用方式、AST 边界与运行时要求见 [TjsParser 接入](tjsparser.md)。

## 8. handler 之间的实际实现差异

| 能力 | DR | LLLJ / 千恋 / 魔女 / 天使现有 handler |
| --- | --- | --- |
| preevals | 字符串或赋值对 | 赋值对 |
| postevals | 已执行 | 当前没有同等处理 |
| 文本变体与内嵌表达式 | 已适配 DR 所需子集 | 主要读取 dialogue[1] |
| 运行时状态 | f 与全局共享，sf 独立 | f 为拷贝，旧前导点替换 |
| 成人版配对筛选 | 已注释，依靠条件跳转 | 仍有 x_ 配对筛选 |
| 无条件 next 数量 | 保留首个默认项 | 仍断言最多一个 |
| 剧情结果 | 返回多语言 StoryTranscript | 仍有直接写 txt / 生成 PDF 的旧实现 |

此表描述当前代码，不能据此断言这些游戏原版缺少某机制，也不表示旧 handler 已通过完整适配验证。
