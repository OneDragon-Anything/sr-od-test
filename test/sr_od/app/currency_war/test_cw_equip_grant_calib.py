"""装备供给结构重校准锁(EQUIP_GRANT_CALIB_VERSION)。

数据源 = 实机 [cw!][grant] 快照逐轮差分画像(W465 同款语料,57 局;
校准目标表见 .debug 产物 w477_supply_recalib/):装备类发放基础件 ~86% /
进阶 ~14%,P1 均 4.7 件分布在 ~3.8 个发放轮。

锁**结构与常量**,不锁分布数值:池成员/版本位/发放轮数下界/出口保有
量级(断言成立的最小 n;粗界防「供给面静默回退成品池」类回归)。
例外(ADR-0447,economy v2 重推导):出口保有均值带 [3.5,6.5] 为
分布级画像锚,推导见 test_p1_grant_volume_matches_real_profile。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENT_ROSTER
from sr_od.application.currency_war.data.cw_synthesis import RESERVED_COMPONENTS
from sr_od.application.currency_war.sim import engine_p1 as cw_sim


def test_calib_constants_shape() -> None:
    """常量在位:版本 ≥1;概率常量在 (0,1);基础池 = 8 件且 ⊆ 注册表。

    登记门语义:池成员/版本位/概率面任一变更 = 供给结构变更,须走
    显式重校准批(engine_p1 供给校准注:结构变更 = 有意行为变更,
    旧基线作废、指纹 +eqg 位递进)。"""
    assert cw_sim.EQUIP_GRANT_CALIB_VERSION >= 1
    assert 0.0 < cw_sim.EQUIP_GRANT_BONUS_P < 1.0
    assert 0.0 < cw_sim.EQUIP_GRANT_BONUS_ADV_SHARE < 1.0
    assert len(set(RESERVED_COMPONENTS)) == 8
    assert all(n in EQUIPMENT_ROSTER for n in RESERVED_COMPONENTS)


# (局指纹 = 池指纹 + eqg 版本位的组合锁由
#  test_cw_delta_pool.py::test_simulate_p1_records_pool_identity 承载
#  ——彼处为超集:fallback+snapshot 双模式 + pool_source 字段;
#  infra_locks/sim_models 的 smoke 同款行各随其专属断言面保留。)
#
# (两 sim 测不共享同一批局结果:供给量画像测已入慢桶(slow_marks
#  补登 2026-09-09),发放名测须在快速集内以自有的 10 局最小 n
#  (纪律 12 存在性断言取最小值)独立成测——共享缓存会让快速集
#  替慢桶测付 20 局全量成本。)


def test_p1_grant_volume_matches_real_profile() -> None:
    """供给量画像锁(economy v2 重推导,ADR-0447;W493/W503 编排者裁决)。

    **因果推导:事件金 v2 → 供给节奏 → 供给量新期望**:
    1. 供给节奏零通路:发放轮 = supply/reward 节点,节点序列采样
       (众数表+变异位)与发放规则**均不读金**——v2 事件金对供给节奏
       无机制通路;v1/v2 实测发放轮同值(4.05/局,n=20);
    2. 供给量新期望:E[发放件] = 发放轮 × (1 + EQUIP_GRANT_BONUS_P)
       = 4.05 × 1.30 ≈ **5.3 件/局**;实机画像 = 4.7 件 / 3.8 轮
       (=1.24 件/轮,57 局 grant 语料)→ 偏差 +12%,±20% 带内——
       **供给量仍匹配实机画像**(本断言直接锁供给量,不依赖保有代理);
    3. 出口保有(供给的下游观测量)= 发放 − 策略 churn(卖带装件/
       合成消耗):v2 富环境 churn 增 → 保有左移(均值 4.42,n=50;
       2 件尾 1%→10%)——保有分布仍锁粗界防归零/虚高。
    **移动靶边界**:实机画像采于旧码旧局(57 局 grant 语料,W477);
    economy v2 靶与缺陷清零轨道见 ADR-0447(清零后重采实机基线,
    本锁随之重推导)。
    单 seed 下界重锚(2026-09-07,M4 残余批):2→1。seed=17 局终保有
    1 件,行为链取证 = 供给面正常(发放轮 4、发放件 5、20 局供给量期望
    5.27 件在画像带内),低尾来自策略 churn 卖出带装件——fdac8186
    (轮岗建模修复)+4cbfb64a(输入基线定稿)行为批的取舍变化所致,
    与上方「churn 增 → 保有左移」同向;供给面静默回退仍由供给量期望带
    (4.7±20%)与均值带看守,单 seed 下界仅防归零,收到 1。"""
    totals: list[int] = []
    grant_rounds = 0
    for seed in range(20):
        r = cw_sim.simulate_p1(seed, pool='snapshot', planes=1)
        p1 = [row for row in r.ledger if row['plane'] == 1]
        grant_rounds += sum(
            1 for row in p1
            if (row.get('sim') or {}).get('node') in ('supply', 'reward'))
        ex = p1[-1]['state']
        owned = ex.get('owned_equips') or []
        worn = [e for d in ex.get('deployed') or []
                for e in (d.get('equips') or [])]
        bench_worn = [e for b in ex.get('bench') or [] if b
                      for e in (b.get('equips') or [])]
        total = owned + worn + bench_worn
        adv = sum(1 for e in total
                  if e not in RESERVED_COMPONENTS)
        # 单 seed 下界=1(重锚依据见 docstring「单 seed 下界重锚」节)
        assert 1 <= len(total) <= 9, f'seed={seed} 总保有 {total}'
        assert adv <= 3, f'seed={seed} 进阶件 {adv} 超量级'
        totals.append(len(total))
    mean = sum(totals) / len(totals)
    assert 3.5 <= mean <= 6.5, f'保有均值 {mean} 越出画像带 [3.5,6.5]'
    # 供给量期望 vs 实机画像 4.7 件(±20% 带;推导见 docstring 2)
    rounds = grant_rounds / 20
    expected_grants = rounds * (1 + cw_sim.EQUIP_GRANT_BONUS_P)
    assert 3.76 <= expected_grants <= 5.64, \
        f'供给量期望 {expected_grants:.2f}/局 越出实机画像 4.7±20%'


def test_grant_names_all_registered() -> None:
    """发放名全在注册表(ADR-0294 件2 池纪律;重校准不得引入死名)。

    独立 10 局最小 n(纪律 12):与慢桶的供给量画像测不共享 sim,
    保快速集预算(理由见上方注释)。"""
    legal = set(RESERVED_COMPONENTS) | set(EQUIPMENT_ROSTER)
    for seed in range(10):
        r = cw_sim.simulate_p1(seed, pool='snapshot', planes=1)
        for row in r.ledger:
            stt = row.get('state') or {}
            for e in (stt.get('owned_equips') or []):
                assert e in legal, f'seed={seed} 非注册表装备 {e}'


