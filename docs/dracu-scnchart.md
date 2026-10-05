# DR 与流程图扩展

适用范围：本项目使用的 Dracu-Riot! Steam 解包资源、成人追加资源及其 SCN 反编译 JSON。下文函数位置均可按名称在本机 `output/tjs_decompiled/scnchart.tjs` 中查找；证据目录见 [入口](README.md)。除特别说明外，不推广到其他游戏版本。

## 1. 选择记录与派生得分

原版证据：scnchart.tjs 的 SetBranchFlags、UpdateBranchFlags、CopyBranchFlags、CheckBranchFlags；scnchartdata.tjs / x_scnchartdata.tjs 的 flagkeys、flags。

flags 中的规则为：

```text
[选择记录的键, 命中的选项值, 贡献值]
```

SetBranchFlags 在键非空时把选择值同时写入 sf 和 f，然后重新计算派生字段。UpdateBranchFlags 默认把结果写入 f，但也接受结果字典及条件判断回调：默认根据 **f 中的选择记录** 判断，回调存在时交给回调。这使计分逻辑可用于临时计算，而不一定立即修改正常游戏状态。

原版先删除每个派生字段，再累加命中的规则；没有命中时字段可能仍缺失。当前 DR 每次将字段设为 undefined，再累加命中的贡献：第一次命中从零开始，没有命中则保持 undefined，命中贡献为零的规则则得到 0。初始化也调用 UpdateBranchFlags，而非把所有字段预设为零。

保留值为 undefined 的全局字段，是为避免裸名称访问产生 ReferenceError；与原版删除属性相比，属性存在性仍有差异。选择比较已改用 JS 的 `==`，对齐原版运算符写法，但不完整复刻 TJS 的类型转换规则。现有整数选择记录适用；新游戏出现不同类型比较时仍需核对。

CopyBranchFlags 只按 flagkeys 复制派生字段，不是复制所有游戏状态；若源字段缺失，会删除目标字典中的对应字段。

### 得分的数值可能编码位状态

DR 路线规则中使用 1、2、4、8 等贡献，`0xF` 即 15，表示所需四个不同位均满足。更准确的描述是：**用二进制位权贡献累加得到条件掩码**。原函数仍然使用 `+=`，并没有换成按位 OR；仅在对应位贡献不会重复累加等前提下，两者结果才等价。

其他游戏的已有计分规则中存在每次加 1 的普通累计方式，不能据此把所有 flags 都解释成好感度或全部解释成掩码。应以每个游戏的规则表及比较表达式为准。

## 2. CheckBranchFlags 的上下文与重新计分

原版核心结构：

```tjs
if (context === void) {
    context = %[];
    UpdateBranchFlags(context);
    (Dictionary.assign incontextof f)(context, 0);
}
var predicate = ("function { return " + string(expression) + "; }")!;
return (predicate incontextof context)();
```

以上为依据反编译结果重命名的说明片段，不是恢复出来的原变量名。

默认路径会根据最新选择记录重算得分、将结果合并回 f，再在临时结果字典的上下文执行动态函数。第二个参数存在时使用指定上下文，跳过默认重算流程。

`(Dictionary.assign incontextof f)(context, 0)` 的方向是 context → f；0 表示不清空 f，保留其他成员。[官方 Dictionary 文档](https://krkrz.github.io/docs/tjs2/j/contents/dictionary.html) 支持此解释。

当前 DR 的 JS CheckBranchFlags 已在检查前调用 UpdateBranchFlags，移除前导点后直接返回 eval 结果，不额外转换为布尔值。SetBranchFlags 仍会立即重算，供正文等后续处理读取派生字段；直接修改选择记录后，也会在下一次 CheckBranchFlags 时重新计算。

为满足现有语料，项目继续使用 f 与全局共享的状态，不建立原版临时字典，也未提供自定义结果字典、条件回调或 CheckBranchFlags 第二个上下文参数。因此本次对齐了重算时机及当前条件求值所需行为，没有完整模拟原版上下文和状态合并过程。

## 3. 通关状态与尼古拉线开放

数据观察：`★本編－その１５_２.ks.json` 的 `*dummy2` 有：

```javascript
CheckBranchFlags("nic_flag == 0xF && ( .sf.clear_eri || .sf.clear_azu || .sf.clear_miu || .sf.clear_rio )")
```

即尼古拉得分满足要求之外，还需其他四条线至少通关一条。普通角色得分和系统通关状态是两类数据。

当前运行时每次建立空 sf，不读取原游戏系统存档，因此通过 DracuConfig 的 clear_* 初始化模拟“本轮开始前已通关哪些路线”。默认值均为 True。删除全部初始化会使该条件中的属性缺失，从而锁住正常的尼古拉入口。

当前语料未找到条件读取 clear_nic，仅有结尾通关记录；这个字段仍在配置中，不能把它描述成尼古拉入口要求。结尾原始场景 data 中的 `"clear_miu", "clear"` 等记录，当前 handler 没有解释执行，不能替代起点的系统状态初始化。

LLLJ / 千恋 / 魔女 / 天使的现有配置/handler 还有 checkAnyClear 等开关；它们是各自适配中注入的条件值，不应未经源码确认就与 DR 的四个 clear_* 完全等同。

## 4. 文本数组、变体与内嵌表达式

数据观察及项目实现：DR 的一条 text 中，text[0] 是原说话人，text[1] 是按语言排列的 dialogue 数组。当前关心的 dialogue 字段：

| 下标 | 含义/处理 |
| --- | --- |
| 0 | 此语言说话人别名，模型保存原值 |
| 1 | 原文本 |
| 2 | 数字元数据，当前忽略；未确认准确用途，不能记录成已证明的文本长度 |
| 3 | 注音文本 PHONETIC_TEXT |
| 4 | 正文文本 WRITTEN_TEXT |

例如原文本 `次の[クラ]患[ンケ]者は？`，注音文本是 `次のクランケは？`，正文文本是 `次の患者は？`。两者可以相同，也可以不同；不能因某条表达式文本相同就删除一个变体。

DracuConfig.DialogueTextVariant 使用 1 / 3 / 4 三个枚举值，默认正文文本。当前代码按所选下标是否存在决定是否回退到 dialogue[1]；这不等于校验 3 和 4 必须同时存在。

语言顺序由根级 languages 决定。模型保留各语言文本及原始 speaker_alias，exporter 对空别名回退到 original_speaker；导出补全不改变模型原数据。

### resolve_text 的范围

当前语料的正文/注音变体含 `${表达式}`，例如 `${_get_dick_word('word','cn')}`。resolve_text 匹配这类片段，将表达式交给当前 JS 上下文，并以 String 转成输出文字。表达式恰好是 `$数字` 时直接转换为字符，例如 `${$38}` → `&`。

原文本中还观察到 `$_get_dick_word('word','cn');`，当前明确不匹配 `$表达式;`。选择 ORIGINAL_TEXT 或回退到原文本时，这种标记可能原样留在结果中。

当前正则不解析嵌套花括号、对象字面量或含花括号的字符串；它是现有语料适配，不是完整模板语言解释器。表达式失败会停止流程。表达式处理发生在正文收集期间，因此依赖当时的状态。

## 5. f.dick 与词表

原版证据：custom.tjs 的 _get_dick_word、getDickWordIndex；append_setup_1.tjs 的 LoadDickWords；adult/dick_words.txt；x_scnchartdata.tjs 的 dick 规则。

append_setup_1.tjs 将文本词表加载到 SystemConfig.DickWordTable。每条配置的前两项为语言和词表键，余下各项为候选词，形成 `table[language][type][index]`。

f.dick 是 UpdateBranchFlags 根据选择记录派生出来的值，不必在对应正文中找到直接 `f.dick = ...` 才能解释其来源。规则包含 `miu04*sel_word` 的 1 / 2 / 4，以及 `miu11*sel_word` 的 8 / 16 / 32，后者使用较高位保存后续选择。

原索引逻辑：

```javascript
if (flag >= 8) flag >>= 3;
return flag >= 4 ? 2 : flag >= 2 ? 1 : 0;
```

因此有高位选择时优先按右移后的高位取词，否则按低位取词。它不是“总分越高好感越高”，而是把选择编码解码成词表下标。

当前 DR 将词表硬编码在 config，内联索引计算，只补充 _get_dick_word，不完整复刻 SystemConfig、LoadDickWords 或 getDickWordIndex 的独立接口。原函数对缺失词表/文本会生成诊断占位串，当前简化函数没有该回退。现有配置词表成立，不代表任意输入同样成立。

## 6. 成人版跳转与追加资源

原版证据：MakeScnChartXNext、FilterScnChartXStorage；scnchart.ks 的 x_next 宏。

MakeScnChartXNext 将 x_next 宏展开为普通 next：

- 当前文件不是 x_ 开头：成人跳转附 `eval=checkAdult()`，全年龄跳转作为默认项。
- 当前已在 x_ 文件：在相应分支直接进入成人目标，延续版本。
- 自动对应文件模式会检查成人资源存在性，检测直接资源名及加 `.scn` 的资源名。
- 显式成人目标可以用 x_storage / x_target 指定，不保证只是给普通文件加 x_ 前缀。
- same 等宏参数控制使用哪种展开路径；现有 JSON 通常已经保存展开后的普通 next，无需重新生成宏。

FilterScnChartXStorage 在 checkAdult 成立且对应资源存在时返回 x_ 目标，否则返回普通目标。前缀选择、资源存在和成人开关是三个不同因素。

数据观察：2026-10-05 扫描当前 DR `.ks.json`，22 个 next 条件包含 checkAdult，20 对 next 的 storage 仅差 x_ 且 target/type 相同，但这 20 对 eval 均不同；没有发现 eval 也相同的配对。这是该份语料的统计，不是固定引擎常量。

当前 handler 保留 checkAdult 并执行剧本的条件/默认跳转；额外 x_ 签名配对筛选已注释。adult_enabled 也与 checkIN / checkOUT / checkMOUTH / checkFACE 四个选项开关联动。这些字段作为全局运行时选项注入，不是统一写入 sf。

custom.tjs 还显示默认 IsTrial=true、scnchartInfo 指向 t_scnchartdata.tjs，并注明由追加侧覆盖。这解释了基础资源的默认配置可能不是完整游戏最终配置。当前项目由 config 指定体验版状态和计分表，不执行原游戏启动/追加覆盖过程。

## 7. 场景宏在解析时生成可执行标签

原版证据：MakeScnChartMacro、ScnChartMacroTable getter；scnchart.ks 的 *macro；data/main/scnchartmacro.tjs。

beginscene / endscene 通过 `[emb escape=false exp=...]` 调用 MakeScnChartMacro。生成的文本会继续当场景标签/宏解析，而非只显示为正文。函数检查解析器是否支持此能力，不支持时提示解析器插件问题。

宏解析大致使用当前 storage 映射为场景 tag，结合当前 label 或显式 label 形成 id；默认标签名的冒号后部分会被截去，再查表决定 enter / leave 宏类别。它会检查生成的宏名是否已经注册，并透传指定的 storage / x_storage 等参数。

例如某些入口对应 `scnchart_enter:com15b*route_jump_miu`。scnchartmacro.tjs 中确实有 `:com15b*route_jump_miu` 等映射，但映射本身不包含 f.route_jump 的赋值证明。

scnchart.ks 中的 chartmap 宏同时写 f.currentChartPos，并发出 scnchart 指令；还有条件调用 `_chartmacro.ks` 的入口。生成宏的具体定义可能来自别的资源/启动阶段，不能只凭某个标签正文为空断定没有副作用。

## 8. 流程图插件记录与环境生命周期

原版证据：ScenarioChartPluginBase 的 onEnvInit / onEnvStore / onEnvRestore / onEnvCommand / setCurrent / setChartFlag。

插件注册 scnchart 指令，跟踪 current；进入新项目时记录 `sf['fos_'+id] = 1`，离开原项目时记录 `sf['eos_'+id] = 1`。leave、enter、force、reset 指令参数影响该位置切换，force 可指定要离开的当前 id。reset 路径直接清空 current，不等于普通离开路径。

isConverting 判断环境是否属于 KAGEnvironment。在回想播放或这种转换环境中，正常的进入/离开持久记录写入受到限制。转换环境实际承担哪些解析任务仍需更多宿主源码确认，不推定每次预解析都具有完全相同语义。

current 在 onEnvStore 中写入环境，在 onEnvRestore 中恢复；onEnvInit 的正常路径从 kag.flags.currentChartPos 初始化。这说明存档/环境恢复涉及插件自己的状态，不只是执行位置和 f 中的数据。

IsScnChartItemOpened 默认读取 global.sf 的 fos_ 标记并返回真假。ScnChartItemOpen 对尚未开放项目写 -1，实际进入则写 1，两者都可被判为开放，但数值记录不同。fos_/eos_ 是流程图访问记录，clear_* 是路线通关记录，不应混为一种状态。

当前文本导出器不解释所有 data 中的 scnchart 指令，也没有实现插件生命周期，因此没有自动维护上述记录。发现正文/跳转依赖这些字段时再确定必要适配范围。

## 9. 流程图跳入剧情与系统执行流程

原版证据：ScenarioChartBase.onJump、SystemActionBase._scnchart、scnchart.ks 的 *jump / *jump_go / *return。

onJump 写 tf.start_storage、tf.start_target、tf.start_point；point 来自项目的 flowjump 信息。随后调用系统场景，根据 conductor 是否为 extraConductor 选择入口，并锁定选择处理。

系统脚本会停止播放、清理部分环境、执行恢复/初始化钩子，最后到 start.ks 的 *jump。具体 flowjump 如何重建选择状态，需要继续追踪 start 和相关系统函数，不能只凭本文件断言。

返回游戏还有 sysrestore_backtogame 与 return；并非所有系统流程都是不可返回的跳转。主 conductor 与 extraConductor 存在不同执行路径，当前单一 storage/target 状态机没有模拟它们或完整调用栈。

流程图 UI 使用 sf.lastChartPage 保存页码，模块 getter 按需加载 scnchart_ui 系列脚本；ScnChartInfo / ScnChartMacroTable 也会缓存加载结果。菜单可用性由模式回调、回想状态及配置函数共同控制。这些是系统/UI 机制，对纯文本导出通常无需完整实现。

## 10. 数据加载与追加合并

原版证据：ScnChartInfo getter、ForeachAppendFileList 回调。

基础表由 Scripts.evalStorage 加载。如果存在追加文件枚举函数，则对提供的追加数据按字段类型合并：items 按外层索引把追加内容 push 到相应数组，其他数组追加元素，Dictionary 使用 assign 合并；类型不匹配会报错。合并结果缓存为 _ScnChartInfo。

这证明原游戏可以在运行时组合多份表，不证明任何名为 x_ 的文件都必定按同一方式自动合并。追加文件的发现规则属于 ForeachAppendFileList，需要另外调查。

当前 parser/handler 只读取 config 指定的一份表，未复刻该追加机制。适配新版本时，应确认读取的是完整表还是依赖追加的基础表，不能仅按文件名推断。

## 11. 待验证及已知差异清单

| 问题 | 现有证据/下一定位点 |
| --- | --- |
| f.route_jump 在哪里赋值 | 当前计分/宏生成函数没有直接证明；继续找生成的 scnchart_enter 宏定义和相关运行钩子。历史“进入路线标签打补丁”是适配策略，不是已证实引擎行为；当前 handler 未保留该专用 patch |
| nexts.type 数字真实来源 | 用户同意过滤 type:1 的导出策略；需 SCN 解析器/编译器或真实字节码证据确认，不能等同标准 KAG return 或引擎退出 |
| dialogue[2] 数字用途 | 尚无足够证据，不能继续沿用“文本长度”猜测 |
| 自定义计分结果、回调及条件上下文 | 检查前重算已实现；这些当前未使用的接口仍未复刻 |
| 缺失属性与 undefined、JS/TJS 类型转换 | 已区分未命中与零贡献，比较改为 JS `==`；属性存在性及跨语言转换仍有差异 |
| 自定义宏、fos_/eos_、通关指令 | 部分位于原始 data 或系统脚本，当前导出未全部执行 |
| 模板更复杂的语法、原文本 $表达式; | 当前 resolve_text 的明确范围之外 |
| 从任意流程图位置开始导出 | 可能需重建选择/环境，当前仅设置位置不足以复刻整个启动流程 |

以上记录仅要求后续开发知晓，不构成本次新增运行时行为的授权。
