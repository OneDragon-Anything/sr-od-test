"""W510 刷新费跨波重复扣修复锁:关店对拍的金账模型 + 执行侧接线结构。

缺陷机理(修复前):两阶段刷新循环里每波重读 ``state.gold``,关店对拍却用
``total_refresh``(跨波计数)× 末波刷价 事后乘出刷新费 —— 末波重读金已净含
前面各波的刷新费,再按总波数扣一遍 = 跨波重复扣,期望恒偏低
(量级 = 前面各波刷新费合计)。修复语义:对拍期望 = 开店首读金
− 全程执行花金(逐动作累计,刷新费按点击波现读价)+ 全程卖入。


出处:被其他测试文件引用(防断链保留,需后续人工归并)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from sr_od.application.currency_war.operations.prep.shop import expected_gold_after_actions


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

