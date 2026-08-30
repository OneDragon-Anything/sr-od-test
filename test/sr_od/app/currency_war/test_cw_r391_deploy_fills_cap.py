# -*- coding: utf-8 -*-
"""r391 检查项锁:deploy_fills_cap 语义(连续 2 轮≤cap-2 且围栏认可件
未上;过渡态/贴 cap/lag=0 不报)。合成账本双向锁。

「有货」口径(W767 收敛,ADR-0473 增补链):旧「非在场同名副本」
计数是围栏判据外的近似——跨线散牌被配方底线合法 held 时误报
(643567 r5-r8 四轮连锁取证:lag=0 而旧口径可上货 ≥3);改吃
``sim.deploy_lag_units``(同一围栏纯函数的认可残余,部署行为与
检查器零口径差)。合成行的 lag 即该字段。"""
from __future__ import annotations


from sr_od.application.currency_war.sim.checks.ledger import check_deploy_fills_cap


def _row(rn: int, deployed: int, cap: int, lag: int) -> dict:
    """合成行:deployed 名单 x0..xN;lag = 围栏认可件未上数。"""
    return {
        'plane': 1, 'round_num': rn,
        'state': {'deployed': [{'char_id': f'x{k}'}
                               for k in range(deployed)],
                  'cap': cap},
        'sim': {'deploy_lag_units': lag},
    }


def test_no_lag_not_reported() -> None:
    """lag=0(bench 有货但围栏合法 held:在场同名素材/跨线散牌)→ 不报
    (W767 643567 r5-r8 形态:旧口径误报,lag 口径不报)。"""
    rows = [_row(5, 4, 7, 0), _row(6, 4, 7, 0)]
    assert not check_deploy_fills_cap(rows)


def test_persistent_gap_reported() -> None:
    """连续 2 轮 deployed≤cap-2 且 lag≥2 → 报(r387 指纹)。"""
    rows = [_row(2, 1, 3, 2), _row(3, 1, 3, 2)]
    assert check_deploy_fills_cap(rows), '连续短缺应报'


def test_transient_gap_not_reported() -> None:
    """单轮短缺(下一轮补满)→ 不报(代理时序过渡态,game14)。"""
    rows = [_row(2, 4, 6, 2), _row(3, 6, 6, 2)]
    assert not check_deploy_fills_cap(rows)


def test_near_cap_not_reported() -> None:
    """差 1(贴 cap)→ 不报(cap 竞争合法保守)。"""
    rows = [_row(2, 2, 3, 2), _row(3, 2, 3, 2)]
    assert not check_deploy_fills_cap(rows)


def test_lag_one_not_reported() -> None:
    """lag=1(单件围栏认可未上)→ 不报(≥2 才成「系统性拦截」量级)。"""
    rows = [_row(2, 1, 3, 1), _row(3, 1, 3, 1)]
    assert not check_deploy_fills_cap(rows)


def test_growing_deployed_not_reported() -> None:
    """ADR-0260 增长豁免:连续短缺但 deployed 在增长 → 不报
    (deploy 代理先于买入,每轮买新件时账本恒见滞后一拍的
    「上轮买未部署」形态;engine_seed 放行后 seed4 实证)。"""
    rows = [_row(2, 4, 6, 2), _row(3, 5, 7, 2)]
    assert not check_deploy_fills_cap(rows)
