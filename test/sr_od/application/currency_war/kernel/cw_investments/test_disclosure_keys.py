"""cw_investments 披露键常量域测试(镜像 src = kernel/cw_investments.py,
按拆目录规范落位):披露键 = 纯声明态常量,不进任何判定分支——锁存在性
与值形(全元组精确比对,披露键静态在册断言家族形),防「常量被静默删
改」;删除即红,提示删除者先清披露语义再动键。"""

from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_DELAYED_RANDOM_CHOICE_ASSUMPTION_KEYS,
    STRATEGY_DESC_UNMODELED_KEYS,
    STRATEGY_HIRING_LETTER_UNMODELED_ASSUMPTION_KEYS,
)


def test_hiring_letter_unmodeled_keys_registered() -> None:
    """披露键静态常量在册断言(聘用书授予族道具腿零建模申报,键 = 族卡
    名):首卡招聘资金在列。家族随族卡实现批追加(招聘资金+/专家招募/
    专家招募+ 各自批并入元组),本断言随批扩员——申报面扩员即红一次,
    批内顺手更新即绿。"""
    assert STRATEGY_HIRING_LETTER_UNMODELED_ASSUMPTION_KEYS == (
        '招聘资金',
        '招聘资金+',
        '专家招募',
        '专家招募+',
    )


def test_strategy_delayed_random_choice_keys_registered() -> None:
    """披露键静态常量在册断言(策略延时发放随机 choice-set 行均匀 v0
    假设申报,是钻石总会发光首例):desc 对「或」无概率载,红/蓝各半
    为建模假设非游戏真值;后继随机发放行随批扩元组,本断言随批扩员
    ——申报面扩员即红一次,批内顺手更新即绿。"""
    assert STRATEGY_DELAYED_RANDOM_CHOICE_ASSUMPTION_KEYS == (
        'strategy_delayed_choice_uniform_v0',
    )

def test_desc_unmodeled_keys_registered() -> None:
    """披露键静态常量在册断言(策略卡「desc 有载但刻意零建模」家族双键):
    键1 佩佩穿戴面零建模申报(用户裁定 2026-10-15 环境侧同源),键2 召唤
    单位周期离场零建模申报(离场原语缺/留装备指涉物死/触发锚歧义/周期
    形状缺四缺口);家族随族卡实现批追加消费方与键,本断言随批扩员——
    申报面扩员即红一次,批内顺手更新即绿。"""
    assert STRATEGY_DESC_UNMODELED_KEYS == (
        'strategy_worn_equip_unmodeled',
        'strategy_periodic_unit_leave_unmodeled',
    )

