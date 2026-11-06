"""补给屏观察上报测试(src 镜像 = kernel/cw_screen_report/supply_node.py;
迭代 = 打捞人才库触发语义调用点;容器写入契约面归
``../test_screen_report_ports.py`` 逐 report 端口族,本文件只承接触发
语义锁)。

锁面(R-entry 触发语义,直调 ``report_screen_supply_node_obs``):
- 读缺帧(options 空)= 整函数早退在调用点之前 → 刻意不发放,未选集
  快照原样保留(实际触发时点 = 进入补给阶段后的首个成功观察帧,
  读缺局发放顺延,发放源不变幂等不变);
- 首个成功观察帧发放:发放物 = 上一阶段未选列快照内容(源字段为
  上一阶段快照,非本帧 options——两帧内容刻意错开构造),发放后
  字段被清;
- 消费即清幂等:同帧二次上报(刷新重进重读形态)零再发放。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_action_report import (
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_events import SupplyOption
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_screen_report.supply_node import (
    CwScreenSupplyNodeObs,
    report_screen_supply_node_obs,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')
_SIG = ChannelSig(family='logic_action', actor='CwScreenSupplyNode',
                  mode='compute')

#: 上一阶段未选列快照(源内容)与下一阶段本帧 options(干扰内容)刻意
#: 错开——发放物只准来自快照面。种子→列映射:Random(7)→列 1(停云)。
_UNCHOSEN = (
    SupplyOption(idx=0, char='希儿', equip='光能电池', extra_equips=()),
    SupplyOption(idx=1, char='停云', equip='折叠小刀', extra_equips=()),
)
_THIS_FRAME = (SupplyOption(idx=0, char='三月七', equip='垃圾袋',
                            extra_equips=()),)


def _salvage_gs(*, card: bool = True,
                unchosen: tuple[SupplyOption, ...] | None = _UNCHOSEN
                ) -> GameState:
    """触发锁直构状态容器(持卡 + 上一阶段未选集快照;bench/equips 已观察)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        BenchView,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if card:
        gs.observe(gs.active_strategies, ['打捞人才库'], sig=_SIG_OBS)
    if unchosen is not None:
        gs.write_logic(gs.unchosen_supply, unchosen, produced_by='test-seed',
                       sig=_SIG)
    return gs


def test_read_miss_frame_does_not_grant() -> None:
    """读缺帧不发放(R-entry 调用点与早退交互):持卡 + 未选集快照在场,
    options 空 = 整函数早退在检查调用点之前 → 零容器写(含 supply/left/
    发放三面),快照原样保留——无画面证据帧不发放,读缺局发放顺延。"""
    gs = _salvage_gs()
    seq = gs.write_seq
    report_screen_supply_node_obs(gs, CwScreenSupplyNodeObs())
    assert gs.write_seq == seq, '读缺帧零写(发放面随整函数早退)'
    assert gs.unchosen_supply.value == _UNCHOSEN, '快照原样保留'


def test_first_success_frame_grants_from_prior_snapshot() -> None:
    """首个成功观察帧发放 + 源字段为上一阶段快照:发放物 = 快照列内容
    (固定种子掷列 1 = 停云),与本帧 options 内容(干扰面)无关;发放后
    字段被清。"""
    gs = _salvage_gs()
    set_action_rng_provider(lambda tool: random.Random(7))
    try:
        report_screen_supply_node_obs(
            gs, CwScreenSupplyNodeObs(in_node=True, options=list(_THIS_FRAME),
                                      refresh_left=1))
    finally:
        set_action_rng_provider(None)
    bench = [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
             if s is not None and s.kind == 'unit' and s.unit is not None]
    assert bench == [('停云', 1)], \
        f'发放物 = 快照列内容(非本帧 options): {bench}'
    assert gs.equips.value == ['折叠小刀'], '同列装备随发'
    assert gs.unchosen_supply.value is None, '发放后消费即清'
    assert gs.supply.value is not None, '本帧 options 照常落状态容器(观察面)'


def test_same_frame_repeat_zero_regrant() -> None:
    """消费即清幂等(重入形态):同阶段观察上报多次(刷新重进重读)——
    第 2 次成功帧观察面照常覆盖写,发放面零写(字段已清,第 2 门早退)。"""
    gs = _salvage_gs()
    set_action_rng_provider(lambda tool: random.Random(7))
    try:
        report_screen_supply_node_obs(
            gs, CwScreenSupplyNodeObs(in_node=True, options=list(_THIS_FRAME),
                                      refresh_left=1))
        equips_after_first = list(gs.equips.value or [])
        report_screen_supply_node_obs(
            gs, CwScreenSupplyNodeObs(in_node=True, options=list(_THIS_FRAME),
                                      refresh_left=1))
    finally:
        set_action_rng_provider(None)
    assert gs.equips.value == equips_after_first, '第二次上报零再发放'
    bench = [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
             if s is not None and s.kind == 'unit' and s.unit is not None]
    assert bench == [('停云', 1)], '零双发(恰一单位)'
