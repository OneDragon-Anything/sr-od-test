"""策略延时发放到点原语测试(镜像 src = kernel/cw_gain_chain.py 的
discharge_due_strategy_grants)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 4(kernel 原语
面;sim 窗口接线与世界真值归 sim/cw_sim_backend 侧文件)+ 裁决点 3/4
默认案。直构形态先例 = 同目录 test_check_strategy_battle_grants.py:
- 未到点(remaining > 0)零发放零写;
- 到点(remaining <= 0)→ 装备腿入栏 + 弹除 + 效果串
  delayed_grant:<item>(placed=…)+ 队列回写 evidence strategy_grant_due
  (姊妹双卡参数化:人才激励 / 人才激励+,T-107 批扩面);
- 分道判据(monkeypatch 临时占席道具条目)→ gain_bench_item 落席;
- 发放拒落(equips 未观察)→ 零写 + 条目仍弹除(到期即消费)+ 回写行
  留存证据;
- 注册表漂移防御(队列卡名查行失败)→ 零发放 + 条目保留。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_gain_chain
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    discharge_due_strategy_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '人才激励'
_ITEM = '员工投影仪'


def _empty_slots(n: int = 9) -> list[BenchSlot]:
    return [BenchSlot(kind='empty')] * n


def _gs(*, equips: list[str] | None, bench_slots: list[BenchSlot] | None,
        queue: tuple) -> GameState:
    """equips/bench/队列直置(equips=None / bench_slots=None = 未观察
    拒落域)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True   # 确定发放 = 锁确定面写通道(先例同款)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       evidence='t:equips', sig=_LSIG)
    if bench_slots is not None:
        gs.observe(gs.bench, BenchView(slots=bench_slots, capacity=9),
                   sig=_SIG_OBS)
    if queue:
        gs.write_logic(gs.pending_strategy_grants, queue,
                       produced_by='test-seed', evidence='t:queue',
                       sig=_LSIG)
    return gs


def test_not_due_zero_grant_zero_write() -> None:
    """未到点:remaining 全 > 0 → 零发放零写(队列原值,装备栏零动)。"""
    gs = _gs(equips=[], bench_slots=None, queue=((_CARD, 2),))
    seq_before = gs.write_seq
    assert discharge_due_strategy_grants(gs, rand=False, sig=_LSIG) == ()
    assert gs.pending_strategy_grants.value == ((_CARD, 2),), '未到点被弹除'
    assert gs.equips.value == [], '未到点误入栏'
    assert gs.write_seq == seq_before, '未到点出现写行'


@pytest.mark.parametrize('card', [_CARD, '人才激励+'])
def test_due_grants_equipment_ejects_entry(card: str) -> None:
    """到点发放真值(姊妹双卡参数化,逐名经真实注册表查行):remaining
    = 0 → 装备腿尾追入栏 + 条目弹除 + 效果串 delayed_grant:<item>
    (placed=True)+ 队列回写 evidence strategy_grant_due(确定面),
    evidence 值含触发卡名(同款发放物经卡名可分)。"""
    gs = _gs(equips=[], bench_slots=None, queue=((card, 0),))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_ITEM}(placed=True)',), \
        f'效果串: {effects}'
    assert gs.equips.value == [_ITEM], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
    assert gs.equips.source == 'logic' \
        and gs.pending_strategy_grants.source == 'logic', '确定发放走确定面'
    assert gs.pending_strategy_grants.evidence == 'strategy_grant_due', \
        f'队列回写 evidence: {gs.pending_strategy_grants.evidence}'
    assert gs.equips.evidence == f'strategy_grant_due:{card}#equip', \
        f'发放 evidence: {gs.equips.evidence}'


def test_due_routing_bench_item_branch(monkeypatch) -> None:
    """分道判据(锁机制):注册表临时条目发放物 ∈ 占席词表 → 占席道具
    腿落席(带名槽件),不走装备栏——两词表归属即分道,零第二源。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        StrategyDelayedGrant,
    )
    monkeypatch.setitem(
        cw_gain_chain.STRATEGY_DELAYED_GRANTS, '占席测试卡',
        StrategyDelayedGrant(id='000000', delay_nodes=1,
                             item='简易武装箱'))
    gs = _gs(equips=[], bench_slots=_empty_slots(),
             queue=(('占席测试卡', 0),))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == ('delayed_grant:简易武装箱(placed=True)',), \
        f'效果串: {effects}'
    assert gs.equips.value == [], '占席道具误入装备栏'
    slots = gs.bench.value.slots
    landed = [s for s in slots if s is not None and s.kind == 'supply_box']
    assert len(landed) == 1 and landed[0].item == '简易武装箱', '未落席'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'


def test_grant_rejected_zero_write_entry_still_ejected() -> None:
    """发放拒落(equips 未观察直构域):零写 + 条目仍弹除(到期即消费,
    裁决点 4 默认案 = 环境通道弹除语义同构)+ 回写行留存证据(世界偏穷
    有界:每条至多 1 件)。"""
    gs = _gs(equips=None, bench_slots=None, queue=((_CARD, 0),))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_ITEM}(placed=False)',), \
        f'效果串: {effects}'
    assert gs.equips.value is None, '拒落域出现写'
    assert gs.pending_strategy_grants.value == (), '拒落条目未弹除'
    assert gs.pending_strategy_grants.evidence == 'strategy_grant_due', \
        '弹除回写行缺留存证据'


def test_registry_miss_defense_retains_entry() -> None:
    """注册表漂移防御(正常不可达):队列卡名查注册表失败 → 零发放 +
    条目保留不弹除(零写,队列原值)。"""
    gs = _gs(equips=[], bench_slots=None, queue=(('未注册的卡', 0),))
    seq_before = gs.write_seq
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (), '漂移条目误发放'
    assert gs.pending_strategy_grants.value == (('未注册的卡', 0),), \
        '漂移条目被弹除'
    assert gs.write_seq == seq_before, '漂移分支出现写行'
