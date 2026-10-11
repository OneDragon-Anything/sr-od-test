"""sim 游戏后端 SimBackend 回归锁(驱动反转迭代;世界本体 + 画面状态机)。

锁面 = 迭代设计判据的可执行形态:
- 确定性:同 seed 同 RunConfig reset 双跑容器逐位一致(全采样由 seed 派生);
- 字段收敛:无第二账——节点键/连胜/相位载荷全部落容器;
- 初始序列(简报 → 环境 → wait_one_one → P1r1)与节点推进序列(收入/
  经验/环境金/发牌/offer 日程)平移语义零改;
- 转移声明重入幂等 + 选卡腿接获得链(契约送卡/burst 免费刷新/板面重写/
  骇客改件,对齐 cw_gain_chain 现役语义);
- 装备腿:穿着即合成住 kernel 穿装备上报(规则件缺口补 kernel,sim 与
  实机动作腿同构)。

设计依据 = sim- 后端结构(正本 = sim/sim-
合法引用;正本更新义务归末阶段)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from sr_od.application.currency_war.data.cw_synthesis import (
    CROSS_RECIPES,
    synthesize_target,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
    report_action_open_box_param,
    report_action_pick_box_card_param,
    report_action_pick_invest_env_param,
    report_action_pick_invest_strategy_param,
    report_action_pick_supply_param,
    report_action_start_battle_param,
    report_action_wear_equip_param,
)
from sr_od.application.currency_war.kernel.cw_economy import MAX_PLAYER_LEVEL
from sr_od.application.currency_war.kernel.cw_env_grants import (
    FIRST_STREAK_KEY,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    deployed_rows_of_view,
    report_node_advance,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    consume_screen_change,
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCollectOreParam,
    CwActionOpenBoxParam,
    CwActionWearEquipParam,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    DISCLOSURE_P3_UNOBSERVED,
    NODE_XP_BY_TYPE,
    ORE_PLANE_START_PENDING,
    SCREEN_BOSS_BRIEFING,
    SCREEN_BOX,
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SUPPLY,
    SimBackend,
    apply_node_xp,
    install_backend,
    stream_rng,
    uninstall_backend,
    xp_apply_amount,
)
from sr_od.application.currency_war.sim.cw_sim_battle import (
    SIM_BATTLE_FACE,
    BattleOutcome,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='SimBackendTest', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='TestSigWriter')

_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _backend(seed: int = 7, cfg: RunConfig = _CFG) -> SimBackend:
    """构造 + 装配(含 kernel 事件钩子订阅;调用方负责 uninstall)。"""
    backend = SimBackend(seed=seed, cfg=cfg)
    install_backend(backend)
    return backend


def _start_battle_feed(gs: GameState) -> None:
    """出战上报 + 声明喂入(声明化单轨;动作 op「上报后一行喂入」同形)。"""
    out = report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
    cw_sim_ports.declare_world(out.world_decl)


def _node_advance_feed(gs: GameState, *, trigger: str) -> None:
    """节点推进上报 + 声明喂入(声明化单轨;喂入 = 动作 op 同形)。"""
    out = report_node_advance(gs, trigger=trigger)
    assert out.applied, f'节点推进未落账: {out.reason!r}'
    cw_sim_ports.declare_world(out.world_decl)


def _encounter_pick_feed(gs: GameState) -> None:
    """遭遇选档上报 + 声明喂入(派发即终结 → battle_resolve 推进)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_encounter_param,
    )
    out = report_action_pick_encounter_param(gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)


# ============================================================ 确定性

def test_reset_deterministic_double_run_container_identical() -> None:
    """确定性锁(验收判据):同 seed 同 RunConfig reset 双跑,容器逐位
    一致(全采样由 seed 派生;世界真值域 + 新容器 Field 全集对拍)。"""
    b1 = SimBackend(seed=42, cfg=_CFG)
    b2 = SimBackend(seed=42, cfg=_CFG)
    for name in ('hp', 'gold', 'level', 'xp', 'streak', 'bench',
                 'deployed', 'enemy_affixes', 'plane_bosses',
                 'active_env', 'active_strategies', 'shop_locked',
                 'diamond_count', 'pending_loss', 'equips'):
        v1 = getattr(b1.gs, name).value
        v2 = getattr(b2.gs, name).value
        assert v1 == v2, (name, v1, v2)
    # 异 seed = 采样分形(词缀/开局手牌由 seed 派生的存在性证据)
    b3 = SimBackend(seed=43, cfg=_CFG)
    assert b3.gs.enemy_affixes.value != b1.gs.enemy_affixes.value or \
        b3.gs.bench.value != b1.gs.bench.value


# ============================================================ 初始序列

def test_reset_presents_briefing_and_env_gating_u07u08() -> None:
    """初始序列:reset 呈现简报屏;env_present=False 无环境屏;True 时
    简报下一步 → 投资环境屏(M02 采样 3 候选写容器 opts 槽,无双账)。"""
    b_live = SimBackend(seed=7, cfg=_CFG)
    assert b_live.screen_identity() == SCREEN_BRIEFING
    assert b_live.gs.plane_bosses.value is not None
    assert len(b_live.gs.enemy_affixes.value) == 3, '词缀入 seed 采样'
    b_live._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b_live._maybe_finish_wait()
    assert b_live.screen_identity() == SCREEN_PREP
    assert (b_live.gs.node.value.plane, b_live.gs.node.value.round_num) == (1, 1)
    assert b_live.gs.gold.value == 7, '开局 3 + P1r1 轮首收入(无环境支路)'

    b_env = SimBackend(seed=11, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b_env)
    try:
        assert b_env.screen_identity() == SCREEN_BRIEFING
        b_env._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b_env.screen_identity() == SCREEN_INVEST_ENV
        opts = b_env.gs.invest_env_opts.value
        assert opts is not None and len(opts) == 3, 'M02 候选写容器槽'
        out = report_action_pick_invest_env_param(
            b_env.gs, SimpleNamespace(idx=1), _SIG)
        assert out.applied
        assert (b_env.gs.active_env.value or '') == opts[1]
        cw_sim_ports.declare_world(out.world_decl)
        b_env._maybe_finish_wait()
        assert b_env.screen_identity() == SCREEN_PREP, '选卡确认交回备战'
    finally:
        uninstall_backend()


def test_reset_rejects_non_standard_mode() -> None:
    """非标准博弈显式拒(不猜差异;sim 首版辖域)。"""
    with pytest.raises(ValueError, match='首版辖域'):
        SimBackend(seed=1, cfg=RunConfig(selected_difficulty='A8',
                                         enemy_difficulty=108,
                                         game_mode='超频博弈'))


def test_affix_override_bypasses_sampling() -> None:
    """RunConfig.enemy_affixes 降级 override:非空 = 定向测试定词缀
    (跳过 reset/affixes 采样直用,开局 HP 查表同一消费面)。"""
    b = SimBackend(seed=5, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108,
        enemy_affixes=('开局不利',)))
    assert b.gs.enemy_affixes.value == ['开局不利']
    assert b.gs.hp.value == 62, 'A8/108 基础 82 + 开局不利 −20(查表单一源)'


# ============================================================ 节点推进序列

def test_node_advance_sequence_income_streak_and_next_window() -> None:
    """节点推进序列平移:终结动作上报 → 经验入账(被离开节点)→ 下一
    节点窗口(轮首收入/发牌)→ 备战呈现;声明重放(同一 node_advance
    声明重入)不二次推进(后端线性序守卫)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        assert gs.gold.value == 7
        xp_before = gs.xp.value
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '战斗窗口呈现结算页'
        assert gs.streak.value == 0, '奖励轮战斗连胜不动(M15:非战斗类)'
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 2)
        assert gs.xp.value[0] == xp_before[0] + NODE_XP_BY_TYPE['reward'], \
            '节点经验在推进时入账(奖励节点 +2)'
        assert b.screen_identity() == SCREEN_PREP
        assert gs.shop.value is not None, '节点切换自动全刷'
        # 重入幂等:同一 node_advance 声明重放(无新 kernel 推进)→
        # 窗口不重入、收入不重发
        gold_before = gs.gold.value
        cw_sim_ports.declare_world(WorldDecl(next_screen=SCREEN_PREP,
                                             trigger='node_advance'))
        assert (gs.node.value.round_num) == 2
        assert gs.gold.value == gold_before, '收入不重发'
    finally:
        uninstall_backend()


def test_start_battle_reentry_idempotent() -> None:
    """出战重入幂等:同一终结动作重复上报不二次结算(扣血/连胜
    不双计)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        _start_battle_feed(gs)
        hp_after_first = gs.hp.value
        streak_after_first = gs.streak.value
        _start_battle_feed(gs)
        assert gs.hp.value == hp_after_first, '重复上报零二次扣血'
        assert gs.streak.value == streak_after_first
    finally:
        uninstall_backend()


def _drive_step(b: SimBackend, rng_seed: int) -> None:
    """单步驱动(backend 直驱测试共用;按呈现屏分派到对应真实写端;
    18 动作全量单轨 = 上报 + 声明喂入,动作 op 同形)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_megastar_param,
        report_action_pick_planner_param,
    )
    screen = b.screen_identity()
    gs = b.gs
    if screen == SCREEN_SUPPLY:
        opts = gs.supply.value.options
        gs.write_logic(gs.chosen_supply,
                       ('', opts[0].equip, opts[0].has_diamond),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_supply_param,
        )
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=0, char_name='', norm_item=opts[0].equip),
            _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        _node_advance_feed(gs, trigger='supply_confirm')
    elif screen == SCREEN_INVEST_STRATEGY:
        opts = gs.invest_strategy_opts.value
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_invest_strategy_param,
        )
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=opts[0]), _SIG,
            rng=stream_rng(rng_seed, 'M11/pick/part'),
            session=SimpleNamespace())
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SETTLE:
        _node_advance_feed(gs, trigger='settle_confirm')
    elif screen == '货币战争-位面过渡':
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
    elif screen == '货币战争-BOSS简报':
        b._handle_click_source('货币战争-BOSS简报', '区域-空白点击')
    elif screen == '货币战争-遭遇节点':
        _encounter_pick_feed(gs)
    elif screen == '货币战争-盛会之星':
        out = report_action_pick_megastar_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-银狼升星':
        out = report_action_pick_planner_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_PREP:
        _start_battle_feed(gs)
    else:
        raise AssertionError(f'未知呈现屏 {screen}')


def test_boss_briefing_click_resolves_battle() -> None:
    """boss 节点:BOSS 简报呈现于节点窗;点空白(点击源)→ coarse 结算
    → 结算页;settle_confirm 推进(位面末 → 位面过渡)。
    seed 61 = 走完通道锚(局终于 P2,必经 P1r9 boss 窗)。"""
    b = _backend(61)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        for _ in range(64):
            if b.done or b.screen_identity() == '货币战争-BOSS简报':
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
            else:
                _drive_step(b, 61)
        assert b.screen_identity() == '货币战争-BOSS简报'
        b._handle_click_source('货币战争-BOSS简报', '区域-空白点击')
        assert b.screen_identity() == SCREEN_SETTLE
        _node_advance_feed(b.gs, trigger='settle_confirm')
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (2, 1)
        assert b.screen_identity() == '货币战争-位面过渡', 'P2 首轮位面过渡'
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        assert b.screen_identity() == SCREEN_PREP
    finally:
        uninstall_backend()


def test_node_window_overlay_detour_reruns_offer_check() -> None:
    """overlay 让路恢复序:offer 槽节点窗起点 overlay 在场 → 呈现压住
    节点屏,选定后复走 offer 检查呈现策略选卡屏(让路不吞 offer 槽),
    选卡落地直出节点屏;窗口前段(轮首收入)不因让路重入。权威序 =
    旧引擎实测收尾检查序(overlay → offer → 下一节点)+ U07 固定日程
    (P1r3/P2r2/P3r2)生效于本节点备战窗口前。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_planner_param,
    )
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        # P1r1(奖励)→ P1r2(战斗)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 2)
        # P1r3(U07 offer 槽)窗口起点 overlay 在场 = 让路前提
        # (呈现数据源 = 容器登记,队列直推退役)
        register_screen_change(
            gs, 'planner', '货币战争-银狼升星', source='test')
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert gs.node.value.round_num == 3
        assert b.screen_identity() == '货币战争-银狼升星', \
            '窗起点 overlay 先呈现(压住节点屏)'
        gold_at_detour = gs.gold.value
        planner_out = report_action_pick_planner_param(
            gs, SimpleNamespace(), _SIG)
        assert planner_out.applied
        cw_sim_ports.declare_world(planner_out.world_decl)
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY, \
            '让路结束复走 offer 检查(U07 P1r3 槽不被跳过)'
        assert gs.gold.value == gold_at_detour, '窗口前段不因让路重入'
        assert gs.invest_strategy_opts.value, 'offer 候选写容器槽'
        gs.write_logic(gs.invest_strategy_opts,
                       ['加油站', '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        invest_out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='加油站'), _SIG,
            session=SimpleNamespace())
        assert invest_out.applied
        cw_sim_ports.declare_world(invest_out.world_decl)
        assert b.screen_identity() == SCREEN_PREP, 'offer 选定 → 节点屏'
    finally:
        uninstall_backend()


# ============================================================ 选卡腿获得链

def test_contract_env_pick_sends_cards_to_bench() -> None:
    """获得链断言(验收判据):选契约环境(公司契约)送卡入席——
    翡翠/砂金经 gain_character 落备战席,效果走 kernel 获得链单一源。"""
    b = SimBackend(seed=7, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        b.gs.write_logic(b.gs.invest_env_opts,
                         ['公司契约', '轮岗', '头彩'],
                         produced_by='Test', evidence='t:opts', sig=_SIG)
        env_out = report_action_pick_invest_env_param(
            b.gs, SimpleNamespace(idx=0), _SIG)
        assert env_out.applied
        cw_sim_ports.declare_world(env_out.world_decl)
        chars = {s.unit.char_id for s in b.gs.bench.value.slots
                 if s is not None and s.kind == 'unit' and s.unit is not None}
        assert {'翡翠', '砂金'} <= chars, '契约送卡入席'
        assert b.gs.active_env.value == '公司契约'
    finally:
        uninstall_backend()


def test_scheduled_env_gift_discharged_at_plane2_first_window() -> None:
    """定时环境发放 sim 收口:选特权阶级 → 队列登记 (2,1) 发放项(登记
    不落席);(1,x) 各节点窗开启与位面过渡屏呈现期队列原样(未到点不
    消费);位面过渡点空白收口(2-1 节点窗打开)→ 特权武装箱落备战席
    (supply_box 槽件)+ 队列回写空。时机语义:「第二位面开始时」=
    位面过渡屏被点掉、2-1 节点窗打开时,发放收口与窗口幂等守卫同段
    (seed 61 通道沿 boss 简报用例:局必经 P1r9 与位面过渡)。"""
    b = SimBackend(seed=61, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        gs = b.gs
        gs.write_logic(gs.invest_env_opts,
                       ['特权阶级', '轮岗', '头彩'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        env_out = report_action_pick_invest_env_param(
            gs, SimpleNamespace(idx=0), _SIG)
        assert env_out.applied
        assert gs.active_env.value == '特权阶级'
        cw_sim_ports.declare_world(env_out.world_decl)
        queued = [{'env': '特权阶级', 'plane': 2, 'round_num': 1,
                   'item': '特权武装箱'}]
        assert gs.pending_item_grants.value == queued, '定时支登记入队'
        b._maybe_finish_wait()
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 1)
        assert gs.pending_item_grants.value == queued, \
            '(1,1) 节点窗开启不消费(未到点)'
        # 先行推进一节点:(1,2) 窗口收口对未到点队列零写
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 2)
        assert gs.pending_item_grants.value == queued, '(1,2) 窗口队列原样'
        # 推进至 P1r9 BOSS 简报 → 结算 → (2,1) 位面过渡
        for _ in range(64):
            if b.done or b.screen_identity() == '货币战争-BOSS简报':
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(gs, trigger='settle_confirm')
            else:
                _drive_step(b, 61)
        assert b.screen_identity() == '货币战争-BOSS简报'
        b._handle_click_source('货币战争-BOSS简报', '区域-空白点击')
        assert b.screen_identity() == SCREEN_SETTLE
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (2, 1)
        assert b.screen_identity() == '货币战争-位面过渡'
        assert gs.pending_item_grants.value == queued, \
            '位面过渡屏呈现时队列未消费(发放收口在点空白后的节点窗)'
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        assert b.screen_identity() == SCREEN_PREP
        assert gs.pending_item_grants.value == [], '到点发放队列回写空'
        boxes = [s for s in gs.bench.value.slots
                 if s is not None and s.kind == 'supply_box']
        assert len(boxes) == 1, '特权武装箱落备战席(supply_box 槽件)'
    finally:
        uninstall_backend()


def test_strategy_pick_chain_burst_gold() -> None:
    """获得链断言:选 burst 策略卡(加油站)→ 免费刷新发放生效
    (effect burst 桥,容器零私持);即时金通道现役无写端不发生
    (kernel ``apply_effect_burst_grant`` 只载 free_refresh_burst),
    断言面只锁免费刷新发放。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        free_before = gs.free_refresh_left.value or 0
        gs.write_logic(gs.invest_strategy_opts,
                       ['加油站', '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='加油站'), _SIG,
            session=SimpleNamespace())
        assert out.applied
        assert (gs.free_refresh_left.value or 0) == free_before + 1, \
            'burst 免费刷新发放(effect burst 桥)'
        assert '加油站' in gs.active_strategies.value
    finally:
        uninstall_backend()


def test_strategy_pick_chain_board_rewrite() -> None:
    """获得链断言:选板面重写卡(人力重组)→ 前台/后台/备战席清空 +
    卖价退款入金(确定性分支逻辑写,apply_board_rewrite 桥)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        gs.observe(gs.deployed, _dvs([Unit(char_id='淘金客', star=1)], []),
                   sig=_SIG_OBS)
        gs.write_logic(gs.invest_strategy_opts,
                       ['人力重组', '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='人力重组'), _SIG,
            session=SimpleNamespace())
        assert out.applied
        _f, _b = deployed_rows_of_view(gs.deployed.value)
        assert (_f, _b) == ([], []), '场清空(板面重写)'
        assert gs.gold.value > 0, '卖价退款入金(>0 = 清空前有单位)'
    finally:
        uninstall_backend()


def test_strategy_pick_chain_hacker_part_grant() -> None:
    """获得链断言:选骇客改件卡(骇客专家:银狼)→ 银狼入席 + 随机
    改件入栏(采样效果子链;rng 注入流键,sim 采样即世界真值)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        gs.write_logic(gs.invest_strategy_opts,
                       ['骇客专家:银狼', '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='骇客专家:银狼'), _SIG,
            rng=stream_rng(7, 'M11/pick/part'))
        assert out.applied
        chars = {s.unit.char_id for s in gs.bench.value.slots
                 if s is not None and s.kind == 'unit' and s.unit is not None}
        assert '银狼' in chars, 'bench 腿(确定性)'
        assert gs.equips.value, '改件腿(采样)入栏'
    finally:
        uninstall_backend()


def test_strategy_pick_chain_box_grant_immediate() -> None:
    """获得链断言:选进阶武装箱腿策略卡(三卡 offer 一次注入、pick
    战术义眼++)→ 进阶武装箱获得时点立即落备战席(supply_box 槽件;
    仅选中卡效果体分派——另两卡若误分派席上会多出箱,恰 1 = 唯一分派
    证据)+ pending_item_grants 不受扰(直发不经定时队列,与特权阶级
    「登记入队、到点发放」形态相斥)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs

        def _box_count() -> int:
            return sum(1 for s in gs.bench.value.slots
                       if s is not None and s.kind == 'supply_box')

        assert _box_count() == 0, '开局备战无箱(发放前基线)'
        gs.write_logic(gs.invest_strategy_opts,
                       ['战术义眼++', '保守派', '快请专家·彩'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='战术义眼++'), _SIG,
            session=SimpleNamespace())
        assert out.applied
        assert '战术义眼++' in gs.active_strategies.value
        assert _box_count() == 1, '选中卡箱腿立即落备战席(supply_box 槽件)'
        assert gs.pending_item_grants.value == [], \
            '获得时点直发,不进入定时队列'
    finally:
        uninstall_backend()


# ============================================================ 节点事件面

def _count_ore_rolls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """collect_ore 兜底掷计数(透传真实现零行为变化;命中路径断言口)。"""
    import sr_od.application.currency_war.kernel.cw_action_report.collect_ore as collect_ore_mod
    calls = [0]
    real = collect_ore_mod.roll_ore_reward

    def counting(rng, level):
        calls[0] += 1
        return real(rng, level)

    monkeypatch.setattr(collect_ore_mod, 'roll_ore_reward', counting)
    return calls


def test_reward_node_ore_substate_and_collect_via_report(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """奖励节点 = 备战档晶矿子态:面板写容器 spheres(U23 锚 8 晶矿)经
    挂接入口**生成即附着**(同批一次写);点晶矿走 kernel 上报按附着值
    兑现——命中零掷骰(掷骰已前移生成侧),金入账 = 附着金精确合计
    (采样即世界真值)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        assert b.screen_identity() == SCREEN_PREP
        assert b._sub == 'ore', '晶矿子态'
        points = gs.spheres.value.points
        assert len(points) == 8, 'U23 单例锚'
        rewards = dict(gs.ore_rewards.value or {})
        assert len(rewards) == 8, '面板矿全部生成附着(无缺项 → 不走兜底)'
        expected_gold = sum(r.gold for r in rewards.values())
        rolls = _count_ore_rolls(monkeypatch)
        gold_before = gs.gold.value
        out = report_action_collect_ore_param(
            gs, CwActionCollectOreParam(points=[(p[1], p[2]) for p in points]),
            _SIG)
        assert out.applied
        assert rolls[0] == 0, '命中路径零掷骰(兜底掷 = 挂接入口不变量破坏)'
        assert gs.spheres.value.count == 0, '逐点摘除'
        assert gs.gold.value == gold_before + expected_gold, \
            '按附着值精确入账(含声明/采样金合计)'
    finally:
        uninstall_backend()


# ============================================================ 3.3 声明矿 sim 接线锁
# (迭代 2026-10-10-ore-reward-attach 3.3;详设 details/ore-sim-plane-start.md
#  §1-§5:节点窗起点分道入队 + 过期清理接线 / 位面开局矿呈现与面板矿
#  同批合并 / spheres 写端统一过挂接入口 / rng 键装配 / 占位退役与披露。)

_ORE_ENV = '增发货币'


def _ore_env_backend(seed: int = 61) -> SimBackend:
    """开局选增发货币环境的装配后端(调用方负责 uninstall)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_ORE_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def _record_logic_writes(gs: GameState,
                         monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand 记录 (通道, 字段, evidence) 写序
    (透传真实现零行为变化;入队先于生成 / 过期留痕的断言口)。"""
    calls: list[tuple] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((channel, gs._field_name(target), evidence))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    return calls


def test_ore_env_plane1_declare_instead_of_direct_gold(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """增发货币 P1(详设 §1/§2):位面开局金不再直发(gold = 开局 +
    轮首收入,直发形态 = 13)→ 声明入队在呈现时消费(pending → done)→
    位面开局声明矿与面板锚点矿**同批合并**一次 spheres 写(第 9 点
    (90,10) 面板序续接,坐标无撞键;声明 6 金归属由生成 rng 掷,采样金
    1..5 与 6 唯一可辨)→ 入队写先于同帧生成写(承载性次序)→ 点击
    全部矿按附着值精确入账(含 6)。"""
    b = _ore_env_backend(61)
    try:
        calls = _record_logic_writes(b.gs, monkeypatch)
        b._maybe_finish_wait()
        gs = b.gs
        assert b.screen_identity() == SCREEN_PREP and b._sub == 'ore'
        assert gs.gold.value == 7, \
            '位面开局金不再直发(开局 3 + P1r1 轮首收入 4)'
        assert gs.ore_declared_pending.value == (), '声明在呈现时消费'
        assert gs.ore_declared_done.value == ((_ORE_ENV, 1),)
        pts = gs.spheres.value.points
        assert len(pts) == 9 and pts[-1] == ('金', 90, 10, 10), \
            '8 面板矿 + 1 声明矿(面板序续接第 9 点,r=10 与面板同)'
        assert len({(p[1], p[2]) for p in pts}) == 9, '同批坐标无撞键'
        rewards = dict(gs.ore_rewards.value or {})
        assert len(rewards) == 9, '同批合并一次写:全部现役身份已附着'
        declared = [k for k, v in rewards.items()
                    if v.kind == 'gold' and v.gold == 6]
        assert len(declared) == 1, \
            '声明 6 金恰占一席(采样金区间 1..5,值域唯一可辨)'
        seq = [(c, n) for c, n, _e in calls]
        assert seq.index(('logic', 'ore_declared_pending')) \
            < seq.index(('rand', 'ore_rewards')), \
            '声明入队写先于挂接生成写(接反则声明永不附着)'
        assert [e for c, n, e in calls
                if c == 'rand' and n == 'ore_rewards'] == ['ore_gen#p1+9'], \
            f'同批恰一次生成写: {calls}'
        assert b.disclosures.get(ORE_PLANE_START_PENDING) is not None, \
            '位面开局矿呈现面披露键在册(实机首遇校)'
        # 入队电平幂等:绕过窗口守卫直查(窗口重放守卫外的第二道保险)
        b._apply_env_plane_start(1)
        assert gs.ore_declared_pending.value == () \
            and gs.ore_declared_done.value == ((_ORE_ENV, 1),), \
            'done 守卫跨查不重发'
        expected = sum(v.gold for v in rewards.values())
        gold_before = gs.gold.value
        out = report_action_collect_ore_param(
            gs, CwActionCollectOreParam(points=[(p[1], p[2]) for p in pts]),
            _SIG)
        assert out.applied
        assert gs.gold.value == gold_before + expected, \
            '点击入账 = 附着金合计(含声明 6)'
    finally:
        uninstall_backend()


def test_ore_env_generation_deterministic_same_seed() -> None:
    """掷序确定性(详设 §4):同 seed 同调用序 → 声明矿附着逐位一致
    (rng 键 'ore_reward_gen' 随 action_sampling_rng 首调自动生效,装配方
    零改动;键序确定性责任在调用序,先例 = 现动作腿键)。"""
    rewards = []
    for _ in range(2):
        b = _ore_env_backend(61)
        try:
            b._maybe_finish_wait()
            rewards.append(dict(b.gs.ore_rewards.value or {}))
        finally:
            uninstall_backend()
    assert rewards[0] and rewards[0] == rewards[1], \
        '同 seed 双跑声明矿附着必须逐位一致'


def test_non_ore_env_keeps_direct_plane_gold_channel(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """直发金通道留置(详设 §1 关键取舍:ENV_ORE_GRANTS 命中即绕行,
    通道为非矿形态位面开局金预留):env ∉ 注册表 ∧ gold_per_plane_start
    非空 → 保留直发(现无此形态环境,以注册表清空构造分道前提)。"""
    import sr_od.application.currency_war.sim.cw_sim_backend as backend_mod
    monkeypatch.setattr(backend_mod, 'ENV_ORE_GRANTS', {})
    b = _ore_env_backend(61)
    try:
        b._maybe_finish_wait()
        gs = b.gs
        assert gs.gold.value == 13, \
            '直发腿生效(开局 3 + 轮首收入 4 + 位面开局金 6)'
        assert gs.ore_declared_pending.value == () \
            and gs.ore_declared_done.value == (), '零声明域写'
        assert len(gs.spheres.value.points) == 8, '无声明矿点(纯面板)'
        assert gs.ore_rewards.value is not None \
            and len(gs.ore_rewards.value) == 8, '面板矿照常生成附着'
    finally:
        uninstall_backend()


def test_battle_prep_empty_spheres_write_cleans_stale_identities() -> None:
    """空读照写清理(详设 §3):普通 battle 备战呈现 spheres 空读照写
    count=0 亦过挂接入口——上节点残留矿身份(未点击面板)在此清理;同
    坐标面板重呈现 = 配对命中继承旧附着零重掷(跨面板别名,sim 侧经济
    中性,ore-reward-channel §4 披露角)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        attached = dict(gs.ore_rewards.value or {})
        assert len(attached) == 8, 'P1r1 面板 8 矿附着(不点击)'
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 2)
        assert b.screen_identity() == SCREEN_PREP and b._sub == 'ore'
        assert gs.ore_rewards.value == attached, \
            'P1r2 同坐标面板重呈现:配对命中继承(零重掷零清洗)'
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 3)
        # P1r3 = U07 offer 槽(固定日程生效于本节点备战窗口前):选卡后
        # 直出节点屏
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=gs.invest_strategy_opts.value[0]),
            _SIG, session=SimpleNamespace())
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
        assert b.screen_identity() == SCREEN_PREP and b._sub == '', \
            '战斗节点无面板无声明 → 常规备战子态'
        assert gs.spheres.value.count == 0, '空读照写 count=0'
        assert gs.ore_rewards.value == {}, '上节点残留矿身份清理'
    finally:
        uninstall_backend()


def test_ore_env_plane2_declared_ore_and_expiry_cleanup(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """增发货币 P2(详设 §1/§2):位面过渡窗口起点声明入队(8 金档)+
    过期清理留痕(done p1 条目移除,evidence ``ore_declared_expired#p1``);
    P2 首节点为战斗节点 → 声明矿点单独呈现(面板序续接首点 (10,10),
    子态 PREP_SUB_ORE),点击入账 8(sim 辖域 P1+P2;12 由 3.1 单测覆盖,
    位面 3 不可达)。"""
    b = _ore_env_backend(61)
    try:
        gs = b.gs
        b._maybe_finish_wait()
        # 走到 P1r9 BOSS 简报 → 结算 → (2,1) 位面过渡(seed 61 通道沿
        # boss 简报用例:局必经 P1r9 与位面过渡)
        for _ in range(64):
            if b.done or b.screen_identity() == SCREEN_BOSS_BRIEFING:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(gs, trigger='settle_confirm')
            else:
                _drive_step(b, 61)
        assert b.screen_identity() == SCREEN_BOSS_BRIEFING
        b._handle_click_source(SCREEN_BOSS_BRIEFING, '区域-空白点击')
        _node_advance_feed(gs, trigger='settle_confirm')
        assert b.screen_identity() == '货币战争-位面过渡'
        # 测试侧整理(真策略同构行为:部署腾席 + 奖励面板点击收口):
        # 备战单位移上板 + 清掉未点击面板残留。不清则残留 (10,10)/(20,10)
        # 与声明点跨面板别名继承 → 声明饿死(该角为 ore-reward-channel
        # §4 在册披露,非本测锁面)。
        units = [s.unit for s in gs.bench.value.slots
                 if s is not None and s.kind == 'unit' and s.unit is not None]
        gs.observe(gs.deployed, _dvs(units[:4], units[4:]), sig=_SIG_OBS)
        gs.observe(gs.bench, BenchView(
            slots=[BenchSlot(kind='empty')] * 9, capacity=9), sig=_SIG_OBS)
        leftover = gs.spheres.value.points
        out = report_action_collect_ore_param(
            gs, CwActionCollectOreParam(
                points=[(p[1], p[2]) for p in leftover]), _SIG)
        assert out.applied and gs.spheres.value.count == 0 \
            and gs.ore_rewards.value == {}, '残留面板清理(腾席后全开)'
        calls = _record_logic_writes(gs, monkeypatch)
        # 位面过渡点空白 → (2,1) 节点窗(声明入队 + 过期清理 + 呈现)
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        assert b.screen_identity() == SCREEN_PREP and b._sub == 'ore', \
            '战斗节点备战档呈现声明矿(面板在场语义复用 PREP_SUB_ORE)'
        assert gs.spheres.value.points == (('金', 10, 10, 10),), \
            'P2 首节点(战斗)声明矿单独呈现(面板序续接首点)'
        assert gs.ore_declared_pending.value == (), '呈现消费(出队即消费)'
        assert gs.ore_declared_done.value == ((_ORE_ENV, 2),)
        assert gs.ore_rewards.value == {
            '10,10': OreReward(kind='gold', gold=8)}, '声明 8 金附着'
        expiry = [e for _c, _n, e in calls
                  if e is not None and e.startswith('ore_declared_expired')]
        assert expiry == ['ore_declared_expired#p1'], \
            f'位面过渡过期清理留痕(p1 done 条目): {calls}'
        gold_before = gs.gold.value
        out = report_action_collect_ore_param(
            gs, CwActionCollectOreParam(points=[(10, 10)]), _SIG)
        assert out.applied
        assert gs.gold.value == gold_before + 8, '点击声明矿入账 8(位面 2 档)'
        assert gs.ore_rewards.value == {} and gs.spheres.value.count == 0
    finally:
        uninstall_backend()


def test_supply_node_window_refresh_and_pick() -> None:
    """补给节点窗:呈现补给屏(3 选项写容器 + 免费刷新 left=1);刷新
    = 点击源(left 递减 + 选项重掷);pick_supply 走获得链,带钻选项给
    宝钻(世界事实写 diamond_count)。"""
    b = _backend(1013)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        while b.gs.node.value.round_num < 5:
            _start_battle_feed(b.gs)
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
        assert b.screen_identity() == SCREEN_SUPPLY
        assert b.gs.supply_refresh_left.value == 1, '节点入口初始 left=1'
        opts_before = [o.equip for o in b.gs.supply.value.options]
        b._handle_click_source(SCREEN_SUPPLY, '文本-剩余次数')
        assert b.gs.supply_refresh_left.value == 0, '刷新 left−1'
        opts_after = [o.equip for o in b.gs.supply.value.options]
        assert opts_after != opts_before, '选项重掷'
        diamond = any(o.has_diamond for o in b.gs.supply.value.options)
        pick = b.gs.supply.value.options[0]
        b.gs.write_logic(b.gs.chosen_supply, ('', pick.equip, pick.has_diamond),
                         produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            b.gs, SimpleNamespace(idx=0, char_name='', norm_item=pick.equip),
            _SIG)
        assert out.applied
        assert pick.equip in b.gs.equips.value, '装备腿入栏'
        cw_sim_ports.declare_world(out.world_decl)
        _node_advance_feed(b.gs, trigger='supply_confirm')
        assert b.gs.diamond_count.value == (1 if diamond else 0)
    finally:
        uninstall_backend()


def test_box_open_pick_grant_via_gain_chain() -> None:
    """开箱动作落地 → 武装箱画面(候选写容器);装备卡点击记录 + 选定
    落地 → 选中装备经获得链入栏;模态交回备战。上报 + 声明喂入单轨
    (open_box / pick_box_card 两腿,动作 op 同形)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        open_out = report_action_open_box_param(
            b.gs, CwActionOpenBoxParam(), _SIG)
        cw_sim_ports.declare_world(open_out.world_decl)
        assert b.screen_identity() == SCREEN_BOX
        cands = b.gs.box_card_names.value
        assert cands is not None and len(cands) == 4
        b._handle_click_source(SCREEN_BOX, '装备卡-3')
        pick_out = report_action_pick_box_card_param(
            b.gs, SimpleNamespace(), _SIG)
        assert pick_out.applied
        cw_sim_ports.declare_world(pick_out.world_decl)
        assert cands[2] in b.gs.equips.value, '选中装备入栏(获得链)'
        assert b.screen_identity() == SCREEN_PREP, '模态交回'
    finally:
        uninstall_backend()


# ============================================================ overlay 触发层

def test_megastar_lazy_presentation_on_identity_query() -> None:
    """巨星呈现(3.5 终态):盛会之星资格集跨档(逻辑写 → 值回调判据
    register)→ 问询时点懒呈现;值等重写零回调不重复登记。
    阵容成员单一源 = data/cw_chars.py 注册表。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        # 呈现数据源 = 容器登记(逻辑写 → 值回调
        # 判据 register;观察写零回调),事实事件保留为呈现检查触发点。
        gs.write_logic(gs.deployed, _dvs([Unit(char_id='大丽花', star=1),
                                      Unit(char_id='加拉赫', star=1)], []),
                       produced_by='test', evidence='t',
                       sig=ChannelSig(family='logic_action', actor='test',
                                      mode='compute'))
        assert any(p.kind == 'megastar'
                   for p in gs.screen_changes.pending), '判据登记在册'
        # 3.5:呈现位 = screen_identity 问询时点懒呈现(事实事件槽退役)。
        assert b.screen_identity() == '货币战争-盛会之星', '跨首层模态呈现'
        assert gs.megastar_opts.value, '候选写容器槽'
        assert any(p.kind == 'megastar'
                   for p in gs.screen_changes.pending), \
            '呈现不清条目(消费归选卡上报)'
        consume_screen_change(gs, 'megastar')
        b._dismiss_modal()
        # 幂等:值等重写零回调(判据不重复登记)
        gs.write_logic(gs.deployed, gs.deployed.value,
                       produced_by='test', evidence='t',
                       sig=ChannelSig(family='logic_action', actor='test',
                                      mode='compute'))
        assert not gs.screen_changes.pending, '值等写零回调(无重复登记)'
    finally:
        uninstall_backend()


def test_planner_lazy_presentation_dedup_marker() -> None:
    """planner 呈现(3.5 终态):场上银狼逻辑写 1★→2★(值回调判据
    register)→ 问询时点懒呈现;同费用档簿记使二次升星不重复。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        slots: list[BenchSlot | None] = [None] * 9
        slots[0] = BenchSlot(kind='unit', unit=Unit(char_id='银狼LV.999',
                                                    star=1))
        gs.observe(gs.bench, cw4_bview(slots), sig=_SIG_OBS)
        gs.write_logic(gs.deployed, _dvs([Unit(char_id='银狼LV.999', star=1)], []),
                       produced_by='test', evidence='t',
                       sig=ChannelSig(family='logic_action', actor='test',
                                      mode='compute'))
        # kernel 合成产物落点 = 场上同名位:逻辑写升星(判据 = 值回调,
        # 观察写零回调)
        gs.write_logic(gs.deployed, _dvs([Unit(char_id='银狼LV.999', star=2)], []),
                       produced_by='test', evidence='t',
                       sig=ChannelSig(family='logic_action', actor='test',
                                      mode='compute'))
        assert any(p.kind == 'planner'
                   for p in gs.screen_changes.pending), '判据登记在册'
        # 3.5:呈现位 = screen_identity 问询时点懒呈现(事实事件槽退役)。
        assert b.screen_identity() == '货币战争-银狼升星'
        consume_screen_change(gs, 'planner')
        b._dismiss_modal()
        # 同费用档簿记:二次升星(值等重写零回调)不重复登记
        gs.write_logic(gs.deployed, gs.deployed.value,
                       produced_by='test', evidence='t',
                       sig=ChannelSig(family='logic_action', actor='test',
                                      mode='compute'))
        assert not gs.screen_changes.pending, '费用档已弹过(零重复登记)'
    finally:
        uninstall_backend()


# ============================================================ 局终

def test_full_walk_terminates_with_p3_disclosure() -> None:
    """P2 走完 → 局终(P3 进场即局终披露);局结果面自容器节点键读。"""
    b = _backend(61)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
            else:
                _drive_step(b, 61)
        assert b.done
        assert DISCLOSURE_P3_UNOBSERVED in b.result().unmodeled
        result = b.result()
        assert result.plane_reached == 2
        assert all(hp >= 0 for hp in result.hp_trail)
        assert len(result.hp_trail) >= 8, 'hp 轨迹覆盖两位面'
    finally:
        uninstall_backend()


# ============================================================ 装备腿(规则件缺口补 kernel)

def _advance_pair() -> tuple[str, str, str]:
    """取一对真配方(组件A, 组件B, 进阶产物)(注册表单一源取用)。"""
    advance, (a, b) = next(iter(CROSS_RECIPES.items()))
    return a, b, advance


def test_wear_report_synthesis_leg() -> None:
    """穿着即合成(世界规则,单一源 = kernel 穿装备上报):穿第二件
    基础件 → worn 内立即合成进阶件;owned 扣减;上限按合成后计。"""
    a, b, advance = _advance_pair()
    assert synthesize_target(a, b) == advance
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [None] * 9
    slots[0] = BenchSlot(kind='unit', unit=Unit(char_id='淘金客', star=1,
                                                equips=[a]))
    gs.observe(gs.bench, cw4_bview(slots), sig=_SIG_OBS)
    gs.observe(gs.equips, [b], sig=_SIG_OBS)
    action = CwActionWearEquipParam(item_name=b, char_name='淘金客',
                                    row='front', slot=1)
    out = report_action_wear_equip_param(gs, action, _SIG)
    assert out.applied
    worn = [list(s.unit.equips) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]
    assert worn == [[advance]], f'穿着即合成:{a}+{b} → {advance}'
    assert gs.equips.value == [], '库存件已穿上'
    # 拒绝形态:owned 无件 / 目标不在册 → applied=False 零写
    out_rej = report_action_wear_equip_param(
        gs, CwActionWearEquipParam(item_name=a, char_name='淘金客',
                                   row='front', slot=1), _SIG)
    assert not out_rej.applied and out_rej.reason == 'wear_item_not_owned'
    gs.observe(gs.equips, ['垃圾袋'], sig=_SIG_OBS)
    out_miss = report_action_wear_equip_param(
        gs, CwActionWearEquipParam(item_name='垃圾袋', char_name='不存在',
                                   row='front', slot=1), _SIG)
    assert not out_miss.applied
    assert out_miss.reason == 'wear_target_unit_missing'


# ============================================================ 经验账本(平移)

def test_xp_apply_amount_carry_and_level_cap() -> None:
    """升级结转与 xp_apply_clicks 单一源同式:攒满门槛即升级、溢出
    结转;cap = MAX_PLAYER_LEVEL 满级零推进(U18)。"""
    assert xp_apply_amount(3, 0, NODE_XP_BY_TYPE['battle']) == (3, 2)
    level, cur = xp_apply_amount(3, 3, 2)
    assert level == 4, '攒满门槛即升级'
    assert cur == 1, '溢出结转(3 + 2 − 升级所需 4 = 1)'
    assert xp_apply_amount(MAX_PLAYER_LEVEL, 0, 12) == (MAX_PLAYER_LEVEL, 0), \
        'lv10 满级零累计(U18 口径)'


def test_node_xp_table_matches_rules_doc() -> None:
    """节点基础经验表(依据 xp-rules.md):战斗/奖励/遭遇 +2、补给 +0、
    BOSS +12(U17 定稿口径);apply_node_xp 补给档零入账。"""
    assert NODE_XP_BY_TYPE == {
        'battle': 2, 'reward': 2, 'encounter': 2, 'supply': 0, 'boss': 12,
    }
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.level, 3, sig=_SIG_OBS)
    gs.observe(gs.xp, (0, 4), sig=_SIG_OBS)
    assert apply_node_xp(gs, node_type='supply') == 0, '补给 +0 显式档'
    assert apply_node_xp(gs, node_type='battle') == 2
    assert gs.xp.value == (2, 4)


def test_node_key_field_convergence() -> None:
    """字段收敛:容器 gs.node 为唯一节点账(无 plane/round_num 第二账);
    NodeKey.kind 与位面日程真值表一致。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        node = b.gs.node.value
        assert isinstance(node, NodeKey)
        assert node.kind == 'reward', 'P1r1 地面真值'
        assert not hasattr(b, 'plane') and not hasattr(b, 'round_num'), \
            '旧引擎双账字段不复活'
    finally:
        uninstall_backend()


# ============================================================ 3.4 联调机制锁

def test_node_window_front_section_idempotent_on_click_replay() -> None:
    """窗口前段幂等守卫(3.4 联调裁决①):同节点线性序的窗口收口二次
    进入(实机形态 = 位面过渡点空白点击重放)不双发轮首收入——收入是
    窗口前段唯一的真双账面(发牌覆盖同值无感)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        assert b.gs.node.value is not None
        gold = b.gs.gold.value
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        assert b.gs.gold.value == gold, '窗口前段收入被双发'
    finally:
        uninstall_backend()


def test_game_over_presents_lobby_terminal_screen() -> None:
    """局终终态呈现 = 大厅屏(死亡/第一期辖域尽头两源共用;3.4 联调
    接线):呈现即可达流程终局链(CwScreenBattleWait 终局锚 → 主循环
    3c 收口),与实机「终局 → 返回货币战争 → 大厅」消费链同形。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SCREEN_LOBBY,
    )
    b = _backend(7)
    try:
        b._game_over()
        assert b.done
        assert b.screen_identity() == SCREEN_LOBBY
    finally:
        uninstall_backend()


def test_expert_screen_presentation_raises_loud_on_observe() -> None:
    """SCREEN_EXPERT「呈现即响错」语义锁(3.4 联调裁决③):open_bookcard
    声明(纯转移)驱动专家邀请函屏呈现;该屏非金路径 13 档(实机触发
    条件零档,数据缺口族),observe 必 LookupError 具名响错——防未来把
    响错静默降级成注册屏/空产物(flow-seam §3 未注册屏响错锁的呈现态
    配对)。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SCREEN_EXPERT,
    )
    b = _backend(7)
    try:
        # 3.4:专家画面呈现由登记承载(open_bookcard 上报 register)——
        # 声明侧改底层屏后,advance 纯转移 + pending 呈现检查。
        register_screen_change(b.gs, 'expert_invite', SCREEN_EXPERT,
                               source='test')
        b.advance(WorldDecl(next_screen='货币战争-备战', trigger=''))
        assert b.screen_identity() == SCREEN_EXPERT
        with pytest.raises(LookupError, match='未注册'):
            b.observe(SCREEN_EXPERT)
    finally:
        uninstall_backend()


def test_unpresented_overlay_anchor_not_visible_on_prep() -> None:
    """visible area 级细化(3.4 联调):sim 不可呈现浮层的在场锚恒
    False(阿哈装备选择浮层检测锚;sim 不建模该浮层 = 世界真值)——
    画面档匹配语义会把它误答真,备战帧被浮层分支抢走。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        assert b.visible(SCREEN_PREP, '备战标识-购买经验'), '备战锚可见'
        assert not b.visible(SCREEN_PREP, '标识-简易装备'), \
            '不可呈现浮层锚必须不可见'
    finally:
        uninstall_backend()


# ============================================================ 3.3 环境条件发放 sim 接线锁
# (迭代 2026-10-10-env-conditional-grants landing 3.3;详设
#  details/env-conditional-grant.md §4/§5:结算腿触发检查接线于 streak
#  observe 之后 / 触发函数两写 sig 写死单形态 = logic_sig('sim:env') /
#  宝钻回调内构 obs 族 sig 三写 / 带钻补给零改动不采纳回调。)

_ENV_GRANT_ENV = '深井角斗场'
_ENV_GRANT_EQUIP = '财富宝钻'


def _forced_outcome(won: bool) -> BattleOutcome:
    """强制胜负结算输出(胜 hp_delta=0 零扣血;败 −23 保不致死)。"""
    return BattleOutcome(won=won, progress=1.0 if won else 0.0,
                         base_damage=None, progress_damage=None,
                         hp_delta=0 if won else -23, face=SIM_BATTLE_FACE)


def _force_settle(monkeypatch: pytest.MonkeyPatch, won: bool) -> None:
    """强制战斗胜负(patch 面 = 调用方模块命名空间绑定;定义模块
    patch 对 from-import 调用点不可见,规约见 CW skill sim-testing)。"""
    import sr_od.application.currency_war.sim.cw_sim_backend as backend_mod
    monkeypatch.setattr(backend_mod, 'settle_battle',
                        lambda rng, *, plane, round_num: _forced_outcome(won))


def _env_grant_backend(seed: int = 23) -> SimBackend:
    """开局选深井角斗场环境的装配后端(调用方负责 uninstall)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_ENV_GRANT_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def _record_all_writes(gs: GameState,
                       monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig) 写序(透传真实现零行为变化)。"""
    calls: list[tuple[str, str, str | None, ChannelSig]] = []

    def _wrap_logic(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((channel, gs._field_name(target), evidence, sig))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    def _wrap_obs(real):
        def rec(target, value, *, evidence=None, sig, note=''):
            calls.append(('obs', gs._field_name(target), evidence, sig))
            real(target, value, evidence=evidence, sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap_logic(gs.write_logic,
                                                       'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap_logic(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return calls


def _drive_env_grant_step(b: SimBackend) -> None:
    """深井局单步驱动(补给恒选无钻选项,保触发局 diamond_count 基线
    干净;带钻补给归专项用例;策略定卡加油站 = 零判读域写,断言与
    seed 采样解耦)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_megastar_param,
        report_action_pick_planner_param,
    )
    screen = b.screen_identity()
    gs = b.gs
    if screen == SCREEN_SETTLE:
        _node_advance_feed(gs, trigger='settle_confirm')
    elif screen == SCREEN_SUPPLY:
        opts = gs.supply.value.options
        pick = next(o for o in opts if not o.has_diamond)
        gs.write_logic(gs.chosen_supply,
                       ('', pick.equip, pick.has_diamond),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=opts.index(pick), char_name='',
                                norm_item=pick.equip), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        _node_advance_feed(gs, trigger='supply_confirm')
    elif screen == SCREEN_INVEST_STRATEGY:
        gs.write_logic(gs.invest_strategy_opts,
                       ['加油站', '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='加油站'), _SIG,
            session=SimpleNamespace())
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-遭遇节点':
        _encounter_pick_feed(gs)
    elif screen == SCREEN_BOSS_BRIEFING:
        b._handle_click_source(SCREEN_BOSS_BRIEFING, '区域-空白点击')
    elif screen == '货币战争-盛会之星':
        out = report_action_pick_megastar_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-银狼升星':
        out = report_action_pick_planner_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_PREP:
        _start_battle_feed(gs)
    else:
        raise AssertionError(f'未预期的呈现屏 {screen}')


def _drive_until(b: SimBackend, pred, limit: int = 200) -> None:
    """步进驱动至谓词成立(超限响错防死循环)。"""
    for _ in range(limit):
        if pred():
            return
        _drive_env_grant_step(b)
    raise AssertionError('驱动步数超限,谓词未达成')


def _grant_snapshot(gs: GameState) -> dict[str, object]:
    """触发局判读域快照(重放对拍共用)。"""
    return {
        'streak': gs.streak.value,
        'equips': list(gs.equips.value or []),
        'env_grants_done': gs.env_grants_done.value,
        'diamond_count': gs.diamond_count.value,
        'deploy_cap': gs.deploy_cap.value,
        'back_layout': gs.back_layout.value,
        'level': gs.level.value,
        'gold': gs.gold.value,
        'hp': gs.hp.value,
    }


def test_env_grant_fires_at_fifth_streak_with_diamond_callback(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """数值对照(landing 3.3):深井角斗场 sim 局 5 连胜达成结算 →
    装备在库(库尾追加)+ done 标记 + diamond_count +1 + deploy_cap
    = level+1 + back_layout +1(基线 6 → 7,min9 未触);同时锁写行
    形态:触发两写 sig 单形态 = logic_action 族 'sim:env',回调三写 =
    observe 渠道 obs 族 'sim:env-diamond'。"""
    b = _env_grant_backend()
    try:
        gs = b.gs
        calls = _record_all_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _drive_until(b, lambda: int(gs.streak.value or 0) >= 5)
        # P1 战斗类节点恰 5 个(r3/r4/r6/r7/r9):全胜 → 5 连胜达成于
        # r9 boss 结算腿,断言面即触发局现值
        assert int(gs.streak.value or 0) == 5
        assert gs.equips.value[-1] == _ENV_GRANT_EQUIP, '装备在库(库尾追加)'
        assert gs.env_grants_done.value == ((_ENV_GRANT_ENV,
                                             FIRST_STREAK_KEY),)
        assert gs.diamond_count.value == 1, 'diamond_count +1(回调)'
        assert gs.deploy_cap.value == int(gs.level.value) + 1, \
            'deploy_cap = level + 拥有财富宝钻数'
        assert gs.back_layout.value == 7, 'back_layout 基线 6 → +1'
        # 触发两写:随机态发放 + done 登记,同 sig 单形态(禁 obs 族)
        grant_rows = [c for c in calls
                      if c[2] is not None and c[2].startswith('env_grant#')]
        assert [(c[0], c[1]) for c in grant_rows] == [
            ('rand', 'equips'), ('logic', 'env_grants_done')]
        for c in grant_rows:
            assert c[3].family == 'logic_action' \
                and c[3].group_id == 'sim:env', f'触发 sig 单形态: {c}'
        # 回调三写:observe 渠道,内构 obs 族 sig(同组同窗)
        cb_rows = [c for c in calls
                   if c[0] == 'obs' and c[2] == 'env_diamond']
        assert [c[1] for c in cb_rows] == [
            'diamond_count', 'deploy_cap', 'back_layout']
        for c in cb_rows:
            assert c[3].family == 'obs' \
                and c[3].group_id == 'sim:env-diamond', f'回调 obs 族: {c}'
        assert gs.equips.source == 'logic_rand', '发放 = 随机态通道'
        assert gs.env_grants_done.source == 'logic', 'done = 登记直写'
        assert gs.diamond_count.source == 'observation', '回调 = 观察通道'
        assert gs.deploy_cap.source == 'observation'
        assert gs.back_layout.source == 'observation'
    finally:
        uninstall_backend()


def test_env_grant_same_seed_replay_identical(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """同 seed 重放一致(sim 确定性判据):同 seed 深井局全胜驱动两跑,
    判读域快照逐键一致(发放/回调在确定性链上,无双发无漂移)。"""
    snaps: list[dict[str, object]] = []
    for _ in range(2):
        b = _env_grant_backend()
        try:
            _force_settle(monkeypatch, won=True)
            _drive_until(b, lambda bb=b: int(bb.gs.streak.value or 0) >= 5)
            snaps.append(_grant_snapshot(b.gs))
        finally:
            uninstall_backend()
    assert snaps[0]['env_grants_done'] == ((_ENV_GRANT_ENV,
                                            FIRST_STREAK_KEY),), \
        '两跑均触发发放(非偶然单发)'
    assert snaps[0] == snaps[1], f'同 seed 重放漂移: {snaps}'


def test_supply_diamond_pick_keeps_zero_callback(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """supply 路径零行为变化(landing 3.3):深井角斗场在册环境下带钻
    补给选定 → 仅 diamond_count +1(_on_supply_picked 既有行为),
    deploy_cap/back_layout 零写、零发放——钻类型未建模,不采纳回调。"""
    b = _env_grant_backend()
    try:
        gs = b.gs
        _force_settle(monkeypatch, won=True)
        _drive_until(b, lambda: b.screen_identity() == SCREEN_SUPPLY)
        assert int(gs.streak.value or 0) == 2, 'r3/r4 两胜,补给轮前 <5'
        opts = gs.supply.value.options
        pick = next(o for o in opts if o.has_diamond)
        cap_before = gs.deploy_cap.value
        back_before = gs.back_layout.value
        gs.write_logic(gs.chosen_supply,
                       ('', pick.equip, pick.has_diamond),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=opts.index(pick), char_name='',
                                norm_item=pick.equip), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        assert gs.diamond_count.value == 1, '带钻补给聚合计数 +1(既有行为)'
        assert gs.deploy_cap.value == cap_before, '不采纳回调:cap 零写'
        assert gs.back_layout.value == back_before, \
            '不采纳回调:back_layout 零写'
        assert gs.env_grants_done.value == (), '连胜未达标,零发放'
        assert _ENV_GRANT_EQUIP not in gs.equips.value
    finally:
        uninstall_backend()


def test_env_grant_non_diamond_equip_skips_callback(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """宝钻裁决只认财富宝钻(接线层):登记表换发非宝钻装备 → 触发照常
    (发放 + done),回调三写零发生(回调内非财富宝钻早退,接线不预判)。"""
    import sr_od.application.currency_war.kernel.cw_env_grants as env_grants_mod
    monkeypatch.setattr(env_grants_mod, 'ENV_STREAK_GRANTS',
                        {_ENV_GRANT_ENV: (5, '永动机')})
    b = _env_grant_backend()
    try:
        gs = b.gs
        calls = _record_all_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _drive_until(b, lambda: int(gs.streak.value or 0) >= 5)
        assert '永动机' in gs.equips.value, '发放照常(库内追加)'
        assert gs.env_grants_done.value == ((_ENV_GRANT_ENV,
                                             FIRST_STREAK_KEY),)
        assert gs.diamond_count.value == 0, '非财富宝钻:回调早退零写'
        assert gs.deploy_cap.value == 3 and gs.back_layout.value == 6, \
            '三域零写(开局值不动)'
        assert not [c for c in calls if c[2] == 'env_diamond'], \
            '回调三写零发生'
    finally:
        uninstall_backend()


def test_env_grant_check_receives_signed_streak_loss_no_grant(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """败向口径:结算腿以带符号 streak 调触发检查(败 −1 传入,kernel
    ≤0 短路)→ 零发放零回调;调用边界 sig = logic_action 'sim:env'
    单形态。"""
    b = _env_grant_backend()
    try:
        gs = b.gs
        import sr_od.application.currency_war.sim.cw_sim_backend as backend_mod
        real_check = backend_mod.check_env_streak_grants
        seen: list[tuple[int, ChannelSig]] = []

        def _rec_check(gs_, streak_after, sig):
            seen.append((streak_after, sig))
            return real_check(gs_, streak_after, sig)

        monkeypatch.setattr(backend_mod, 'check_env_streak_grants',
                            _rec_check)
        calls = _record_all_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _drive_until(b, lambda: int(gs.streak.value or 0) < 0)
        assert seen, '触发检查在结算腿被调用'
        last_streak, last_sig = seen[-1]
        assert last_streak == -1, '带符号口径(败向 −1 传入)'
        assert last_sig.family == 'logic_action' \
            and last_sig.group_id == 'sim:env', '调用边界 sig 单形态'
        assert not [c for c in calls
                    if c[2] is not None and c[2].startswith('env_grant#')], \
            '败向零发放写'
        assert gs.env_grants_done.value == ()
        assert _ENV_GRANT_EQUIP not in gs.equips.value
        assert gs.diamond_count.value == 0
    finally:
        uninstall_backend()


# ============================================================ 3.4 扑满结算统一公式接线锁
# (T-6 经济过热,2026-10-10 用户裁定:战斗结算收入 = 统一公式「基础+息
#  +连胜成分,战败无」;扑满胜负接入连胜账 = 胜+1/败清零;收入递延至
#  结算腿落账,基数 = 窗口开快照即轮初口径。)

_PIGGY_ENV = '经济过热'


def _piggy_backend(seed: int = 31) -> SimBackend:
    """开局选经济过热环境的装配后端(调用方负责 uninstall)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_PIGGY_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def _reward_expect(gold_at_window: int, base: int, streak_in: int,
                   won: bool) -> int:
    """统一公式期望收入(缺省修饰):基础+息恒有;连胜成分 = 进轮
    streak_gold(缺省倍率 1),战败无(lost_round 形)。"""
    from sr_od.application.currency_war.kernel.cw_economy import streak_gold
    streak_part = streak_gold(streak_in) if won else 0
    return base + min(gold_at_window // 10, 5) + streak_part


def test_piggy_win_income_deferred_and_streak_counts(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """扑满胜局:备战帧(开战前)金不含本节点收入(递延锁);结算腿一次
    落账 = 基础+进轮连胜金+息;连胜账 0→1→2(胜局计数,用户裁定)。"""
    from sr_od.application.currency_war.kernel.cw_economy import \
        REWARD_BASE_GOLD_BY_ROUND
    b = _piggy_backend()
    try:
        gs = b.gs
        assert b.screen_identity() == SCREEN_PREP
        _force_settle(monkeypatch, won=True)
        # r1 备战:递延生效,金 = 初始值;连胜 0
        gold0 = int(gs.gold.value or 0)
        assert int(gs.streak.value or 0) == 0
        _start_battle_feed(gs)
        expect1 = gold0 + _reward_expect(gold0, REWARD_BASE_GOLD_BY_ROUND[1],
                                         0, won=True)
        assert int(gs.gold.value or 0) == expect1, 'r1 收入 = 基础+连胜+息'
        assert int(gs.streak.value or 0) == 1, '扑满胜局 +1'
        # r2 备战:r2 收入同样递延(金停在 r1 落账值)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert b.screen_identity() == SCREEN_PREP
        assert int(gs.gold.value or 0) == expect1, 'r2 收入未提前落账'
        _start_battle_feed(gs)
        expect2 = expect1 + _reward_expect(expect1,
                                           REWARD_BASE_GOLD_BY_ROUND[2],
                                           1, won=True)
        assert int(gs.gold.value or 0) == expect2
        assert int(gs.streak.value or 0) == 2, '连胜 1→2'
    finally:
        uninstall_backend()


def test_piggy_loss_base_interest_only_and_streak_reset(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """扑满败局(统一公式败局形):收入 = 基础+息(无连胜成分);连胜账
    1→0(清零,非负账);不掉血豁免照常(hp 不动)。"""
    from sr_od.application.currency_war.kernel.cw_economy import \
        REWARD_BASE_GOLD_BY_ROUND
    b = _piggy_backend()
    try:
        gs = b.gs
        assert b.screen_identity() == SCREEN_PREP
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        gold1 = int(gs.gold.value or 0)
        assert int(gs.streak.value or 0) == 1
        hp_before = int(gs.hp.value or 0)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert b.screen_identity() == SCREEN_PREP
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert int(gs.gold.value or 0) == gold1 + _reward_expect(
            gold1, REWARD_BASE_GOLD_BY_ROUND[2], 1, won=False), \
            'r2 败局收入 = 基础+息(无连胜成分)'
        assert int(gs.streak.value or 0) == 0, '扑满败局清零'
        assert int(gs.hp.value or 0) == hp_before, '扑满不掉血'
    finally:
        uninstall_backend()


def test_non_piggy_reward_income_still_window_open(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """非扑满对照:常态奖励轮收入仍在窗口开落账(备战帧金已含收入),
    递延仅扑满域(常态行为零变化)。"""
    from sr_od.application.currency_war.kernel.cw_economy import \
        REWARD_BASE_GOLD_BY_ROUND
    b = SimBackend(seed=33, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    try:
        gs = b.gs
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        gold0 = int(gs.gold.value or 0)
        gs.write_logic(gs.invest_env_opts,
                       ['轮岗', '头彩', _PIGGY_ENV],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_env_param(
            gs, SimpleNamespace(idx=0), _SIG)
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
        assert b.screen_identity() == SCREEN_PREP
        assert int(gs.gold.value or 0) == gold0 + _reward_expect(
            gold0, REWARD_BASE_GOLD_BY_ROUND[1], 0, won=True), \
            '窗口开已落账(备战金已含收入)'
    finally:
        uninstall_backend()
