"""货币战争角色注册表语义锁(镜像 src = data/cw_chars.py)。

出处 = cw_chars.py 模块 docstring(库形态/牌池口径/规范名原则/系统单位/
派生集合各段)与 docs/game/currency_war/research/v47_tenghuang_binding.md
(丹恒·腾荒 is_hide 依据)。锁 v4.7 赛季名单的结构语义:多档查询/名字归一/
系统单位拆分/虚拟集合并集/牌池排除/专家空集/开拓者基名直通/掉出角色
不在册。规模断言(63/68/66/费段分布)为该赛季 roster 事实——版本更新
重跑生成器重写官方段时,随同批更新这些期望值。
"""

from __future__ import annotations

from collections import Counter

import pytest

from sr_od.application.currency_war.data.cw_chars import (
    ALL_UNIT_NAMES,
    ALL_UNITS,
    CHARACTER_ROSTER,
    CHARACTERS,
    EXPERT_CHARS,
    SYSTEM_UNIT_ROSTER,
    SYSTEM_UNITS,
    assert_expert_names,
    chars_by_cost,
    get_char,
    is_trailblazer,
    trailblazer_form,
)

#: 官方 config 衍生角色名用的 bullet 点(U+2022 •);规范名一律间隔号
#: U+00B7(·),归一单一源 = 生成器 canon()。
_BULLET = '\u2022'


def test_get_char_identity_and_tier_query() -> None:
    """多档角色查询语义(cw_chars.get_char docstring):身份查询(cost=None)
    返起始档——星神★阿哈三档(4/5/7,source 151112/151122/151132)中最小
    档 4;档位查询命中 5 费档(source='151122');该档不存在返 None
    (cost 给定分支下名字不存在同返 None)。"""
    aha = get_char('星神★阿哈')
    assert aha is not None
    assert aha.cost == 4
    assert aha.source == '151112'
    tier5 = get_char('星神★阿哈', 5)
    assert tier5 is not None
    assert tier5.source == '151122'
    assert get_char('星神★阿哈', 6) is None


def test_name_canon_no_bullet_in_registry() -> None:
    """规范名归一锁(cw_chars.py 规范名原则段):官方衍生角色名用 bullet
    U+2022(•),注册表规范名 = 间隔号 U+00B7(·) = 模板目录名 = roster
    成员名——丹恒·饮月按间隔号命中;角色名与系统单位名全名单零 bullet
    残留(遍历断言,防生成端归一守卫失效回流)。"""
    assert get_char('丹恒·饮月') is not None
    assert all(_BULLET not in c.name for c in CHARACTERS)
    assert all(_BULLET not in n for n in SYSTEM_UNITS)


def test_hide_char_and_visible_cost_distribution() -> None:
    """牌池排除锁(cw_chars.py 牌池口径段;腾荒 is_hide 依据 =
    docs/game/currency_war/research/v47_tenghuang_binding.md):丹恒·腾荒
    is_hide=True(饮月绑定随从,剔出玩家可见列表);可见口径费段分布 =
    {1:14, 2:12, 3:12, 4:13, 5:10, 7:1}(63 条中 62 条可见,腾荒 5 费被剔);
    数据层查询 chars_by_cost 不过滤 is_hide(过滤归购买/概率语义消费方)。"""
    th = get_char('丹恒·腾荒')
    assert th is not None
    assert th.is_hide is True
    dist = Counter(c.cost for c in CHARACTERS if not c.is_hide)
    assert dict(sorted(dist.items())) == {
        1: 14,
        2: 12,
        3: 12,
        4: 13,
        5: 10,
        7: 1,
    }
    assert sum(dist.values()) == 62
    assert any(c.is_hide for c in chars_by_cost(5)), (
        '数据层查询不滤 is_hide(牌池排除归消费方)'
    )


def test_system_units_split_from_characters() -> None:
    """系统单位拆分锁(cw_chars.py 系统单位段):佩佩为游戏系统赠送的非
    购买单位,不在纯角色注册表(CHARACTER_ROSTER 不含、get_char 返 None),
    在 SYSTEM_UNITS/SYSTEM_UNIT_ROSTER;姵姵(投资卡孪生姵姵发放对象)在册;
    dict 键 = name 构造约定全量一致。"""
    assert '佩佩' not in CHARACTER_ROSTER
    assert '佩佩' in SYSTEM_UNIT_ROSTER
    assert get_char('佩佩') is None
    assert '姵姵' in SYSTEM_UNIT_ROSTER
    assert len(SYSTEM_UNITS) == 5
    assert all(SYSTEM_UNITS[k].name == k for k in SYSTEM_UNITS)


def test_virtual_collections_union() -> None:
    """虚拟集合并集锁(cw_chars.py 派生集合段):ALL_UNITS = 官方镜像 63
    角色 + 系统单位 5 = 68;ALL_UNIT_NAMES = CHARACTER_ROSTER ∪
    SYSTEM_UNIT_ROSTER = 66(角色 63 名唯一——阿哈三档同名不重复计,
    加系统单位 5)。"""
    assert len(CHARACTERS) == 63
    assert len(ALL_UNITS) == 68
    assert len(ALL_UNIT_NAMES) == 66
    assert ALL_UNIT_NAMES == CHARACTER_ROSTER | SYSTEM_UNIT_ROSTER


def test_dropped_chars_not_registered() -> None:
    """掉出角色不在册锁(v4.7 换赛季收缩;掉出确认清单 =
    data/cw_dropped_names.V47_DROPPED_CHARS):布洛妮娅/彦卿(v4.7 名单外)
    与开拓者·欢愉(旧双形态名,现名单开拓者仅基名条目)查无——get_char
    返 None 且不入任何 roster 词表(闭集闸按现役口径拒绝)。"""
    for name in ('布洛妮娅', '彦卿', '开拓者·欢愉'):
        assert get_char(name) is None, name
        assert name not in CHARACTER_ROSTER, name
        assert name not in ALL_UNIT_NAMES, name


def test_expert_chars_empty_and_gate_rejects_all() -> None:
    """专家空集锁(cw_chars.py EXPERT_CHARS 段注):v4.7 名单 is_expert 全
    False → 空集;空集下闭集闸 = 拒绝一切专家写入——assert_expert_names
    传入任意角色名 raise ValueError(解锁状态写入期防线)。"""
    assert len(EXPERT_CHARS) == 0
    assert all(not c.is_expert for c in CHARACTERS)
    with pytest.raises(ValueError):
        assert_expert_names(('花火',))


def test_trailblazer_base_name_passthrough() -> None:
    """开拓者基名直通锁(cw_chars.py 开拓者形态切换段):v4.7 名单开拓者
    仅基名单条目 → 形态表清空,trailblazer_form 双排均原样返回基名;
    非开拓者原样返回;is_trailblazer 恒 False(数据驱动空转,形态表恢复
    时归一机制随之复活)。"""
    assert trailblazer_form('开拓者', 'front') == '开拓者'
    assert trailblazer_form('开拓者', 'back') == '开拓者'
    assert trailblazer_form('花火', 'front') == '花火'
    assert is_trailblazer('开拓者') is False
    assert is_trailblazer('花火') is False
