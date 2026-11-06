"""sr_codes 码表快照与三层查表单测。

锁的内容（design.md changes/mys-roster-detail §2 契约 1 / §3 码表单测策略；
断言依据全部来自本文件固化的权威映射对照表，不读本机易失实测件）：

- 四表封闭集：PROPERTY_INFO_SNAPSHOT 恰 56 码逐键锁定（权威快照，映射内容
  禁自行增删改——新码走兜底不进表）、命途/元素/部位三表全集与基准、
  RELIC_MAIN_AFFIX_ALLOWED 部位可选集逐键锁定；
- 三层查表行为：动态词典「干净可用值」优先（property_name_relic 先于 name）、
  占位符规避（实测词典两形态对偶：name 带 '#1[f1]%' 靠 relic 规避、relic 带
  '#1[i]' 靠 name 规避）、词典缺失退快照、空名占位码与词典外码落「未知属性」
  终兜底不抛异常；
- validate_relic_main_affix 部位校验：命中 / 跨部位拒绝 / 未知部位拒绝；
- 单参助手接入：各自查对应的表且 miss 兜底文案含入参。

撞域纪律（文档性声明，design.md §2 契约 1）：RELIC_POS_CN 键域 1-6 与星魂
ranks[].pos（星魂序号）撞值域但语义无关——部位表只服务遗器/饰品 pos 字段，
禁两处共用（src 侧 RELIC_POS_CN 注释同此声明）。
"""

from sr_od.mys.sr_codes import (
    BASE_TYPE_CN,
    ELEMENT_CN,
    PROPERTY_INFO_SNAPSHOT,
    RELIC_MAIN_AFFIX_ALLOWED,
    RELIC_POS_CN,
    PropertyNameInfo,
    resolve_base_type_cn,
    resolve_element_cn,
    resolve_property_cn,
    resolve_relic_pos_cn,
    validate_relic_main_affix,
)


def test_property_info_snapshot_closed_set() -> None:
    """快照恰 56 码逐键锁定：任何增删改映射即失败（权威快照禁自行增删改，
    新码一律走兜底而非进表）。空名占位码（8/61）如实存空串；pt=36 存干净值
    「治疗量加成」而非含 '#1[f1]%' 占位符的词典 name 原文。"""
    expected: dict[int, str] = {
        1: '生命值', 2: '攻击力', 3: '防御力', 4: '速度', 5: '暴击率',
        6: '暴击伤害', 7: '治疗量加成', 8: '', 9: '能量恢复效率',
        10: '效果命中', 11: '效果抵抗',
        12: '物理属性伤害提高', 13: '物理属性抗性提高',
        14: '火属性伤害提高', 15: '火属性抗性提高',
        16: '冰属性伤害提高', 17: '冰属性抗性提高',
        18: '雷属性伤害提高', 19: '雷属性抗性提高',
        20: '风属性伤害提高', 21: '风属性抗性提高',
        22: '量子属性伤害提高', 23: '量子属性抗性提高',
        24: '虚数属性伤害提高', 25: '虚数属性抗性提高',
        26: '基础生命值', 27: '生命值', 28: '基础攻击力', 29: '攻击力',
        30: '基础防御力', 31: '防御力', 32: '生命值', 33: '攻击力',
        34: '防御力', 35: '速度', 36: '治疗量加成',
        37: '物理属性抗性提高', 38: '火属性抗性提高', 39: '冰属性抗性提高',
        40: '雷属性抗性提高', 41: '风属性抗性提高', 42: '量子属性抗性提高',
        43: '虚数属性抗性提高',
        51: '速度', 52: '暴击率', 53: '暴击伤害', 54: '能量恢复效率',
        55: '治疗量加成', 56: '效果命中', 57: '效果抵抗', 58: '击破特攻',
        59: '击破特攻', 60: '能量上限', 61: '',
        71: '欢愉度', 72: '欢愉度',
    }
    assert len(PROPERTY_INFO_SNAPSHOT) == 56
    assert expected == PROPERTY_INFO_SNAPSHOT
    assert PROPERTY_INFO_SNAPSHOT[8] == ''
    assert PROPERTY_INFO_SNAPSHOT[61] == ''
    assert PROPERTY_INFO_SNAPSHOT[36] == '治疗量加成'
    assert '#' not in PROPERTY_INFO_SNAPSHOT[36]


def test_base_type_element_pos_anchor_and_closed_set() -> None:
    """命途/元素/部位三表全集与基准：命途恰 9 键（9=欢愉——开拓者 id 8010 与
    wiki「开拓者•欢愉」词条双确认；3=智识——姬子为基准）；元素恰 7 键
    （lightning→雷）；部位恰 6 键。"""
    assert len(BASE_TYPE_CN) == 9
    assert set(BASE_TYPE_CN.keys()) == set(range(1, 10))
    assert BASE_TYPE_CN[9] == '欢愉'
    assert BASE_TYPE_CN[3] == '智识'

    assert len(ELEMENT_CN) == 7
    assert set(ELEMENT_CN.keys()) == {
        'physical', 'fire', 'ice', 'lightning', 'wind', 'quantum', 'imaginary',
    }
    assert ELEMENT_CN['lightning'] == '雷'

    assert len(RELIC_POS_CN) == 6
    assert set(RELIC_POS_CN.keys()) == {1, 2, 3, 4, 5, 6}


def test_resolve_property_cn_prefers_clean_dynamic_dict_name() -> None:
    """层 1 动态词典：词条内取「干净可用值」，property_name_relic 优先于 name；
    任一字段含 '#' 占位符即弃用、落另一字段（两形态对偶：pt=36 形态与
    pt=26 形态）；词条两字段全空（pt=8 空名形态）退快照再落终兜底；
    词典缺该码（键不命中）退快照。"""
    both_clean: dict[int, PropertyNameInfo] = {
        52: {'name': '面板侧名', 'property_name_relic': '词条侧名'},
    }
    assert resolve_property_cn(52, both_clean) == '词条侧名'

    name_dirty: dict[int, PropertyNameInfo] = {
        36: {'name': '受治疗量提高#1[f1]%', 'property_name_relic': '治疗量加成'},
    }
    assert resolve_property_cn(36, name_dirty) == '治疗量加成'

    relic_dirty: dict[int, PropertyNameInfo] = {
        26: {'name': '基础生命值', 'property_name_relic': '基础生命值提高#1[i]'},
    }
    assert resolve_property_cn(26, relic_dirty) == '基础生命值'

    empty_entry: dict[int, PropertyNameInfo] = {
        8: {'name': '', 'property_name_relic': ''},
    }
    assert resolve_property_cn(8, empty_entry) == '未知属性(pt=8)'

    assert resolve_property_cn(1, {}) == '生命值'


def test_resolve_property_cn_snapshot_then_unknown_fallback() -> None:
    """层 2 快照（词典 None 直达快照值）；层 3 快照也 miss（pt=999，官方预占
    码位场景）返回「未知属性(pt=999)」不抛异常；快照中的空名占位码（8/61）
    同样落终兜底文案。"""
    assert resolve_property_cn(36, None) == '治疗量加成'
    assert resolve_property_cn(1, None) == '生命值'
    assert resolve_property_cn(999, None) == '未知属性(pt=999)'
    assert resolve_property_cn(8, None) == '未知属性(pt=8)'
    assert resolve_property_cn(61, None) == '未知属性(pt=61)'


def test_relic_main_affix_allowed_closed_set() -> None:
    """部位→主词条可选集逐键锁定（表 4 配置封闭集：1-2 恒单选、躯干无效果
    抵抗、连结绳无治疗量加成、位面球三百分比+七属性伤害）。"""
    expected: dict[int, frozenset[int]] = {
        1: frozenset({27}),
        2: frozenset({29}),
        3: frozenset({32, 33, 34, 52, 53, 55, 56}),
        4: frozenset({32, 33, 34, 51}),
        5: frozenset({32, 33, 34, 12, 14, 16, 18, 20, 22, 24}),
        6: frozenset({32, 33, 34, 54, 59}),
    }
    assert expected == RELIC_MAIN_AFFIX_ALLOWED


def test_validate_relic_main_affix() -> None:
    """主词条部位校验：pos=1 只认 27（头部恒生命平坦）；跨部位码（52 暴击率
    不在头部集）与未知部位（pos=7）一律 False。"""
    assert validate_relic_main_affix(1, 27) is True
    assert validate_relic_main_affix(1, 52) is False
    assert validate_relic_main_affix(7, 27) is False


def test_resolve_helpers_table_wiring_and_fallback() -> None:
    """三个单参助手接入：各查对应的表（命中值 = 表值），miss 兜底文案含入参
    便于定位。元素侧顺带锁 lightning≠Thunder 陷阱（传社区内部名 thunder 落
    兜底而非查中）。"""
    assert resolve_base_type_cn(9) == '欢愉'
    assert resolve_base_type_cn(99) == '未知命途(bt=99)'
    assert resolve_element_cn('lightning') == '雷'
    assert resolve_element_cn('thunder') == '未知元素(thunder)'
    assert resolve_relic_pos_cn(5) == '位面球'
    assert resolve_relic_pos_cn(7) == '未知部位(pos=7)'
