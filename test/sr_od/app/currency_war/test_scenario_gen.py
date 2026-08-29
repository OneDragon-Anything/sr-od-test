# -*- coding: utf-8 -*-
"""r125 场景生成器:枚举决策岔路口组合 → 批量不变量测试。

高效造数 = 组合枚举 × 不变量断言(不是逐场景手写期望值)。
不变量来自设计文档语义(框架稳定/预囤收口/同名守卫),枚举面来自
真实决策维度。生成器与断言分离——新不变量直接加一条 assert 系列。
"""
import itertools
import sys

import pytest

sys.path.insert(0, 'src')

from sr_od.application.currency_war.strategy_v1.cw_plan import _should_deploy, deploy_legal
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, ShopCard
from sr_od.application.currency_war.kernel.cw_transition import (
    FRAMEWORKS,
    TRANSITION_PACK,
    pick_framework,
    transition_score,
)

# 代表件(每框架 carry/partial/drop 各一)
REPS = {
    '仙舟': {'carry': '藿藿', 'partial': '爻光', 'drop': '卡芙卡'},
    '列车': {'carry': '三月七', 'partial': '姬子·启行', 'drop': '艾丝妲'},
    '量子': {'carry': '希儿', 'partial': '缇宝', 'drop': None},
}
SCATTER = '万敌'


def _bc(name, faction='?', pref='back', star=1, slot=0):
    return BenchChar(slot=slot, char_id=name, faction=faction,
                     star=star, position_pref=pref)


def _fw_faction(fw):
    return {'仙舟': '仙舟', '列车': '列车同行', '量子': '贝洛伯格'}[fw]


# ===== 不变量 1:持有 ≥2 同框架件 → 框架必选且稳定 =====

@pytest.mark.parametrize('fw,n_owned,shop_noise', itertools.product(
    FRAMEWORKS, (2, 3), (None, 'scatter', 'other_fw')))
def test_inv_framework_locks_with_two_owned(fw, n_owned, shop_noise):
    carry = REPS[fw]['carry']
    bench = [_bc(carry, _fw_faction(fw)) for _ in range(n_owned)]
    shop = []
    if shop_noise == 'scatter':
        shop = [ShopCard(x=0, name=SCATTER, faction='夜之半神', cost=1)]
    elif shop_noise == 'other_fw':
        other = next(f for f in FRAMEWORKS if f != fw)
        shop = [ShopCard(x=0, name=REPS[other]['carry'],
                         faction=_fw_faction(other), cost=1)]
    a = pick_framework(bench, [], shop)
    b = pick_framework(bench, [], shop, current=a)   # 下一轮(同持有)
    assert a == fw, f'持有 {n_owned} 张 {fw} carry 应锁定 {fw},实得 {a}'
    assert b == fw, f'持有不变时框架不得漂移({a}→{b})'


# ===== 不变量 2:预囤模式 drop/散件恒 0 分 =====

@pytest.mark.parametrize('fw', FRAMEWORKS)
def test_inv_hoard_zero_for_drop_and_scatter(fw):
    drop = REPS[fw]['drop']
    if drop:
        assert transition_score(drop, _fw_faction(fw), '') == 0.0
    assert transition_score(SCATTER, '夜之半神', '') == 0.0


# ===== 不变量 3:同名禁双(deploy 合法性)在任意局面下成立 =====

@pytest.mark.parametrize('fw', FRAMEWORKS)
def test_inv_same_name_never_deploys_twice(fw):
    carry = REPS[fw]['carry']
    gs = GameState(round_num=5, plane=1, dual_track_phase=True)
    gs.level = 6
    gs.bench = []
    gs.deployed = [_bc(carry, _fw_faction(fw)), _bc(SCATTER, '夜之半神')]
    cand = _bc(carry, _fw_faction(fw), slot=1)
    assert deploy_legal(cand, {carry}) is False
    assert _should_deploy(cand, gs, None) is False


# ===== 不变量 4:息档不降(压缩语义)跨全部费位 =====

@pytest.mark.parametrize('gold,cost', itertools.product(
    (39, 40, 41, 49, 50, 51), (1, 2, 3, 4)))
def test_inv_interest_tier_never_drops(gold, cost):
    """买入后息档不降(除非刻意跨档——压缩语义允许金够高时;此处锁
    _compress_release 的保息门行为)。"""
    from sr_od.application.currency_war.strategy_v1.cw_plan import _compress_release
    ok = _compress_release(cost, gold, set())
    if ok:
        assert (gold - cost) // 10 == gold // 10, \
            f'放行的买入降息档(gold={gold}, cost={cost})'


# ===== 不变量 5:合并权启动门(纯 shop 不启动;持有1+在售1 启动) =====

@pytest.mark.parametrize('fw', FRAMEWORKS)
def test_inv_boot_gate_semantics(fw):
    carry, partial = REPS[fw]['carry'], REPS[fw]['partial']
    # 纯在售 1 张(0.5)不启动
    assert pick_framework([], [], [ShopCard(x=0, name=carry, faction=_fw_faction(fw), cost=2)]) == ''
    # 持有 1 + 在售 1 = 1.5 启动
    got = pick_framework([_bc(carry, _fw_faction(fw))], [],
                         [ShopCard(x=0, name=partial, faction=_fw_faction(fw), cost=2)])
    assert got == fw


# ===== 不变量 6:保持滞回——现任持有 ≥1 时 shop 蒸发不丢框架 =====

@pytest.mark.parametrize('fw', FRAMEWORKS)
def test_inv_incumbent_survives_shop_evaporation(fw):
    carry = REPS[fw]['carry']
    fw_kept = pick_framework([_bc(carry, _fw_faction(fw))], [], [],
                             current=fw)
    assert fw_kept == fw, '现任持有 1 张,shop 空时不得回退未定'
