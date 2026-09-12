"""掩蔽式源码扫描公共模块(测试仓单一源;T-107 从三处内联收敛)。

手法出处(持久索引)= 测试仓 commit 149f86b「retirement 锁判定域改掩蔽式,
恢复 refs 复合正则检出力」定型的 T-93 版本;此前以三处内联同构存在
(test_cw_old_stream_write_retirement.py / test_cw_runnode_retire.py /
test_cw_infra_locks.py),T-107 抽取为本模块,三锁改引。

机制:注释 token(tokenize)与 docstring 跨度(ast 定义体首语句孤立字符串)
在源文本上**按字符等长置空**(保行号),正则对置空后的全文跑 finditer——

- 豁免面:注释/docstring 里的文档性提及(「禁复用 X.jsonl」「X 已退役」类
  负向声明、出处注记)是退役背书而非活引用,置空后不误红;
- 检出面:置空不拆结构,正则在连续文本上匹配,跨 token 复合正则
  (如 ``'stream'\\s*:\\s*'流名'``,源码拆三 token)照常检出;禁逐 token
  search 承载复合正则——该退化使复合形永久失配盲绿;
- 失败回退(宁误红不漏判):tokenize 失败 → 原文全判;ast 解析失败 →
  docstring 不掩蔽(同向)。代码位置的非 docstring 字符串字面量不掩蔽,照判。

读取容差统一申报:文本读取用 ``errors='ignore'``(原 runnode 形;old_stream
原为严格读——生产树均为合法 UTF-8,实测无差异面),OSError 跳过该文件。

掩蔽语料共享(全树扫描锁的性能结构性方案,T-107):``build_masked_sources``
按扫描根做**进程内缓存**的文件列表+文本+掩蔽一次构建,多个扫描锁(可跨
测试模块)经各自 module fixture 复用同一份掩蔽语料。前提 = 同一 pytest 进程
内生产树不增删改(测试纪律:测试零真实副作用,写真实 src 本就违规)。
"""
from __future__ import annotations

import ast
import bisect
import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path

#: 掩蔽语料缓存(键 = 扫描根路径字符串;进程内,pytest 会话级生命周期)。
_corpus_cache: dict[str, tuple[MaskedSource, ...]] = {}


def docstring_spans(text: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """收集模块/类/函数 docstring 跨度((起行,起列),(止行,止列))。

    docstring 判定 = 定义体首语句为孤立字符串表达式(ast 标准语义),
    嵌套定义逐层收集;解析失败返回空表(扫描回退不掩蔽 docstring,宁误红)。
    """
    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return spans
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                expr = body[0]
                spans.append(((expr.lineno, expr.col_offset),
                              (expr.end_lineno, expr.end_col_offset)))
    return spans


def mask_source_text(text: str) -> str:
    """返回掩蔽后的文本:注释与 docstring 按字符等长置空(保行号)。

    tokenize 失败回退返回原文(全判,宁误红不漏判);其余机制见模块 docstring。
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return text   # 回退:原文全判
    masked_lines = text.split('\n')
    doc_spans = docstring_spans(text)

    def _in_docstring(tok: tokenize.TokenInfo) -> bool:
        start = (tok.start[0], tok.start[1])
        end = (tok.end[0], tok.end[1])
        return any(s <= start and end <= e for s, e in doc_spans)

    def _blank(srow: int, scol: int, erow: int, ecol: int) -> None:
        """把 (srow,scol)-(erow,ecol) 跨度逐字符置空(等长,保行号)。"""
        for row in range(srow, erow + 1):
            line = masked_lines[row - 1]
            c0 = scol if row == srow else 0
            c1 = ecol if row == erow else len(line)
            masked_lines[row - 1] = \
                line[:c0] + ' ' * (c1 - c0) + line[c1:]

    for tok in tokens:
        if tok.type == tokenize.COMMENT or (
                tok.type == tokenize.STRING and _in_docstring(tok)):
            _blank(tok.start[0], tok.start[1], tok.end[0], tok.end[1])

    return '\n'.join(masked_lines)


def find_violations(
        masked_text: str, *patterns: re.Pattern) -> list[tuple[int, str, int]]:
    """在**已掩蔽**文本上跑正则,返回 (行号, 命中行原文, 正则序号)。

    行号取匹配起点所在行,1 基;命中行原文取自掩蔽**前**的对应行
    (同一 (行, 正则) 只记一条;不同正则分别记账,序号供调用方区分类别)。
    断言消息的格式化归调用方(各锁报错文案不同)。
    """
    lines = masked_text.split('\n')
    # 掩蔽保行号:掩蔽前后行集合一致,命中行原文取自本列表即可。
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line) + 1)

    hits: dict[tuple[int, int], str] = {}
    for pi, pat in enumerate(patterns):
        for m in pat.finditer(masked_text):
            row = bisect.bisect_right(line_starts, m.start()) - 1
            hits.setdefault((row, pi), lines[row].strip()[:120])
    return [(row + 1, hits[(row, pi)], pi)
            for row, pi in sorted(hits)]


def scan_code_violations(
        text: str, *patterns: re.Pattern) -> list[tuple[int, str, int]]:
    """掩蔽 + 扫描一步入口(单文件/合成语料直扫用)。

    全树扫描锁走 ``build_masked_sources`` + ``find_violations``(掩蔽一次
    多锁复用);本入口保留原始语义等价形,供变异自检与零散单文件扫描。
    """
    return find_violations(mask_source_text(text), *patterns)


@dataclass(frozen=True)
class MaskedSource:
    """一棵扫描根下的单个源文件(掩蔽语料项)。

    path = 文件绝对路径;rel = 相对扫描根的 posix 相对路径(白名单/豁免
    判定用);masked = 掩蔽后全文(注释/docstring 置空,保行号)。
    """
    path: Path
    rel: str
    masked: str


def build_masked_sources(root: Path) -> tuple[MaskedSource, ...]:
    """收集 root 下全部 *.py,文件列表+文本+掩蔽各一次(进程内缓存)。

    多个全树扫描锁(可跨测试模块)经各自 module fixture 调用本函数,同根
    只构建一次;缓存键 = 扫描根路径。排序按全路径(断言消息顺序确定)。
    """
    key = str(root)
    cached = _corpus_cache.get(key)
    if cached is not None:
        return cached
    sources: list[MaskedSource] = []
    for p in sorted(root.rglob('*.py')):
        if '__pycache__' in p.parts:
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        sources.append(MaskedSource(
            path=p, rel=p.relative_to(root).as_posix(),
            masked=mask_source_text(text)))
    result = tuple(sources)
    _corpus_cache[key] = result
    return result
