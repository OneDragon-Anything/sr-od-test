"""世界后果声明对照测试(schema 形状 / 载体兼容 / 喂入端口 / 分派校验 /
表 #1-#18 逐动作声明对照)。

钉住设计约定(动作后果声明化迭代总纲  契约 1/2/3/5 + 详设
details/world-decl.md §1/§2/§3/§7;3.1 = 声明基建骨架,行为对照测试随
3.2/3.3 按 §2 对照表增量填充):
- WorldDecl 形状测试(冻结 dataclass;字段序 = next_screen 在前,位置
  构造契约);
- LogicOutcome.world_decl 缺省兼容测试(缺省 None,既有全量构造点
  零改动兼容);
- declare_world 喂入契约测试(未装配 no-op = 实机零行为变化的机制
  前提;装配后转发后端 advance;decl=None 端口层直返);
- advance 分派表集外值 ValueError 测试(键集防线,构造点漂移禁静默);
- 表 #1-#18 对照测试(3.2 表 #1-#4 + 3.3 表 #5-#18):桩 gs 触发上报,
  断言 world_decl 的 trigger/next_screen 与对照表逐位一致;node_advance
  按推导规则对桩 gs 节点序断言(含局终分支 eff 超总长 → '');
  applied=False → None。
"""
import dataclasses
from types import SimpleNamespace

import pytest
from test.harness.sim_backend_runner import (
    MinimalSimBackend,
    sim_backend_fixture,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_encounter_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.close_shop import (
    report_action_close_shop_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.open_bookcard import (
    report_action_open_bookcard_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_invest_env import (
    report_action_pick_invest_env_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_invest_strategy import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
    report_action_pick_planner_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_supply import (
    report_action_pick_supply_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.start_battle import (
    report_action_start_battle_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.zero_writes import (
    report_action_open_box_param,
    report_action_pick_box_card_param,
    report_action_pick_expert_invite_param,
    report_action_pick_fortune_param,
    report_action_pick_megastar_param,
    report_action_pick_partner_param,
    report_action_pick_star_tome_param,
    report_action_pick_wish_trial_param,
    report_action_refresh_invest_cards_param,
)
from sr_od.application.currency_war.kernel.cw_events import EncounterOption
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    SCREEN_SHOP_PANEL,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    LogicOutcome,
    observe_node_anchor,
    report_node_advance,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionOpenBoxParam
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_ports import declare_world

_SIG = ChannelSig(family='logic_action', actor='WorldDeclTest', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='WorldDeclTest')

#: 桩 gs 节点键 → 预期 next_screen(推导规则逐分支对照;键 = 推进后
#: 新序位,总长 = P1(9) + P2(7) + P3(7) = 23,P3 末无后继 = 局终 '')。
#: 2026-10-29 流程模型对齐:node_advance 稳态落点 = 新节点窗呈现屏
#: ——弹窗型节点(supply/encounter/boss)= 备战底层上的节点弹窗模态、
#: battle/reward = 回备战自动弹店 = 商店档、1-1 = 备战档(不弹店)、
#: 位面首 = 位面过渡、超序列 = 局终 '')。
_NODE_ADVANCE_SCREEN_TABLE: tuple[tuple[tuple[int, int], str], ...] = (
    ((1, 1), SCREEN_SHOP_PANEL),        # →P1r2 battle(1-1 例外外 → 弹店)
    ((1, 4), '货币战争-补给'),          # →P1r5 supply(节点弹窗模态)
    ((1, 6), '货币战争-遭遇节点'),      # →P1r7 encounter(节点弹窗模态)
    ((1, 8), '货币战争-BOSS简报'),      # →P1r9 boss(节点弹窗模态)
    ((1, 9), '货币战争-位面过渡'),      # →P2r1 位面切换优先
    ((2, 1), SCREEN_SHOP_PANEL),        # →P2r2 battle(非 1-1 → 弹店)
    ((2, 6), '货币战争-BOSS简报'),      # →P2r7 boss
    ((2, 7), '货币战争-位面过渡'),      # →P3r1 位面切换优先(P3 在表)
    ((3, 6), '货币战争-BOSS简报'),      # →P3r7 boss(真值表末节点)
    ((3, 7), ''),                       # 局终:P3 末无后继 → 事件式 ''
)


def test_world_decl_shape_lock():
    """WorldDecl 形状测试(契约 1):冻结 dataclass;字段面 = next_screen/
    trigger/slots 且 next_screen 在前(全部上报构造点与 backend 消费端按
    此位置契约解析;字段增删/换序/可变性漂移 = 声明契约破坏)。slots =
    2026-10-19 用户裁定批新增(参数化动作槽位载荷,坐标系 = 动作参数类
    slots 同源),缺省空 = 既有构造点零改动兼容。"""
    assert [f.name for f in dataclasses.fields(WorldDecl)] == [
        'next_screen', 'trigger', 'slots']
    decl = WorldDecl(next_screen='货币战争-备战', trigger='')
    assert decl.slots == (), '载荷缺省空(既有构造点零改动兼容)'
    with pytest.raises(dataclasses.FrozenInstanceError):
        decl.next_screen = 'x'  # type: ignore[misc]


def test_refresh_invest_decl_trigger_derivation():
    """投资刷新声明对照测试(2026-10-19 用户裁定批;T-427 验收 F-1 修正
    后三状态全 Sound):active_env 非空 = 策略屏逐卡;active_env 空 ∧
    env_refresh_left 非 None(环境屏已呈现,该字段唯一写端 = 环境屏呈现
    写点)= 环境屏整组;active_env 空 ∧ None(无环境局,env_present 缺省
    False 的合法配置)= 策略屏逐卡——旧单一 active_env 依据在该局误派
    env 分支造成静默活锁,本分支即回归锁;slots 自 param 原样透传。容器
    零写(刷新真值归重入观察覆盖)。"""
    gs_open = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs_open.write_logic(gs_open.env_refresh_left, 1,
                        produced_by='WorldDeclTest', sig=_SIG)
    out_env = report_action_refresh_invest_cards_param(
        gs_open, SimpleNamespace(slots=(0, 1, 2)), _SIG)
    assert out_env.applied
    assert out_env.world_decl == WorldDecl(
        next_screen='货币战争-投资环境', trigger='refresh_invest_env',
        slots=(0, 1, 2))
    gs_strat = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs_strat.write_logic(gs_strat.active_env, '火药味',
                         produced_by='WorldDeclTest', sig=_SIG)
    out_strat = report_action_refresh_invest_cards_param(
        gs_strat, SimpleNamespace(slots=(1,)), _SIG)
    assert out_strat.applied
    assert out_strat.world_decl == WorldDecl(
        next_screen='货币战争-投资策略', trigger='refresh_invest_strategy',
        slots=(1,))
    gs_noenv = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out_noenv = report_action_refresh_invest_cards_param(
        gs_noenv, SimpleNamespace(slots=(2,)), _SIG)
    assert out_noenv.applied
    assert out_noenv.world_decl == WorldDecl(
        next_screen='货币战争-投资策略', trigger='refresh_invest_strategy',
        slots=(2,)), '无环境局(active_env 空 + 计数未写)走策略分支'


def test_logic_outcome_world_decl_default_compat():
    """LogicOutcome.world_decl 缺省兼容测试(契约 2):缺省 None =
    既有全量构造点零改动兼容——关键字构造(applied 起)与位置构造
    (至 bought_count 位)均不受新字段影响,拒绝路径(world_decl=None)
    语义不变。"""
    assert LogicOutcome(applied=True).world_decl is None
    positional = LogicOutcome(True, '同名拒上', 3, None, 2)
    assert positional.world_decl is None
    assert positional.bought_count == 2


def test_declare_world_port_default_off_and_forwarding():
    """declare_world 喂入契约测试(契约 3):未装配 = no-op(实机零开销
    零行为变化——本迭代产物「在库未接线」的机制前提);装配后 =
    后端 advance(decl) 恰转发一次;decl = None(非转移动作)端口层
    直返,装配与否都不触后端。"""
    # 未装配:no-op 不响(纯实机缺省态)
    assert cw_sim_ports.get_sim_backend() is None
    declare_world(WorldDecl(next_screen='货币战争-备战', trigger=''))
    declare_world(None)

    class _RecordingBackend(MinimalSimBackend):
        """advance 调用记录桩(喂入转发的观测面;其余端口分支继承最小实现)。"""

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
    """advance 分派表集外值 ValueError 测试(详设 world-decl.md §3 集外
    处置):集外 trigger 响亮(构造点漂移 = 接线 bug 禁静默);'' 纯转移
    恒在键集(空串安全 = 不 raise,零专属过程)。"""
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


# ============================================================ 表 #1/#2 对照测试
# (settle_confirm / supply_finish → report_node_advance;声明归一 =
#  trigger 'node_advance',next_screen 按推导规则;2026-10-29 流程模型
#  对齐:supply_confirm 随「确认即推节点」废止,出战完成 = supply_finish)

def test_node_advance_decl_normalizes_both_triggers():
    """表 #1/#2 归一语义测试:settle_confirm 与 supply_finish 两触发
    上报的声明同形(trigger 恒 'node_advance',next_screen 同按推导
    ——归一不改推进/去重逻辑,详设 world-decl.md §2 表 #1/#2;
    supply_finish = 补给节点出战完成语义,2026-10-29 流程模型对齐:
    补给选完回备战弹店零推进,出战动作才完成节点)。桩 gs 锚 (1,1)
    → 推进 (1,2) reward 节点:非 1-1 → 商店档(回备战自动弹店)。"""
    for trigger in ('settle_confirm', 'supply_finish'):
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        observe_node_anchor(gs, (1, 1), trigger_screen='货币战争-备战',
                            actor='WorldDeclTest')
        out = report_node_advance(gs, trigger=trigger)
        assert out.applied
        assert out.world_decl == WorldDecl(next_screen=SCREEN_SHOP_PANEL,
                                           trigger='node_advance'), \
            f'trigger={trigger} 声明与表 #1/#2 不一致'


def test_node_advance_decl_next_screen_derivation_table():
    """表 #1/#2 next_screen 推导规则测试(详设 §2 推导规则逐分支):
    桩 gs 锚定节点键 → 上报推进 → 新键按「无后继局终事件式 → 位面切换
    优先 → 节点窗呈现屏(弹窗型节点 = 节点模态/battle-reward = 商店档/
    1-1 = 备战档)」断言单值(权威源 = kernel 节点日程真值表
    cw_node_schedule + effective_node_pos,禁读 gs.node 镜像)。"""
    for anchor_pos, expected_screen in _NODE_ADVANCE_SCREEN_TABLE:
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        observe_node_anchor(gs, anchor_pos, trigger_screen='货币战争-备战',
                            actor='WorldDeclTest')
        out = report_node_advance(gs, trigger='settle_confirm')
        assert out.applied
        decl = out.world_decl
        assert decl is not None
        assert decl.trigger == 'node_advance'
        assert decl.next_screen == expected_screen, \
            f'anchor={anchor_pos} 推导值 {decl.next_screen!r} ≠ {expected_screen!r}'


def test_node_advance_decl_none_on_gate_blocked():
    """applied=False → 声明 None(构造义务契约:拒绝/未发出 = None,
    对齐现行「applied=False 零广播」):新容器未锚定,观察态门挡。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied is False
    assert out.world_decl is None


# ============================================================ 表 #3/#4 对照测试
# (start_battle → battle_resolve + 结算屏;pick_encounter → 商店档 +
#  pick_encounter——2026-10-29 流程模型对齐:遭遇选完关模态回备战自动
#  弹店,遭遇战改由出战动作开打,旧「选完即结算」声明废止)

def test_start_battle_decl_table_row3():
    """表 #3 对照测试:出战上报 applied 出口声明 = (结算屏,
    battle_resolve);两个 applied 出口(常规/免战跳过递减)同声明;
    桩 gs = 新容器(出战上报零容器写,语义 = 结算屏观察覆盖接管)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out = report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-结算',
                                       trigger='battle_resolve')


def test_start_battle_decl_skip_substate_exit():
    """表 #3 免战跳过出口测试:skip_substate 上报(递减出口)声明与常规
    出口逐位一致(构造义务覆盖全部 applied 出口,详设 world-decl.md
    §1)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EFFECTS,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    session = SimpleNamespace()
    game_state_of(session).effects.register_strategy(
        STRATEGY_EFFECTS['免战牌'], acquired_key=None)
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
    """表 #4 对照测试:遭遇选档上报(派发即终结)applied 出口声明 =
    (商店档, pick_encounter)——遭遇选完关遭遇模态回备战并自动弹店,
    遭遇战由出战动作开打(2026-10-29 流程模型对齐,旧「选档落地即该
    遭遇战结算」battle_resolve 直达声明废止);选值照常落 chosen_encounter
    (结算时点后移,消费语义不改)。"""
    gs = _gs_with_encounter_payload()
    out = report_action_pick_encounter_param(gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert gs.chosen_encounter.value is not None, '选值照常落账(发射即写)'
    assert out.world_decl == WorldDecl(next_screen=SCREEN_SHOP_PANEL,
                                       trigger='pick_encounter')


def test_pick_encounter_decl_none_on_unresolved():
    """表 #4 applied=False → 声明 None(payload 离屏/idx 越界 = 留证
    不写,fail-closed 出口零声明)。"""
    out = report_action_pick_encounter_param(
        GameState(schema_version=GAME_STATE_SCHEMA_VERSION),
        SimpleNamespace(idx=0), _SIG)
    assert out.applied is False
    assert out.world_decl is None


# ============================================================ 表 #5-#18 对照测试
# (3.3:选卡族与箱 / 书册卡 / 关店,余 14 动作;桩 gs 最小播种,声明逐位
#  对照详设 world-decl.md §2 终值)

#: 纯转移选卡族共用声明(partner/fortune/wish_trial/star_tome/expert_invite:
#: trigger = '' 零专属过程,backend 仅按 next_screen 幂等交回备战)。
_PREP_PURE_DECL: WorldDecl = WorldDecl(next_screen='货币战争-备战', trigger='')

#: 零写族上报直引表(具名 import 消费,禁包级 ``__getattr__`` 动态解析
#: ——静态可见,漏 import = 收集期红;对照测试按动作名取用)。
_ZERO_WRITE_REPORTS: dict[str, object] = {
    'open_box': report_action_open_box_param,
    'pick_box_card': report_action_pick_box_card_param,
    'pick_megastar': report_action_pick_megastar_param,
    'pick_partner': report_action_pick_partner_param,
    'pick_fortune': report_action_pick_fortune_param,
    'pick_wish_trial': report_action_pick_wish_trial_param,
    'pick_star_tome': report_action_pick_star_tome_param,
    'pick_expert_invite': report_action_pick_expert_invite_param,
}


def test_zero_write_transition_family_decl_rows_5_9_10_13_17():
    """零写族 8 转移上报对照测试(表 #5/#9/#10/#13-#17):applied 出口声明
    逐位一致——open_box = 备战底屏 + 具名 trigger(
    S6:武装箱选择画面出现事实改登记承载,声明回归底层屏);
    pick_box_card/pick_megastar = 备战 + 具名 trigger;纯转移五选卡 =
    备战 + ''。桩 gs = 新容器(容器零写,真值归观察)。"""
    cases: tuple[tuple[str, object, WorldDecl], ...] = (
        ('open_box', CwActionOpenBoxParam(),
         WorldDecl(next_screen='货币战争-备战',
                   trigger='open_box')),
        ('pick_box_card', SimpleNamespace(),
         WorldDecl(next_screen='货币战争-备战', trigger='pick_box_card')),
        ('pick_megastar', SimpleNamespace(),
         WorldDecl(next_screen='货币战争-备战', trigger='pick_megastar')),
        ('pick_partner', SimpleNamespace(), _PREP_PURE_DECL),
        ('pick_fortune', SimpleNamespace(), _PREP_PURE_DECL),
        ('pick_wish_trial', SimpleNamespace(), _PREP_PURE_DECL),
        ('pick_star_tome', SimpleNamespace(), _PREP_PURE_DECL),
        ('pick_expert_invite', SimpleNamespace(), _PREP_PURE_DECL),
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    for name, param, expected in cases:
        fn = _ZERO_WRITE_REPORTS.get(name)
        assert fn is not None, f'对照测试驱动表缺上报函数: {name}'
        out = fn(gs, param, _SIG)  # type: ignore[operator]
        assert out.applied
        assert out.world_decl == expected, f'{name} 声明与对照表不一致'


def test_pick_supply_decl_row12_both_applied_exits():
    """表 #12 对照测试:补给选卡上报两个 applied 出口(内容未知翻来源分支/
    装备落地分支)声明同形 = (商店档, pick_supply)——补给选完关模态回
    备战并自动弹店(2026-10-29 流程模型对齐,「确认即推节点」的
    supply_confirm 推进随声明废止,出战动作才完成节点);选卡后画面本
    瞬间不变,弹店由 sim 世界承接。装备名 = 注册表真名(垃圾袋);留证行
    经 consume_defect_sink 前清后清隔离。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
    )
    expected = WorldDecl(next_screen=SCREEN_SHOP_PANEL, trigger='pick_supply')
    consume_defect_sink()
    try:
        gs_unknown = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        out_unknown = report_action_pick_supply_param(
            gs_unknown, SimpleNamespace(idx=0, char_name='', norm_item=''),
            _SIG)
        assert out_unknown.applied
        assert out_unknown.world_decl == expected

        gs_landing = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        gs_landing.observe(gs_landing.equips, [], sig=_SIG_OBS)
        out_landing = report_action_pick_supply_param(
            gs_landing,
            SimpleNamespace(idx=0, char_name='', norm_item='垃圾袋'),
            _SIG)
        assert out_landing.applied
        assert out_landing.world_decl == expected
        assert '垃圾袋' in (gs_landing.equips.value or []), \
            '装备入账分支照常落账(声明不改上报写语义)'
    finally:
        consume_defect_sink()


def test_pick_invest_env_decl_row7():
    """表 #7 对照测试:投资环境上报 applied 出口声明 = (备战,
    pick_invest_env);获得链照常落账(active_env 写入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.invest_env_opts, ['公司契约', '轮岗', '头彩'],
                   produced_by='WorldDeclTest', sig=_SIG)
    out = report_action_pick_invest_env_param(
        gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                       trigger='pick_invest_env')
    assert gs.active_env.value == '公司契约', '获得链照常落账'


def test_pick_invest_strategy_decl_row8():
    """表 #8 对照测试:投资策略上报 applied 出口声明 = (备战,
    pick_invest_strategy);获得链照常落账(active_strategies 追加)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.invest_strategy_opts, ['加油站', '躺平', '淘金客'],
                   produced_by='WorldDeclTest', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name='加油站'), _SIG, session=None)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                       trigger='pick_invest_strategy')
    assert '加油站' in (gs.active_strategies.value or []), '获得链照常落账'


def test_pick_planner_decl_row11_applied_and_reject():
    """表 #11 对照测试:银狼策划上报未路由分支(终态兜底零写)applied 出口
    声明 = (备战, pick_planner);升费前置硬校验拒出口 applied=False →
    声明 None(留证行经 consume_defect_sink 前清后清隔离)。"""
    from sr_od.application.currency_war.kernel.cw_events import (
        PLANNER_LEG_UPGRADE,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out = report_action_pick_planner_param(gs, SimpleNamespace(), _SIG,
                                           branch_type='')
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                       trigger='pick_planner')
    consume_defect_sink()
    try:
        gs_unobserved = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        out_rej = report_action_pick_planner_param(
            gs_unobserved, SimpleNamespace(), _SIG,
            branch_type=PLANNER_LEG_UPGRADE)
        assert out_rej.applied is False
        assert out_rej.world_decl is None
    finally:
        consume_defect_sink()


def test_open_bookcard_decl_row6_all_exits():
    """表 #6 对照测试:开书册卡上报三出口声明——bench 未观察(零写占位
    出口)与腾席成功出口均 applied=True = (备战底屏, '')纯转移
    ( S6:专家邀请函画面出现事实改登记承载,声明
    回归底层屏);槽类型不符拒出口 applied=False → None。腾席写端 =
    本上报(开卡即腾席),声明不改写语义。"""
    gs_unobserved = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out_unobserved = report_action_open_bookcard_param(
        gs_unobserved, SimpleNamespace(slot=None), _SIG)
    assert out_unobserved.applied, 'bench 未观察出口 = 零写占位(applied)'
    assert out_unobserved.world_decl == WorldDecl(
        next_screen='货币战争-备战', trigger='')

    slots: list[BenchSlot | None] = [BenchSlot(kind='unit'),
                                     BenchSlot(kind='bookcard')]
    slots += [BenchSlot(kind='empty') for _ in range(7)]
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    out = report_action_open_bookcard_param(gs, SimpleNamespace(slot=2), _SIG)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                       trigger='')
    assert gs.bench.value.slots[1].kind == 'empty', '腾席照常落账'

    out_rej = report_action_open_bookcard_param(gs, SimpleNamespace(slot=2),
                                                _SIG)
    assert out_rej.applied is False
    assert out_rej.world_decl is None


def test_close_shop_decl_row18():
    """表 #18 对照测试:关店上报 applied 出口声明 = (备战, '')纯转移
    (离屏写端 = 本上报);离屏写照常落账(shop payload 离屏)。
    裸容器生效序位缺位 → 推导回退备战档,与历史口径同值。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out = report_action_close_shop_param(gs, SimpleNamespace(), _SIG)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                       trigger='')


def test_bottom_screen_decl_family_derives_at_encounter_slot():
    """「返回节点屏」声明族按当前生效节点推导(统一节点改写批修根,
    推导单一源 = ``node_screen_now``):生效序位锚在遭遇槽(战争边疆
    替换使固定 offer 槽 P3-2 变遭遇)→ 上报声明 next_screen = 备战档
    ——2026-10-29 呈现改造后节点弹窗(补给/遭遇/BOSS 简报)都是备战
    底层上的模态,「返回节点屏」类动作(关店/选卡/开卡)稳态落点恒
    备战档,旧「遭遇节点屏」类型化映射废止;推导机制保留(位面首例外
    = 位面过渡屏,本文件尾部判别位)。全链零漂移对拍面 =
    sim/cw_sim_backend/test_p3_win_terminal。"""
    from sr_od.application.currency_war.kernel.cw_node_schedule import (
        resolve_plane_node_seqs,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.node_seq_by_plane,
                   resolve_plane_node_seqs('战争边疆'),
                   produced_by='WorldDeclTest', evidence='node_seq:env',
                   sig=_SIG)
    observe_node_anchor(gs, (3, 2), trigger_screen='货币战争-遭遇节点',
                        actor='WorldDeclTest')
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name='加油站'), _SIG, session=None)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                       trigger='pick_invest_strategy'), \
        'offer 选卡结束返回备战档(节点弹窗 = 备战底层模态,类型化映射废止)'
    out = report_action_pick_megastar_param(gs, SimpleNamespace(), _SIG)
    assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                       trigger='pick_megastar')
    out = report_action_pick_fortune_param(gs, SimpleNamespace(), _SIG)
    assert out.world_decl == WorldDecl(next_screen='货币战争-备战',
                                       trigger=''), '纯转移同归备战档'
    # 位面首例外 = 推导机制保留的判别位(硬编码备战在此必红):「返回
    # 节点屏」声明族经 node_screen_now 推导,位面首窗起点 = 位面过渡屏。
    gs_first = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs_first.write_logic(gs_first.node_seq_by_plane,
                         resolve_plane_node_seqs('战争边疆'),
                         produced_by='WorldDeclTest', evidence='node_seq:env',
                         sig=_SIG)
    observe_node_anchor(gs_first, (3, 1),
                        trigger_screen='货币战争-位面过渡',
                        actor='WorldDeclTest')
    out = report_action_pick_invest_strategy_param(
        gs_first, SimpleNamespace(norm_name='加油站'), _SIG, session=None)
    assert out.applied
    assert out.world_decl == WorldDecl(next_screen='货币战争-位面过渡',
                                       trigger='pick_invest_strategy'), \
        '位面首「返回节点屏」推导 = 位面过渡屏(非硬编码备战)'
