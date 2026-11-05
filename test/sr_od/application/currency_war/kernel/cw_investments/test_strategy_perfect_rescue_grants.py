"""策略卡完胜判定改写登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_PERFECT_RESCUE_GRANTS + 构建校验;世界发放腿注册面镜像 =
cw_gain_effects.PICK_INVEST_EFFECTS 组合登记行)。

测试面依据 = 迭代设计 designs/T-412-doushi-zhejiade-cuo.md §2.2 件1 +
§4 锁 1/锁 2(治理口径 = 用户裁定 2026-10-28「写表人笔误类校验删、漂移哨
留」:值形哨不加,孤儿键/徽名双源两漂移哨在册;直构形态先例 = 同目录
test_strategy_death_save_grants.py 死亡救援同形三件套):
- 登记单一源:行值 = 卡面原文直读(都是这家伙的错!id 352801:「……视为
  完美通关并出售1名携带【命运圣杯星徽】的上场角色,可生效3次」→
  (命运圣杯星徽, 3));
- 腿1 注册面:金腿 instant_gold=10(卡面「和10金币」直读)+ 世界发放腿
  PICK 组合登记行在册;登记表 STRATEGY_GRANTS 零登记(装备腿唯一出现点
  纪律,控制规模同物同形);
- 构建校验 2 条漂移哨(直调校验函数锁定):孤儿键 + 徽名双源。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_GRANTS,
    STRATEGY_PERFECT_RESCUE_GRANTS,
    _validate_strategy_perfect_rescue_grants,
)

_CARD = '都是这家伙的错！'
_EM = '命运圣杯星徽'
_ROW = (_EM, 3)


def test_registry_row_single_source() -> None:
    """登记单一源:本卡行 = 卡面直读(徽名/配额 3);闭集 = 完胜改写族
    现役首例(同族后继改写卡各自独立批,禁顺手代登记);键 ∈ 策略注册表
    (孤儿哨现值通过 = import 过闸即证,显式对拍防静默漂移)。"""
    assert set(STRATEGY_PERFECT_RESCUE_GRANTS) == {_CARD}, \
        '注册面 = 完胜改写族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_PERFECT_RESCUE_GRANTS[_CARD] == _ROW, \
        f'行值漂移(卡面明写 徽名/配额3): {STRATEGY_PERFECT_RESCUE_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_emblem_dual_source_emblem_family() -> None:
    """徽名双源对表(构建校验②现值通过 = import 过闸即证,显式对拍):
    徽名 ∈ EQUIPMENTS 且类别 = 星徽族(校验哨同判据;零配方非合成件事实
    不校验,T-219 设计稿定谳,登记面注释申报)。"""
    assert _EM in EQUIPMENTS, '徽名必须在装备注册表'
    assert EQUIPMENTS[_EM].category == '星徽', '徽名必须属星徽族'


def test_economy_row_instant_gold() -> None:
    """腿1b 金腿注册行:instant_gold=10(卡面「获得…和10金币」直读,
    估值现金计分通道自动入册);息顶未覆写(测试 cap 链零扰依据——
    interest_cap_override 非 None 条目才入 cap 测试迭代域)。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.instant_gold == 10, \
        f'金腿注册行漂移: instant_gold={eff.instant_gold}'
    assert eff.interest_cap_override is None, '息顶零覆写'


def test_pick_row_world_grant_registered() -> None:
    """腿1a 世界发放腿注册面:PICK 组合登记行在册(效果体引用存活);
    登记表 STRATEGY_GRANTS 零登记(装备腿唯一出现点纪律,镜像一致性
    锁零涉——本卡无 GRANTS 条目即无逐对相等对)。"""
    assert _CARD in PICK_INVEST_EFFECTS, 'PICK 组合登记行缺位'
    assert _CARD not in STRATEGY_GRANTS, \
        '登记表零登记(装备腿唯一出现点 = PICK 直书登记行)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。值形(徽名非空 str/配额 ≥1 int)按
    2026-10-28 治理裁定不加(手抄常量纯笔误类,对账归评审与本文件行值
    断言把关)。"""
    monkeypatch.setitem(STRATEGY_PERFECT_RESCUE_GRANTS, '不存在的卡', _ROW)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_perfect_rescue_grants()


def test_validator_emblem_drift_raises(monkeypatch) -> None:
    """构建校验(徽名双源哨):徽名 ∉ EQUIPMENTS / 类别非星徽 → ValueError
    (装备注册表版本改名/类别调整的漂移响应)。"""
    monkeypatch.setitem(STRATEGY_PERFECT_RESCUE_GRANTS, _CARD,
                        ('不存在的装备', 3))
    with pytest.raises(ValueError, match='徽名双源'):
        _validate_strategy_perfect_rescue_grants()
    non_emblem = next(n for n, e in EQUIPMENTS.items()
                      if e.category != '星徽')
    monkeypatch.setitem(STRATEGY_PERFECT_RESCUE_GRANTS, _CARD,
                        (non_emblem, 3))
    with pytest.raises(ValueError, match='徽名双源'):
        _validate_strategy_perfect_rescue_grants()
