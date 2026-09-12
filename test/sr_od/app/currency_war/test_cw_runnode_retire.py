"""RunNode 历史抽象退役批:行为等价锁(用户裁决:按新架构统一)。

RunSupplyNode → CwScreenSupplyNode(cw_screen/cw_screen_supply_node.py)、
RunMegastarNode → CwScreenMegastar 内联(委托壳废止)。本文件锁迁移前后的
**行为断言一致**:①验证完成才 success(离开节点画面)(原 ADR-0264 关态
基线预置断言随 gate 模块退役删除,见 test_supply_leaves_node_success 注);
②仍在节点内 = 做动作 + round_retry(计 node_max_retry_times=8 预算,
超限框架转 FAIL 交回——预算语义不变);③源码零残留(基类/包路径)。
"""
# 掩蔽式扫描器依赖(T-103;实现见文件末尾「零残留」节)
import ast
import bisect
import io
import re
import tokenize
from pathlib import Path
from types import SimpleNamespace


def _make_op(cls, *, in_node: bool, do_action_calls: list):
    """构画面 op 桩(bypass __init__):round_by_find_area 程序化回 in_node。"""

    class _FakeArea:
        def __init__(self, ok: bool): self.is_success = ok

    class _Op(cls):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self.last_screenshot = object()
            self.op_name = cls.__name__
            self.ctx = SimpleNamespace(cw_match=None)

        def round_by_find_area(self, scr, screen, area, **k):
            return _FakeArea(in_node)

        def _do_action(self, screen):
            do_action_calls.append(1)

        def round_success(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=True)

        def round_retry(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=None,
                                   _retry=True)

        def round_fail(self, status=''):
            return SimpleNamespace(status=status, success=False)

        def save_screenshot(self, prefix=None):
            return ''

    return _Op()

# ==================== 补给节点流转(行为等价①②) ====================

def test_supply_leaves_node_success() -> None:
    """验证完成才 success:离开补给屏(锚 miss)→ success(节点完成)。
    (gate 清尾批:原「+关态稳定基线预置」断言随 gate 模块退役删除。)"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    actions: list = []
    op = _make_op(CwScreenSupplyNode, in_node=False, do_action_calls=actions)
    res = op.handle()
    assert res.success is True
    assert '节点完成' in res.status
    assert actions == []                       # 离开节点 = 不再发动作


def test_supply_in_node_act_then_retry() -> None:
    """仍在补给屏 → 做一个动作 + round_retry(计节点预算;不 success)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    actions: list = []
    op = _make_op(CwScreenSupplyNode, in_node=True, do_action_calls=actions)
    res = op.handle()
    assert actions == [1]                      # 每轮恰好一个动作
    assert getattr(res, '_retry', False) is True


def test_supply_budget_semantics_unchanged() -> None:
    """预算语义不变:node_max_retry_times=8(原 RunNode 子类口径,
    超限框架转 FAIL bail 交回)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    node = CwScreenSupplyNode.handle.operation_node_annotation
    assert node.node_max_retry_times == 8


# ==================== 巨星流转(行为等价①②) ====================

def test_megastar_leaves_node_success_with_settle() -> None:
    """巨星:overlay 消失 → success(完成承诺 = 固定 1.0s,原委托壳语义)
    (选中标记复位副作用随迁)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_flow_const import (
        CW_OVERLAY_SETTLE_S,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    actions: list = []
    op = _make_op(CwScreenMegastar, in_node=False, do_action_calls=actions)
    res = op.handle()
    assert res.success is True
    assert res.wait == CW_OVERLAY_SETTLE_S
    assert actions == []


def test_megastar_in_node_act_then_retry() -> None:
    """巨星:仍在 overlay → 一个动作 + round_retry。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    actions: list = []
    op = _make_op(CwScreenMegastar, in_node=True, do_action_calls=actions)
    res = op.handle()
    assert actions == [1]
    assert getattr(res, '_retry', False) is True


def test_megastar_budget_semantics_unchanged() -> None:
    """预算语义不变:node_max_retry_times=8(原 RunNode 子类口径)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    node = CwScreenMegastar.handle.operation_node_annotation
    assert node.node_max_retry_times == 8


# ==================== 零残留 ====================

# 掩蔽式扫描器(T-103,手法单一源 = T-93 定型版:同仓
# test_cw_old_stream_write_retirement.py 的 _docstring_spans/_scan_code_violations,
# commit 149f86b「retirement 锁判定域改掩蔽式,恢复 refs 复合正则检出力」;
# 两文件内联同构,三处成型后由后续批抽公共模块——申报见 T-103 报告⑤):
# 注释/docstring 在源文本上按字符等长置空后对代码文本跑正则。「RunNode 已
# 退役」类负向声明是退役背书而非活引用,置空后不误红;代码域引用(标识符/
# 字符串字面量)仍在域内,防复活。tokenize/ast 失败回退原文全判(宁误红)。
# (import 在文件顶部。)


def _docstring_spans(text: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """收集模块/类/函数 docstring 跨度((起行,起列),(止行,止列))。

    docstring 判定 = 定义体首语句为孤立字符串表达式(ast 标准语义),
    嵌套定义逐层收集;解析失败返回空表(扫描回退逐行全判,宁误红)。"""
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


def _scan_code_violations(
        text: str, *patterns: re.Pattern) -> list[tuple[int, str, int]]:
    """在掩蔽后的代码文本上跑正则,返回 (行号, 命中行原文, 正则序号)。

    机制 = T-93 定型掩蔽式:tokenize 取注释 token + ast 取 docstring 跨度,
    逐字符等长置空(保行号),finditer 对掩蔽后全文跑正则——豁免注释/
    docstring 文档性提及,正则按连续全文匹配,复合/跨 token 形照常检出
    (禁逐 token search:该退化使跨 token 正则永久失配盲绿)。失败回退 =
    tokenize 失败对原文全判、ast 失败不掩蔽 docstring(同向宁误红)。"""
    lines = text.split('\n')
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line) + 1)
    masked_lines: list[str] | None
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        masked_lines = None   # 回退:原文全判
    else:
        masked_lines = list(lines)
        doc_spans = _docstring_spans(text)

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

    judge_text = '\n'.join(masked_lines) if masked_lines is not None else text
    hits: dict[tuple[int, int], str] = {}
    for pi, pat in enumerate(patterns):
        for m in pat.finditer(judge_text):
            row = bisect.bisect_right(line_starts, m.start()) - 1
            hits.setdefault((row, pi), lines[row].strip()[:120])
    return [(row + 1, hits[(row, pi)], pi)
            for row, pi in sorted(hits)]


#: 零残留扫描正则(基类名/包路径;字面子串,无正则元字符)。
_RUNNODE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r'RunNode'), re.compile(r'run_nodes'))
_RUNNODE_LABELS: tuple[str, ...] = ('RunNode', 'run_nodes')


def test_runnode_zero_residue_in_src() -> None:
    """grep 零残留:currency_war src 下无 RunNode 基类/run_nodes 包路径的
    活引用(sim/telemetry 注释中的旧类名 RunSupplyNode 不含 RunNode 子串,
    且按纪律不动)。

    判定域 = 掩蔽代码域(T-103 迁移,机制见 _scan_code_violations):
    「RunNode 已退役」类负向声明(注释/docstring)不判红——退役背书而非
    活引用;代码域标识符/字符串字面量引用仍判红,防复活。"""
    root = Path('src/sr_od/application/currency_war')
    assert not (root / 'operations' / 'run_nodes').exists(), \
        'run_nodes/ 包应已删除'
    violations: list[str] = []
    for p in root.rglob('*.py'):
        text = p.read_text(encoding='utf-8', errors='ignore')
        for lineno, snippet, pi in _scan_code_violations(
                text, *_RUNNODE_PATTERNS):
            violations.append(
                f'{p}:{lineno} 残留 {_RUNNODE_LABELS[pi]}: {snippet}')
    assert not violations, 'RunNode 活引用残留(防复活):\n' + '\n'.join(violations)


def test_runnode_scan_mutation_selfcheck() -> None:
    """掩蔽式扫描变异自检(双向):负向声明不判红,代码域引用仍判红。

    防两种回归:①豁免写宽(注释/docstring 未置空即跳过整行)→ 真实引用
    漏判;②豁免失效(回退逐行原文)→「RunNode 已退役」负向声明误红复发。
    合成语料直扫 _scan_code_violations,不落生产树。"""
    # 豁免腿:注释/docstring 中的负向声明与历史提及不得判红
    assert _scan_code_violations(
        '# RunNode 基类已退役(按新架构统一,禁复活)', *_RUNNODE_PATTERNS) == []
    assert _scan_code_violations(
        '"""RunNode 历史抽象退役批:run_nodes 包路径已删除。"""',
        *_RUNNODE_PATTERNS) == []
    # 检出腿:代码域标识符/字符串字面量必须判红(防复活)
    hits = _scan_code_violations('class RunNode(SrOperation):',
                                 *_RUNNODE_PATTERNS)
    assert len(hits) == 1 and hits[0][2] == 0, f'类定义复活形须红,实得 {hits}'
    hits = _scan_code_violations("pkg = 'operations.run_nodes'",
                                 *_RUNNODE_PATTERNS)
    assert len(hits) == 1 and hits[0][2] == 1, f'包路径字面量复活形须红,实得 {hits}'
    # 混合腿:行尾注释不吞同行代码引用(豁免按 token 置空,不按行)
    hits = _scan_code_violations(
        '_legacy = RunNode  # RunNode 已退役(负向声明)', *_RUNNODE_PATTERNS)
    assert len(hits) == 1, f'行尾注释不豁免同行代码,实得 {hits}'
    # 跨 token 复合形:引用与注释隔行相邻,掩蔽只吞注释行不吞引用行
    hits = _scan_code_violations(
        'from x import RunNode\n# RunNode 已退役\ny = 1', *_RUNNODE_PATTERNS)
    assert len(hits) == 1 and hits[0][0] == 1, \
        f'隔行注释掩蔽不吞引用行,实得 {hits}'
