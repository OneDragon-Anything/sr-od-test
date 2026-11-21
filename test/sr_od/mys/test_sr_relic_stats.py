"""sr_relic_stats 词条语义层单测（口径词解析/名册消歧/数值解析直测）。

场景随迁自 test_relic_eval_tools 的规则 1 场景（该文件走 evaluate 公开
接口的回归锁不变），并对下沉公开函数补遗器侧直测：游戏内 op（词缀约束
判定）是这套语义的第二消费者，约束入参的展开与消歧行为按本文件锁死。
零副作用纯函数测试，零真实 IO。
"""

from sr_od.mys.sr_relic_stats import (
    parse_stat_value,
    resolve_criteria_word,
    resolve_roster_stat,
)


def test_criteria_word_alias_and_pack_expansion() -> None:
    """口径词展开三优先级：口径包 → 别名 → 标准名直通；未识别词返 None。"""
    assert resolve_criteria_word('双暴攻') == ['暴击率', '暴击伤害', '攻击力提高']
    assert resolve_criteria_word('双暴') == ['暴击率', '暴击伤害']
    assert resolve_criteria_word('暴击') == ['暴击率']
    assert resolve_criteria_word('暴伤') == ['暴击伤害']
    assert resolve_criteria_word('速度') == ['速度']  # 同名直通
    assert resolve_criteria_word('击破特攻') == ['击破特攻']
    assert resolve_criteria_word('充能') == ['能量恢复效率']
    assert resolve_criteria_word('不存在的词条') is None
    assert resolve_criteria_word(123) is None  # 非 str 入参


def test_roster_stat_flat_percent_disambiguation() -> None:
    """同名异义三词按 value 的 % 后缀消歧；非同名标准名直通；未识别返 None。

    % 后缀是 flat/% 唯一判别依据（名册 name_cn 平坦与百分比同名，出处见
    sr_relic_stats 模块 docstring 名册核对结论）。"""
    assert resolve_roster_stat('生命值', '42') == '生命值'
    assert resolve_roster_stat('生命值', '3.4%') == '生命值提高'
    assert resolve_roster_stat('攻击力', '352') == '攻击力'
    assert resolve_roster_stat('攻击力', '43.2%') == '攻击力提高'
    assert resolve_roster_stat('防御力', '55') == '防御力'
    assert resolve_roster_stat('防御力', '5.4%') == '防御力提高'
    assert resolve_roster_stat('暴击率', '9.3%') == '暴击率'  # 非同名直通
    assert resolve_roster_stat('速度', '25') == '速度'
    assert resolve_roster_stat('不认识的词条', '1%') is None
    assert resolve_roster_stat(None, '1%') is None


def test_parse_stat_value_percent_flat_and_failure() -> None:
    """数值解析：% 去后缀、平坦直取、失败按 0 计并返回警告文案。"""
    assert parse_stat_value('22.0%') == (22.0, None)
    assert parse_stat_value('55') == (55.0, None)
    value, warning = parse_stat_value('abc')
    assert value == 0.0
    assert warning is not None and '解析失败' in warning
    value, warning = parse_stat_value(None)
    assert value == 0.0
    assert warning is not None and '解析失败' in warning
