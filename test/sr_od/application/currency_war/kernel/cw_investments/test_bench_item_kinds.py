"""占席道具映射桥 BENCH_ITEM_KINDS 测试(镜像 src = kernel/cw_investments.py,
被测 = `_validate_bench_item_kinds` 与映射表,按拆目录规范落位;同 src 兄弟
测试 = kernel/test_cw_investments.py〔在册超限文件,只读复用不追加〕)。

测试面依据 = 迭代 T-39 专家研讨会设计(.debug/progress/2026-09-23-invest-
effects-calc/designs/T-39-zhuanjia-yantaohui.md)§2.2 + §4 锁 1:
- 键集双向闭合 = 两张授予表 items_* 通道道具名并集(期望值派生式现算,
  不手抄键集;少登 = 落席直查 KeyError 前置炸 / 多登 = 孤儿键炸,import 期
  校验直调复现);
- 值域封闭:'supply_box' | 'bookcard'(观察专属 tome 豁免不在检域);
- 专家研讨会登记与映射同批在册(缺一 = 闭集双向炸,无书写顺序语义)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_KINDS,
    BENCH_ITEM_NAMES,
    ENV_GIFTS,
    STRATEGY_GRANTS,
)


def _granted_item_names() -> set[str]:
    """授予通道占席道具名并集(与校验体同式派生;期望单一来源 = 登记表
    本身,不手抄)。"""
    granted: set[str] = set()
    for grant in (*ENV_GIFTS.values(), *STRATEGY_GRANTS.values()):
        granted.update(grant.items_immediate)
        granted.update(item for _node_key, item in grant.items_scheduled)
    return granted


def test_bench_item_kinds_closed_set_and_expert_registration() -> None:
    """闭集正态 + 登记在册(设计 §2.2/§4 锁 1):映射键集 == 授予通道并集
    (双向闭合,派生式现算);词表 = 键集派生;专家研讨会登记 =
    items_immediate('专家邀请函', '简易武装箱')(卡文序),专家邀请函
    ∈ 映射且 kind='bookcard'(bookcard 槽件发放首例);现值直调校验零炸。"""
    assert set(BENCH_ITEM_KINDS) == _granted_item_names(), \
        '键集双向闭合(少登/多登任一即失配)'
    assert frozenset(BENCH_ITEM_KINDS) == BENCH_ITEM_NAMES, '词表派生自映射'
    grant = ENV_GIFTS['专家研讨会']
    assert grant.items_immediate == ('专家邀请函', '简易武装箱'), \
        '登记双件卡文序(邀请函先箱后)'
    assert BENCH_ITEM_KINDS['专家邀请函'] == 'bookcard'
    assert BENCH_ITEM_KINDS['简易武装箱'] == 'supply_box'
    cw_investments._validate_bench_item_kinds()   # 现值直调零炸


def test_bench_item_kinds_missing_key_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """少登 = import 炸(设计 §4 锁 1):删任一箱名 → 授予通道道具落席直查
    KeyError 前置炸,校验 ValueError 响亮(注入 + 直调沿登记表校验惯用法)。"""
    bad = {k: v for k, v in BENCH_ITEM_KINDS.items() if k != '简易武装箱'}
    monkeypatch.setattr(cw_investments, 'BENCH_ITEM_KINDS', bad)
    with pytest.raises(ValueError, match='键集缺登'):
        cw_investments._validate_bench_item_kinds()


def test_bench_item_kinds_orphan_key_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """多登 = 孤儿键炸(设计 §4 锁 1):加非授予通道道具名 → 静默落错身份
    风险,校验 ValueError 响亮。"""
    bad = dict(BENCH_ITEM_KINDS)
    bad['不存在道具X'] = 'supply_box'
    monkeypatch.setattr(cw_investments, 'BENCH_ITEM_KINDS', bad)
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_bench_item_kinds()


def test_bench_item_kinds_value_domain_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """值域封闭(设计 §4 锁 1):值越界('unit' 等)→ ValueError;合法值 =
    'supply_box' | 'bookcard'(观察专属 tome 豁免不在检域)。"""
    bad = dict(BENCH_ITEM_KINDS)
    bad['简易武装箱'] = 'unit'
    monkeypatch.setattr(cw_investments, 'BENCH_ITEM_KINDS', bad)
    with pytest.raises(ValueError, match='值域越界'):
        cw_investments._validate_bench_item_kinds()
