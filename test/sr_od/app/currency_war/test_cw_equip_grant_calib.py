# -*- coding: utf-8 -*-
"""装备供给结构重校准锁(EQUIP_GRANT_CALIB_VERSION)。

数据源 = 实机 [cw!][grant] 快照逐轮差分画像(W465 同款语料,57 局;
校准目标表见 .debug 产物 w477_supply_recalib/):装备类发放基础件 ~86% /
进阶 ~14%,P1 均 4.7 件分布在 ~3.8 个发放轮。

锁**结构与常量**,不锁分布数值:池成员/版本位/发放轮数下界/出口保有
量级(断言成立的最小 n;粗界防「供给面静默回退成品池」类回归)。
"""
from __future__ import annotations

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_equipment_data import EQUIPMENT_ROSTER
from sr_od.application.currency_war.cw_synthesis import RESERVED_COMPONENTS


def test_calib_constants_shape() -> None:
    """常量在位:版本 ≥1;概率常量在 (0,1);基础池 = 8 件且 ⊆ 注册表。"""
    assert cw_sim.EQUIP_GRANT_CALIB_VERSION >= 1
    assert 0.0 < cw_sim.EQUIP_GRANT_BONUS_P < 1.0
    assert 0.0 < cw_sim.EQUIP_GRANT_BONUS_ADV_SHARE < 1.0
    assert len(set(RESERVED_COMPONENTS)) == 8
    assert all(n in EQUIPMENT_ROSTER for n in RESERVED_COMPONENTS)


def test_fingerprint_carries_grant_version() -> None:
    """局指纹 = 池指纹 + eqg 版本位(新旧供给结构不可比,显式失败)。"""
    r = cw_sim.simulate_p1(1, pool='snapshot')
    delta_fp = cw_sim.pool_fingerprint(cw_sim.resolve_pool('snapshot')[0])
    assert r.pool_fingerprint == (
        delta_fp + f'+eqg{cw_sim.EQUIP_GRANT_CALIB_VERSION}')


def test_p1_grant_volume_matches_real_profile() -> None:
    """n=15 出口保有粗界:每局 owned ∈ [3, 9](实机 4-8 画像 ±1 容差)
    且进阶 ≤3(实机进阶占比 ~14% 的量级上界)。"""
    for seed in range(15):
        r = cw_sim.simulate_p1(seed, pool='snapshot', planes=1)
        p1 = [row for row in r.ledger if row['plane'] == 1]
        ex = p1[-1]['state']
        owned = ex.get('owned_equips') or []
        worn = [e for d in ex.get('deployed') or []
                for e in (d.get('equips') or [])]
        adv = sum(1 for e in owned + worn
                  if e not in RESERVED_COMPONENTS)
        assert 3 <= len(owned) <= 9, f'seed={seed} owned={owned}'
        assert adv <= 3, f'seed={seed} 进阶件 {adv} 超量级'


def test_grant_names_all_registered() -> None:
    """发放名全在注册表(ADR-0294 件2 池纪律;重校准不得引入死名)。"""
    legal = set(RESERVED_COMPONENTS) | set(EQUIPMENT_ROSTER)
    for seed in range(10):
        r = cw_sim.simulate_p1(seed, pool='snapshot', planes=1)
        for row in r.ledger:
            stt = row.get('state') or {}
            for e in (stt.get('owned_equips') or []):
                assert e in legal, f'seed={seed} 非注册表装备 {e}'
