"""策略卡合成触发发放注册面测试(cw_investments 分目录镜像;单一源 +
两表同键各表各域对账 + 构建校验负例,先例 = 同目录
test_strategy_win_gold_grants.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-179-shali-
taojin.md(定稿)§4 锁 5 + REVIEW-T179 §2.3/§3.4。卡面官方原文:「合成
2星2费角色时，获得1张【砂金】。」(id 201501,品质金):

- 登记单一源:STRATEGY_MERGE_GRANTS 行值 = 卡面直读(判据 2星+2费,
  发放砂金——注册行直测承担值形对账:判据值域(星级/费用)与非负查按
  2026-10-28 治理口径不设校验,值形漂移唯此锁可暴露);
- 双母体对账:本表(世界发放域)与 STRATEGY_GRANTS(估值域档位机器)
  同键共存 = 合法形态,条目保留零删(反扫闭集底册完整);
- 构建校验 2 条(漂移哨,import 即炸语义经直调校验函数锁定):
  孤儿键 + 发放角色名漂移。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTERS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    CHARACTER_ROSTER,
    INVESTMENT_STRATEGIES,
    STRATEGY_GRANTS,
    STRATEGY_MERGE_GRANTS,
    _validate_strategy_merge_grants,
)

_CARD = '砂里淘金'
_REWARD = '砂金'


def test_registry_row_single_source() -> None:
    """登记单一源(锁 5 主锚):行值 = 卡面直读三元组(判据星级 2 +
    判据费用 2 + 发放砂金);键 ∈ 策略注册表(孤儿哨现值通过 = import
    过闸即证,显式对拍防静默漂移);注册面 = 策略卡合成触发发放族现役
    首例(同族后续卡各自独立批,禁顺手代登记)。"""
    assert set(STRATEGY_MERGE_GRANTS) == {_CARD}, \
        '注册面 = 合成触发发放族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_MERGE_GRANTS[_CARD] == (2, 2, _REWARD), \
        f'行值漂移(卡面明写合成2星2费得砂金): {STRATEGY_MERGE_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_reward_char_registered_and_cost_matches_criterion() -> None:
    """发放角色在册双对拍:奖励名 ∈ CHARACTER_ROSTER(角色漂移哨现值
    通过);且登记判据费用(2)与发放角色注册费用一致——砂金确为 2 费
    (卡面「合成2星2费」的判据域含发放物自身,费用漂移两表面独立字面量
    的失配唯此锁可暴露)。"""
    assert _REWARD in CHARACTER_ROSTER, '发放角色必须在角色注册表'
    assert CHARACTERS[_REWARD].cost == STRATEGY_MERGE_GRANTS[_CARD][1], \
        '判据费用 ≠ 发放角色注册费用(两表面漂移)'


def test_grants_entry_coexists_world_channel_pointer() -> None:
    """双母体对账:STRATEGY_GRANTS 估值域条目保留零删(chars_conditional
    条件腿底册完整,反扫闭集不受新表影响);本表辖世界发放,两表同键
    各表各域。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_conditional == ((_REWARD, '合成2星2费角色时'),), \
        f'估值域条件腿底册漂移: {grant.chars_conditional!r}'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。值域/非负查按 2026-10-28 治理口径
    不设,无对应锁(校验函数本体不存在该查,防哨复增由评审把关)。"""
    monkeypatch.setitem(STRATEGY_MERGE_GRANTS, '不存在的卡', (2, 2, _REWARD))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_merge_grants()


def test_validator_reward_char_drift_raises(monkeypatch) -> None:
    """构建校验(角色名漂移哨):发放角色不在 CHARACTER_ROSTER →
    ValueError(版本改名不静默)。"""
    monkeypatch.setitem(STRATEGY_MERGE_GRANTS, _CARD, (2, 2, '不存在的角色'))
    with pytest.raises(ValueError, match='角色名漂移'):
        _validate_strategy_merge_grants()
