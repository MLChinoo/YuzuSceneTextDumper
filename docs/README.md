# KAG / krkr / TJS 运行机理记录

本目录保存本项目适配游戏时确认的机制、实现约定与尚未解决的问题，供后续开发及 agent 使用。最后核对日期：2026-10-05。

## 阅读入口

- [脚本数据与运行时](script-runtime.md)：分层概念、场景数据、执行顺序、状态对象、表达式兼容、跨 handler 差异。
- [DR 与流程图扩展](dracu-scnchart.md)：分支计分、文本取词、成人版切换、场景宏、插件状态及待查问题。
- [TjsParser 接入](tjsparser.md)：pythonnet 加载已有 DLL、AST 数据还原及解析边界。
- [维护规范](maintenance.md)：新机制如何记录、如何引用证据以及适配时的调查顺序。

## 如何理解确认程度

| 标记 | 含义 |
| --- | --- |
| 原版证据 | 官方语言/框架文档、游戏文本源码或可定位的反编译函数支持该结论；反编译结果仍需考虑还原误差 |
| 数据观察 | 在指定游戏的反编译样本中出现，不能据此证明其他版本或所有引擎都如此 |
| 项目约定 | 当前代码实际采取的处理方式；可能是简化或有意忽略某些引擎行为 |
| 待验证 | 有调查线索，但尚未找到足够证据 |

这四种标记可以同时出现在一条机制中。尤其不要把“已在项目中实现”写成“已证明原版行为”。

## 本机证据位置

大体积游戏资源和反编译结果不纳入仓库。以下位置是本次调查的本机证据，迁移环境后应按文件名、函数名和标签重新定位：

| 证据 | 本机位置 |
| --- | --- |
| 已反编译 SCN | `C:/Users/MLChinoo/Desktop/yuzu_scns/<游戏目录>/*.ks.json` |
| DR 原始解包资源 | `D:/gals/dumps/dracu_steam_dumps/` |
| DR 流程图 TJS 反编译结果 | `output/tjs_decompiled/scnchart.tjs`，对应原资源 `data/sysscn/scnchart.tjs` |
| DR 系统场景宏 | 解包资源 `data/sysscn/scnchart.ks` |
| DR 流程图映射及计分表 | 解包资源 `data/main/scnchartmacro.tjs`、`data/main/scnchartdata.tjs`、`adult/x_scnchartdata.tjs` |
| DR 特殊词表 | 解包资源 `data/main/custom.tjs`、`adult/append_setup_1.tjs`、`adult/dick_words.txt` |

文档保留必要的小段示例和函数/标签定位信息，因此无需依赖聊天历史才能理解结论。源码链接使用相对路径，便于仓库迁移。
