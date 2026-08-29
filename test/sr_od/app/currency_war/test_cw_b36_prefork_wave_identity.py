# -*- coding: utf-8 -*-
"""批㊱ 检查项锁:paired_prefork_wave_identity(分叉前牌面恒等)。

变异自检纪律:检查器必须被变异锁钉死——篡改一臂分叉前轮的首帧
牌面必须涌现违规,否则检查器是安慰剂(不消费 wave 数据)。
数据边界:green 臂用 3 seed 双臂直跑(snapshot 池,CPU 配额纪律)。
default 栈退役后对照臂改双 v2 独立重跑(跨运行确定性锁;跨策略
分叉前恒等的全量口径归 sim A/B 批的冻结快照 off 臂,W630 协议)。
不变式语义见 cw_sim_checks.check_paired_prefork_wave_identity。
"""
from __future__ import annotations

import copy

import pytest

from sr_od.application.currency_war.sim import cw_sim, cw_sim_checks

SEEDS = [0, 1, 2]


@pytest.fixture(scope='module')
def arms():
    """v2 双臂账本(3 seed;两臂独立重跑,锁跨运行确定性)。"""
    a = [cw_sim.simulate_p1(s, pool='snapshot') for s in SEEDS]
    b = [cw_sim.simulate_p1(s, pool='snapshot') for s in SEEDS]
    return a, b


def test_prefork_wave_identity_green(arms) -> None:
    """确定性双臂在动作分叉前每轮首波必须逐位一致(红 = 隐藏随机性)。"""
    a, b = arms
    r = cw_sim_checks.check_paired_prefork_wave_identity(
        [x.ledger for x in a], [x.ledger for x in b])
    assert r['violations'] == 0, f'{r}'


def test_prefork_wave_identity_mutation_kill(arms) -> None:
    """篡改变异:改一臂 r1 首波卡名(动作分叉前轮)→ 必须涌现违规。"""
    a, b = arms
    mutated = copy.deepcopy([x.ledger for x in a])
    row = next(r for r in mutated[0] if r.get('round_num') == 1)
    cards = row['sim']['shop_waves'][0]['cards']
    cards[0]['name'] = '__mutated__'
    r = cw_sim_checks.check_paired_prefork_wave_identity(
        mutated, [x.ledger for x in b])
    assert r['violations'] > 0, (
        '变异未杀:分叉前首波被篡改仍 0 违规 = 检查器不消费牌面波'
        '(安慰剂)')
