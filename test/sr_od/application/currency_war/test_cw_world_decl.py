"""世界后果声明对照锁(schema 形状 / 载体兼容 / 喂入端口 / 分派校验 /
表 #1-#4 逐动作声明对照)。

锁设计约定(动作后果声明化迭代总纲 design.md §2.2 契约 1/2/3/5 + 详设
details/world-decl.md §1/§2/§3/§7;3.1 = 声明基建骨架,行为对照锁随
3.2/3.3 按 §2 对照表增量填充):
- WorldDecl 形状锁(冻结 dataclass;字段序 = next_screen 在前,位置
  构造契约);
- LogicOutcome.world_decl 缺省兼容锁(缺省 None,既有全量构造点
  零改动兼容);
- declare_world 喂入契约锁(未装配 no-op = 实机零行为变化的机制
  前提;装配后转发后端 advance;decl=None 端口层直返);
- advance 分派表集外值 ValueError 锁(封闭集防线与转移事件同型);
- 表 #1-#4 对照锁(3.2):桩 gs 触发上报,断言 world_decl 的
  trigger/next_screen 与对照表逐位一致;node_advance 按推导规则对桩
  gs 节点序断言(含局终分支 eff 超总长 → '');applied=False → None。
"""
import dataclasses
from types import SimpleNamespace

import pytest
from test.harness.sim_backend_runner import (
    MinimalSimBackend,
    sim_backend_fixture,
)

from sr_od.application.currency_war.kernel.cw_action_report.pick_encounter import (
    report_action_pick_encounter_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.start_battle import (
    report_action_start_battle_param,
)
from sr_od.application.currency_war.kernel.cw_events import EncounterOption
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    LogicOutcome,
    observe_node_anchor,
    report_node_advance,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_ports import declare_world

_SIG = ChannelSig(family='logic_action', actor='WorldDeclTest', mode='compute')

#: 桩 gs 节点序 → 预期 next_screen(推导规则逐分支对照;ord = 推进后
#: 新序,总长 = P1(9) + P2(7) = 16,超长 = 局终 '')。
_NODE_ADVANCE_SCREEN_TABLE: tuple[tuple[int, str], ...] = (
    (2, '货币战争-备战'),          # P1r2 battle
    (5, '货币战争-补给'),          # P1r5 supply
    (7, '货币战争-遭遇节点'),      # P1r7 encounter
    (9, '货币战争-BOSS简报'),      # P1r9 boss
    (10, '货币战争-位面过渡'),     # P2r1 位面切换优先
    (11, '货币战争-备战'),         # P2r2 battle
    (16, '货币战争-BOSS简报'),     # P2r7 boss(真值表末节点)
    (17, ''),                      # 局终分支:eff 超总长 → ''
)


def test_world_decl_shape_lock():
    """WorldDecl 形状锁(契约 1):冻结 dataclass;字段面 = next_screen/
    trigger 且 next_screen 在前(18 个上报构造点与 backend 消费端按此
    位置契约解析;字段增删/换序/可变性漂移 = 声明契约破坏)。"""
    assert [f.name for f in dataclasses.fields(WorldDecl)] == [
        'next_screen', 'trigger']
    decl = WorldDecl(next_screen='货币战争-备战', trigger='')
    with pytest.raises(dataclasses.FrozenInstanceError):
        decl.next_screen = 'x'  # type: ignore[misc]


def test_logic_outcome_world_decl_default_compat():
    """LogicOutcome.world_decl 缺省兼容锁(契约 2):缺省 None =
    既有全量构造点零改动兼容——关键字构造(applied 起)与位置构造
    (至 bought_count 位)均不受新字段影响,拒绝路径(world_decl=None)
    语义不变。"""
    assert LogicOutcome(applied=True).world_decl is None
    positional = LogicOutcome(True, '同名拒上', 3, None, 2)
    assert positional.world_decl is None
    assert positional.bought_count == 2


def test_declare_world_port_default_off_and_forwarding():
    """declare_world 喂入契约锁(契约 3):未装配 = no-op(实机零开销
    零行为变化——本迭代产物「在库未接线」的机制前提);装配后 =
    后端 advance(decl) 恰转发一次;decl = None(非转移动作)端口层
    直返,装配与否都不触后端。"""
    # 未装配:no-op 不响(纯实机缺省态)
    assert cw_sim_ports.get_sim_backend() is None
    declare_world(WorldDecl(next_screen='货币战争-备战', trigger=''))
    declare_world(None)

    class _RecordingBackend(MinimalSimBackend):
        """advance 调用记录桩(喂入转发的观测面;其余端口腿继承最小实现)。"""

        def __init__(self) -> None:
            super().__init__()
            self.advanced: list[WorldDecl] = []

        def advance(self, decl: WorldDecl) -> None:
            self.advanced.append(decl)

    backend = _RecordingBackend()
    with sim_backend_fixture(backend):
        declare_world(None)
        assert backend.advanced == []
        decl = WorldDecl(next_screen='货币战争-备战', trigger='')
        declare_world(decl)
        assert backend.advanced == [decl]
    assert cw_sim_ports.get_sim_backend() is None, 'teardown 必卸'


def test_advance_trigger_out_of_set_raises():
    """advance 分派表集外值 ValueError 锁(详设 world-decl.md §3 集外
    处置):集外 trigger 响亮(构造点漂移 = 接线 bug 禁静默),与现行
    转移事件封闭集同等防线;'' 纯转移恒在键集(空串安全 = 不 raise,
    零专属过程)。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        ADVANCE_TRIGGER_KINDS,
        SimBackend,
    )
    from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

    backend = SimBackend(seed=9, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    # box_pick = 详设点名的禁入反例(与画面名/动作名错位的自造词)
    with pytest.raises(ValueError, match='分派表'):
        backend.advance(WorldDecl(next_screen='货币战争-备战',
                                  trigger='box_pick'))
    assert '' in ADVANCE_TRIGGER_KINDS
    backend.advance(WorldDecl(next_screen='货币战争-备战', trigger=''))


# ============================================================ 表 #1/#2 对照锁
# (settle_confirm / supply_confirm → report_node_advance;声明归一 =
#  trigger 'node_advance',next_screen 按推导规则)

def test_node_advance_decl_normalizes_both_triggers():
    """表 #1/#2 归一语义锁:settle_confirm 与 supply_confirm 两触发
    上报的声明同形(trigger 恒 'node_advance',next_screen 同按推导
    ——归一不改推进/去重逻辑,详设 world-decl.md §2 表 #1/#2)。"""
    for trigger in ('settle_confirm', 'supply_confirm'):
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        observe_node_anchor(gs, 1, trigger_screen='货币战争-备战',
                            actor='WorldDeclTest')
        out = report_node_advance(gs, trigger=trigger)
        assert out.applied
        assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                           trigger='node_advance'), \
            f'trigger={trigger} 声明与表 #1/#2 不一致'


def test_node_advance_decl_next_screen_derivation_table():
    """表 #1/#2 next_screen 推导规则锁(详设 §2 推导规则逐分支):
    桩 gs 锚定节点序 → 上报推进 → eff 新序按「超总长局终 → 变长反解 →
    位面切换优先 → kind 映射」断言单值(权威源 = kernel 节点日程
    真值表 cw_node_schedule + effective_node_ord,禁读 gs.node 镜像)。"""
    for eff_new, expected_screen in _NODE_ADVANCE_SCREEN_TABLE:
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        observe_node_anchor(gs, eff_new - 1, trigger_screen='货币战争-备战',
                            actor='WorldDeclTest')
        out = report_node_advance(gs, trigger='settle_confirm')
        assert out.applied
        decl = out.world_decl
        assert decl is not None
        assert decl.trigger == 'node_advance'
        assert decl.next_screen == expected_screen, \
            f'eff={eff_new} 推导值 {decl.next_screen!r} ≠ {expected_screen!r}'


def test_node_advance_decl_none_on_gate_blocked():
    """applied=False → 声明 None(构造义务契约:拒绝/未发出 = None,
    对齐现行「applied=False 零广播」):新容器未锚定,观察态门挡。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied is False
    assert out.world_decl is None


# ============================================================ 表 #3/#4 对照锁
# (start_battle / pick_encounter → battle_resolve + 结算屏)

def test_start_battle_decl_table_row3():
    """表 #3 对照锁:出战上报 applied 出口声明 = (结算屏,
    battle_resolve);两个 applied 出口(常规/免战跳过递减)同声明;
    桩 gs = 新容器(出战上报零容器写,语义 = 结算屏观察覆盖接管)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out = report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-结算',
                                       trigger='battle_resolve')


def test_start_battle_decl_skip_substate_exit():
    """表 #3 免战跳过出口锁:skip_substate 上报(递减出口)声明与常规
    出口逐位一致(装饰器覆盖全部 applied 出口 → 构造义务同覆盖)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EFFECTS,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    session = SimpleNamespace()
    game_state_of(session).effects.register_strategy(
        STRATEGY_EFFECTS['免战牌'], acquired_t=None)
    out = report_action_start_battle_param(
        gs, SimpleNamespace(), _SIG, session=session, skip_substate=True)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-结算',
                                       trigger='battle_resolve')


def _gs_with_encounter_payload() -> GameState:
    """桩容器 + 遭遇 payload 双选项(选值组装的读源)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.encounter, SimpleNamespace(options=[
        EncounterOption(idx=0, difficulty=1, affixes=['超凡入圣'],
                        rewards=['金币+100']),
        EncounterOption(idx=1, difficulty=3, affixes=['不速之约'],
                        rewards=['装备+1', '钻石+5']),
    ]), sig=ChannelSig(family='obs', actor='WorldDeclTest'))
    return gs


def test_pick_encounter_decl_table_row4():
    """表 #4 对照锁:遭遇选档上报(派发即终结)applied 出口声明 =
    (结算屏, battle_resolve);选值照常落 chosen_encounter。"""
    gs = _gs_with_encounter_payload()
    out = report_action_pick_encounter_param(gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert gs.chosen_encounter.value is not None, '选值照常落账(发射即写)'
    assert out.world_decl == WorldDecl(next_screen='货币战争-结算',
                                       trigger='battle_resolve')


def test_pick_encounter_decl_none_on_unresolved():
    """表 #4 applied=False → 声明 None(payload 离屏/idx 越界 = 留证
    不写,fail-closed 出口零声明)。"""
    out = report_action_pick_encounter_param(
        GameState(schema_version=GAME_STATE_SCHEMA_VERSION),
        SimpleNamespace(idx=0), _SIG)
    assert out.applied is False
    assert out.world_decl is None


# ============================================================ 单轨锁(3.2)

def test_migrated_actions_single_track_no_transition_event():
    """单动作单轨锁(详设 §5):已迁四动作的上报不再广播转移事件
    (装饰器/emit 摘除)——sink 在场收不到事件,推进唯一驱动 = 声明喂入。"""
    from sr_od.application.currency_war.kernel.cw_event_hooks import (
        set_transition_event_sink,
    )
    received: list[str] = []
    set_transition_event_sink(lambda ev: received.append(ev.kind))
    try:
        # start_battle / pick_encounter:applied 出口
        gs = _gs_with_encounter_payload()
        report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
        report_action_pick_encounter_param(gs, SimpleNamespace(idx=0), _SIG)
        # node_advance:落账出口
        gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        observe_node_anchor(gs2, 1, trigger_screen='货币战争-备战',
                            actor='WorldDeclTest')
        out = report_node_advance(gs2, trigger='settle_confirm')
        assert out.applied
    finally:
        set_transition_event_sink(None)
    assert received == [], \
        f'已迁动作不得广播转移事件(单轨): {received}'
