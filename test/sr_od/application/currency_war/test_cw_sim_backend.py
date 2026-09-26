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

设计依据 = sim 统一迭代 design.md §2 + details/sim-backend.md(迭代内
合法引用;正本更新义务归末阶段)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_overlay_register import (
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

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
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    deployed_rows_of_view,
    report_node_advance,
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
        # (overlay-trigger 3.4:呈现数据源 = 容器登记,队列直推退役)
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

def test_reward_node_ore_substate_and_collect_via_report() -> None:
    """奖励节点 = 备战档晶矿子态:面板写容器 spheres(U23 锚 8 晶矿);
    点晶矿走 kernel 上报(流键 rng 注入,采样即世界真值)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        assert b.screen_identity() == SCREEN_PREP
        assert b._sub == 'ore', '晶矿子态'
        points = gs.spheres.value.points
        assert len(points) == 8, 'U23 单例锚'
        gold_before = gs.gold.value
        out = report_action_collect_ore_param(
            gs, CwActionCollectOreParam(points=[(p[1], p[2]) for p in points]),
            _SIG, rng=stream_rng(7, 'M1x/ore/1'))
        assert out.applied
        assert gs.spheres.value.count == 0, '逐点摘除'
        assert gs.gold.value > gold_before, '晶矿内容即时入账'
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

def test_megastar_evaluator_fires_on_faction_tier_cross() -> None:
    """巨星评估器:board_changed 事实事件消费盛会之星羁绊计数,跨层
    (tiers 首层 2)入队并模态呈现;重复事件不重复入队(逐层水位)。
    阵容成员单一源 = data/cw_chars.py 注册表;事件发射 = 真实写端形态
    (行域观察后 emit,与 deploy/buy/sell/wear 上报落地同形)。"""
    from sr_od.application.currency_war.kernel.cw_event_hooks import (
        emit_fact_event,
    )
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        # overlay-trigger 3.4:呈现数据源 = 容器登记(逻辑写 → 值回调
        # 判据 register;观察写零回调),事实事件保留为呈现检查触发点。
        gs.write_logic(gs.deployed, _dvs([Unit(char_id='大丽花', star=1),
                                      Unit(char_id='加拉赫', star=1)], []),
                       produced_by='test', evidence='t',
                       sig=ChannelSig(family='logic_action', actor='test',
                                      mode='compute'))
        assert any(p.kind == 'megastar'
                   for p in gs.screen_changes.pending), '判据登记在册'
        emit_fact_event('board_changed', {'actor': 'test'})
        assert b.screen_identity() == '货币战争-盛会之星', '跨首层模态呈现'
        assert gs.megastar_opts.value, '候选写容器槽'
        assert len(b.overlay_queue) == 1   # 评估器入队(3.5 退役清扫面)
        # 幂等:同层重复事实事件不再入队(水位不回退)
        emit_fact_event('board_changed', {'actor': 'test'})
        assert len(b.overlay_queue) == 1
    finally:
        uninstall_backend()


def test_planner_evaluator_fires_on_silver_wolf_two_star() -> None:
    """planner 呈现(overlay-trigger 3.4:数据源 = 容器登记):场上银狼
    逻辑写 1★→2★(值回调判据 register)→ star_up 事实事件呈现检查 →
    模态呈现;同费用档簿记使二次升星不重复。"""
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
        from sr_od.application.currency_war.kernel.cw_event_hooks import (
            emit_fact_event,
        )
        emit_fact_event('star_up', {'card': '银狼LV.999'})
        assert b.screen_identity() == '货币战争-银狼升星'
        assert b.planner_fired
        assert len(b.overlay_queue) == 1   # 评估器入队(3.5 退役清扫面)
        emit_fact_event('star_up', {'card': '银狼LV.999'})
        assert len(b.overlay_queue) == 1, '一次性标志去重(队列不重复入队)'
        assert b.screen_identity() == '货币战争-银狼升星'
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
