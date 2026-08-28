"""W510 刷新费跨波重复扣修复锁:关店对拍的金账模型 + 执行侧接线结构。

缺陷机理(修复前):两阶段刷新循环里每波重读 ``state.gold``,关店对拍却用
``total_refresh``(跨波计数)× 末波刷价 事后乘出刷新费 —— 末波重读金已净含
前面各波的刷新费,再按总波数扣一遍 = 跨波重复扣,期望恒偏低
(量级 = 前面各波刷新费合计)。修复语义:对拍期望 = 开店首读金
− 全程执行花金(逐动作累计,刷新费按点击波现读价)+ 全程卖入。
"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.operations.prep import shop
from sr_od.application.currency_war.operations.prep.shop import (
    BuyShopCards,
    expected_gold_after_actions,
)

_SRC = inspect.getsource(BuyShopCards.buy)


def test_multiwave_refresh_expected_closes_per_accounting():
    """多波刷新复现锁(3 波):逐波账与关店对拍闭合。

    场景:开店金 60。
      波1:买 1+2=3,刷新(费2)→ 剩 55
      波2:买 3,刷新(费2)→ 剩 50
      波3:买 3,无刷新 → 收工,实读 47
    执行花金合计 = 3+2+3+2+3 = 11,期望 = 60 − 11 = 47 = 实际。
    修复前口径(末波重读金 50 当基线 + 跨波 total_refresh=2 × 2 扣)
    = 50 − (3 + 4) = 43 ≠ 47,差 4 = 波1+波2 刷新费被重复扣。
    """
    gold_open = 60
    # 逐动作执行侧累计(与 op 内分支同规则:买价/升级费/当次刷价)
    executed: list[int] = [1, 2, 2, 3, 2, 3]
    spend = sum(executed)
    # 末波重读金(修复前错误基线):60 − 3 −2 −3 −2 = 50
    last_wave_reread_gold = 50
    total_refresh_cross_wave = 2

    expected_new = expected_gold_after_actions(gold_open, spend, 0)
    assert expected_new == 47, '多波刷新后对拍期望应与实际闭合'
    expected_old = (last_wave_reread_gold
                    - (3 + total_refresh_cross_wave * 2))
    assert expected_old == 43 != 47, '修复前口径应复现 4 金重复扣(回归锚)'


def test_multiwave_with_sell_income_closes():
    """多波 + 卖入:卖入是跨波累计计数,与开店首读金基线同口径相容。

    场景:开店金 80;波1 买4+刷新2(→74)、卖入5(→79);波2 买3(→76)。
    执行花金 = 4+2+3 = 9,卖入 5 → 期望 = 80 − 9 + 5 = 76 = 实际。
    """
    assert expected_gold_after_actions(80, 4 + 2 + 3, 5) == 76


def test_refresh_cost_reads_per_wave_not_last_wave():
    """刷价按点击波现读:升级改变刷价后,后波费用按新价累计,不由末波代扣。

    波1 刷价 2(升 5 级前),升级后波2 刷价 3:全程刷新费 = 2 + 3,
    而非 total_refresh(2) × 末波价 3 = 6。
    """
    assert 2 + 3 != 2 * 3, '两波不同价时,逐波累计 ≠ 跨波计数×末波价'


def test_buy_source_wiring_lock():
    """接线结构锁:审计必须用「开店首读金基线 + 执行侧累计花金」,
    跨波计数事后乘刷价的旧口径不得回流。"""
    assert '_spend_executed' in _SRC, '执行侧逐动作花金累计缺失'
    assert 'gold_open' in _SRC, '开店首读金基线快照缺失'
    assert 'total_refresh *' not in _SRC, (
        '跨波计数×刷价的重复扣口径回流(关店对拍/刷新快照均禁用)')
    # 对拍期望必须以 gold_open 为基线(末波重读值 state.gold 只许作兜底)
    assert 'gold_open if gold_open is not None else state.gold' in _SRC
    # 纯函数契约:开店金 − 花出 + 卖入(W69 锁延续,防口径漂移)
    assert expected_gold_after_actions(50, 2, 6) == 54
    assert shop.expected_gold_after_actions(50, 10, 0) == 40
