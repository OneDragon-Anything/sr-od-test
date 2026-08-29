# -*- coding: utf-8 -*-
"""r361 补档优先部署键测试(局46:cap 满序竞争,桥件挤掉仙舟3 补档件)。

局46 实锤:xianzhou_train 锁线下,飞霄(hunt 桥 core)与丹恒·饮月
(仙舟 2→3 恰达 tier1)同为 tgt;slot 序让飞霄先占 cap,丹恒·饮月
全程 bench → 激活档 0 → 恒 -13 失败。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS, get_char
from sr_od.application.currency_war.operations.prep.deploy_bench import (
    _tier_completes,
)


def _bonds(name: str) -> frozenset[str]:
    ch = get_char(name)
    assert ch is not None, name
    return frozenset(ch.factions) | frozenset(ch.flows)


def test_tier_completes_xianzhou3() -> None:
    """局46 场景:板面仙舟2(爻光+藿藿),丹恒·饮月上阵 → 仙舟3=tier1。"""
    deployed = {'仙舟': 2}
    assert CHARACTERS.get('丹恒·饮月') is not None
    assert _tier_completes(_bonds('丹恒·饮月'), deployed) == 1


def test_bridge_char_no_tier_jump() -> None:
    """飞霄(hunt 桥件,狼狩+追击)在仙舟2 板面无档跃迁 → 0(排序后置)。"""
    deployed = {'仙舟': 2}
    assert _tier_completes(_bonds('飞霄'), deployed) == 0


def test_no_completion_when_below_tier() -> None:
    """仙舟1 时第 2 张仙舟(2<3 未达档)→ 0;第 3 张才是 1。"""
    assert _tier_completes(_bonds('丹恒·饮月'), {'仙舟': 1}) == 0
    assert _tier_completes(_bonds('丹恒·饮月'), {'仙舟': 2}) == 1


def test_sort_order_semantics() -> None:
    """排序语义:tgt 内补档件先于桥件(稳定排序,同键保 slot 序)。"""
    deployed = {'仙舟': 2, '列车同行': 1}
    # slot 序:飞霄(桥)在前,丹恒·饮月(补档)在后 → 排序后反转
    candidates = ['飞霄', '丹恒·饮月']
    candidates.sort(key=lambda n: _tier_completes(_bonds(n), deployed),
                    reverse=True)
    assert candidates[0] == '丹恒·饮月'


def test_flow_faction_also_counts() -> None:
    """流派羁绊同样计档(击破 2→3 用 flows tag 判)。"""
    ch = next(c for c in CHARACTERS.values() if '击破' in c.flows)
    tiers_has_3 = 3 in __import__(
        'sr_od.application.currency_war.data.cw_factions', fromlist=['FACTIONS']
    ).FACTIONS['击破'].tiers
    if tiers_has_3:
        assert _tier_completes(frozenset(ch.flows), {'击破': 2}) == 1


def test_empty_names_no_discount() -> None:
    """r361b(review A 守卫):board_names 空集(tracked miss)不折扣。"""
    from sr_od.application.currency_war.cw_line_defs import (
        p1_formation_target,
    )
    board = {'仙舟': 3, '列车同行': 2}   # recipe 5 档
    _ph, _tgt, cur = p1_formation_target(5, board, set())
    assert cur == 5, '空集=SIFT miss,应足额不折扣'


def test_discount_applies_with_real_names() -> None:
    """核心不在场(有名可判)→ 折扣生效(空壳档位不算数)。"""
    from sr_od.application.currency_war.cw_line_defs import (
        p1_formation_target,
    )
    board = {'仙舟': 3, '列车同行': 2}
    _ph, _tgt, cur = p1_formation_target(5, board, {'飞霄', '椒丘'})
    assert cur == 3, '核心 0/3 → 5-2=3'
