"""占席道具映射桥 BENCH_ITEM_KINDS 测试(镜像 src = kernel/cw_investments.py,
被测 = 映射表数据性质,按拆目录规范落位;同 src 兄弟测试 =
kernel/test_cw_investments.py〔已登记超限文件,只读复用不追加〕)。

测试面依据 = 迭代 T-39 专家研讨会设计(.debug/progress/2026-09-23-invest-
effects-calc/designs/T-39-zhuanjia-yantaohui.md)§2.2 + §4 锁 1;
2026-10-28 校验治理后 `_validate_bench_item_kinds` 已删(键集双向闭合/
值域封闭属防登记笔误类,漏登的运行期后果 = 落席直查 KeyError 响亮可见),
本文件只留映射表数据性质锁(期望值派生式现算,不手抄键集):
- 键集 == 两张授予表 items_* 通道道具名并集(双向);
- 词表 = 键集派生;
- 专家研讨会登记与映射同批已登记(专家邀请函 = bookcard 槽件首例)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_KINDS,
    BENCH_ITEM_NAMES,
    ENV_GIFTS,
    STRATEGY_GRANTS,
)


def _granted_item_names() -> set[str]:
    """授予通道占席道具名并集(与已删校验体同式派生;期望单一来源 =
    登记表本身,不手抄)。"""
    granted: set[str] = set()
    for grant in (*ENV_GIFTS.values(), *STRATEGY_GRANTS.values()):
        granted.update(grant.items_immediate)
        granted.update(item for _node_key, item in grant.items_scheduled)
    return granted


def test_bench_item_kinds_closed_set_and_expert_registration() -> None:
    """闭集正态 + 已登记(设计 §2.2/§4 锁 1 数据性质):映射键集 ==
    授予通道并集(双向,派生式现算);词表 = 键集派生;专家研讨会登记 =
    items_immediate('专家邀请函', '简易武装箱')(卡文序),专家邀请函
    ∈ 映射且 kind='bookcard'(bookcard 槽件发放首例)。"""
    assert set(BENCH_ITEM_KINDS) == _granted_item_names(), \
        '键集双向闭合(少登/多登任一即失配)'
    assert frozenset(BENCH_ITEM_KINDS) == BENCH_ITEM_NAMES, '词表派生自映射'
    grant = ENV_GIFTS['专家研讨会']
    assert grant.items_immediate == ('专家邀请函', '简易武装箱'), \
        '登记双件卡文序(邀请函先箱后)'
    assert BENCH_ITEM_KINDS['专家邀请函'] == 'bookcard'
    assert BENCH_ITEM_KINDS['简易武装箱'] == 'supply_box'
