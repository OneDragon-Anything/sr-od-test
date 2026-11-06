"""大扩招注册面 + 扣金计划锁(cw_investments 分目录镜像;先例 =
同目录 test_strategy_dacaiyuan_registry.py 单卡注册测试模式)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-197-dakuozhao.
md §3 锁 1/锁 2 + REVIEW-T197 八裁决点默认案(经族级授权收尾)。卡面
官方原文(cw_invest_data.py:145 逐字):「扣除你的金币，每损失4金币，
获得一个随机4费角色，最多扣除40金币。获得1个【完美投影仪】和16金币。」

- 注册行直测(锁 1):STRATEGY_ECONOMY['大扩招'] 全等 EconomyEffect(
  instant_gold=16)——+16 金腿注册已登记;扣金侧不进 EconomyEffect
  (禁 instant_gold 定额扣金建模,fields.md §5.2 金面缺口行权威版本);
- 扣金计划边界表(锁 2):dakuozhao_deduction_plan 纯函数 7 点边界
  (0/3/4/39/40/41/80),取整读法 = 只扣 4 的整数倍、余金保留;
- 载体形态负锁(裁决点 3 默认案):卡不入 STRATEGY_EFFECTS(零持卡
  聚合面——效果全部拿卡拍一次结清,登记即错挂轮询语义)、效果表
  已登记(随机角色腿 + 具名装备腿组合效果体)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    RECRUIT_MAX_DEDUCT,
    RECRUIT_STEP_GOLD,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
    dakuozhao_deduction_plan,
)

_CARD = '大扩招'


def test_dakuozhao_registry_instant_gold_only() -> None:
    """锁 1(注册行直测):STRATEGY_ECONOMY['大扩招'] 全等
    EconomyEffect(instant_gold=16)——其余字段全缺省(+16 金腿注册已登记;
    扣金面不注册,扣金 = sim 状态副本里的值负腿,非估值常量)。"""
    assert STRATEGY_ECONOMY[_CARD] == EconomyEffect(instant_gold=16), \
        '注册行漂移(卡面「获得…16金币」直读,其余字段禁载)'


@pytest.mark.parametrize(('gold', 'expected'), [
    (0, (0, 0)),
    (3, (0, 0)),
    (4, (4, 1)),
    (39, (36, 9)),
    (40, (40, 10)),
    (41, (40, 10)),
    (80, (40, 10)),
])
def test_dakuozhao_deduction_plan_boundaries(
        gold: int, expected: tuple[int, int]) -> None:
    """锁 2(扣金计划边界表):n = min(gold//4, 10),扣金 = n*4——
    39 → (36, 9) = 取整读法核心点(余 3 金保留非全扣);40 封顶
    (RECRUIT_MAX_DEDUCT//RECRUIT_STEP_GOLD = 10);41+ 同 40(余金保留
    且上限不破)。"""
    assert dakuozhao_deduction_plan(gold) == expected


def test_dakuozhao_plan_constants_desc_literal() -> None:
    """结构值钉死:步进 4 / 上限 40 = 卡文「每损失4金币」「最多扣除40
    金币」直读非编数(常量漂移 = 卡文读法漂移,改值须过卡文对表)。"""
    assert RECRUIT_STEP_GOLD == 4
    assert RECRUIT_MAX_DEDUCT == 40


def test_dakuozhao_carrier_no_strategy_effects_entry() -> None:
    """载体形态负锁(裁决点 3 默认案):卡不入 STRATEGY_EFFECTS(零持卡
    聚合面,零条目零停机钩子激活);效果表已登记(组合效果体交付)。"""
    assert _CARD not in STRATEGY_EFFECTS, \
        '零条目(拿卡拍一次结清,登记即错挂 tick 轮询语义)'
    assert _CARD in PICK_INVEST_EFFECTS, '组合效果体登记面已登记'
