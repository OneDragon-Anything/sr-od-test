"""_step6_equip_tools 穿戴/重观察交替编排测试(entry 第 7 步发出面)。

锁的设计约定(坐标伴随域新鲜度机制;与 mandate M7 发出面同构,M1 两发出
点计数语义不得分叉):
- 标志交替:未置位帧产穿装并置位;置位帧产 Obs(in_place) 且读后清
  (「记账后→重观察前伴随域陈旧条目窗口禁消费」契约的执行点);
- M1 保全:空计划帧 equip_plan_empty_noop 计数仍发生(合法稳态 NOOP);
- 坐标全缺席帧:计数 m7_equip_xy_pending(值 = 跳过步数)+
  equip_plan_xy_all_pending(自愈重派帧),零穿装产出。

计划构造器经 monkeypatch 打桩(被测对象 = 发出面编排,非计划构造本体);
helper 与状态容器消费走真实路径。
"""

from sr_od.application.currency_war.kernel import cw_equip_wear_plan
from sr_od.application.currency_war.kernel.cw_equip_wear_plan import (
    EquipPlanBuild,
    EquipWearStep,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionObsParam,
    CwActionWearEquipParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_OBS = ChannelSig(family='obs', actor='test')

_STEP = EquipWearStep(item_name='量产型装甲', char_name='银狼',
                      row='front', slot=1)


def _seed_gs(xy: dict | None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, ['量产型装甲'], sig=_OBS)
    if xy is not None:
        gs.observe(gs.owned_equip_xy, xy, sig=_OBS)
    gs.observe(gs.deployed,
               DeployedView(front_slots=[Unit(char_id='银狼', star=2,
                                              equips=[])],
                            back_slots=[None] * 6),
               sig=_OBS)
    return gs


def _stub_build(monkeypatch, build: EquipPlanBuild) -> None:
    monkeypatch.setattr(cw_equip_wear_plan, '_build_equip_wear_plan',
                        lambda session, registry: build)


def test_flag_alternation(monkeypatch) -> None:
    """标志交替:穿装帧置位 → 下帧 Obs(in_place) 读后清。"""
    _stub_build(monkeypatch, EquipPlanBuild(steps=[_STEP], branch='m7'))
    session = StrategySession()
    gs = _seed_gs({'量产型装甲': [(1740, 210)]})
    st = state_of(session)

    out1 = entry._step6_equip_tools(session, gs, None)
    assert len(out1) == 1
    assert isinstance(out1[0].action, CwActionWearEquipParam)
    assert (out1[0].action.src_cx, out1[0].action.src_cy) == (1740, 210)
    assert st.cw4_wear_pending is True

    out2 = entry._step6_equip_tools(session, gs, None)
    assert len(out2) == 1
    assert isinstance(out2[0].action, CwActionObsParam)
    assert out2[0].action.scope == 'in_place'
    assert st.cw4_wear_pending is False


def test_empty_plan_noop_counter_preserved(monkeypatch) -> None:
    """M1 保全:空计划帧 → equip_plan_empty_noop 计数仍发生,标志不置。"""
    _stub_build(monkeypatch, EquipPlanBuild(steps=[],
                                            empty_reason='pool_empty',
                                            branch='m7'))
    session = StrategySession()
    gs = _seed_gs({'量产型装甲': [(1740, 210)]})
    st = state_of(session)
    out = entry._step6_equip_tools(session, gs, None)
    assert out == []
    assert st.cw4_counters.get('equip_plan_empty_noop') == 1
    assert st.cw4_wear_pending is False


def test_xy_missing_counts_and_self_heal_frame(monkeypatch) -> None:
    """坐标全缺席帧:m7_equip_xy_pending 按步数计数 + 自愈重派帧计数,
    零穿装产出、标志不置。"""
    _stub_build(monkeypatch, EquipPlanBuild(steps=[_STEP], branch='m7'))
    session = StrategySession()
    gs = _seed_gs({'折叠小刀': [(10, 20)]})   # 计划件名不在伴随域
    st = state_of(session)
    out = entry._step6_equip_tools(session, gs, None)
    assert out == []
    assert st.cw4_counters.get('m7_equip_xy_pending') == 1
    assert st.cw4_counters.get('equip_plan_xy_all_pending') == 1
    assert st.cw4_wear_pending is False
