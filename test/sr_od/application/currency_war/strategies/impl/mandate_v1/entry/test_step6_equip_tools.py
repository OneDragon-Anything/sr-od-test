"""_step6_equip_tools 穿戴/重观察交替编排测试(entry 第 7 步发出面)。

锁的设计约定(装备网格伴随域新鲜度机制;与 mandate M7 发出面同构,M1
两发出点计数语义不得分叉):
- 标志交替:未置位帧产穿装并置位;置位帧产 Obs(in_place) 且读后清
  (「记账后→重观察前伴随域陈旧条目窗口禁消费」契约的执行点);
- M1 保全:空计划帧 equip_plan_empty_noop 计数仍发生(合法稳态 NOOP);
- 坐标全缺席帧:计数 m7_equip_xy_pending(值 = 跳过步数)+
  equip_plan_xy_all_pending(自愈重派帧),零穿装产出;
- 交替检查上提步首(置位帧提前 return):置位帧即使判据面有可用工具
  也不产工具原子(窗口禁消费强保证),m7_5_evaluated 置位帧不递增;
- 工具置位交替:工具原子帧置位 + 下一帧 Obs 读后清、零工具参数构造;
- 工具坐标缺席计数:m7_5_tool_xy_pending(按量)+
  m7_5_tool_xy_all_pending(自愈重派帧)。

计划构造器/工具判据面经 monkeypatch 打桩(被测对象 = 发出面编排,非
计划构造与判据本体);helper 与状态容器消费走真实路径。
"""

import types

from sr_od.application.currency_war.kernel import cw_equip_wear_plan
from sr_od.application.currency_war.data import cw_synthesis
from sr_od.application.currency_war.kernel import cw_equip_env as _equip_env_mod
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
    CwActionPrivilegeCardUseParam,
    CwActionWearEquipParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_OBS = ChannelSig(family='obs', actor='test')

_STEP = EquipWearStep(item_name='量产型装甲', char_name='银狼',
                      row='front', slot=1)


def _seed_gs(xy: dict | None, owned: list[str] | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, list(owned if owned is not None
                               else ['量产型装甲']), sig=_OBS)
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


def _stub_tools_usable(monkeypatch, tool: str = '特权赋予卡',
                       action: str = 'privilege_upgrade') -> None:
    """工具判据面打桩:返回一条 usable 判据条(被测对象 = 发出面编排,
    判据本体与准入走桩)。"""
    from sr_od.application.currency_war.kernel.cw_equip_env import (
        ToolAction,
    )
    monkeypatch.setattr(_equip_env_mod, 'evaluate_tool_actions',
                        lambda owned, comp: [
                            ToolAction(tool, action, True)])
    monkeypatch.setattr(_equip_env_mod, 'admitted_tool_actions',
                        lambda actions: list(actions))


def _stub_direction_comp(monkeypatch, key_equips: list[str]) -> None:
    """方向阵容读口打桩(key_equips 供目标选择逻辑取目标名)。"""
    monkeypatch.setattr(session_scope, 'direction_comp_of',
                        lambda session: types.SimpleNamespace(
                            key_equips=list(key_equips)))


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
    assert st.cw4_equip_xy_pending is True

    out2 = entry._step6_equip_tools(session, gs, None)
    assert len(out2) == 1
    assert isinstance(out2[0].action, CwActionObsParam)
    assert out2[0].action.scope == 'in_place'
    assert st.cw4_equip_xy_pending is False


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
    assert st.cw4_equip_xy_pending is False


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
    assert st.cw4_equip_xy_pending is False


def test_tool_atom_emission_sets_flag(monkeypatch) -> None:
    """工具置位交替:判据放行 + 伴随域种子 → 帧1 产工具原子且置标志。"""
    _stub_build(monkeypatch, EquipPlanBuild(steps=[], branch='m7'))
    _stub_tools_usable(monkeypatch)
    _stub_direction_comp(monkeypatch, ['量产型装甲·特权'])
    session = StrategySession()
    gs = _seed_gs({'特权赋予卡': [(1660, 120)], '量产型装甲': [(1740, 210)]},
                  owned=['特权赋予卡', '量产型装甲'])
    st = state_of(session)
    out1 = entry._step6_equip_tools(session, gs, None)
    assert len(out1) == 1
    atom = out1[0].action
    assert isinstance(atom, CwActionPrivilegeCardUseParam)
    assert atom.target_kind == 'equip'
    assert (atom.tool_cx, atom.tool_cy) == (1660, 120)
    assert (atom.tgt_cx, atom.tgt_cy) == (1740, 210)
    assert atom.item_name == '量产型装甲'
    assert out1[0].reason == 'm7_5_tool_consume'
    assert st.cw4_equip_xy_pending is True
    assert st.cw4_counters.get('m7_5_evaluated') == 1


def test_pending_frame_skips_tool_segment(monkeypatch) -> None:
    """置位帧跳工具段(提前 return 锁测):置位帧即使判据面有可用工具也
    只产 Obs(in_place)、零工具参数构造,读后清;m7_5_evaluated 不递增。"""
    _stub_build(monkeypatch, EquipPlanBuild(steps=[], branch='m7'))
    _stub_tools_usable(monkeypatch)
    _stub_direction_comp(monkeypatch, ['量产型装甲·特权'])
    session = StrategySession()
    gs = _seed_gs({'特权赋予卡': [(1660, 120)], '量产型装甲': [(1740, 210)]},
                  owned=['特权赋予卡', '量产型装甲'])
    st = state_of(session)
    st.cw4_equip_xy_pending = True   # 上帧已发穿装/工具原子
    out = entry._step6_equip_tools(session, gs, None)
    assert len(out) == 1
    assert isinstance(out[0].action, CwActionObsParam)
    assert out[0].action.scope == 'in_place'
    assert out[0].reason == 'm7_equip_reobserve'
    assert st.cw4_equip_xy_pending is False
    assert st.cw4_counters.get('m7_5_evaluated') is None   # 提前 return 不递增


def test_tool_alternation_two_frames(monkeypatch) -> None:
    """工具帧 → Obs 帧(交替机制延伸):帧1 工具原子置位,帧2 Obs 读后清
    且零工具参数构造;Obs 帧后判据面与伴随域仍在,续发恢复原状。"""
    _stub_build(monkeypatch, EquipPlanBuild(steps=[], branch='m7'))
    _stub_tools_usable(monkeypatch)
    _stub_direction_comp(monkeypatch, ['量产型装甲·特权'])
    session = StrategySession()
    gs = _seed_gs({'特权赋予卡': [(1660, 120)], '量产型装甲': [(1740, 210)]},
                  owned=['特权赋予卡', '量产型装甲'])
    st = state_of(session)
    out1 = entry._step6_equip_tools(session, gs, None)
    assert len(out1) == 1 and st.cw4_equip_xy_pending is True
    out2 = entry._step6_equip_tools(session, gs, None)
    assert len(out2) == 1
    assert isinstance(out2[0].action, CwActionObsParam)
    assert st.cw4_equip_xy_pending is False
    assert st.cw4_counters.get('m7_5_evaluated') == 1   # 置位帧不计评估
    out3 = entry._step6_equip_tools(session, gs, None)
    assert len(out3) == 1
    assert isinstance(out3[0].action, CwActionPrivilegeCardUseParam)
    assert st.cw4_counters.get('m7_5_evaluated') == 2


def test_tool_xy_missing_counts_and_self_heal(monkeypatch) -> None:
    """工具坐标缺席计数:m7_5_tool_xy_pending 按量 +
    m7_5_tool_xy_all_pending 帧;零工具原子产出、标志不置。"""
    _stub_build(monkeypatch, EquipPlanBuild(steps=[], branch='m7'))
    _stub_tools_usable(monkeypatch)
    _stub_direction_comp(monkeypatch, ['量产型装甲·特权'])
    session = StrategySession()
    gs = _seed_gs({'折叠小刀': [(10, 20)]},   # 工具/目标坐标全缺席
                  owned=['特权赋予卡', '量产型装甲'])
    st = state_of(session)
    out = entry._step6_equip_tools(session, gs, None)
    assert out == []
    assert st.cw4_counters.get('m7_5_tool_xy_pending') == 1
    assert st.cw4_counters.get('m7_5_tool_xy_all_pending') == 1
    assert st.cw4_equip_xy_pending is False
    assert st.cw4_counters.get('m7_5_evaluated') == 1


def test_tool_pending_count_accumulates_by_quantity(monkeypatch) -> None:
    """按量累加口径:两可用原子 × 坐标全缺席 → 计数 = 2(帧粒度事件按量
    累加,与 m7_equip_xy_pending 同口径)。"""
    _stub_build(monkeypatch, EquipPlanBuild(steps=[], branch='m7'))
    from sr_od.application.currency_war.kernel.cw_equip_env import ToolAction
    monkeypatch.setattr(_equip_env_mod, 'evaluate_tool_actions',
                        lambda owned, comp: [
                            ToolAction('特权赋予卡', 'privilege_upgrade',
                                       True),
                            ToolAction('冶金炉', 'furnace_single', True)])
    monkeypatch.setattr(_equip_env_mod, 'admitted_tool_actions',
                        lambda actions: list(actions))
    # 回收合格集打桩(判据本体非被测对象;确定性目标名)
    monkeypatch.setattr(cw_synthesis, 'recycle_qualified',
                        lambda key_equips: frozenset({'量产型装甲'}))
    _stub_direction_comp(monkeypatch, ['量产型装甲·特权'])
    session = StrategySession()
    gs = _seed_gs({}, owned=['特权赋予卡', '冶金炉', '量产型装甲'])
    st = state_of(session)
    out = entry._step6_equip_tools(session, gs, None)
    assert out == []
    assert st.cw4_counters.get('m7_5_tool_xy_pending') == 2
    assert st.cw4_counters.get('m7_5_tool_xy_all_pending') == 1
    assert st.cw4_equip_xy_pending is False
