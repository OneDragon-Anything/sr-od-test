"""补给选卡上报挂点测试(src 镜像 = kernel/cw_action_report/pick_supply.py;
主断言对象 = report_action_pick_supply_param 的 R-choice 检查挂点——三个
applied 出口前统一调 check_strategy_take_all_supply,全都要族发放腿)。

锁面(卡面 id 131001「下1个补给阶段选择后，额外获得所有未选择的
角色及装备」):
- 三 applied 出口(内容全未知/无装备名列/落地)均到达检查:持卡局首个
  出口即耗 1 格配额(A 案事件消耗制,含内容全未知兜底轮);
- 检查读到场字段 ``unchosen_supply`` 本阶段快照(时序:画面 op 真选分支
  确认窗写点在派发动作 op 之前,上报入口已见同窗值——本文件在报告边界
  以种子字段构造该时点;op 侧写点锁 = operations/cw_screen/
  test_cw_screen_supply_node.py);
- 未持卡局三出口零一次性标志位零发放(挂点零扰)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_action_report.pick_supply import (
    report_action_pick_supply_param,
)
from sr_od.application.currency_war.kernel.cw_events import (
    SupplyOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    consume_defect_sink,
)

_SIG = ChannelSig(family='logic_action', actor='CwActionPickSupplyOp',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='test', mode='read')

_UNCHOSEN = (SupplyOption(idx=1, char='停云', equip='折叠小刀',
                          extra_equips=()),)


def _hook_gs(*, card: bool, unchosen: tuple[SupplyOption, ...] | None = None,
             latched: bool = False) -> GameState:
    """挂点直构容器(bench/equips 已观察 = 上报主分支可写;持卡/源/一次性标志位按参)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if card:
        gs.observe(gs.active_strategies, ['全都要·银'], sig=_SIG_OBS)
    if latched:
        gs.write_logic(gs.strategy_conditional_done,
                       ('take_all#全都要·银#1',),
                       produced_by='test-seed', sig=_SIG)
    if unchosen is not None:
        gs.write_logic(gs.unchosen_supply, unchosen, produced_by='test-seed',
                       sig=_SIG)
    return gs


def _bench_names(gs: GameState) -> list[str]:
    return [s.unit.char_id for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_content_unresolved_exit_arms_latch_zero_grant() -> None:
    """内容全未知兜底出口(A 案核心形态):持卡局该出口同样耗 1 格配额
    (选择事件即耗,零发放——源 None);预置一次性标志位耗尽局 / 未持卡局零一次性标志位写。"""
    consume_defect_sink()
    try:
        gs = _hook_gs(card=True)
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=0, char_name='', norm_item=''), _SIG)
        assert out.applied and out.reason == 'content_unresolved'
        assert gs.strategy_conditional_done.value == \
            ('take_all#全都要·银#1',), \
            '兜底出口即耗格(A 案簿记,计数复合键)'
        assert _bench_names(gs) == [] and gs.equips.value == [], '零发放'

        gs_prelatched = _hook_gs(card=True, latched=True)
        latch_before = gs_prelatched.strategy_conditional_done.value
        report_action_pick_supply_param(
            gs_prelatched,
            SimpleNamespace(idx=0, char_name='', norm_item=''), _SIG)
        assert gs_prelatched.strategy_conditional_done.value == latch_before, \
            '预置一次性标志位耗尽局零一次性标志位写(计数形封账)'

        gs_nocard = _hook_gs(card=False)
        report_action_pick_supply_param(
            gs_nocard, SimpleNamespace(idx=0, char_name='', norm_item=''),
            _SIG)
        assert not gs_nocard.strategy_conditional_done.value, '未持卡零一次性标志位'
    finally:
        consume_defect_sink()


def test_no_equip_column_exit_grants_from_field_snapshot() -> None:
    """无装备名列出口(真选 char-only 列):检查读到本阶段快照——场字段
    种子列照发(发放物 = 快照内容,与上报载荷列无关),置一次性标志位 + 字段清。"""
    gs = _hook_gs(card=True, unchosen=_UNCHOSEN)
    out = report_action_pick_supply_param(
        gs, SimpleNamespace(idx=0, char_name='希儿', norm_item=''), _SIG)
    assert out.applied and out.reason == 'no_equip_column'
    assert _bench_names(gs) == ['希儿', '停云'], \
        f'载荷列入席 + 快照列发放: {_bench_names(gs)}'
    assert gs.equips.value == ['折叠小刀'], '快照列装备随发'
    assert gs.strategy_conditional_done.value == \
        ('take_all#全都要·银#1',), '置一次性标志位(计数复合键)'
    assert gs.unchosen_supply.value is None, '消费即清'


def test_landing_exit_grants_from_field_snapshot() -> None:
    """落地出口:装备入账分支照常 + 检查发放快照列(时序同前)——置一次性标志位 +
    字段清;未持卡局同出口零一次性标志位零快照发放(挂点零扰对照)。"""
    gs = _hook_gs(card=True, unchosen=_UNCHOSEN)
    out = report_action_pick_supply_param(
        gs, SimpleNamespace(idx=0, char_name='希儿', norm_item='垃圾袋'),
        _SIG)
    assert out.applied and out.reason == 'landing_applied'
    assert '垃圾袋' in (gs.equips.value or []), '载荷装备照常入账'
    assert '折叠小刀' in (gs.equips.value or []), '快照列装备发放'
    assert _bench_names(gs) == ['希儿', '停云'], '载荷列 + 快照列双入席'
    assert gs.strategy_conditional_done.value == \
        ('take_all#全都要·银#1',), '置一次性标志位(计数复合键)'
    assert gs.unchosen_supply.value is None, '消费即清'

    gs_nocard = _hook_gs(card=False, unchosen=_UNCHOSEN)
    report_action_pick_supply_param(
        gs_nocard, SimpleNamespace(idx=0, char_name='希儿', norm_item=''),
        _SIG)
    assert _bench_names(gs_nocard) == ['希儿'], '未持卡仅载荷列入席'
    assert gs_nocard.equips.value == [], '未持卡零快照发放'
    assert not gs_nocard.strategy_conditional_done.value, '未持卡零一次性标志位'
    assert gs_nocard.unchosen_supply.value == _UNCHOSEN, '未持卡字段不清'
