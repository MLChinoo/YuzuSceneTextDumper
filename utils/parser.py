from pathlib import Path

from pythonnet import load


BINARIES_DIR = Path(__file__).resolve().parents[1] / "binaries"

# 必须在 import clr 前选择运行时；提供的 TjsParser.dll 面向 .NET 8。
load("coreclr", runtime_config=str(BINARIES_DIR / "TjsParser.runtimeconfig.json"))

import clr

clr.AddReference(str(BINARIES_DIR / "TjsParser.dll"))

from TjsParser import Parser
from TjsParser.Parsing import ParseOptions, RootMode
from TjsParser.Syntax import SyntaxKind


def _read_integer(node):
    if node.Kind == SyntaxKind.UnaryExpression and node.Operator in ("+", "-"):
        value = int(node.Operand.Value)
        return value if node.Operator == "+" else -value
    return int(node.Value)


def load_branch_flags(filepath: str | Path) -> dict[str, list[list[str | int]]]:
    """直接从计分表 AST 提取完整 flags，不还原其他字段。"""
    options = ParseOptions()
    options.RootMode = RootMode.Expression
    result = Parser.ParseFile(str(Path(filepath).resolve()), options)
    if not result.Success:
        diagnostics = "\n".join(
            f"{item.Code}（{item.Span.Start.Line}:{item.Span.Start.Column}）：{item.Message}"
            for item in result.Diagnostics
        )
        raise ValueError(f"解析计分表失败：{filepath}\n{diagnostics}")

    flags_node = None
    for entry in result.Document.Expression.Entries:
        if str(entry.Key.Value) == "flags":
            flags_node = entry.Value
    if flags_node is None:
        raise KeyError("flags")

    flags = {}
    for entry in flags_node.Entries:
        rules = []
        for element in entry.Value.Elements:
            selection, selected_id, bonus = (
                item.Expression for item in element.Expression.Elements
            )
            rules.append([
                str(selection.Value),
                _read_integer(selected_id),
                _read_integer(bonus),
            ])
        flags[str(entry.Key.Value)] = rules
    return flags
