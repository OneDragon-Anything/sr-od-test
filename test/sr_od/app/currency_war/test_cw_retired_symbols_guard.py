"""退役符号全零守卫(负向墓碑扫描;AST 扫描形态同守卫锁先例)。

来源:自 test_cw_t64_retired_symbols_guard.py 整体并入(2026-09-12 归并批,
按机制主题文件命名规范);被删符号集出处见下。

被删符号集(17 个;第 18 个 ``v3_pending_rollback`` 由
test_cw_comps_library.py::test_valley_rollback_slot_zero_consumer_guard
专辖,不在此重复断言,两锁合计恰覆盖方案申报的 18 符号集):

- C2 谷底回滚(04_survival_budget §7 #7,2026-09-04 用户裁定退役):
  ``VALLEY_ROLLBACK_LOSS``/``rollback_weakest``/``_swap_action``/
  ``_sell_action``/``v3_evolution``(登记臂唯一前置,零写端);
- C5 掉血三臂(04_survival_budget §7 #8,同日定谳退役):
  ``BloodAlarmTracker``/``v3_alarm``/``v3_prev_hp``/
  ``_alarm_node_type_fallback``/``NODE_TOKEN_TO_WORD``/
  ``DEFECT_KIND_BLOOD_ALARM_NODE_FALLBACK``;
- flow 结算策略半(随 #8 同批删除):``_drain_pending_round_outcomes``/
  ``_process_settlement_strategy_half``;
- T-183 三死函数(v1/decision_v2 旧栈遗留,调用面已随旧栈消亡):
  ``_want_level_up``/``_resolve_level_goal``/``roll_affordable``/
  ``_xp_gold_floor``(伴生死)。

删除依据 = 方案正本 .debug/temp/currency_war/T-64-交付报告.md §3
(v2)+ ADR-0638。本锁守「退役不复活」:src 树内上述符号的任何
标识符出现(声明/读/写)一律红。注释/docstring 中的墓碑提及不入
AST 标识符,天然不计——墓碑注是裁决索引,不是复活。

红(复活出现)处置 = 对应裁决均要求走新立项(硬闸门)而非原地复活:
谷底回滚/掉血趋势 → §7 #7/#8 各自的替代立项路径;三死函数语义 →
mandate_v1 契约域 comp 节奏锚命题件(候方案审)。立项落地后改判本锁
(禁机械跟绿)。

扫描边界申报:AST 标识符等值匹配(Name/Attribute/函数与类名/参数名);
字符串拼名、getattr 字符串形态、exec/动态构造不属本锁辖域(同
test_cw_read_primitive_guard / test_cw_comps_library 盲区自检的边界口径)。
"""
from __future__ import annotations

from pathlib import Path

#: 退役符号集(17;不含 v3_pending_rollback——见模块 docstring 分工)。
RETIRED_SYMBOLS: frozenset[str] = frozenset({
    # C2 谷底回滚 + 登记臂前置
    'VALLEY_ROLLBACK_LOSS',
    'rollback_weakest',
    '_swap_action',
    '_sell_action',
    'v3_evolution',
    # C5 掉血三臂 + 伴生
    'BloodAlarmTracker',
    'v3_alarm',
    'v3_prev_hp',
    '_alarm_node_type_fallback',
    'NODE_TOKEN_TO_WORD',
    'DEFECT_KIND_BLOOD_ALARM_NODE_FALLBACK',
    # flow 结算策略半
    '_drain_pending_round_outcomes',
    '_process_settlement_strategy_half',
    # T-183 三死函数 + 伴生
    '_want_level_up',
    '_resolve_level_goal',
    'roll_affordable',
    '_xp_gold_floor',
})


def _scan_symbol_occurrences(src_root: Path) -> dict[str, list[str]]:
    """AST 扫描 src 树退役符号的标识符出现 → {符号: ['相对路径:行号']}。

    收集面 = ast.Name(变量/常量引用)/ast.Attribute(属性与方法访问)/
    FunctionDef·AsyncFunctionDef·ClassDef(声明)/ast.arg(参数名)——
    覆盖声明/读/写三形态(写 Store 也是 Name 节点)。注释/docstring
    不入 AST,天然不计。
    """
    import ast

    hits: dict[str, list[str]] = {}
    for f in sorted(src_root.rglob('*.py')):
        text = f.read_text(encoding='utf-8')
        if not any(s in text for s in RETIRED_SYMBOLS):
            continue   # 文本预过滤(便宜),命中才做 AST 解析
        tree = ast.parse(text)
        rel = f.relative_to(src_root).as_posix()
        for node in ast.walk(tree):
            name: str | None = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                name = node.name
            elif isinstance(node, ast.arg):
                name = node.arg
            if name is not None and name in RETIRED_SYMBOLS:
                hits.setdefault(name, []).append(f'{rel}:{node.lineno}')
    return hits


def test_t64_retired_symbols_absent_in_src() -> None:
    """退役 17 符号在 src 树零标识符出现(声明/读/写全零)。"""
    src_root = Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
    hits = _scan_symbol_occurrences(src_root)
    assert not hits, (
        '退役符号在 src 树复活(04_survival_budget §7 #7/#8 已裁退役,'
        f'ADR-0638;复活须走各裁决的新立项路径后改判本锁): {hits}')
