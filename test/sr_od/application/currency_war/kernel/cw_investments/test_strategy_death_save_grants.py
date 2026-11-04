"""策略卡死亡救援触发登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_DEATH_SAVE_GRANTS + 构建校验 + 建模假设披露键家族)。

测试面依据 = 迭代设计 designs/T-323-cang-yishou.md §4 锁 1 + §6 披露键
(用户裁定 2026-11-04:R1 救援时发 + 一次性 + M-B 独立叠加;直构形态
先例 = 同目录 test_strategy_hp_loss_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(藏一手 id 302801:「……免疫这次
  伤害并将生命值变为40点，并获得30点经验和80金币」→ (40, 30, 80),
  数值面全 desc 明写);
- R1 注册面双源对账:注册行即时双腿必须全默认(奖励载荷单一源迁本表,
  注册行复活 instant_gold/xp_instant = 同一奖励双源双发——用户裁定
  2026-10-28「写表人笔误类校验删、漂移哨留」下,import 期双源哨在册,
  行现值断言为测试侧对账把关);
- 构建校验 2 条漂移哨(直调校验函数锁定):孤儿键 + 注册面双源。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_DEATH_SAVE_ASSUMPTION_KEYS,
    STRATEGY_DEATH_SAVE_GRANTS,
    STRATEGY_ECONOMY,
    _validate_strategy_death_save_grants,
)

_CARD = '藏一手'
_ROW = (40, 30, 80)


def test_registry_row_single_source() -> None:
    """登记单一源(设计 §4 锁 1):藏一手行 = 卡面数值直读(救援后生命值
    40/经验 30/金币 80);闭集 = 死亡救援族现役首例(全池普查族成员恰 1,
    同族后续救援卡各自独立批,禁顺手代登记);键 ∈ 策略注册表(孤儿哨
    现值通过 = import 过闸即证,显式对拍防静默漂移)。"""
    assert set(STRATEGY_DEATH_SAVE_GRANTS) == {_CARD}, \
        '注册面 = 死亡救援族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_DEATH_SAVE_GRANTS[_CARD] == _ROW, \
        f'行值漂移(卡面明写 40/30/80): {STRATEGY_DEATH_SAVE_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_registry_row_r1_default_economy() -> None:
    """R1 注册面双源对账(设计 §4 锁 1 R1 形态):STRATEGY_ECONOMY 注册行
    即时双腿全默认——奖励(经验/金)已迁发放表随救援触发,注册行复活
    任一即时腿 = 选卡拍双发(import 期双源哨同判据,本断言为测试侧
    对账位);历史形态 instant_gold=80(选牌当场读)已被用户裁定
    2026-11-04 反向改判,复活即裁判定向漂移。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.instant_gold == 0 and eff.xp_instant == 0, \
        f'注册行即时双腿复活(奖励载荷单一源在发放表): ' \
        f'instant_gold={eff.instant_gold}/xp_instant={eff.xp_instant}'


def test_disclosure_keys_family_registered() -> None:
    """披露键家族在册且恰两键(设计 §6:一次性 + 独立叠加两建模假设各
    一键,奖励时点 R1 定读非假设不设键;消费 = sim 救援发放刻随局
    setdefault,sim 链锁断言发射形态)。"""
    assert set(STRATEGY_DEATH_SAVE_ASSUMPTION_KEYS) == {
        'death_save_once_assumption',
        'death_save_independent_floor_assumption',
    }, f'披露键家族漂移: {STRATEGY_DEATH_SAVE_ASSUMPTION_KEYS!r}'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。三元组值形按 2026-10-28 治理裁定
    不加(手抄常量纯笔误类,对账归评审与本文件行值断言把关)。"""
    monkeypatch.setitem(STRATEGY_DEATH_SAVE_GRANTS, '不存在的卡', _ROW)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_death_save_grants()


def test_validator_registry_dual_source_raises(monkeypatch) -> None:
    """构建校验(注册面双源哨):注册行复活即时腿 → ValueError(奖励
    同源双发面——救援拍 + 选卡拍;R1 用户裁定反向改判的防复活哨,
    import 期前移拦截)。"""
    monkeypatch.setitem(
        STRATEGY_ECONOMY, _CARD,
        STRATEGY_ECONOMY[_CARD].__class__(instant_gold=80))
    with pytest.raises(ValueError, match='注册面双源'):
        _validate_strategy_death_save_grants()
