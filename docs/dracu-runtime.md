# Dracu 运行原理

本页描述 [DracuHandler](../handlers/dracu_handler.py) 的当前实现。其他游戏有独立的状态机，修改时应分别核对。

## 输入与分支运行时

场景 JSON 的核心字段是脚本 `name` 和 `scenes`。场景包含 `label`、`firstLine`、`title`，以及 `preevals`、`selects`、`texts`、`nexts` 等数据。

`scnchartdata.tjs` 以 UTF-16 读取，经 [parser.py](../utils/parser.py) 转换后交给 `json.loads()`。转换主要处理 `(const) %[`、`(const) [`、`=>`、`void` 和配对括号。

该转换器面向当前分支数据的结构，字符串、转义和注释处理并不完整。例如去除 `//` 使用正则，不能作为通用 TJS 语法解析器。

转换结果中的 `flagkeys` 与 `flags` 键顺序需要一致。每个角色的加点规则由若干 `[选项变量名, 选项值, 分值]` 组成。

MiniRacer 执行 JavaScript，用以下函数适配脚本所需的分支行为：

| 函数 | 行为 |
| --- | --- |
| `initialize()` | 将 `flags` 中各角色对应的全局分数清零 |
| `finalize()` | 将全局对象的可枚举属性同步到 `f` |
| `UpdateBranchFlags()` | 清零角色分数，根据已记录选择重新计算，再同步到 `f` |
| `SetBranchFlags(name, value)` | 记录选择变量，然后重新计算分数 |
| `CheckBranchFlags(expr)` | 将空格后紧接的 `.` 替换为 `f.`，求值并返回布尔结果 |
| `checkAdult()` | 返回当前成人总开关 |

`IsTrial` 和四个成人选项初始化到全局对象；通关状态初始化到 `f.sf.clear_*`。这些配置使用 `json.dumps()` 转成 JavaScript 字面量后写入。

## 文件与标签遍历

状态变量分工：

| 变量 | 含义 |
| --- | --- |
| `current_storage` | 当前加载和执行的脚本 |
| `next_storage` | 选中跳转的目的脚本，空白时回退到当前脚本 |
| `next_label` | 当前待进入或下一次待进入的标签 |
| `scenes_by_label` | 当前文件的标签到场景映射 |
| `selected_transition` | 本次最终选中的选择项或跳转项 |

文件循环读取 `{current_storage}.json`，关闭文件后建立标签映射，并追加一个章节。标签循环在内存中执行场景；目的脚本变化时退出标签循环，重新加载下一个文件。

`target` 缺失时，`next_label` 为 `None`，从当前文件 `firstLine` 数值最小的场景进入。`storage` 为纯空白字符串时回退到当前脚本。

到达 `start.ks` 时结束，不读取该文件、不新增章节。同一文件内跳转不创建新章节；重新进入文件会创建新章节。

## 一个场景的执行顺序

1. 定位场景并记录进入日志；需要时输出进入时的 flag 状态。
2. 按顺序执行 `preevals`。
3. 有 `selects` 时处理选择；否则有 `nexts` 时先收集正文，再选择下一跳。
4. 执行选中项的 `exp`。
5. 更新下一位置，继续当前文件或切换文件。

`selects` 优先于 `nexts`。当前只在 `nexts` 分支收集 `texts`，选项文字不会写入 `StoryTranscript`。

### `preevals`：进入场景前的赋值

每项为 `[赋值目标表达式, 数据值]`，例如：

```json
[
  ["f.route_jump", "miu"],
  ["f.visited", true]
]
```

依次执行：

```javascript
f.route_jump = "miu";
f.visited = true;
```

赋值目标作为代码使用，数据值通过 `json.dumps()` 序列化。字符串值不会再次作为表达式求值。

### `selects`：用户选择

按整数 `selidx` 建立字典并排序，不将序号当作原始数组下标。重复序号保留最后一个项。

存在 `eval` 的选项只有求值为真才可选。输入必须是可用序号的字符串；没有可用选项时抛出 `RuntimeError`。当前输入不做空白去除。

日志显示日文和提供的翻译。DEBUG 日志输出除 `selidx`、`text`、`language` 外的所有字段。

### `texts`：原样收集多语言正文

每条文本保存原始说话人、实际提供的各语言别名和正文。收集阶段不拼接说话人括号，也不根据配置提前选定语言。

`skip_text` 只控制正文日志，`skip_confirm` 只控制逐条确认。关闭日志不会跳过收集。

## `nexts` 的选取规则

首先过滤所有 `type == 1` 的项。以下是本项目当前的提取规则。

剩余项用元组作为字典键：

```python
(eval, storage, target, type)
```

各字段通过 `.get()` 读取；相同签名保留最后一条记录，遍历位置保持第一次插入该签名的位置。Dracu 不再使用字符串签名函数，旧 handler 仍使用原来的辅助函数。

随后按候选顺序遍历：

- 含 `eval` 字段的项立即求值，首个为真的项成为最终跳转并停止搜索。
- 没有 `eval` 字段的项参与版本配对，首个保留项暂存为默认跳转；继续搜索条件项。
- 没有条件项匹配时使用默认跳转。
- 没有条件项匹配且没有默认跳转时结束整个提取流程。

“无条件”指缺少 `eval` 字段；存在该字段但求值为假，仍属于条件项。

### 普通版和成人版配对

只对无条件跳转进行版本筛选，并且对应项的 `eval`、`target`、`type` 必须一致。

| 成人开关 | 候选情况 | 结果 |
| --- | --- | --- |
| 开启 | `foo.ks` 与 `x_foo.ks` 同时存在 | 跳过 `foo.ks` |
| 关闭 | `foo.ks` 与 `x_foo.ks` 同时存在 | 跳过 `x_foo.ks` |
| 任意 | 仅存在其中一个版本 | 保留该候选 |

此机制是配对选择：关闭成人开关时，单独存在的 `x_` 候选仍可保留。它没有对所有 `x_` 跳转做全局过滤。

### `exp`：选中跳转后的代码

只有选中项的非空 `exp` 会执行，而且先执行代码，再更新下一位置。例如：

```json
{
  "type": 0,
  "eval": "f.route_jump === \"miu\"",
  "exp": "delete f.route_jump;",
  "storage": "route_miu.ks",
  "target": "*start"
}
```

`eval` 决定是否选择此项；选中后执行删除，再跳到目标。`exp` 是原始代码，不能对其整体使用 `json.dumps()`，否则只会得到字符串字面量。

`preevals` 和选中项 `exp` 通过局部 `execute_script()` 执行。失败时记录异常并抛出带原异常链的 `RuntimeError`，不会继续推进或返回完整剧情对象。条件 `eval` 直接交给 MiniRacer，失败时同样中断，但保留原始求值异常类型。

## 路线变量与资源生命周期

`f.route_jump` 的赋值可以由场景 `preevals` 提供。例如路线入口赋值后，后续跳转条件读取它，再由选中项 `exp` 删除。处理 `preevals` 后，Dracu 当前不再使用按场景名强制设定路线的补丁。

场景文件只在读取 JSON 时打开。MiniRacer 使用上下文管理器，在正常结束和异常退出时关闭。所有剧情内容先保存在内存对象中；成功返回后，调用方才决定是否生成文件。
