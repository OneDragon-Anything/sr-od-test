"""统一节点改写注册表解析层 · 测试面(cw_node_schedule)。

设计依据 = invest-effects-calc 迭代 designs/T-18-zhanzheng-bianjiang.md
§9(用户裁定 2026-10-15:统一机制设计 + 位面 3 真值入码);知识权威版本 =
docs/game/currency_war/research/plane_schedule_observed.md「裁定记录
(用户,2026-10-15)」。测试面地图:

- 战争边疆(替换型):P1/P2 原样默认表(对象同一性)、P3 逐值替换
  (3-1/3-2/3-4 battle→encounter,其余槽不动,节点总数不变);
- 人身意外险(插入型,T-8 迁移护航):三位面 boss 位前插 supply 逐值
  不变(P3 自动适用 = 8 节点);
- 默认环境(表外/空名):原样返回默认表(对象同一性,禁原地改);
- 多规则共存:插入 + 替换同 env 正交叠加(封闭集承诺);
- import 期校验炸错:规则形状封闭集逐形(未知种类/元组形状/位面集外/
  kind 集外/old=new/空键/空规则);
- 户口唯一性:战争边疆只在节点改写注册表,全部 ENV_* 效果表零条目
  (设计裁决点 2:无经济/赠品通道,误装域内通道由本组断言先红)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_node_schedule as ns
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    P1_NODE_SEQUENCE,
    P2_NODE_SEQUENCE,
    P3_NODE_SEQUENCE,
    PLANE_NODE_TABLES,
    resolve_plane_node_seqs,
)


def test_war_frontier_replaces_p3_battle_slots_only() -> None:
    """战争边疆:P1/P2 与默认表逐值同(对象同一性);P3 battle 槽换
    encounter、其余槽原样(替换 1:1,长度不变;「战斗节点」= 类型读法
    仅普通战斗,裁决点 3)。"""
    out = resolve_plane_node_seqs('战争边疆')
    assert set(out) == {1, 2, 3}
    assert out[1] is P1_NODE_SEQUENCE and out[2] is P2_NODE_SEQUENCE
    assert out[3] == ('encounter', 'encounter', 'supply', 'encounter',
                      'encounter', 'reward', 'boss')
    assert len(out[3]) == len(P3_NODE_SEQUENCE), '替换 1:1 不改节点总数'


def test_insurance_insert_migration_value_identical_p3_now_applies() \
        -> None:
    """人身意外险(T-8 迁移后护航):每个 boss 位前插 supply,三位面
    逐值与迁移前一致(位面 1 9→10、位面 2 7→8;P3 入表后插入自动适用
    = 7→8,设计 §9.2)。"""
    mod = resolve_plane_node_seqs('人身意外险')
    assert set(mod) == {1, 2, 3}
    assert mod[1][-2:] == ('supply', 'boss')
    assert mod[1][:-2] == P1_NODE_SEQUENCE[:-1]
    assert len(mod[1]) == 10
    assert mod[2][-2:] == ('supply', 'boss')
    assert mod[2][:-2] == P2_NODE_SEQUENCE[:-1]
    assert len(mod[2]) == 8
    assert mod[3][-2:] == ('supply', 'boss')
    assert mod[3][:-2] == P3_NODE_SEQUENCE[:-1]
    assert len(mod[3]) == 8


def test_non_registry_env_returns_default_tables_identity() -> None:
    """表外环境(含空名)原样返回默认表,元组对象不复制不原地改。"""
    for name in ('头彩', '火药味', '过剩经费', ''):
        out = resolve_plane_node_seqs(name)
        assert out == dict(PLANE_NODE_TABLES)
        assert out[1] is P1_NODE_SEQUENCE \
            and out[2] is P2_NODE_SEQUENCE \
            and out[3] is P3_NODE_SEQUENCE


def test_multi_rule_env_insert_and_replace_compose(monkeypatch) -> None:
    """多规则共存(元组多元素,设计 §9.1):同 env 插入 + 替换按序
    叠加,两规则正交(P3 同时吃到 supply 前插与 battle→encounter)。"""
    monkeypatch.setattr(
        ns, 'ENV_NODE_REWRITE_RULES',
        {'测试合成环境': (('replace', 3, 'battle', 'encounter'),
                          ('insert_supply_before_boss',))})
    out = resolve_plane_node_seqs('测试合成环境')
    assert out[1][-2:] == ('supply', 'boss'), '插入型逐位面生效'
    assert out[3] == ('encounter', 'encounter', 'supply', 'encounter',
                      'encounter', 'reward', 'supply', 'boss'), \
        'P3 = 替换 + boss 前插叠加(8 节点)'


def test_validate_rewrite_rules_bad_shapes_raise(monkeypatch) -> None:
    """import 期校验炸错逐形(沿「import 即炸」风格,非法形状在注册期
    响亮而非静默失义)。"""
    bad: tuple[tuple[str, dict], ...] = (
        ('规则种类', {'X': (('delete_all',),)}),
        ('插入型规则形状非法', {'X': (('insert_supply_before_boss', 1),)}),
        ('替换型规则形状非法', {'X': (('replace', 3, 'battle'),)}),
        ('不在真值表', {'X': (('replace', 4, 'battle', 'encounter'),)}),
        ('kind 集外', {'X': (('replace', 3, 'minion', 'encounter'),)}),
        ('old=new 无义', {'X': (('replace', 3, 'battle', 'battle'),)}),
        ('空串键', {'': (('insert_supply_before_boss',),)}),
        ('空规则元组', {'X': ()}),
    )
    for tag, registry in bad:
        monkeypatch.setattr(ns, 'ENV_NODE_REWRITE_RULES', registry)
        with pytest.raises(ValueError, match=tag):
            ns.validate_rewrite_rules()


def test_war_frontier_has_no_domain_effect_channel() -> None:
    """户口唯一性(设计 §8 裁定 4):战争边疆只在统一节点改写注册表有
    户口,全部效果域 ENV_* 表零条目——任何人误装经济/赠品通道,本断言
    先红。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        ENV_ECONOMY,
        ENV_GIFTS,
        ENV_ORE_GRANTS,
        ENV_POOL_REWRITE,
        ENV_REFRESH_GRANTS,
        ENV_STREAK_GRANTS,
        ENV_SUPPLY_EQUIP_COUNT,
    )
    assert '战争边疆' in ns.ENV_NODE_REWRITE_RULES
    for table in (ENV_ECONOMY, ENV_GIFTS, ENV_ORE_GRANTS,
                  ENV_POOL_REWRITE, ENV_REFRESH_GRANTS,
                  ENV_STREAK_GRANTS, ENV_SUPPLY_EQUIP_COUNT):
        assert '战争边疆' not in table, type(table).__name__
