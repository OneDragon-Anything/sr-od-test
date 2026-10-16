"""collect_ore 上报合并升星触发发放腿测试(镜像 src =
kernel/cw_action_report/collect_ore.py;晶矿域存量测试 =
kernel/test_ore.py 已超行限,本文件按镜像规范落新位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-26-liangzi-tongpin-qiyue.md(定稿)§2.4 条 3 + §4.6:晶矿角色腿的
inline 级联采集升星事实,整批全部写毕后收尾发火(发火时序与买牌腿
同构)——bench 终态 = 合并产物 + 发放角色并存。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    OreSight,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCollectOreParam,
)

_POOL = ('符玄', '希儿')

_SEED_SIG = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep',
                  group_id='g1')

_XY = (100, 200)


@pytest.fixture
def seeded_provider() -> Iterator[None]:
    """注确定 rng 提供槽(固定种子,期望名可现算钉名),必达复位。"""
    set_action_rng_provider(lambda tool: random.Random(20261016))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def _make_gs():
    """晶矿角色腿场景:1 颗晶矿(附着角色奖励 = 1★花火,零掷骰兑现)+
    2×1★花火在席 + 量子同频契约激活(附着眼 = 逻辑写种子)。"""
    gs = game_state_of(cw4_session())
    gs.observe(gs.spheres, OreSight(count=1, colors=('gold',),
                                    points=(('gold', *_XY, 30),)),
               sig=_SEED_SIG)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1))
             for _ in range(2)]
    slots += [BenchSlot(kind='empty')] * 7
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SEED_SIG)
    gs.observe(gs.active_env, '量子同频契约', sig=_SEED_SIG)
    gs.write_logic(gs.ore_rewards,
                   {f'{_XY[0]},{_XY[1]}': OreReward(kind='char',
                                                    char_id='花火',
                                                    char_star=1)},
                   produced_by='test-seed', sig=_SIG)
    return gs


def test_collect_ore_char_reward_fires_grant(seeded_provider) -> None:
    """晶矿角色腿发火时序锁(T-26 设计 §4.6 同构腿):角色奖励补齐三连
    → 级联合并 2★ 产物;整批写毕后发火 → bench 终态 = 产物 + 发放角色
    并存(发放名 = 注入槽种子现算;spheres 摘除与附着键移除照常)。"""
    expected = random.Random(20261016).choice(list(_POOL))
    gs = _make_gs()
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=(_XY,)), sig=_SIG)
    assert out.applied, f'晶矿开成: {out.reason}'
    units = [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
             if s is not None and s.kind == 'unit' and s.unit is not None]
    assert units == [('花火', 2), (expected, 1)], \
        f'合并产物 + 发放角色并存: {units}'
    assert f'{_XY[0]},{_XY[1]}' not in gs.ore_rewards.value, \
        '开成即附着键移除(既有语义不变)'
