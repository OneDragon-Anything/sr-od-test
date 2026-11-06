"""STRATEGY_ORE_OPEN_EFFECTS 白名单表直测锁(镜像 src = cw_investments.py
策略晶矿开启效果注册表;test_cw_investments.py 已超行限禁追加,本文件按
拆目录规范落新位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-316-huangjing-kuanggong.md(定稿,REVIEW-T316 无需用户决定 7/7)§4 锁 1:
- 注册行直测 = 行值防线(治理口径 2026-10-28「笔误哨删/漂移哨留」——
  值形笔误哨按 M12 判删,行值精确断言防线强于 import 期形查);
- 孤儿键负例 = 唯一漂移哨的负控(版本改名/移除后静默失联形态);
- 披露键注册锁(「极低概率」零建模 + 链序推断两键常驻)。
"""
from __future__ import annotations

import pytest

import sr_od.application.currency_war.kernel.cw_investments as cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ORE_OPEN_ASSUMPTION_KEYS,
    STRATEGY_ORE_OPEN_EFFECTS,
    _validate_strategy_ore_open_effects,
)

_CARD = '黄晶矿工'


def test_registry_row_value() -> None:
    """注册行直测锁(T-316 设计 §4 锁 1;行值防线承载,值形哨按治理不建):
    表 = {'黄晶矿工': (0.5, 1)} 且键在策略注册表。"""
    assert STRATEGY_ORE_OPEN_EFFECTS == {_CARD: (0.5, 1)}, \
        '表集合对拍(表扩员须随批改锁,禁静默)'
    assert _CARD in INVESTMENT_STRATEGIES, '键 ∈ INVESTMENT_STRATEGIES'


def test_orphan_key_negative() -> None:
    """孤儿键负例(T-316 设计 §4 锁 1;唯一漂移哨负控):注入注册表外
    卡名 → 校验器 ValueError(import 即炸语义的直调形态,先例 =
    同目录 test_env_pick_grants 同族形)。"""
    assert _validate_strategy_ore_open_effects() is None, '现值复跑不炸'
    cw_investments.STRATEGY_ORE_OPEN_EFFECTS['假卡名'] = (0.5, 1)
    try:
        with pytest.raises(ValueError, match='孤儿键'):
            _validate_strategy_ore_open_effects()
    finally:
        del cw_investments.STRATEGY_ORE_OPEN_EFFECTS['假卡名']


def test_disclosure_keys_registered() -> None:
    """披露键注册锁(T-316 设计 §6 键 1/2 常驻;消费面 = 披露清单):
    「极低概率」零建模键 + 链序推断键,逐字对拍防漂移。"""
    assert STRATEGY_ORE_OPEN_ASSUMPTION_KEYS == (
        'strategy_ore_tier_down_prism_prob_unknown',
        'strategy_ore_tier_chain_inferred',
    ), '披露键集合对拍'
