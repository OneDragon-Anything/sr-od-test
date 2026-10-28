"""gift_hit_tier 送卡档位机器回归锁(镜像 src = kernel/cw_comps.py 的该
被测函数;此前零直测,本锁 = 估值域「现值不变」防线)。

测试面依据 = T-28 设计稿(迭代 2026-09-23-invest-effects-calc)§2.5 +
§4.3:条件分支建模批对估值域零动作——持续伤害契约(即时集非空,走规则①
即时优先)的档位由 COMP_LIBRARY 数据派生,不得随条件分支引擎落地漂移。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_comps import gift_hit_tier
from sr_od.application.currency_war.kernel.cw_investments import ENV_GIFTS


def test_dot_contract_gift_tier_unchanged() -> None:
    """持续伤害契约估值档位现值锁(T-28 设计稿 §2.5 估值域零动作):
    即时集 {椒丘, 卡芙卡} 非空 → 规则①即时优先取成员最优档;卡芙卡在
    DOT 队等套为 core(COMP_LIBRARY 分档数据派生,档位语义单一源 =
    gift_hit_tier docstring),整卡档 = 'core'。条件分支建模(猜测写+证实)
    不触碰估值域,本值漂移 = 回归信号。"""
    assert gift_hit_tier(ENV_GIFTS['持续伤害契约']) == 'core'


def test_concept_stock_gift_tier_off() -> None:
    """追击概念股估值档恒 'off'(概念股族模式卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记):档位机器只读 chars_immediate/
    chars_conditional 两个具名估值域字段,随机规格(阵营轴)/随机装备
    条目不入 → 恒 off → named_gift_value 恒 0——登记概念股不产生策略层
    双重计分(与策略层 random_faction_gift_value 随机阵营路径正交)。"""
    assert gift_hit_tier(ENV_GIFTS['追击概念股']) == 'off'


def test_ranxue_concept_stock_gift_tier_off() -> None:
    """燃血概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第二实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交。"""
    assert gift_hit_tier(ENV_GIFTS['燃血概念股']) == 'off'


def test_nengliang_concept_stock_gift_tier_off() -> None:
    """能量概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第三实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交。"""
    assert gift_hit_tier(ENV_GIFTS['能量概念股']) == 'off'


def test_lieche_concept_stock_gift_tier_off() -> None:
    """列车同行概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第四实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交。"""
    assert gift_hit_tier(ENV_GIFTS['列车同行概念股']) == 'off'


def test_yinhe_concept_stock_gift_tier_off() -> None:
    """银河学者概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第五实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交。"""
    assert gift_hit_tier(ENV_GIFTS['银河学者概念股']) == 'off'


def test_beluoboge_concept_stock_gift_tier_off() -> None:
    """贝洛伯格概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第六实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(注册表修正使贝洛伯格期望域扩为 6 名 = 随机路径既定传导,
    本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['贝洛伯格概念股']) == 'off'


def test_xingjianlvren_concept_stock_gift_tier_off() -> None:
    """星间旅人概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第七实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域成员构成随注册表传导〔采样域牌库时点过滤见 cw_pool
    grant_char_pool,2026-10-28 用户裁定〕,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['星间旅人概念股']) == 'off'


def test_xianzhou_concept_stock_gift_tier_off() -> None:
    """仙舟概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第八实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 9 名含专家青雀/停云 = 随机路径注册表传导,估值分母与流程
    采样域的牌库时点分叉系范围外申报,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['仙舟概念股']) == 'off'


def test_langshou_concept_stock_gift_tier_off() -> None:
    """狼狩概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第九实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 7 名含专家貊泽 = 随机路径注册表传导,估值分母与流程采样域
    的牌库时点分叉系范围外申报沿仙舟实例同指针,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['狼狩概念股']) == 'off'


def test_zhouzhibanshen_concept_stock_gift_tier_off() -> None:
    """昼之半神概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 6 名 is_expert 全空 = 非专家域,随机路径期望域与流程过滤域
    同集,无仙舟/狼狩型分叉申报,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['昼之半神概念股']) == 'off'


def test_yezhibanshen_concept_stock_gift_tier_off() -> None:
    """夜之半神概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十一实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 7 名 is_expert 全空 = 非专家域,随机路径期望域与流程过滤域
    同集,无仙舟/狼狩型分叉申报,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['夜之半神概念股']) == 'off'


def test_jipo_concept_stock_gift_tier_off() -> None:
    """击破概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十二实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 9 名含专家加拉赫/姬子 = 随机路径注册表传导,估值分母与流程
    采样域的牌库时点分叉系范围外申报沿仙舟/狼狩实例同指针,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['击破概念股']) == 'off'
