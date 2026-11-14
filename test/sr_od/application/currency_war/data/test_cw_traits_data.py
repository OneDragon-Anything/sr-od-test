"""货币战争羁绊数据层结构守卫(镜像 src = data/cw_traits_data.py)。

出处 = cw_traits_data.py 模块 docstring(TRAITS/trait_by_name 双索引契约)与
文件头 members 口径注释块(可组队员口径/is_hide 过滤/count_mode 枚举)。
锁生成产物的结构不变量:双索引键集一致/count_mode 枚举合法/members 注册表
sanity——条目数与成员名单随游戏版本变动(版本更新重跑生成器重写数据),
一律不锁。
"""

from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_traits_data import TRAITS, trait_by_name

#: count_mode 合法枚举(TOTAL=总上场人数 / STAR3=三星上场人数;新增口径
#: 须数据层字段注释与消费分支同步扩展后才入本集)。
_COUNT_MODES = {'TOTAL', 'STAR3'}


def test_dual_index_key_consistency() -> None:
    """双索引键集一致锁(cw_traits_data.py 模块 docstring):TRAITS 键集 =
    各条目 trait_id 集合,trait_by_name 键集 = 各条目 trait_name 集合;两索引
    条目数一致且名字索引回指同对象(键型分别为「稳定机器键」与「消费侧标签
    键型」,两路查询必须取到同一份数据——平行索引双份抄写时此锁红)。
    空表(生成器断流)同红。"""
    assert len(TRAITS) > 0
    assert set(TRAITS) == {t.trait_id for t in TRAITS.values()}
    assert set(trait_by_name) == {t.trait_name for t in TRAITS.values()}
    assert len(trait_by_name) == len(TRAITS)
    assert all(trait_by_name[t.trait_name] is t for t in TRAITS.values())


def test_count_mode_enum_legal() -> None:
    """激活计数控枚举锁(cw_traits_data.py Trait.count_mode 字段注释):
    count_mode 全集 ⊆ {TOTAL, STAR3}——消费链按此二值分支选计数口径,
    枚举外值 = 口径分支断裂;具体哪些羁绊为 STAR3 随官方文案变动,不锁名单。"""
    assert all(t.count_mode in _COUNT_MODES for t in TRAITS.values())


def test_members_registry_sanity() -> None:
    """成员口径 sanity 锁(cw_traits_data.py 文件头 members 口径注释块):
    每个羁绊成员非空(独立羁绊成员为单角色名,空集 = 翻译断流);全员 ⊆
    角色注册表规范名(members = role_ids 经注册表翻译的名字形态,查无名 =
    脱离注册表的平行名单回流);零 is_hide 成员(可组队员口径:腾荒类隐藏
    随从不算成员,过滤锚 = 注册表 is_hide)。"""
    registry_names = {c.name for c in CHARACTERS}
    hidden_names = {c.name for c in CHARACTERS if c.is_hide}
    for t in TRAITS.values():
        assert len(t.members) > 0, t.trait_name
        assert set(t.members) <= registry_names, t.trait_name
        assert not (set(t.members) & hidden_names), t.trait_name
