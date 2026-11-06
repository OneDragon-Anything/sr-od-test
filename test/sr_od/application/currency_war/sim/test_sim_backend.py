"""sim 游戏后端 SimBackend 回归测试(驱动反转迭代;世界本体 + 画面状态机
+ 观察生成 + 装配接缝 + 商店写回)。

测试面 = 迭代设计判据的可执行形态:
- 确定性:同 seed 同 RunConfig reset 双跑容器逐位一致(全采样由 seed 派生);
- 字段收敛:无第二账——节点键/连胜/相位载荷全部落容器;
- 初始序列(简报 → 环境 → wait_one_one → P1r1)与节点推进序列(收入/
  经验/环境金/发牌/offer 日程)平移语义零改;
- 转移声明重入幂等 + 选卡分支接获得链(契约送卡/burst 免费刷新/板面重写/
  骇客改件,对齐 cw_gain_chain 现役语义);
- 呈现流程(2026-10-29 流程模型对齐,单一源 =
  docs/game/currency_war/research/screen_flow_timing.md 口述流程模型节):
  节点窗起点 = 备战底层 + 节点弹窗模态(补给/遭遇/BOSS 简报),battle/
  reward 节点与节点弹窗关闭后自动弹店(1-1 例外不弹),关店回备战 =
  策略器主窗口;战斗统一由出战动作触发(supply 节点 = supply_finish
  完成节点,无战斗无结算屏,'supply_confirm' 随「确认即推节点」废止);
- 装备入账分支:穿着即合成住 kernel 穿装备上报(规则件缺口补 kernel,sim 与
  实机动作分支同构);
- 观察生成(sim 统一 3.3):金路径 13 档名注册表与清单零差零冗余,逐档
  生成器经 backend.observe 生产路径落容器;未注册屏 LookupError 具名
  响错(防静默失真);
- 装配接缝(flow-seam §1/§2):端口槽缺省关 + 单装配纪律;sim 模式
  CwOperation 三条分支(哨兵帧不触 controller/点击分支机械镜/find_area
  visible 应答);controller 桩触碰即炸;动作分支 rng 提供槽装卸复位;
- 商店牌面(2026-10-17 用户裁定):牌面 = 节点级持久事实(发牌时定),
  开店呈现写回/关店清呈现不清记录/节点切换新发牌覆盖。

设计依据 = sim- 后端结构(正本 = sim/sim-
合法引用;正本更新义务归末阶段)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.harness.sim_backend_runner import (
    MinimalSimBackend,
    SimControllerStub,
    sim_backend_fixture,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.data.cw_chars import (
    chars_by_cost,
    chars_by_faction,
)
from sr_od.application.currency_war.data.cw_synthesis import (
    CROSS_RECIPES,
    synthesize_target,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
    report_action_open_box_param,
    report_action_pick_box_card_param,
    report_action_pick_encounter_param,
    report_action_pick_invest_env_param,
    report_action_pick_invest_strategy_param,
    report_action_pick_megastar_param,
    report_action_pick_planner_param,
    report_action_pick_supply_param,
    report_action_refresh_invest_cards_param,
    report_action_refresh_shop_param,
    report_action_start_battle_param,
    report_action_wear_equip_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.close_shop import (
    report_action_close_shop_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.level_up import (
    report_action_level_up_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    MAX_PLAYER_LEVEL,
    xp_apply_amount,
)
from sr_od.application.currency_war.kernel.cw_env_grants import (
    BOSS_NODE_KEY_PREFIX,
    FIRST_STREAK_KEY,
    STAR_GRANT_KEY_PREFIX,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    ENV_REROLL_DECL,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    consume_defect_sink,
    deployed_rows_of_view,
    report_node_advance,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_GIFTS,
    ENV_REROLL_ASSUMPTION_POOL,
    ENV_REROLL_NAMES,
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
    equips_by_category,
    random_char_pool,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    PLANE_NODE_TABLES,
    resolve_plane_node_seqs,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    consume_screen_change,
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCloseShopParam,
    CwActionCollectOreParam,
    CwActionOpenBoxParam,
    CwActionRefreshShopParam,
    CwActionWearEquipParam,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.operations.cw_operation_base import (
    CwOperation,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    DISCLOSURE_RUN_COMPLETE,
    INVEST_OFFER_SCHEDULE,
    JOINT_DECISION_EXTRA_SLOT,
    NODE_XP_BY_TYPE,
    OFFER_CANDIDATES,
    ORE_PLANE_START_PENDING,
    SCREEN_BOSS_BRIEFING,
    SCREEN_BOX,
    SCREEN_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_ENV,
    SCREEN_INVEST_STRATEGY,
    SCREEN_MEGASTAR,
    SCREEN_PLANE_TRANSITION,
    SCREEN_PLANNER,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    apply_node_xp,
    install_backend,
    stream_rng,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_battle import (
    SIM_BATTLE_FACE,
    BattleOutcome,
)
from sr_od.application.currency_war.sim.cw_sim_enemy import (
    ENCOUNTER_TIER_BONUS,
    QUALITY_DIFFICULTY_BONUS,
)
from sr_od.application.currency_war.sim.cw_sim_obs_gen import (
    GOLDEN_PATH_SCREEN_NAMES,
    registered_screens,
)
from sr_od.application.currency_war.sim.cw_sim_ports import (
    install_sim_backend,
    sim_backend_installed,
    sim_or_live_observation,
    uninstall_sim_backend,
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
    out = report_action_pick_encounter_param(gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)


# ============================================================ 确定性

def test_reset_deterministic_double_run_container_identical() -> None:
    """确定性测试(验收判据):同 seed 同 RunConfig reset 双跑,容器逐位
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
    节点窗口(轮首收入/发牌)→ 备战呈现 + 自动弹店(1-1 例外外,#14);
    声明重放(同一 node_advance 声明重入)不二次推进(后端线性序守卫)。"""
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
        assert b.screen_identity() == SCREEN_SHOP, \
            '节点窗收尾自动弹店(备战过渡帧被弹店覆盖,稳态 = 开商店)'
        assert gs.shop.value is not None, '节点切换自动全刷'
        # 重入幂等:同一 node_advance 声明重放(无新 kernel 推进)→
        # 窗口不重入、收入不重发
        gold_before = gs.gold.value
        cw_sim_ports.declare_world(WorldDecl(next_screen=SCREEN_SHOP,
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
    18 动作全量单轨 = 上报 + 声明喂入,动作 op 同形)。

    2026-10-29 流程模型对齐:补给确认零推进(选完关模态回备战自动弹店,
    节点推进归出战动作 supply_finish);商店档(自动弹店态)走关店动作
    单轨回备战——策略器主窗口 = 关店后的可操作备战帧。"""
    screen = b.screen_identity()
    gs = b.gs
    if screen == SCREEN_SUPPLY:
        opts = gs.supply.value.options
        gs.write_logic(gs.chosen_supply,
                       ('', (opts[0].equip, *opts[0].extra_equips)),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=0, char_name='', norm_item=opts[0].equip),
            _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SHOP:
        _close_shop_feed(b)
    elif screen == SCREEN_INVEST_STRATEGY:
        opts = gs.invest_strategy_opts.value
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


def test_boss_briefing_click_returns_to_prep_with_auto_shop() -> None:
    """boss 节点:BOSS 简报呈现于节点窗(备战底层 + 模态);点空白(点击
    源)→ 关简报模态回备战并自动弹店(2026-10-29 流程模型对齐:不再直接
    结算,boss 战由出战动作触发);关店 → 出战(battle_resolve)→ 结算页
    → settle_confirm 推进(位面末 → 位面过渡);P2r1 窗收尾自动弹店
    (1-1 例外外)。seed 61 = 走完通道锚(局终于 P2,必经 P1r9 boss 窗)。"""
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
        b._handle_click_source(SCREEN_BOSS_BRIEFING, '区域-空白点击')
        assert b.screen_identity() == SCREEN_SHOP, \
            '简报点空白关模态回备战自动弹店(不结算)'
        _close_shop_feed(b)
        assert b.screen_identity() == SCREEN_PREP, '关店回备战(可操作主窗口)'
        _start_battle_feed(b.gs)
        assert b.screen_identity() == SCREEN_SETTLE, 'boss 战由出战动作触发'
        _node_advance_feed(b.gs, trigger='settle_confirm')
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (2, 1)
        assert b.screen_identity() == '货币战争-位面过渡', 'P2 首轮位面过渡'
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        assert b.screen_identity() == SCREEN_SHOP, 'P2r1 窗收尾自动弹店'
    finally:
        uninstall_backend()


def test_node_window_overlay_detour_reruns_offer_check() -> None:
    """overlay 让路恢复序:offer 槽节点窗起点 overlay 在场 → 呈现压住
    节点屏,选定后复走 offer 检查呈现策略选卡屏(让路不吞 offer 槽),
    选卡落地直出节点屏;窗口前段(轮首收入)不因让路重入。权威序 =
    旧引擎实测收尾检查序(overlay → offer → 下一节点)+ U07 固定日程
    (P1r3/P2r2/P3r2)生效于本节点备战窗口前。"""
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
        assert b.screen_identity() == SCREEN_SHOP, \
            'offer 选定 → 节点窗收尾自动弹店(battle 节点无弹窗)'
    finally:
        uninstall_backend()


# ============================================================ 选卡分支获得链

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


def test_random_env_gift_sim_seeded_roll_to_bench() -> None:
    """随机环境赠卡 sim 全链(迭代 2026-09-23-invest-effects-calc T-10
    设计 §4 测试 7):播种 invest_env_opts 选人才引进 → 选卡后 bench = 5 张
    (4 张 M01 开局 + 1 张随机 4 费 1★ 赠卡);恰 1 张 4 费(开局手牌
    费用形状 (1,1,1,3)/(1,1,2,2) 无 4 费件,4 费 = 赠卡);同 seed 重放
    确定性(同名同星)——rng 经 install_backend 动作分支提供槽(流键
    action/pick_invest_env/0)注入 = 采样即世界真值。"""
    def _pick_once() -> list[tuple[str, int]]:
        b = SimBackend(seed=7, cfg=RunConfig(
            selected_difficulty='A8', enemy_difficulty=108, env_present=True))
        install_backend(b)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            assert b.screen_identity() == SCREEN_INVEST_ENV
            b.gs.write_logic(b.gs.invest_env_opts,
                             ['人才引进', '轮岗', '头彩'],
                             produced_by='Test', evidence='t:opts', sig=_SIG)
            env_out = report_action_pick_invest_env_param(
                b.gs, SimpleNamespace(idx=0), _SIG)
            assert env_out.applied
            cw_sim_ports.declare_world(env_out.world_decl)
            units = [(s.unit.char_id, s.unit.star)
                     for s in b.gs.bench.value.slots
                     if s is not None and s.kind == 'unit'
                     and s.unit is not None]
            assert len(units) == 5, '4 张 M01 开局 + 1 张随机赠卡'
            assert all(st == 1 for _, st in units), '开局手牌与赠卡全 1★'
            cost4 = {c.name for c in chars_by_cost(4)}  # 注册表现算
            assert sum(1 for n, _ in units if n in cost4) == 1, \
                '恰 1 张 4 费(开局形状无 4 费件,4 费 = 赠卡)'
            return units
        finally:
            uninstall_backend()

    first = _pick_once()
    second = _pick_once()
    assert first == second, '同 seed 重放确定性(同名同星)'


def test_typed_random_env_gift_sim_seeded_roll_to_bench() -> None:
    """类型过滤随机赠卡 sim 全链(T-36 设计 §4 锁 8):播种 invest_env_opts
    选战力提升 → 选卡后 bench = 5 张(4 张 M01 开局全 1★ + 1 张 2★ 赠卡;
    星级 2 = 赠卡唯一判据,开局手牌无 2★);赠卡名 ∈ 规格过滤池(注册表
    现算);同 seed 重放确定性(同名同星)——rng 经 install_backend 动作分支
    提供槽(流键 action/pick_invest_env/0)注入 = 采样即世界真值。"""
    def _pick_once() -> list[tuple[str, int]]:
        b = SimBackend(seed=7, cfg=RunConfig(
            selected_difficulty='A8', enemy_difficulty=108, env_present=True))
        install_backend(b)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            assert b.screen_identity() == SCREEN_INVEST_ENV
            b.gs.write_logic(b.gs.invest_env_opts,
                             ['战力提升', '轮岗', '头彩'],
                             produced_by='Test', evidence='t:opts', sig=_SIG)
            env_out = report_action_pick_invest_env_param(
                b.gs, SimpleNamespace(idx=0), _SIG)
            assert env_out.applied
            cw_sim_ports.declare_world(env_out.world_decl)
            units = [(s.unit.char_id, s.unit.star)
                     for s in b.gs.bench.value.slots
                     if s is not None and s.kind == 'unit'
                     and s.unit is not None]
            assert len(units) == 5, '4 张 M01 开局 + 1 张随机赠卡'
            pool = set(random_char_pool(
                ENV_GIFTS['战力提升'].chars_random_immediate[0]))
            star2 = [(n, st) for n, st in units if st == 2]
            assert len(star2) == 1 and star2[0][0] in pool, \
                '恰 1 张 2★ 赠卡且名 ∈ 类型过滤池'
            return units
        finally:
            uninstall_backend()

    first = _pick_once()
    second = _pick_once()
    assert first == second, '同 seed 重放确定性(同名同星)'


def test_cost2_random_env_gift_sim_seeded_roll_to_bench() -> None:
    """战力飙升(2 费无类型词)sim 全链(T-37 设计 §4 锁 8):播种
    invest_env_opts 选战力飙升 → 选卡后 bench = 5 张(4 张 M01 开局全 1★
    + 1 张 2★ 赠卡;星级 2 = 赠卡唯一判据,开局手牌无 2★);赠卡名 ∈
    2 费全档池(注册表现算);同 seed 重放确定性(同名同星)——rng 经
    install_backend 动作分支提供槽(流键 action/pick_invest_env/0)注入。"""
    def _pick_once() -> list[tuple[str, int]]:
        b = SimBackend(seed=7, cfg=RunConfig(
            selected_difficulty='A8', enemy_difficulty=108, env_present=True))
        install_backend(b)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            assert b.screen_identity() == SCREEN_INVEST_ENV
            b.gs.write_logic(b.gs.invest_env_opts,
                             ['战力飙升', '轮岗', '头彩'],
                             produced_by='Test', evidence='t:opts', sig=_SIG)
            env_out = report_action_pick_invest_env_param(
                b.gs, SimpleNamespace(idx=0), _SIG)
            assert env_out.applied
            cw_sim_ports.declare_world(env_out.world_decl)
            units = [(s.unit.char_id, s.unit.star)
                     for s in b.gs.bench.value.slots
                     if s is not None and s.kind == 'unit'
                     and s.unit is not None]
            assert len(units) == 5, '4 张 M01 开局 + 1 张随机赠卡'
            pool = set(random_char_pool(
                ENV_GIFTS['战力飙升'].chars_random_immediate[0]))
            star2 = [(n, st) for n, st in units if st == 2]
            assert len(star2) == 1 and star2[0][0] in pool, \
                '恰 1 张 2★ 赠卡且名 ∈ 2 费全档池'
            return units
        finally:
            uninstall_backend()

    first = _pick_once()
    second = _pick_once()
    assert first == second, '同 seed 重放确定性(同名同星)'


def test_opening_replace_env_sim_replaces_m01_hand() -> None:
    """开局替换 sim 全链(T-43 设计 §4 锁 6):播种 invest_env_opts 选
    人才储备 → 选卡后 bench = 恰 3 张(替换语义,M01 预写的 4 张被清席支
    纠回,非 4+3=7 叠加;选卡前无消费者,瞬态不可见);每张 1★ 且名 ∈
    3 费全档池(注册表现算);同 seed 重放确定性(同名同星)——rng 经
    install_backend 动作分支提供槽(流键 action/pick_invest_env/0)注入 =
    采样即世界真值。"""
    def _pick_once() -> list[tuple[str, int]]:
        b = SimBackend(seed=7, cfg=RunConfig(
            selected_difficulty='A8', enemy_difficulty=108, env_present=True))
        install_backend(b)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            assert b.screen_identity() == SCREEN_INVEST_ENV
            b.gs.write_logic(b.gs.invest_env_opts,
                             ['人才储备', '轮岗', '头彩'],
                             produced_by='Test', evidence='t:opts', sig=_SIG)
            env_out = report_action_pick_invest_env_param(
                b.gs, SimpleNamespace(idx=0), _SIG)
            assert env_out.applied
            cw_sim_ports.declare_world(env_out.world_decl)
            units = [(s.unit.char_id, s.unit.star)
                     for s in b.gs.bench.value.slots
                     if s is not None and s.kind == 'unit'
                     and s.unit is not None]
            assert len(units) == 3, '替换后恰 3 张(M01 4 张被纠回)'
            pool = set(random_char_pool(
                ENV_GIFTS['人才储备'].chars_random_immediate[0]))
            assert all(n in pool and st == 1 for n, st in units), \
                '全 3 费 1★(星级先验 1)'
            return units
        finally:
            uninstall_backend()

    first = _pick_once()
    second = _pick_once()
    assert first == second, '同 seed 重放确定性(同名同星)'


def test_default_env_sim_bench_untouched_by_replace_branch() -> None:
    """默认环境局回归(T-43 设计 §4 锁 6 末项):选无替换标记环境(轮岗)
    → bench = 4 张 M01 原样(清席支缺省 False 零行为差——「默认环境局
    rng 消耗序列不变」的登记面行为锁)。"""
    b = SimBackend(seed=7, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        b.gs.write_logic(b.gs.invest_env_opts,
                         ['轮岗', '人才储备', '头彩'],
                         produced_by='Test', evidence='t:opts', sig=_SIG)
        env_out = report_action_pick_invest_env_param(
            b.gs, SimpleNamespace(idx=0), _SIG)
        assert env_out.applied
        cw_sim_ports.declare_world(env_out.world_decl)
        units = [(s.unit.char_id, s.unit.star)
                 for s in b.gs.bench.value.slots
                 if s is not None and s.kind == 'unit'
                 and s.unit is not None]
        assert len(units) == 4, 'M01 开局 4 张原样,替换分支零误伤'
    finally:
        uninstall_backend()


def test_scheduled_env_gift_discharged_at_plane2_first_window() -> None:
    """定时环境发放 sim 收尾:选特权阶级 → 队列登记 (2,1) 发放项(登记
    不落席);(1,x) 各节点窗开启与位面过渡屏呈现期队列原样(未到点不
    消费);位面过渡点空白收尾(2-1 节点窗打开)→ 特权武装箱落备战席
    (supply_box 槽件)+ 队列回写空。时机语义:「第二位面开始时」=
    位面过渡屏被点掉、2-1 节点窗打开时,发放收尾与窗口幂等守卫同段
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
        # 先行推进一节点:(1,2) 窗口收尾对未到点队列零写
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 2)
        assert gs.pending_item_grants.value == queued, '(1,2) 窗口队列原样'
        # 推进至 P1r9 BOSS 简报 → 出战结算 → (2,1) 位面过渡
        for _ in range(64):
            if b.done or b.screen_identity() == '货币战争-BOSS简报':
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(gs, trigger='settle_confirm')
            else:
                _drive_step(b, 61)
        assert b.screen_identity() == '货币战争-BOSS简报'
        b._handle_click_source('货币战争-BOSS简报', '区域-空白点击')
        assert b.screen_identity() == SCREEN_SHOP, \
            '简报点空白关模态回备战自动弹店(不结算)'
        _close_shop_feed(b)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, 'boss 战由出战动作触发'
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (2, 1)
        assert b.screen_identity() == '货币战争-位面过渡'
        assert gs.pending_item_grants.value == queued, \
            '位面过渡屏呈现时队列未消费(发放收尾在点空白后的节点窗)'
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        assert b.screen_identity() == SCREEN_SHOP, '(2,1) 节点窗收尾自动弹店'
        assert gs.pending_item_grants.value == [], '到点发放队列回写空'
        boxes = [s for s in gs.bench.value.slots
                 if s is not None and s.kind == 'supply_box']
        assert len(boxes) == 1, '特权武装箱落备战席(supply_box 槽件)'
    finally:
        uninstall_backend()


def test_laowu_env_star_grant_and_boss_node_legs() -> None:
    """劳务派遣合同 sim 全链(该迭代 designs/T-19-laowu-paiqian-hetong.md
    §4.7):选卡后 equips 含 1 件 category='星徽' 装备 + done 有
    star_grant# 绑定键(分支1,采样 = 注入槽流键世界真值);推进至 P1 boss
    窗 → bench 恰 +1 个 1★ 绑定羁绊角色 + done 有 boss#<位面>-<轮> 键
    (分支2,M21 流键);同 seed 重放确定性(equips/bench/done 逐位同)。"""

    def _bench_units(gs: GameState) -> list[tuple[str, int]]:
        return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
                if s is not None and s.kind == 'unit'
                and s.unit is not None]

    def _run_once() -> tuple[tuple[str, ...], tuple, tuple]:
        b = SimBackend(seed=61, cfg=RunConfig(
            selected_difficulty='A8', enemy_difficulty=108, env_present=True))
        install_backend(b)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            assert b.screen_identity() == SCREEN_INVEST_ENV
            gs = b.gs
            gs.write_logic(gs.invest_env_opts,
                           ['劳务派遣合同', '轮岗', '头彩'],
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            env_out = report_action_pick_invest_env_param(
                gs, SimpleNamespace(idx=0), _SIG)
            assert env_out.applied
            assert gs.active_env.value == '劳务派遣合同'
            cw_sim_ports.declare_world(env_out.world_decl)

            # 分支1:开局选卡即发 —— equips 1 件星徽 + done 绑定键
            binding = [k for e, k in (gs.env_grants_done.value or ())
                       if e == '劳务派遣合同'
                       and k.startswith(STAR_GRANT_KEY_PREFIX)]
            assert len(binding) == 1, '绑定键恰一枚'
            assert len(gs.equips.value) == 1, '分支1 发放 1 件星徽入栏'
            star_name = gs.equips.value[0]
            assert star_name == binding[0][len(STAR_GRANT_KEY_PREFIX):], \
                '绑定键值 = 发放星徽名'
            assert star_name in equips_by_category('星徽'), '发放 ∈ 星徽类别池'
            pool = {c.name for c in chars_by_faction(star_name[:-2])}

            # 推进至 P1 boss 窗(boss 简报呈现前节点窗已开 → 分支2 已发);
            # 每个 settle 推进前快照 bench,窗开恰 +1 = 分支2 独占增量
            prev_units: list[tuple[str, int]] | None = None
            for _ in range(64):
                if b.done or b.screen_identity() == '货币战争-BOSS简报':
                    break
                if b.screen_identity() == SCREEN_SETTLE:
                    prev_units = _bench_units(gs)
                    _node_advance_feed(gs, trigger='settle_confirm')
                else:
                    _drive_step(b, 61)
            assert b.screen_identity() == '货币战争-BOSS简报'
            boss_round = resolve_plane_node_seqs('劳务派遣合同')[1] \
                .index('boss') + 1
            assert ('劳务派遣合同', f'{BOSS_NODE_KEY_PREFIX}1-{boss_round}') \
                in (gs.env_grants_done.value or ()), 'done 记 boss 节点键'
            units = _bench_units(gs)
            assert prev_units is not None and \
                len(units) == len(prev_units) + 1, \
                f'boss 窗 bench 恰 +1(分支2 独占): {len(prev_units)}→{len(units)}'
            name, star = units[-1]
            assert name in pool, '分支2 角色 ∈ 绑定星徽的羁绊成员池'
            assert star == 1, '分支2 星级 1★ 先验'
            return (tuple(gs.equips.value), tuple(units),
                    gs.env_grants_done.value)
        finally:
            uninstall_backend()

    first = _run_once()
    second = _run_once()
    assert first == second, '同 seed 重放确定性(equips/bench/done 逐位同)'


def test_strategy_pick_chain_burst_gold() -> None:
    """获得链断言:选 burst 策略卡(加油站)→ 免费刷新发放生效
    (effect burst 桥,容器零私持);即时金通道现役无写端不发生
    (kernel ``apply_effect_burst_grant`` 只载 free_refresh_burst),
    断言面只校验免费刷新发放。"""
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


def test_strategy_pick_chain_deposit_return_conditional() -> None:
    """获得链断言(T-92 设计 §4 锁 5,sim 世界同链):选存款回报 →
    零买牌节点进下一节点桥 +2;对拍:有花费节点(购经验 cost>0 置位)
    不发放;两拍滚位均复位 False(世界真值闭环:置位→桥评估→滚位,
    sim 节点推进走 kernel 同链)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        assert gs.prev_node_spent.value is False, 'sim 开局种子 False(前置)'
        gs.write_logic(gs.invest_strategy_opts,
                       ['存款回报', '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='存款回报'), _SIG,
            session=SimpleNamespace())
        assert out.applied
        assert gs.free_refresh_left.value is None, \
            '无立即腿 = 登记期零发放(burst 桥零额度 no-op)'
        cw_sim_ports.declare_world(out.world_decl)
        b._maybe_finish_wait()
        # (1,1) 零买牌节点 → 推进 (1,2):桥条件腿 +2,滚位判等跳写
        if b.screen_identity() == SCREEN_SHOP:
            _close_shop_feed(b)
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert gs.node.value.round_num == 2
        assert (gs.free_refresh_left.value or 0) == 2, \
            '零买牌节点边界 +2(上节点未花费)'
        assert gs.prev_node_spent.value is False
        # 对拍节点 (1,2):购经验上报置位(花费通道,cost=2>0)→ 推进 (1,3) 不发放
        lv_out = report_action_level_up_param(
            gs, SimpleNamespace(cost=2), _SIG)
        assert lv_out.applied, '购经验上报成功'
        assert gs.prev_node_spent.value is True, '花费事件置位'
        _close_shop_feed(b)   # (1,2) 窗收尾自动弹店 → 关店回备战
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert gs.node.value.round_num == 3
        assert (gs.free_refresh_left.value or 0) == 2, \
            '有花费节点不发放(True 不授予)'
        assert gs.prev_node_spent.value is False, '滚位照常复位 False'
    finally:
        uninstall_backend()


def test_strategy_pick_chain_free_lunch_burst() -> None:
    """获得链断言:选免费午餐 → burst 桥一次 +11 入世界免费刷新余额,
    后续一次商店刷新判免费(Field 扣减 + 免费帧禁进付费计数;T-88 设计
    §4 锁 4,形态 = test_strategy_pick_chain_burst_gold 同构)。免费判
    单一源 = ``gs.free_refresh_left``,选卡前 sim 世界未发放(None 基)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        assert gs.free_refresh_left.value is None, '前置:未发放(None 基)'
        gs.write_logic(gs.invest_strategy_opts,
                       ['免费午餐', '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='免费午餐'), _SIG,
            session=SimpleNamespace())
        assert out.applied
        assert (gs.free_refresh_left.value or 0) == 11, \
            'burst 免费刷新一次 +11(effect burst 桥)'
        assert '免费午餐' in gs.active_strategies.value
        # 后续一次商店刷新判免费:免费分支扣减 11→10,付费计数不动
        paid_before = gs.effects.refresh_paid
        total_before = gs.effects.refresh_total
        refresh_out = report_action_refresh_shop_param(
            gs, CwActionRefreshShopParam(cost=2), _SIG)
        assert refresh_out.applied
        assert gs.free_refresh_left.value == 10, \
            '免费帧 Field 扣减(免费判单一源 = free_refresh_left)'
        assert gs.effects.refresh_paid == paid_before, '免费帧禁进付费计数'
        assert gs.effects.refresh_total == total_before + 1, '全量计数含免费'
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


def test_strategy_pick_chain_named_equip_grant() -> None:
    """获得链断言:选全员晋升 → equips 恰 +2 拆装扳手(具名装备授予腿,
    实机(live)和模拟器(sim)两边同链,sim 写状态副本即容器写)+ bench/deployed 零变化(板面重写面
    零建模 = 既有边界申报,sim-design §8.2 板面重写族行)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        gs.write_logic(gs.invest_strategy_opts,
                       ['全员晋升', '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)

        def _bench_ids() -> list:
            return [s.unit.char_id if s is not None and s.kind == 'unit'
                    else None for s in gs.bench.value.slots]

        bench_before = _bench_ids()
        deployed_before = gs.deployed.value
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='全员晋升'), _SIG,
            session=SimpleNamespace())
        assert out.applied
        assert gs.equips.value == ['拆装扳手', '拆装扳手'], \
            '装备腿恰 2 件入栏(sim 世界真值)'
        assert _bench_ids() == bench_before, 'bench 零变化(板面零建模)'
        assert gs.deployed.value == deployed_before, \
            'deployed 零变化(板面零建模)'
    finally:
        uninstall_backend()


def test_strategy_pick_chain_named_equip_grant_wuhai_laji() -> None:
    """获得链断言:选无害垃圾 → equips 恰 +1 垃圾袋(具名装备授予腿,
    具名确定发放零采样,同 seed 重放确定不经 rng 注入)+ bench/deployed
    零变化(板面重写面零建模 = 既有边界申报);金腿 8 金 = instant_gold
    已登记计分、发放写端 = 族级缺口(sim 金面锁不住,维持观察)。"""
    def _run_once() -> tuple:
        b = _backend(7)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            b._maybe_finish_wait()
            gs = b.gs
            equips_before = list(gs.equips.value or [])

            def _bench_ids() -> list:
                return [s.unit.char_id if s is not None and s.kind == 'unit'
                        else None for s in gs.bench.value.slots]

            bench_before = _bench_ids()
            deployed_before = gs.deployed.value
            gs.write_logic(gs.invest_strategy_opts,
                           ['无害垃圾', '躺平', '淘金客'],
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            out = report_action_pick_invest_strategy_param(
                gs, SimpleNamespace(norm_name='无害垃圾'), _SIG,
                session=SimpleNamespace())
            assert out.applied
            assert '无害垃圾' in gs.active_strategies.value
            assert list(gs.equips.value) == equips_before + ['垃圾袋'], \
                f'装备腿恰 1 件入栏(sim 世界真值): {gs.equips.value}'
            assert _bench_ids() == bench_before, 'bench 零变化(板面零建模)'
            assert gs.deployed.value == deployed_before, \
                'deployed 零变化(板面零建模)'
            return tuple(gs.equips.value)
        finally:
            uninstall_backend()

    assert _run_once() == _run_once(), '同 seed 重放确定性(equips 逐位同)'


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
        assert '银狼' in chars, 'bench 分支(确定性)'
        assert gs.equips.value, '改件分支(采样)入栏'
    finally:
        uninstall_backend()


@pytest.mark.parametrize('card', ['战术义眼++', '军火贸易', '军火贸易+'])
def test_strategy_pick_chain_box_grant_immediate(card: str) -> None:
    """获得链断言:选开箱分支策略卡(箱腿组五卡 offer 一次注入、pick 该卡)
    → 箱道具获得时点立即落备战席(supply_box 槽件;仅选中卡效果体分派
    ——另四卡若误分派席上会多出箱,恰 1 = 唯一分派证据)+
    pending_item_grants 不受扰(直发不经定时队列,与特权阶级
    「登记入队、到点发放」形态相斥);军火贸易变体 = 简易武装箱名首次走
    report 上报链,+ 变体道具名同名、链路同形(与姊妹卡仅金量 4→8 差分,
    金腿不经本链,族级缺口维持)。"""
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
                       ['战术义眼++', '保守派', '快请专家·彩', '军火贸易',
                        '军火贸易+'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=card), _SIG,
            session=SimpleNamespace())
        assert out.applied
        assert card in gs.active_strategies.value
        assert _box_count() == 1, '选中卡箱分支立即落备战席(supply_box 槽件)'
        assert gs.pending_item_grants.value == [], \
            '获得时点直发,不进入定时队列'
    finally:
        uninstall_backend()


def test_strategy_pick_chain_reinforcement_grant() -> None:
    """获得链断言:选二费援军 → 费用档注册池内 4 名 1★ 入席(采样效果
    子链;rng 注入流键,sim 采样即世界真值);同 seed 同流键重放 bench
    逐位一致(掷序 = 批内同 rng 实例顺序推进)。"""
    from collections import Counter

    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_reinforcement_names,
    )
    stream_key = 'M11/pick/reinforce'

    def _run_once() -> tuple:
        b = _backend(7)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            b._maybe_finish_wait()
            gs = b.gs

            def _units() -> list:
                return [(s.unit.char_id, s.unit.star)
                        for s in gs.bench.value.slots
                        if s is not None and s.kind == 'unit'
                        and s.unit is not None]

            before = _units()
            picks = roll_reinforcement_names(
                stream_rng(7, stream_key), 2, 4)
            # 预验证:4 抽互异且与开局手牌无 (名, 1★) 三连(否则触发链外
            # 合成,+4 形态破——失配换流键,禁在测试里写第二套合并语义)
            opening_1star = Counter(n for n, s in before if s == 1)
            assert len(set(picks)) == 4 and all(
                opening_1star[n] + picks.count(n) < 3 for n in set(picks)), \
                f'预验证失配: before={before} picks={picks}'
            gs.write_logic(gs.invest_strategy_opts,
                           ['二费援军', '躺平', '淘金客'],
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            out = report_action_pick_invest_strategy_param(
                gs, SimpleNamespace(norm_name='二费援军'), _SIG,
                rng=stream_rng(7, stream_key))
            assert out.applied
            assert '二费援军' in gs.active_strategies.value
            delta = Counter(_units()) - Counter(before)
            assert delta == Counter((n, 1) for n in picks), \
                f'bench 恰 +4 全 1★ 且名 = 流键采样值: {dict(delta)} vs {picks}'
            return tuple(sorted(_units()))
        finally:
            uninstall_backend()

    assert _run_once() == _run_once(), '同 seed 重放确定性(bench 逐位同)'


def test_strategy_pick_chain_random_equip_grant() -> None:
    """获得链断言(打捞人才库+ 迁移回归重锚):选打捞人才库+ → 简易池均匀
    采样 1 件入栏(采样效果子链;rng 注入流键,sim 采样即世界真值);同
    seed 同流键重放 equips 逐位一致;主腿 unchosen_supply 恒 None(sim 局
    不种本域 → 检查恒第 2 门早退 = fail-closed 零发放,沿打捞族 T-94 键族
    语义)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    stream_key = 'M11/pick/random-equip'

    def _run_once() -> tuple:
        b = _backend(7)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            b._maybe_finish_wait()
            gs = b.gs
            before = list(gs.equips.value or [])
            pick = roll_random_equip(stream_rng(7, stream_key), '简易')
            gs.write_logic(gs.invest_strategy_opts,
                           ['打捞人才库+', '躺平', '淘金客'],
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            out = report_action_pick_invest_strategy_param(
                gs, SimpleNamespace(norm_name='打捞人才库+'), _SIG,
                rng=stream_rng(7, stream_key))
            assert out.applied
            assert '打捞人才库+' in gs.active_strategies.value
            assert pick in equips_by_category('简易'), '预验证:采样值 ∈ 池'
            assert list(gs.equips.value) == before + [pick], \
                f'equips 恰 +1 且名 = 流键采样值: {gs.equips.value} vs {pick}'
            assert gs.unchosen_supply.value is None, \
                '主腿 unchosen_supply 恒 None(sim fail-closed 继承)'
            return tuple(gs.equips.value)
        finally:
            uninstall_backend()

    assert _run_once() == _run_once(), '同 seed 重放确定性(equips 逐位同)'


def test_strategy_pick_chain_random_star_equip_grant() -> None:
    """获得链断言(买彩票,星徽行):选买彩票 → 星徽池均匀采样 1 件入栏
    (采样效果子链;rng 注入流键,sim 采样即世界真值);同 seed 同流键
    重放 equips 逐位一致。与打捞人才库+ 锁同构——泛化表 (category, count)
    两行走同一工厂路径,本锁辖星徽行的 sim 全链接入调用(零特殊接入调用申报,
    实机和模拟器两边同链)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    stream_key = 'M11/pick/random-star-equip'

    def _run_once() -> tuple:
        b = _backend(7)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            b._maybe_finish_wait()
            gs = b.gs
            before = list(gs.equips.value or [])
            pick = roll_random_equip(stream_rng(7, stream_key), '星徽')
            gs.write_logic(gs.invest_strategy_opts,
                           ['买彩票', '躺平', '淘金客'],
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            out = report_action_pick_invest_strategy_param(
                gs, SimpleNamespace(norm_name='买彩票'), _SIG,
                rng=stream_rng(7, stream_key))
            assert out.applied
            assert '买彩票' in gs.active_strategies.value
            assert pick in equips_by_category('星徽'), '预验证:采样值 ∈ 池'
            assert list(gs.equips.value) == before + [pick], \
                f'equips 恰 +1 且名 = 流键采样值: {gs.equips.value} vs {pick}'
            return tuple(gs.equips.value)
        finally:
            uninstall_backend()

    assert _run_once() == _run_once(), '同 seed 重放确定性(equips 逐位同)'


# ============================================================ 追加随机环境分支(蓝海 id113)
# 语义正本 = gain-chain.md §3 追加随机环境申报行段 + invest_effects.md
# 蓝海条:选卡上报完整首链(获得蓝海:active_env + 金 +6 + 申报行)→
# advance 消费选卡声明 → 后端掷骰二次入链「获得卷中环境」。池掷骰流键
# 桩 = _stub_env_reroll_roll(恒定下标;卷中随机支 'M02/env-reroll-gift'
# 透传真流键保同 seed 确定性)。

@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(前清防他测残留、后清防本测外泄——全局缓冲被
    后续测试整池排水对账,残留行即假红;沿 kernel/test_action_report
    同名 fixture 先例)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _stub_env_reroll_roll(monkeypatch: pytest.MonkeyPatch,
                          target_env: str) -> None:
    """桩追加环境池掷骰流键:'M02/env-reroll' 恒返回 target_env 池下标,
    其余流键透传真实现(卷中环境随机支保持真流键,同 seed 确定性)。"""
    import sr_od.application.currency_war.sim.cw_sim_backend as backend_mod
    real = backend_mod.stream_rng
    pool = sorted(n for n in INVESTMENT_ENVS if n not in ENV_REROLL_NAMES)
    idx = pool.index(target_env)

    class _FixedRoll:
        """恒定掷骰桩(只实现追加分支消费面 randrange)。"""

        def randrange(self, n: int) -> int:
            return idx

    def fake_stream_rng(seed: int, key: str):
        if key == 'M02/env-reroll':
            return _FixedRoll()
        return real(seed, key)

    monkeypatch.setattr(backend_mod, 'stream_rng', fake_stream_rng)


def _seed_and_pick_env(b: SimBackend, first_opt: str, *,
                       feed_decl: bool = True):
    """推进到投资环境屏 + 播种候选(首项 = first_opt)+ 上报选中首项
    ——选卡上报完整首链即「获得蓝海」构造口径(金 +6 与申报行都以首链
    为前提)。feed_decl=True 连做声明喂入(追加获得分支随之触发);
    False 返回上报出参,由调用方择时喂入(首链中间态断言面)。"""
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [first_opt, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    env_out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert env_out.applied
    if feed_decl:
        cw_sim_ports.declare_world(env_out.world_decl)
    return env_out


def _env_pick_backend(seed: int = 7) -> SimBackend:
    """env_present 后端构造 + 装配(uninstall 责任在调用方 try/finally)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    return b


def test_env_reroll_pick_second_gain_branch(_isolate_defect_buffer) -> None:
    """追加随机环境分支(设计锁面 3):选蓝海完整首链 → 掷骰二次入链——
    active_env ∈ 全集−追加名单且 ≠ 蓝海(追加非替换)、金净变恰 +6
    (池无 gold_instant 条目,二次入链零重复发金)、池分布披露键已登记、
    申报行恰一行(首链所产;卷中名 ∉ 名单,二次入链零新增)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    b = _env_pick_backend()
    try:
        gold0 = int(b.gs.gold.value or 0)
        env_out = _seed_and_pick_env(b, '蓝海', feed_decl=False)
        assert b.gs.active_env.value == '蓝海', '首链选择事实'
        assert int(b.gs.gold.value) == gold0 + 6, '首链金收入分支'
        cw_sim_ports.declare_world(env_out.world_decl)
        pool = sorted(n for n in INVESTMENT_ENVS
                      if n not in ENV_REROLL_NAMES)
        rolled = b.gs.active_env.value
        assert rolled in pool, (rolled, '卷中名 ∈ 池(全集−追加名单)')
        assert int(b.gs.gold.value) == gold0 + 6, '二次入链零重复发金'
        assert ENV_REROLL_ASSUMPTION_POOL in b.disclosures, '池分布披露键已登记'
        kinds = [r['kind'] for r in rows]
        assert kinds.count(ENV_REROLL_DECL) == 1, kinds
    finally:
        uninstall_backend()


def test_env_reroll_rng_explicit_stream_deterministic(
        monkeypatch: pytest.MonkeyPatch,
        _isolate_defect_buffer) -> None:
    """rng 确定性锁(设计锁面 4):同 seed 重放同卷中名;桩卷中名 =
    人才引进(池内唯一随机支环境)时随机赠卡发放逐位一致——锁「追加分支
    rng 显式传参」:实现漏传则 on_env_gained 缺省回退自掷(random.
    Random()),同 seed 两跑发放不同即红。"""
    _stub_env_reroll_roll(monkeypatch, '人才引进')

    def _run() -> list[tuple[str, int]]:
        b = _env_pick_backend()
        try:
            _seed_and_pick_env(b, '蓝海')
            assert b.gs.active_env.value == '人才引进', '桩下卷中名'
            return [(s.unit.char_id, s.unit.star)
                    for s in b.gs.bench.value.slots
                    if s is not None and s.kind == 'unit'
                    and s.unit is not None]
        finally:
            uninstall_backend()

    first = _run()
    second = _run()
    assert first == second, '同 seed 随机赠卡支逐位一致(缺省自掷即红)'
    cost4 = {c.name for c in chars_by_cost(4)}   # 注册表现算
    assert len(first) == 5, '4 张 M01 开局 + 1 张赠卡'
    assert sum(1 for n, _ in first if n in cost4) == 1, \
        '恰 1 张 4 费(开局形状无 4 费件,4 费 = 赠卡,发放确已落地)'


def test_env_reroll_rolled_effects_identical_to_direct_pick(
        monkeypatch: pytest.MonkeyPatch,
        _isolate_defect_buffer) -> None:
    """卷中环境效果完整入链(设计锁面 5):桩卷中名 = 火药味 → 2 个简易
    武装箱落席 + 节点序列场改写,与直接选火药味逐位一致(active_env/
    备战席/序列场三域对拍——原语复用零新发放实现)。"""
    _stub_env_reroll_roll(monkeypatch, '火药味')

    def _run(first_opt: str) -> tuple[str, int, dict[int, tuple[str, ...]]]:
        b = _env_pick_backend()
        try:
            _seed_and_pick_env(b, first_opt)
            boxes = sum(1 for s in b.gs.bench.value.slots
                        if s is not None and s.kind == 'supply_box')
            return (str(b.gs.active_env.value), boxes,
                    dict(b.gs.node_seq_by_plane.value or {}))
        finally:
            uninstall_backend()

    via_reroll = _run('蓝海')
    direct = _run('火药味')
    assert via_reroll == direct, '卷中名效果与直接选中逐位一致'
    assert via_reroll[0] == '火药味'
    assert via_reroll[1] == 2, '火药味 2 个简易武装箱落席'


def test_env_reroll_non_member_regression(_isolate_defect_buffer) -> None:
    """非名单环境回归(设计锁面 6):选火药味(∈ ENV_GIFTS,∉ 追加名单)
    → active_env 保持被选名、追加分支零触发(金不变、无池披露键)、申报
    行零新增;既有环境选卡基线逐位不变由全量回归承载。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    b = _env_pick_backend()
    try:
        gold0 = int(b.gs.gold.value or 0)
        _seed_and_pick_env(b, '火药味')
        assert b.gs.active_env.value == '火药味', '保持被选名'
        assert int(b.gs.gold.value) == gold0, '追加分支零触发(无即时金)'
        assert ENV_REROLL_ASSUMPTION_POOL not in b.disclosures, '无池披露键'
        kinds = [r['kind'] for r in rows]
        assert kinds.count(ENV_REROLL_DECL) == 0, '零申报行'
    finally:
        uninstall_backend()


def test_env_reroll_downstream_gates_follow(
        monkeypatch: pytest.MonkeyPatch,
        _isolate_defect_buffer) -> None:
    """门控跟随冒烟(设计锁面 7):卷中名 = 经济过热 → 环境场读现值
    自动跟随(active_env 电平);卷中名 = 人身意外险 → 节点序列场命中补给
    修饰(容器序列 = resolve_plane_node_seqs(卷中名),写点唯一,位面 1
    插入一个补给节点)。全量跟随面归各卡自身批次,本条锁「无新接入调用」。"""
    # 经济过热:环境场读现值跟随(原扑满门控断言已随 P8 废弃删除)
    _stub_env_reroll_roll(monkeypatch, '经济过热')
    b = _env_pick_backend()
    try:
        _seed_and_pick_env(b, '蓝海')
        assert b.gs.active_env.value == '经济过热'
    finally:
        uninstall_backend()
    # 人身意外险:节点序列场命中修饰
    _stub_env_reroll_roll(monkeypatch, '人身意外险')
    b2 = _env_pick_backend()
    try:
        _seed_and_pick_env(b2, '蓝海')
        assert b2.gs.active_env.value == '人身意外险'
        assert b2.gs.node_seq_by_plane.value == \
            resolve_plane_node_seqs('人身意外险'), '序列场 = 卷中环境修饰表'
        base = resolve_plane_node_seqs('蓝海')   # 白名单外 = 默认表
        assert len(b2.gs.node_seq_by_plane.value[1]) == len(base[1]) + 1, \
            '位面 1 插入一个补给节点(9→10)'
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


# ============================================================ 3.3 声明矿 sim 接入调用测试
# (迭代 2026-10-10-ore-reward-attach 3.3;详设 details/ore-sim-plane-start.md
#  §1-§5:节点窗起点分道入队 + 过期清理接入调用 / 位面开局矿呈现与面板矿
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
            '位面开局矿呈现面披露键已登记(实机首遇校)'
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
    零改动;键序确定性责任在调用序,先例 = 现动作分支键)。"""
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
            '直发分支生效(开局 3 + 轮首收入 4 + 位面开局金 6)'
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
        assert b.screen_identity() == SCREEN_SHOP and b._sub == 'ore', \
            '奖励节点窗收尾自动弹店(晶矿子态随 _return_sub 跨商店模态存续)'
        _drive_step(b, 7)   # 关店回备战
        assert b.screen_identity() == SCREEN_PREP
        assert gs.ore_rewards.value == attached, \
            'P1r2 同坐标面板重呈现:配对命中继承(零重掷零清洗)'
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 3)
        # P1r3 = U07 offer 槽(固定日程生效于本节点备战窗口前):选卡后
        # 直出节点窗收尾
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=gs.invest_strategy_opts.value[0]),
            _SIG, session=SimpleNamespace())
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
        assert b.screen_identity() == SCREEN_SHOP, \
            'offer 选定 → 节点窗收尾自动弹店(battle 节点无面板无弹窗)'
        _drive_step(b, 7)   # 关店回备战
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
        assert b.screen_identity() == SCREEN_SHOP, \
            '简报点空白关模态回备战自动弹店(不结算)'
        _close_shop_feed(b)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, 'boss 战由出战动作触发'
        _node_advance_feed(gs, trigger='settle_confirm')
        assert b.screen_identity() == '货币战争-位面过渡'
        # 测试侧整理(真策略同构行为:部署腾席 + 奖励面板点击收尾):
        # 备战单位移上板 + 清掉未点击面板残留。不清则残留 (10,10)/(20,10)
        # 与声明点跨面板别名继承 → 声明饿死(该角为 ore-reward-channel
        # §4 已登记披露,非本测试面)。
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
        assert b.screen_identity() == SCREEN_SHOP and b._sub == 'ore', \
            '战斗节点窗收尾自动弹店(声明矿子态随 _return_sub 跨商店模态存续)'
        _drive_step(b, 61)   # 关店回备战
        assert b.screen_identity() == SCREEN_PREP
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
    = 点击源(left 递减 + 选项重掷);pick_supply 走获得链,选完关模态
    回备战自动弹店、节点不推进(2026-10-29 流程模型对齐:推进归出战动作
    supply_finish)。宝钻发放分支 = chosen_supply (角色, 装备名列表) 按
    DIAMOND_EQUIP_NAMES 名单派生(T-9 裁定 2)——sim 选项件名恒非钻名 →
    派生不发(选项级钻标属呈现面近似,U24 披露已登记);含钻名形态的派生
    测试 = test_supply_diamond_leg_derives_from_chosen_name_list。"""
    b = _backend(1013)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        _walk_to(b, 1, 5)
        assert b.screen_identity() == SCREEN_SUPPLY
        assert b.gs.supply_refresh_left.value == 1, '节点入口初始 left=1'
        opts_before = [(o.equip, o.extra_equips)
                       for o in b.gs.supply.value.options]
        b._handle_click_source(SCREEN_SUPPLY, '文本-剩余次数')
        assert b.gs.supply_refresh_left.value == 0, '刷新 left−1'
        opts_after = [(o.equip, o.extra_equips)
                      for o in b.gs.supply.value.options]
        assert opts_after != opts_before, '选项重掷'
        pick = b.gs.supply.value.options[0]
        b.gs.write_logic(b.gs.chosen_supply,
                         ('', (pick.equip, *pick.extra_equips)),
                         produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            b.gs, SimpleNamespace(idx=0, char_name='', norm_item=pick.equip),
            _SIG)
        assert out.applied
        assert pick.equip in b.gs.equips.value, '装备入账分支入栏'
        cw_sim_ports.declare_world(out.world_decl)
        assert b.screen_identity() == SCREEN_SHOP, \
            '补给选完关模态回备战自动弹店(不再确认即推节点)'
        assert b.gs.node.value.round_num == 5, \
            '补给确认零节点推进(推进归出战动作 supply_finish)'
        assert b.gs.diamond_count.value == 0, \
            'sim 选项名单不含钻名 → 列表派生零宝钻发放分支(fail-visible 边)'
    finally:
        uninstall_backend()


def test_box_open_pick_grant_via_gain_chain() -> None:
    """开箱动作落地 → 武装箱画面(候选写容器);装备卡点击记录 + 选定
    落地 → 选中装备经获得链入栏;模态交回备战。上报 + 声明喂入单轨
    (open_box / pick_box_card 两条分支,动作 op 同形)。"""
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
                   for p in gs.screen_changes.pending), '判据已登记'
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
                   for p in gs.screen_changes.pending), '判据已登记'
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

def test_full_walk_terminates_with_terminal_invariant() -> None:
    """全链走查到局终:终局合法形态二值不变式(胜利 = run_complete 披露
    且 hp>0 / 死亡 = hp 归零且无 run_complete,胜负判别单一源在披露集);
    位面 3 行入表后全链自然走进位面 3。局结果面自容器节点键读。"""
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
        result = b.result()
        assert result.plane_reached == 3, '位面 3 在表,全链走进 P3'
        assert (DISCLOSURE_RUN_COMPLETE in result.unmodeled) \
            == (result.final_hp > 0), \
            '终局二值不变式:run_complete ⟺ 存活'
        assert all(hp >= 0 for hp in result.hp_trail)
        assert len(result.hp_trail) >= 8, 'hp 轨迹覆盖多节点'
    finally:
        uninstall_backend()


# ============================================================ 品质改写接入(彩虹时代局)

_RAINBOW_ENV = '彩虹时代'


def _rainbow_env_backend(seed: int = 61) -> SimBackend:
    """开局选彩虹时代环境的装配后端(调用方负责 uninstall;装配模式 =
    _ore_env_backend 同款:opts 首位定向 → idx=0 上报 → 声明喂入)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_RAINBOW_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def test_rainbow_env_full_walk_offers_all_prism() -> None:
    """彩虹时代 sim 全流程测试(品质改写接入 sim 三选一;2026-10-14 用户
    裁定:全改写型 + 取卡全局序):开局环境 offer 走 opening 形态不进
    取卡序(选环境后序数 = 0);此后每次策略三选一呈现,候选全棱彩
    注册名;呈现次数 = 固定日程落在序列表内的槽数(P3 行入表后第 3 槽
    P3r2 可达;槽数自 PLANE_NODE_TABLES 现算,防日程/建模域漂移静默
    失配);局终序数 = 呈现次数(每呈现恰 +1,overlay 让路/其余节点不
    计数——单计另由 overlay 用例校验);品质改写披露键已退役,
    disclosures 无 invest_quality_rewrite 前缀键。

    seed 61 = 全槽呈现锚(探针实测:P3r2 offer 在 3-2 窗呈现后局于
    3-5 死亡收尾,三个日程槽全部呈现;改写判据对序数 3 的行为由判据
    测试与抽样测试覆盖)。"""
    b = _rainbow_env_backend(61)
    try:
        assert b._invest_pick_ordinal == 0, '开局环境 offer 不计数'
        modelled_slots = [slot for slot in INVEST_OFFER_SCHEDULE
                          if slot[0] in PLANE_NODE_TABLES]
        offers_seen = 0
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                opts = b.gs.invest_strategy_opts.value
                assert len(opts) == OFFER_CANDIDATES
                for name in opts:
                    assert name in INVESTMENT_STRATEGIES, name
                    assert INVESTMENT_STRATEGIES[name].rarity == '棱彩', \
                        f'改写次候选必棱彩: {name}'
                offers_seen += 1
            _drive_step(b, 61)
        assert b.done, '彩虹局走完到局终'
        assert offers_seen == len(modelled_slots), \
            (offers_seen, modelled_slots)
        assert b._invest_pick_ordinal == offers_seen, \
            '序数 = 实际呈现次数(呈现一次计一次)'
        assert not [k for k in b.disclosures
                    if k.startswith('invest_quality_rewrite')], \
            '品质改写披露键已退役'
    finally:
        uninstall_backend()


def test_rainbow_env_overlay_detour_offer_counted_once() -> None:
    """overlay 让路单计测试:offer 槽节点窗起点 overlay 在场 → 让路呈现
    planner(此时取卡序数仍 0,让路不进 offer 分支),选定复走 offer
    检查 → 改写次候选全棱彩,序数恰 +1(复走无双计;开局环境 offer
    走 opening 形态不计数 → 首呈现后序数 = 1)。让路序权威 = 旧引擎
    实测收尾检查序(overlay → offer → 下一节点)。"""
    b = _rainbow_env_backend(7)
    try:
        b._maybe_finish_wait()
        assert b.screen_identity() == SCREEN_PREP
        assert b._invest_pick_ordinal == 0
        gs = b.gs
        # P1r1(奖励)→ P1r2(战斗)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 2)
        _close_shop_feed(b)   # (1,2) 窗收尾自动弹店 → 关店回备战
        # P1r3(U07 offer 槽)窗口起点 overlay 在场 = 让路前提
        register_screen_change(
            gs, 'planner', '货币战争-银狼升星', source='test')
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert gs.node.value.round_num == 3
        assert b.screen_identity() == '货币战争-银狼升星', \
            '窗起点 overlay 先呈现(压住节点屏)'
        assert b._invest_pick_ordinal == 0, '让路期间不计数'
        planner_out = report_action_pick_planner_param(
            gs, SimpleNamespace(), _SIG)
        assert planner_out.applied
        cw_sim_ports.declare_world(planner_out.world_decl)
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY, \
            '让路结束复走 offer 检查(U07 P1r3 槽不被跳过)'
        opts = gs.invest_strategy_opts.value
        assert opts, 'offer 候选写容器槽'
        for name in opts:
            assert INVESTMENT_STRATEGIES[name].rarity == '棱彩', name
        assert b._invest_pick_ordinal == 1, '呈现恰计一次(复走无双计)'
        invest_out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=opts[0]), _SIG,
            session=SimpleNamespace())
        assert invest_out.applied
        cw_sim_ports.declare_world(invest_out.world_decl)
        assert b.screen_identity() == SCREEN_SHOP, \
            'offer 选定 → 节点窗收尾自动弹店(battle 节点无弹窗)'
    finally:
        uninstall_backend()


# ============================================================ 黄金时代局(验收面)+ 难度账记录

_GOLDEN_ENV = '黄金时代'


def _golden_env_backend(seed: int = 61) -> SimBackend:
    """开局选黄金时代环境的装配后端(调用方负责 uninstall;装配模式 =
    _rainbow_env_backend 同款:opts 首位定向 → idx=0 上报 → 声明喂入)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_GOLDEN_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def test_golden_env_full_walk_offers_all_gold() -> None:
    """黄金时代 sim 全流程测试(T-12 验收测试一;品质改写机制 = T-11
    已落地全改写型判据自动覆盖):开局环境 offer 不进取卡序;此后每次
    策略三选一呈现,候选全金注册名(改写目标品质 '棱彩'→'金' 为两族
    唯一行为差);呈现次数 = 固定日程落在建模域内的槽数(现算,防日程/
    建模域漂移静默失配);局终序数 = 呈现次数。披露键已随 T-11 整体
    退役,无改写申报面可断言(设计稿 §8.4①)。"""
    b = _golden_env_backend(61)
    try:
        assert b._invest_pick_ordinal == 0, '开局环境 offer 不计数'
        modelled_slots = [slot for slot in INVEST_OFFER_SCHEDULE
                          if slot[0] in PLANE_NODE_TABLES]
        offers_seen = 0
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                opts = b.gs.invest_strategy_opts.value
                assert len(opts) == OFFER_CANDIDATES
                for name in opts:
                    assert name in INVESTMENT_STRATEGIES, name
                    assert INVESTMENT_STRATEGIES[name].rarity == '金', \
                        f'改写次候选必金: {name}'
                offers_seen += 1
            _drive_step(b, 61)
        assert b.done, '黄金局走完到局终'
        assert offers_seen == len(modelled_slots), \
            (offers_seen, modelled_slots)
        assert b._invest_pick_ordinal == offers_seen, \
            '序数 = 实际呈现次数(呈现一次计一次)'
    finally:
        uninstall_backend()


def test_golden_env_difficulty_records_track_selections() -> None:
    """难度账记录轨迹测试(T-12 验收测试二;2026-10-14 用户裁定:sim 对
    选择后的难度做记录更新,胜负建模另批)。两个观察面一起校验:

    - **备战画面敌方难度读数观察面**(``gs.enemy_difficulty``):每次结算屏时点,
      值 = 局级输入档 108 + 该时点已选数×金档——选卡落地即时反映
      (0→3→6 移动的可观察形态);写点 = 节点窗开 + 选卡落地。
    - **难度账快照面**(``difficulty_records``):每场战斗结算恰一条
      记录(落账在幂等守卫后,重入无双计),逐条品质分量 = 该结算
      时点已选数×金档;encounter 类遭遇档分量已登记表值域内,非遭遇类
      恒 0;轨迹单调不减;首段 0 + 末段三档齐 = 全链拉通(P3 行入表后
      固定日程三槽全部可达)。"""
    b = _golden_env_backend(61)
    try:
        picks_at_settle: list[int] = []
        flag_at_settle: list[int] = []
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                picks_at_settle.append(
                    len(b.gs.active_strategies.value or []))
                flag_at_settle.append(int(b.gs.enemy_difficulty.value or 0))
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            _drive_step(b, 61)
        assert b.done, '黄金局走完到局终'
        # 备战画面敌方难度读数观察面(gs.enemy_difficulty,live 生产主源 =
        # 备战画面敌方难度读数管线):值随选择即时更新,= 局级输入档 108
        # + 该时点已选数×金档;节点间基线移动不在 sim 面(U25 基础曲线
        # 未采,基线恒 108)。金档查表,防数值重订时字面量假红(2026-10-15)。
        assert flag_at_settle == \
            [108 + p * QUALITY_DIFFICULTY_BONUS['金'] for p in picks_at_settle], \
            (flag_at_settle, picks_at_settle)
        assert flag_at_settle[-1] == \
            108 + 3 * QUALITY_DIFFICULTY_BONUS['金'], \
            '三个日程槽(P1r3/P2r2/P3r2)全部取卡后敌方难度读数 = 108+3×金档'
        records = b.difficulty_records
        # 死亡收尾形态(seed 61 死于 3-5):死亡节点在结算起点已落记录、
        # 死亡分支不经结算屏 → 记录数 = 结算读数 + 1(末条无对应结算读数)。
        assert len(records) == len(picks_at_settle) + 1, \
            (len(records), len(picks_at_settle))
        assert (records[-1].plane, records[-1].round_num) == (3, 5), \
            '末条记录 = 死亡节点(战斗类结算起点落账,死亡分支不删)'
        assert records[-1].breakdown.quality_bonus \
            == 3 * QUALITY_DIFFICULTY_BONUS['金'], \
            '死亡节点记录品质分量 = 终局已选数'
        quality_seq: list[int] = []
        for rec, picks in zip(records[:-1], picks_at_settle, strict=True):
            assert rec.breakdown.base is None, 'U25 基础曲线未采恒 None'
            assert rec.breakdown.quality_bonus \
                == picks * QUALITY_DIFFICULTY_BONUS['金'], \
                (rec.plane, rec.round_num, rec.node_kind,
                 rec.breakdown.quality_bonus, picks)
            if rec.node_kind == 'encounter':
                assert rec.breakdown.encounter_tier_bonus \
                    in ENCOUNTER_TIER_BONUS
            else:
                assert rec.breakdown.encounter_tier_bonus == 0
            quality_seq.append(rec.breakdown.quality_bonus)
        assert quality_seq == sorted(quality_seq), \
            '轨迹单调不减(选择只增不减)'
        assert quality_seq[0] == 0, '取卡日程前的战斗品质分量为 0'
        assert quality_seq[-1] == 3 * QUALITY_DIFFICULTY_BONUS['金'], \
            '全部日程槽取卡后(全金)末段记录 = 3×金档(P3 行入表后第 3 槽可达)'
    finally:
        uninstall_backend()


# ============================================================ 白银时代局(验收面)

_SILVER_ENV = '白银时代'

#: 节点类型词表 → 注册表难度辖域词映射(与 cw_sim_enemy 难度派生同源
#: 语义;测试侧独立持有,防期望计算经被测函数自证)。
_SILVER_NODE_KIND_SCOPE_CN = {'encounter': '遭遇', 'boss': '首领'}


def _silver_env_backend(seed: int = 61) -> SimBackend:
    """开局选白银时代环境的装配后端(调用方负责 uninstall;装配模式 =
    _golden_env_backend 同款:opts 首位定向 → idx=0 上报 → 声明喂入)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_SILVER_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def _silver_static_delta(names: list[str], node_kind: str) -> int:
    """白银局难度期望的静态 Δ 现场算(2026-10-15 用户裁定:期望值不写
    死,按实际拿到的卡在注册表登记的难度修正逐点现算——银池含简单模式
    −3/难度修改器 −4(遭遇+首领限定),写死 108 会误报)。

    辖域过滤与 cw_sim_enemy 难度派生同一映射(遭遇/首领 ↔
    encounter/boss),测试侧独立重写,不经被测函数自证。"""
    scope_cn = _SILVER_NODE_KIND_SCOPE_CN.get(node_kind, '')
    total = 0
    for name in names:
        economy = INVESTMENT_STRATEGIES[name].economy
        if economy is None or not economy.difficulty_delta:
            continue
        scoped = economy.difficulty_node_types
        if not scoped or scope_cn in scoped:
            total += economy.difficulty_delta
    return total


def test_silver_env_full_walk_offers_all_silver() -> None:
    """白银时代 sim 全流程测试(T-13 验收测试一;品质改写机制 = T-11
    已落地全改写型判据自动覆盖,本测试补 T-11/T-12 未覆盖的白银局
    验收面):开局环境 offer 不进取卡序;此后每次策略三选一呈现,候选
    全银注册名;呈现次数 = 固定日程落在建模域内的槽数(现算,防日程/
    建模域漂移静默失配);局终序数 = 呈现次数;品质改写披露键已随
    T-11 整体退役,全程无改写申报。seed 61 走满建模域。"""
    b = _silver_env_backend(61)
    try:
        assert b._invest_pick_ordinal == 0, '开局环境 offer 不计数'
        modelled_slots = [slot for slot in INVEST_OFFER_SCHEDULE
                          if slot[0] in PLANE_NODE_TABLES]
        offers_seen = 0
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                opts = b.gs.invest_strategy_opts.value
                assert len(opts) == OFFER_CANDIDATES
                for name in opts:
                    assert name in INVESTMENT_STRATEGIES, name
                    assert INVESTMENT_STRATEGIES[name].rarity == '银', \
                        f'改写次候选必银: {name}'
                assert not [k for k in b.disclosures
                            if k.startswith('invest_quality_rewrite')], \
                    '品质改写披露键已退役,无改写申报'
                offers_seen += 1
            _drive_step(b, 61)
        assert b.done, '白银局走完到局终'
        assert offers_seen == len(modelled_slots), \
            (offers_seen, modelled_slots)
        assert b._invest_pick_ordinal == offers_seen, \
            '序数 = 实际呈现次数(呈现一次计一次)'
    finally:
        uninstall_backend()


def test_silver_env_difficulty_records_track_selections() -> None:
    """白银局难度账轨迹测试(T-13 验收测试二)。与黄金局的差异 =
    期望值现场算(2026-10-15 用户裁定):白银局品质分量恒 0,但银池含
    负静态 Δ 卡(简单模式 −3/难度修改器 −4),读数期望不写死 108,
    逐点 = 108 + 已选卡注册表难度修正之和(按节点型过滤现算),选到
    减难度卡测试不误报;品质分量断言只读分量字段,不读 total(total
    混入策略静态 Δ 会误报)。

    选卡策略 = offer 中有静态 Δ 卡就选它(非 _drive_step 首选),使
    现场算期望被非平凡行使——seed 18 首槽必中简单模式(−3),写死 108
    的期望在此局必红。两种观察面一起校验:

    - **备战画面敌方难度读数观察面**(``gs.enemy_difficulty``):每次
      结算屏时点,值 = 108 + 该时点已选卡静态 Δ 之和(现算);
    - **难度账快照面**(``difficulty_records``):逐条品质分量恒 0
      (守 economy.md §9「白银+0」定谳,防已作废的「白银−3」旧说
      回流)、策略静态 Δ = 按记录节点重建的已选卡注册表现算、特殊
      加成恒 0(伟大征服棱彩品质,结构性进不了银池)、encounter 类
      遭遇档在表值域、非遭遇类恒 0。计数口径:结算屏访问数 ≤ 记录数
      (败局局终结算不呈现结算屏,记录仍逐场落账),故记录
      以「键严格递增 + 采样节点全覆盖」对账,不做两数全等断言。"""
    b = _silver_env_backend(18)
    try:
        picks_by_slot: dict[tuple[int, int], str] = {}
        samples: list[tuple[tuple[int, int], str, list[str], int]] = []
        for _ in range(4096):
            if b.done:
                break
            screen = b.screen_identity()
            if screen == SCREEN_SETTLE:
                node = b.gs.node.value
                samples.append((
                    (node.plane, node.round_num), node.kind,
                    list(b.gs.active_strategies.value or []),
                    int(b.gs.enemy_difficulty.value or 0),
                ))
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            if screen == SCREEN_INVEST_STRATEGY:
                opts = b.gs.invest_strategy_opts.value
                target = next(
                    (o for o in opts
                     if _silver_static_delta([o], 'battle') != 0), opts[0])
                slot = INVEST_OFFER_SCHEDULE[
                    b._invest_pick_ordinal - 1][:2]
                out = report_action_pick_invest_strategy_param(
                    b.gs, SimpleNamespace(norm_name=target), _SIG,
                    rng=stream_rng(18, 'M11/pick/part'),
                    session=SimpleNamespace())
                cw_sim_ports.declare_world(out.world_decl)
                picks_by_slot[slot] = target
                continue
            _drive_step(b, 18)
        assert b.done, '白银局走完到局终'
        assert picks_by_slot, '选卡日程至少落地一次'
        # 读数观察面:期望现场算(用户裁定 2026-10-15),品质分量恒 0,
        # 静态 Δ 逐点跟随实际拿到的卡;至少一个采样点 Δ 非零,防期望
        # 退化成常数后测试失去信息量。
        assert any(_silver_static_delta(names, kind) != 0
                   for _, kind, names, _ in samples), \
            '本局没有任何非零 Δ 采样点,现场算期望退化,换 seed'
        for key, kind, names, flag in samples:
            assert flag == 108 + _silver_static_delta(names, kind), \
                (key, kind, names, flag)
        # 快照面:逐条记录对账。已选卡按槽位键重建(选卡发生在该槽
        # 节点窗内,槽键 ≤ 记录节点键的选卡全部在场)。
        records = b.difficulty_records
        assert len(records) == len({(r.plane, r.round_num)
                                    for r in records}), '记录键无重复'
        record_keys = [(r.plane, r.round_num) for r in records]
        assert record_keys == sorted(record_keys), '记录键严格递增'
        assert {key for key, _, _, _ in samples} <= set(record_keys), \
            '结算屏访问过的节点必有记录'
        assert any(rec.breakdown.strategy_delta != 0 for rec in records), \
            '本局没有任何非零 Δ 记录,静态 Δ 分支未被行使'
        assert any(rec.breakdown.strategy_delta == 0 for rec in records), \
            '本局没有任何零 Δ 记录,零/非零两段轨迹不齐'
        for rec in records:
            names = [name for slot, name in sorted(picks_by_slot.items())
                     if slot <= (rec.plane, rec.round_num)]
            assert rec.breakdown.base is None, 'U25 基础曲线未采恒 None'
            assert rec.breakdown.quality_bonus == 0, \
                '白银局全银,品质分量恒 0(守「白银+0」定谳)'
            assert rec.breakdown.special_bonus == 0, \
                '伟大征服棱彩品质进不了银池,连胜项无源'
            assert rec.breakdown.strategy_delta \
                == _silver_static_delta(names, rec.node_kind), \
                (rec.plane, rec.round_num, rec.node_kind,
                 rec.breakdown.strategy_delta, names)
            if rec.node_kind == 'encounter':
                assert rec.breakdown.encounter_tier_bonus \
                    in ENCOUNTER_TIER_BONUS
            else:
                assert rec.breakdown.encounter_tier_bonus == 0
    finally:
        uninstall_backend()


# ============================================================ 头彩局(settled 定谳接入)

_TOUCAI_ENV = '头彩'


def _toucai_env_backend(seed: int = 61) -> SimBackend:
    """开局选头彩环境的装配后端(调用方负责 uninstall;装配模式 =
    _rainbow_env_backend 同款:opts 首位定向 → idx=0 上报 → 声明喂入)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_TOUCAI_ENV, '轮岗', '彩虹时代'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def test_toucai_env_full_walk_first_offer_all_prism() -> None:
    """头彩局 sim 全流程测试(部分改写型 settled 定谳接入首例;2026-10-16
    用户裁定:offer 级覆盖面 = 第 1 次取卡机会 3 张候选全棱彩):开局
    环境 offer 走 opening 形态不进取卡序;第 1 次策略三选一呈现,候选全
    棱彩注册名;第 2 次起不设品质断言(单抽不可断言「按默认分布」,恒真
    空断言不可用,该序语义由判据锁——头彩 2/3 序 → None——与序数对账
    承担);呈现次数 = 固定日程落在建模域内的槽数(现算,防日程/建模域
    漂移静默失配);局终序数 = 呈现次数;品质改写披露键已退役,全程无
    invest_quality_rewrite 前缀键。"""
    b = _toucai_env_backend(61)
    try:
        assert b._invest_pick_ordinal == 0, '开局环境 offer 不计数'
        modelled_slots = [slot for slot in INVEST_OFFER_SCHEDULE
                          if slot[0] in PLANE_NODE_TABLES]
        offers_seen = 0
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                opts = b.gs.invest_strategy_opts.value
                assert len(opts) == OFFER_CANDIDATES
                if offers_seen == 0:
                    for name in opts:
                        assert name in INVESTMENT_STRATEGIES, name
                        assert INVESTMENT_STRATEGIES[name].rarity == '棱彩', \
                            f'改写次候选必棱彩: {name}'
                offers_seen += 1
            _drive_step(b, 61)
        assert b.done, '头彩局走完到局终'
        assert offers_seen == len(modelled_slots), \
            (offers_seen, modelled_slots)
        assert b._invest_pick_ordinal == offers_seen, \
            '序数 = 实际呈现次数(呈现一次计一次)'
        assert not [k for k in b.disclosures
                    if k.startswith('invest_quality_rewrite')], \
            '品质改写披露键已退役'
    finally:
        uninstall_backend()


# ============================================================ 尾彩局(settled 定谳接入·末张)

_WEICAI_ENV = '尾彩'


def _weicai_env_backend(seed: int = 61) -> SimBackend:
    """开局选尾彩环境的装配后端(调用方负责 uninstall;装配模式 =
    _toucai_env_backend 同款:opts 首位定向 → idx=0 上报 → 声明喂入)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_WEICAI_ENV, '轮岗', '彩虹时代'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def test_weicai_env_full_walk_third_offer_all_prism() -> None:
    """尾彩局 sim 全流程测试(部分改写型末张 settled 定谳接入;2026-10-16
    用户裁定:offer 级覆盖面 = 第 3 次取卡机会 3 张候选全棱彩):开局
    环境 offer 走 opening 形态不进取卡序;第 1/2 次三选一不设品质断言
    (单抽不可断言「按默认分布」,恒真空断言不可用,该两序语义由判据锁
    ——尾彩 1/2 序 → None——与序数对账承担);第 3 次呈现,候选全棱彩
    注册名;呈现次数 = 固定日程落在建模域内的槽数(现算,防日程/建模域
    漂移静默失配);局终序数 = 呈现次数;品质改写披露键已退役,全程无
    invest_quality_rewrite 前缀键。

    seed 61 = 全槽呈现锚(头彩局同 seed 走满建模域先例;尾彩局第 3 序
    +6 难度改变后续轨迹,若换 seed 需在 docstring 记锚定依据)。"""
    b = _weicai_env_backend(61)
    try:
        assert b._invest_pick_ordinal == 0, '开局环境 offer 不计数'
        modelled_slots = [slot for slot in INVEST_OFFER_SCHEDULE
                          if slot[0] in PLANE_NODE_TABLES]
        offers_seen = 0
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                opts = b.gs.invest_strategy_opts.value
                assert len(opts) == OFFER_CANDIDATES
                if offers_seen == 2:
                    for name in opts:
                        assert name in INVESTMENT_STRATEGIES, name
                        assert INVESTMENT_STRATEGIES[name].rarity == '棱彩', \
                            f'改写次候选必棱彩: {name}'
                offers_seen += 1
            _drive_step(b, 61)
        assert b.done, '尾彩局走完到局终'
        assert offers_seen == len(modelled_slots), \
            (offers_seen, modelled_slots)
        assert b._invest_pick_ordinal == offers_seen, \
            '序数 = 实际呈现次数(呈现一次计一次)'
        assert not [k for k in b.disclosures
                    if k.startswith('invest_quality_rewrite')], \
            '品质改写披露键已退役'
    finally:
        uninstall_backend()


# ============================================================ 银·金·彩局(槽位向量型·卡面即真值)

_YINJINCAI_ENV = '银·金·彩'


def _yinjincai_env_backend(seed: int = 61) -> SimBackend:
    """开局选银·金·彩环境的装配后端(调用方负责 uninstall;装配模式 =
    _toucai_env_backend 同款:opts 首位定向 → idx=0 上报 → 声明喂入)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_YINJINCAI_ENV, '轮岗', '彩虹时代'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def test_yinjincai_env_full_walk_slot_qualities() -> None:
    """银·金·彩局 sim 全流程测试(槽位向量型接入,2026-10-19 用户裁定:
    卡面即真值 = 左银中金右彩,旧「实测金重仓」观察记录作废):每次固定
    取卡 offer 三槽品质按位 = (银,金,棱彩)(判据锁承担逐序语义,本锁锁
    局级可观察面);逐卡刷新计数 = 基准 1 + 增量 2 = 3(extra_pick_
    refreshes 消费端);呈现次数 = 固定日程建模域槽数(现算);局终序数
    = 呈现次数。"""
    b = _yinjincai_env_backend(61)
    try:
        modelled_slots = [slot for slot in INVEST_OFFER_SCHEDULE
                          if slot[0] in PLANE_NODE_TABLES]
        offers_seen = 0
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                opts = b.gs.invest_strategy_opts.value
                assert len(opts) == OFFER_CANDIDATES
                for slot, (name, quality) in enumerate(
                        zip(opts, ('银', '金', '棱彩'), strict=False)):
                    assert name in INVESTMENT_STRATEGIES, name
                    assert INVESTMENT_STRATEGIES[name].rarity == quality, \
                        f'槽{slot}候选必 {quality}: {name}'
                left = b.gs.strategy_refresh_left.value
                assert all(left.get(n) == 3 for n in opts), \
                    f'逐卡计数 = 基准1+增量2: {left}'
                offers_seen += 1
            _drive_step(b, 61)
        assert b.done, '银·金·彩局走完到局终'
        assert offers_seen == len(modelled_slots), \
            (offers_seen, modelled_slots)
        assert b._invest_pick_ordinal == offers_seen, \
            '序数 = 实际呈现次数(呈现一次计一次)'
    finally:
        uninstall_backend()


def test_yinjincai_env_refresh_world_leg_slot_quality_persists() -> None:
    """银·金·彩局刷新世界分支(2026-10-19 用户裁定「sim 与实机一致提供
    刷新次数」批):首次 offer 逐卡计数 3 → 刷新声明喂入(槽 0,生产同形
    = 上报函数取声明 + declare_world 喂入)→ 该槽重掷新银卡(槽位品质
    承诺跨刷新保持)、计数 3→2、未刷槽不动 → 重复刷新至计数尽 → 尽后
    再喂声明 = 静默无操作(容器剩余闸防线)。"""
    b = _yinjincai_env_backend(61)
    try:
        b._maybe_finish_wait()
        for _ in range(64):
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                break
            _drive_step(b, 61)
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY, '首次 offer 呈现'
        opts = list(b.gs.invest_strategy_opts.value)
        assert [INVESTMENT_STRATEGIES[n].rarity for n in opts] \
            == ['银', '金', '棱彩']
        # 刷新槽 0
        out = report_action_refresh_invest_cards_param(
            b.gs, SimpleNamespace(slots=(0,)), _SIG)
        assert out.applied
        assert out.world_decl.trigger == 'refresh_invest_strategy'
        assert out.world_decl.next_screen == SCREEN_INVEST_STRATEGY
        assert out.world_decl.slots == (0,)
        cw_sim_ports.declare_world(out.world_decl)
        opts2 = list(b.gs.invest_strategy_opts.value)
        assert opts2[0] != opts[0], '刷新槽重掷换卡'
        assert opts2[1:] == opts[1:], '未刷槽不动'
        assert INVESTMENT_STRATEGIES[opts2[0]].rarity == '银', \
            '槽位品质承诺跨刷新保持'
        left = b.gs.strategy_refresh_left.value
        assert left[opts2[0]] == 2, '计数 3→2 随新卡呈现'
        assert left[opts[1]] == 3 and left[opts[2]] == 3, '未刷槽计数不动'
        # 重复刷新至计数耗尽
        for _ in range(2):
            out = report_action_refresh_invest_cards_param(
                b.gs, SimpleNamespace(slots=(0,)), _SIG)
            cw_sim_ports.declare_world(out.world_decl)
        slot0_now = list(b.gs.invest_strategy_opts.value)[0]
        assert b.gs.strategy_refresh_left.value[slot0_now] == 0, \
            '首槽三卡各刷 1 次 = 3 次预算耗尽(逐卡通道)'
        # 尽后再喂声明 = 静默无操作
        last = list(b.gs.invest_strategy_opts.value)
        out = report_action_refresh_invest_cards_param(
            b.gs, SimpleNamespace(slots=(0,)), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        assert list(b.gs.invest_strategy_opts.value) == last, \
            '计数尽 → 刷新无操作'
    finally:
        uninstall_backend()


def test_env_screen_refresh_world_leg_group_reroll() -> None:
    """环境屏整组刷新世界分支(2026-10-19 用户裁定批):开局环境屏呈现
    refresh=(1,...)(基准 1 次,呈现写点落容器)→ 整组刷新声明喂入
    (active_env 空 → 触发词 refresh_invest_env)→ 候选整组重掷(组内
    全换)+ 计数落 0 → 尽后再喂声明 = 静默无操作。"""
    b = SimBackend(seed=11, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        opts = list(b.gs.invest_env_opts.value)
        assert b.gs.env_refresh_left.value == 1, '呈现写点落基准 1'
        assert b.observe(SCREEN_INVEST_ENV).refresh == (1, 10, 20), \
            '生成器自容器现读整组剩余'
        out = report_action_refresh_invest_cards_param(
            b.gs, SimpleNamespace(slots=(0, 1, 2)), _SIG)
        assert out.applied
        assert out.world_decl.trigger == 'refresh_invest_env'
        assert out.world_decl.next_screen == SCREEN_INVEST_ENV
        cw_sim_ports.declare_world(out.world_decl)
        opts2 = list(b.gs.invest_env_opts.value)
        assert set(opts2).isdisjoint(opts), '整组重掷组内全换'
        assert b.gs.env_refresh_left.value == 0, '计数扣减'
        assert b.observe(SCREEN_INVEST_ENV).refresh == (0, 10, 20)
        # 尽后再喂声明 = 静默无操作
        out = report_action_refresh_invest_cards_param(
            b.gs, SimpleNamespace(slots=(0, 1, 2)), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        assert list(b.gs.invest_env_opts.value) == opts2
    finally:
        uninstall_backend()


def test_no_env_match_refresh_routes_strategy_branch() -> None:
    """无环境局刷新路由锁(T-427 验收 F-1 回归):env_present 缺省 False
    = 合法无环境支路配置,该局 active_env 恒空 + env_refresh_left 未写
    (None)→ 刷新声明推导必须走策略屏逐卡分支(旧单一 active_env 依据会
    误派 env 分支 → env_refresh_left=None 静默无操作 → 计数不减 → 活锁);
    世界分支照常重掷扣减(基准 1 次)。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        _walk_to(b, 1, 3)
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY
        assert (b.gs.active_env.value or '') == '', '无环境局前提'
        assert b.gs.env_refresh_left.value is None, '环境屏未呈现前提'
        opts = list(b.gs.invest_strategy_opts.value)
        assert b.gs.strategy_refresh_left.value == dict.fromkeys(opts, 1)
        out = report_action_refresh_invest_cards_param(
            b.gs, SimpleNamespace(slots=(0,)), _SIG)
        assert out.world_decl.trigger == 'refresh_invest_strategy', \
            '无环境局刷新走策略分支(env 分支会静默无操作活锁)'
        assert out.world_decl.next_screen == SCREEN_INVEST_STRATEGY
        cw_sim_ports.declare_world(out.world_decl)
        new_first = list(b.gs.invest_strategy_opts.value)[0]
        assert new_first != opts[0], '重掷换卡'
        assert b.gs.strategy_refresh_left.value[new_first] == 0, '计数 1→0'
    finally:
        uninstall_backend()


def test_refresh_multi_slot_decl_no_duplicate_names() -> None:
    """多槽声明同窗重掷去重锁(T-427 验收 F-2):同向量环境(头彩,三槽
    同棱彩池)直喂 slots=(0,1) 声明 → 两刷新槽新名互异且不撞未刷槽
    (offer「全程不重复」契约;生产单槽链行为不变)。"""
    b = _toucai_env_backend(61)
    try:
        b._maybe_finish_wait()
        for _ in range(64):
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                break
            _drive_step(b, 61)
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY
        out = report_action_refresh_invest_cards_param(
            b.gs, SimpleNamespace(slots=(0, 1)), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        opts = list(b.gs.invest_strategy_opts.value)
        assert len(set(opts)) == OFFER_CANDIDATES, f'重掷后仍三卡互异: {opts}'
        for name in opts[:2]:
            assert INVESTMENT_STRATEGIES[name].rarity == '棱彩', \
                f'两刷新槽仍落头彩棱彩池: {name}'
    finally:
        uninstall_backend()


def _joint_env_backend(seed: int = 61) -> SimBackend:
    """开局选联席决策环境的装配后端(调用方负责 uninstall;装配模式 =
    _toucai_env_backend 同款)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     ['联席决策', '轮岗', '彩虹时代'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def test_joint_extra_slot_presents_no_refresh() -> None:
    """联席额外槽不呈现刷新锁(T-427 验收 F-3):联席决策局 walk 到 2-6
    额外三选一 → 授权簿记 False + refresh_slots 空(op 闸无授权失败
    安全,保守缺位);对照 = 固定日程槽照常呈现逐卡计数。"""
    b = _joint_env_backend(61)
    try:
        b._maybe_finish_wait()
        hit = False
        for _ in range(4096):
            if b.done:
                break
            if b.screen_identity() == SCREEN_INVEST_STRATEGY:
                if b._node_pos() == JOINT_DECISION_EXTRA_SLOT:
                    hit = True
                    break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(b.gs, trigger='settle_confirm')
                continue
            _drive_step(b, 61)
        assert hit, '走到 2-6 额外三选一(联席调用点)'
        assert b._offer_refreshable is False, '额外槽无刷新授权(保守缺位)'
        assert b.observe(SCREEN_INVEST_STRATEGY).refresh_slots == []
    finally:
        uninstall_backend()


# ============================================================ 装备入账分支(规则件缺口补 kernel)

def _advance_pair() -> tuple[str, str, str]:
    """取一对真配方(组件A, 组件B, 进阶产物)(注册表单一源取用)。"""
    advance, (a, b) = next(iter(CROSS_RECIPES.items()))
    return a, b, advance


def test_wear_report_synthesis_branch() -> None:
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
    # 拒绝形态:owned 无件 / 目标未登记 → applied=False 零写
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


def test_wear_report_synthesis_grant_world_truth() -> None:
    """sim 世界真值同口:动作注入穿戴合成与 live 同一上报函数单口,
    账本持卡 → 合成发放自动生效(free_refresh_left +2,sim 世界容器
    与 live 同格)——发放腿住上报函数内,sim 穿戴批未来接入调用零返工。
    sim 自主局零穿戴 = 零触发(装备域 sim 未建模既有边界,不设负锁)。"""
    advance, (a, b) = next(iter(CROSS_RECIPES.items()))
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [None] * 9
    slots[0] = BenchSlot(kind='unit', unit=Unit(char_id='淘金客', star=1,
                                                equips=[a]))
    gs.observe(gs.bench, cw4_bview(slots), sig=_SIG_OBS)
    gs.observe(gs.equips, [b], sig=_SIG_OBS)
    gs.effects.register_strategy(STRATEGY_EFFECTS['武力刷新'],
                                 acquired_key=(1, 1))
    out = report_action_wear_equip_param(
        gs, CwActionWearEquipParam(item_name=b, char_name='淘金客',
                                   row='front', slot=1), _SIG)
    assert out.applied
    assert gs.free_refresh_left.value == 2, '世界真值同口:合成 +2 到账'


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


# ============================================================ 3.4 联调机制测试

def test_node_window_front_section_idempotent_on_click_replay() -> None:
    """窗口前段幂等守卫(3.4 联调裁决①):同节点线性序的窗口收尾二次
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
    接入调用):呈现即可达流程终局链(CwScreenBattleWait 终局锚 → 主循环
    3c 收尾),与实机「终局 → 返回货币战争 → 大厅」消费链同形。"""
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


# ============================================================ 画面广播
# (迭代 sim-screen-announce §2.1:内部画面状态机 → 容器画面域广播,
# 渲染复盘的画面章证据面。消费方 = tools/cw/replay_to_md.py 画面章
# 切分,切章锚 = field='current_screen' 写入行本体。)

def test_screen_announce_broadcast_points_and_value_exemption() -> None:
    """画面广播逐点断言(sim-screen-announce §2.1):
    - _announce_screen 写 prev_screen/current_screen 同形对,渠道 =
      obs 族合成签名(group_id='sim:screen',mode='synthesized' 为
      obs_sig 内建的渠道级如实标记,evidence 前缀 screen:);
    - 广播点 = 12 处 ``self._screen`` 赋值点中除 SETTLE/LOBBY 外 10 处:
      直通 8 点(简报/备战×2/位面过渡/投资策略/补给/遭遇/BOSS简报)
      + 动态模态呈现/返回 2 点(六 overlay 值经此流动),逐点断
      current_screen 行值;
    - 豁免按值不按赋值点:SETTLE/LOBBY 值不广播(结算/大厅复盘事实
      已有承载位,广播只造未注册空壳章;模态返回位=结算屏的泄漏形态
      一并封死)。

    基建暗坑:断言 sig/family 须 raw sink 直挂
    (``set_state_journal_sink(rows.append)``——harness capture_state_
    journal 是投影捕获无 sig)**并配 ``set_run_id_provider``**(双装,
    缺一则局外拒写门静默吞全部行;同 harness capture_state_journal
    双装纪律)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        set_run_id_provider,
        set_state_journal_sink,
    )
    from sr_od.application.currency_war.kernel.cw_node_schedule import (
        node_sequence_of,
    )
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SCREEN_EXPERT,
        SCREEN_LOBBY,
    )

    rows: list[dict] = []
    set_state_journal_sink(rows.append)
    set_run_id_provider(lambda: 'run_announce')
    try:
        b = _backend(7)  # 装配端口槽(出战结算分支走 declare_world 须在装)
        gs = b.gs

        def assert_broadcast(value: str) -> None:
            """最近一次广播:current_screen 行值命中,且前一行 =
            prev_screen(两行一对)。"""
            hits = [i for i, r in enumerate(rows)
                    if r.get('field') == 'current_screen']
            assert hits, '无 current_screen 行'
            i = hits[-1]
            assert rows[i]['after'] == value, (rows[i]['after'], value)
            assert rows[i - 1]['field'] == 'prev_screen', '广播两行一对'

        def cs_values_since(mark: int) -> list[str]:
            return [r['after'] for r in rows[mark:]
                    if r.get('field') == 'current_screen']

        # ① 简报(构造即 reset 广播;首对 prev = 容器冷建空串)
        assert_broadcast(SCREEN_BRIEFING)
        pair = rows[-2:]
        assert [r['field'] for r in pair] == ['prev_screen',
                                              'current_screen']
        assert pair[0]['after'] == ''
        for r in pair:
            assert r['sig']['family'] == 'obs'
            assert r['sig']['mode'] == 'synthesized'
            assert r['sig']['group_id'] == 'sim:screen'
            assert r['state']['prov'][r['field']]['evidence'] == \
                f'sim:engine:screen:{SCREEN_BRIEFING}'

        # ② 备战(简报下一步;_CFG 无环境支路 → wait_one_one 变体直通点)
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert_broadcast(SCREEN_PREP)

        # ③④ 动态点:六 overlay 值呈现/返回(值词表经此两点流动;
        #    返回位 = 进入模态前的底层屏)
        for v in (SCREEN_BOX, SCREEN_EXPERT, SCREEN_MEGASTAR,
                  SCREEN_PLANNER, SCREEN_INVEST_ENV, SCREEN_SHOP):
            b._present_modal(v)
            assert_broadcast(v)
            b._dismiss_modal()
            assert_broadcast(SCREEN_PREP)

        # ⑤ 位面过渡(位面首轮直通点)
        b._enter_node_window((2, 1))
        assert_broadcast(SCREEN_PLANE_TRANSITION)

        # ⑥ 投资策略(offer 槽直通点;U07 固定日程 P1r3,环境不在场也命中)
        gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
                   evidence='t:node', sig=_SIG_OBS)
        b._present_offer_or_node_screen()
        assert_broadcast(SCREEN_INVEST_STRATEGY)

        # ⑦⑧⑨ 节点屏三型直通点(补给/遭遇/BOSS 简报;kind 取同一
        #      序列真值源,禁测试侧硬编码节点类型)
        for pos, want in (((1, 5), SCREEN_SUPPLY),
                          ((1, 7), SCREEN_ENCOUNTER),
                          ((1, 9), SCREEN_BOSS_BRIEFING)):
            kind = node_sequence_of(pos[0])[pos[1] - 1]
            gs.observe(gs.node,
                       NodeKey(plane=pos[0], round_num=pos[1], kind=kind),
                       evidence='t:node', sig=_SIG_OBS)
            b._present_node_screen()
            assert_broadcast(want)

        # ⑩ 备战(battle 型直通点;经真实节点窗收尾 = P1r1 进窗 → 窗口
        #    前段 → 节点屏呈现,出战结算分支依赖此窗态)
        b._enter_node_window((1, 1))
        assert_broadcast(SCREEN_PREP)

        # SETTLE 赋值点(战斗结算分支):赋值发生、广播零行(值豁免)
        mark = len(rows)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE
        assert cs_values_since(mark) == []

        # 值级豁免直证 + 动态返回位=结算屏泄漏形态封死(B4:豁免按值
        # 不按赋值点——返回位可为结算屏,点位豁免会泄漏空壳章)
        mark = len(rows)
        b._announce_screen(SCREEN_SETTLE)
        b._announce_screen(SCREEN_LOBBY)
        b._present_modal(SCREEN_LOBBY)  # 呈现豁免值:赋值发生,广播零行
        assert b._screen == SCREEN_LOBBY
        b._dismiss_modal()              # 返回位 = 结算屏:同样零广播
        assert b._screen == SCREEN_SETTLE
        assert cs_values_since(mark) == []

        # LOBBY 赋值点(局终):赋值发生、广播零行(值豁免)
        b._game_over()
        assert b._screen == SCREEN_LOBBY
        assert cs_values_since(mark) == []
    finally:
        uninstall_backend()
        set_run_id_provider(None)
        set_state_journal_sink(None)


def test_expert_screen_presentation_raises_loud_on_observe() -> None:
    """SCREEN_EXPERT「呈现即响错」语义测试(3.4 联调裁决③):open_bookcard
    声明(纯转移)驱动专家邀请函屏呈现;该屏非金路径 13 档(实机触发
    条件零档,数据缺口族),observe 必 LookupError 具名响错——防未来把
    响错静默降级成注册屏/空产物(flow-seam §3 未注册屏响错测试的呈现态
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


# ============================================================ 3.3 环境条件发放 sim 接入调用测试
# (迭代 2026-10-10-env-conditional-grants landing 3.3;详设
#  details/env-conditional-grant.md §4/§5:结算分支触发检查接入调用于 streak
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
    seed 采样解耦)。2026-10-29 流程模型对齐:补给确认零推进(选完
    回备战自动弹店,推进归出战);商店档 = 关店动作单轨回备战。"""
    screen = b.screen_identity()
    gs = b.gs
    if screen == SCREEN_SETTLE:
        _node_advance_feed(gs, trigger='settle_confirm')
    elif screen == SCREEN_SUPPLY:
        opts = gs.supply.value.options
        pick = next(o for o in opts if not o.has_diamond)
        gs.write_logic(gs.chosen_supply,
                       ('', (pick.equip, *pick.extra_equips)),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=opts.index(pick), char_name='',
                                norm_item=pick.equip), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SHOP:
        _close_shop_feed(b)
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
    = level+1 + back_layout +1(基线 6 → 7,min9 未触);同时校验写行
    形态:触发两写 sig 单形态 = logic_action 族 'sim:env',回调三写 =
    observe 渠道 obs 族 'sim:env-diamond'。"""
    b = _env_grant_backend()
    try:
        gs = b.gs
        calls = _record_all_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _drive_until(b, lambda: int(gs.streak.value or 0) >= 5)
        # P1 战斗类节点恰 5 个(r3/r4/r6/r7/r9):全胜 → 5 连胜达成于
        # r9 boss 结算分支,断言面即触发局现值
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


_DOT_ENV = '持续伤害契约'
_DOT_CHAR = '黑天鹅'


def _dot_env_backend(seed: int = 23) -> SimBackend:
    """开局选持续伤害契约环境的装配后端(调用方负责 uninstall)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     [_DOT_ENV, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return b


def _bench_char_ids(gs: GameState) -> list[str]:
    return [s.unit.char_id for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_dot_contract_opening_acquisition_confirms_at_eighth_battle(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """开局获取形态主路径锁面(T-28 设计稿 §4.1⑥,防「锚键门控死寂」
    回归):开局选环境链 node 未进窗(锚键分支不写 = 预期形态)→ 连打战斗
    结算,active_env 门驱动猜测写 + 进度累计,第 8 个战斗结算证实落地,
    锚键可缺(纯登记非门控)。P1 序(reward×2/battle×2/supply/battle/
    encounter/reward/boss)恰 8 个战斗结算节点;补给轮不经结算分支 = 不计数
    (非战斗轮锁面,设计稿 §2.3);猜测写在结算分支非获得刻(§2.2)。"""
    b = _dot_env_backend()
    try:
        gs = b.gs
        _force_settle(monkeypatch, won=True)
        chars = set(_bench_char_ids(gs))
        assert {'椒丘', '卡芙卡'} <= chars, '即时分支(获得刻,零改动回归)'
        assert _DOT_CHAR not in chars, '猜测写在结算分支,不在获得刻'
        assert not [k for _e, k in (gs.env_grants_done.value or ())
                    if k.startswith('dot_anchor#')], \
            '开局形态锚键可缺(node 未进窗不写)'
        # 驱至 P1 补给轮(r5):前 4 个战斗结算已逐笔计数;补给轮非战斗
        # 不推进计数
        _drive_until(b, lambda: b.screen_identity() == SCREEN_SUPPLY)
        keys = [k for e, k in (gs.env_grants_done.value or ())
                if e == _DOT_ENV and k.startswith('dot_battle#')]
        assert keys == [f'dot_battle#{i}' for i in range(1, 5)], \
            f'补给轮前 4 笔进度键: {keys}'
        assert _DOT_CHAR in _bench_char_ids(gs), '首结算猜测态在席'
        # 证实落地(第 8 个战斗结算 = P1 boss 结算分支)
        _drive_until(b, lambda: (_DOT_ENV, 'dot_confirm')
                     in (gs.env_grants_done.value or ()))
        keys = [k for e, k in (gs.env_grants_done.value or ())
                if e == _DOT_ENV and k.startswith('dot_battle#')]
        assert keys == [f'dot_battle#{i}' for i in range(1, 9)], \
            f'进度键 1..8 逐笔: {keys}'
        assert (_DOT_ENV, 'dot_confirm') in (gs.env_grants_done.value or ())
        assert _bench_char_ids(gs).count(_DOT_CHAR) == 1, \
            '猜测态恰一只(幂等守卫防叠写)'
    finally:
        uninstall_backend()


def test_supply_diamond_pick_keeps_zero_callback(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """supply 路径零行为变化(landing 3.3):深井角斗场已登记环境下带钻
    补给选定 → 仅 diamond_count +1(_on_supply_picked 既有行为,带钻以
    名单内件名入 chosen 列表承载——T-9 列表派生,sim 选项级钻标属呈现
    面不入名单),deploy_cap/back_layout 零写、零发放——钻类型未建模,
    不采纳回调。"""
    b = _env_grant_backend()
    try:
        gs = b.gs
        _force_settle(monkeypatch, won=True)
        _drive_until(b, lambda: b.screen_identity() == SCREEN_SUPPLY)
        assert int(gs.streak.value or 0) == 2, 'r3/r4 两胜,补给轮前 <5'
        cap_before = gs.deploy_cap.value
        back_before = gs.back_layout.value
        # 红钻 = 三钻之一(避开 _ENV_GRANT_EQUIP=财富宝钻,两条分支不混淆:
        # 本测试只证 supply 钻分支聚合,环境发放仍零发生)
        gs.write_logic(gs.chosen_supply,
                       ('', ('红钻',)),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=0, char_name='', norm_item='红钻'),
            _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        assert gs.diamond_count.value == 1, '带钻补给聚合计数 +1(既有行为)'
        assert gs.deploy_cap.value == cap_before, '不采纳回调:cap 零写'
        assert gs.back_layout.value == back_before, \
            '不采纳回调:back_layout 零写'
        assert gs.env_grants_done.value == (), '连胜未达标,零发放'
        assert _ENV_GRANT_EQUIP not in gs.equips.value
    finally:
        uninstall_backend()


def test_supply_diamond_leg_derives_from_chosen_name_list() -> None:
    """sim 宝钻发放分支列表派生测试(T-9 裁定 2):chosen_supply = (角色,
    装备名列表),列表任一件名命中 DIAMOND_EQUIP_NAMES → diamond_count
    +1;不含 → 不发(两态同 backend 直驱;live 写端 = 画面 op 确认即写,
    sim 决策链未接 = chosen 恒 None 死分支维持)。OCR 误读边(列表名不
    匹配漏发)= fail-visible,装备/钻数观察下一帧暴露,披露 4 已登记。"""
    b = _backend(5)
    try:
        gs = b.gs
        gs.write_logic(gs.chosen_supply, ('', ('折叠小刀', '财富宝钻')),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        b._on_supply_picked()
        assert gs.diamond_count.value == 1, '列表含钻名 → 宝钻发放分支 +1'
        gs.write_logic(gs.chosen_supply, ('', ('折叠小刀', '垃圾袋')),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        b._on_supply_picked()
        assert gs.diamond_count.value == 1, '列表不含钻名 → 不发'
    finally:
        uninstall_backend()


def test_env_grant_non_diamond_equip_skips_callback(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """宝钻裁决只认财富宝钻(接入调用层):登记表换发非宝钻装备 → 触发照常
    (发放 + done),回调三写零发生(回调内非财富宝钻早退,接入调用不预判)。"""
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
    """败向口径:结算分支以带符号 streak 调触发检查(败 −1 传入,kernel
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
        assert seen, '触发检查在结算分支被调用'
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


# ============================================================ 3.4 扑满结算统一公式接入调用测试
# (T-6 经济过热,2026-10-10 用户裁定:战斗结算收入 = 统一公式「基础+息
#  +连胜成分,战败无」;扑满胜负接入连胜账 = 胜+1/败清零;收入递延至
#  结算分支落账,基数 = 窗口开快照即轮初口径。)

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
    """扑满胜局:备战帧(开战前)金不含本节点收入(递延断言);结算分支一次
    落账 = 基础+进轮连胜金+息;连胜账 0→1→2(胜局计数,用户裁定)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        REWARD_BASE_GOLD_BY_ROUND,
    )
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
        # r2 备战:r2 收入同样递延(金停在 r1 落账值);窗收尾自动弹店
        _node_advance_feed(gs, trigger='settle_confirm')
        assert b.screen_identity() == SCREEN_SHOP, '(1,2) 窗收尾自动弹店'
        _close_shop_feed(b)
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
    from sr_od.application.currency_war.kernel.cw_economy import (
        REWARD_BASE_GOLD_BY_ROUND,
    )
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
        assert b.screen_identity() == SCREEN_SHOP, '(1,2) 窗收尾自动弹店'
        _close_shop_feed(b)
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
    from sr_od.application.currency_war.kernel.cw_economy import (
        REWARD_BASE_GOLD_BY_ROUND,
    )
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


def test_non_piggy_reward_always_wins_no_hp_loss(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """普通奖励关恒胜白拿(奖励关不需要战力 = 用户账本 408 行裁定,
    单一源 = kernel cw_reward_node.py 裁定权威行):强制败局结算输出
    (−23)也被结算分支改写为胜——hp 不掉、败态不登记 pending_loss、
    连胜账不动(奖励关不计连胜);扑满局不受本改写(掷点语义保留,
    见 test_piggy_loss_base_interest_only_and_streak_reset)。"""
    b = SimBackend(seed=35, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    try:
        gs = b.gs
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        gs.write_logic(gs.invest_env_opts,
                       ['轮岗', '头彩', _PIGGY_ENV],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_env_param(
            gs, SimpleNamespace(idx=0), _SIG)
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
        assert b.screen_identity() == SCREEN_PREP
        hp0 = int(gs.hp.value or 0)
        streak0 = int(gs.streak.value or 0)
        _force_settle(monkeypatch, won=False)   # 强制败局输出(−23)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE
        assert int(gs.hp.value or 0) == hp0, '奖励关恒胜:不掉血'
        assert int(gs.streak.value or 0) == streak0, '奖励关不计连胜'
        assert (gs.pending_loss.value is None), '胜局不登记败态'
    finally:
        uninstall_backend()


# ============================================================ 观察生成器
# (sim 统一 3.3:每生成器单测 = 构造世界态 → backend.observe(档名) 生成
#  obs(生产路径 = 注册表分派,产物经同名 report_screen_* 落容器)→ 容器
#  字段断言;设计依据 = sim- + flow-seam 接缝契约。)

def _open_to_first_window(b: SimBackend, *, env_present: bool = False) -> None:
    """开局序列推进到 P1r1(无环境)或投资环境屏(env_present=True)。"""
    if env_present:
        b.cfg = RunConfig(selected_difficulty='A8', enemy_difficulty=108,
                          env_present=True)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')


def _obs_step(b: SimBackend) -> None:
    """观察生成器走局单步驱动(按呈现屏分派到对应真实写端;与
    _drive_step 同形,唯策略选卡不注入 rng —— 生成器测试面与采样值无关)。"""
    screen = b.screen_identity()
    gs = b.gs
    if screen == SCREEN_SUPPLY:
        opts = gs.supply.value.options
        gs.write_logic(gs.chosen_supply,
                       ('', (opts[0].equip, *opts[0].extra_equips)),
                       produced_by='Test', evidence='t:chosen', sig=_SIG)
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=0, char_name='', norm_item=opts[0].equip),
            _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SHOP:
        _close_shop_feed(b)
    elif screen == SCREEN_INVEST_STRATEGY:
        opts = gs.invest_strategy_opts.value
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=opts[0]), _SIG,
            session=SimpleNamespace())
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SETTLE:
        _node_advance_feed(gs, trigger='settle_confirm')
    elif screen == SCREEN_PLANE_TRANSITION:
        b._handle_click_source(SCREEN_PLANE_TRANSITION, '区域-空白点击')
    elif screen == SCREEN_BOSS_BRIEFING:
        b._handle_click_source(SCREEN_BOSS_BRIEFING, '区域-空白点击')
    elif screen == SCREEN_ENCOUNTER:
        out = report_action_pick_encounter_param(gs, SimpleNamespace(idx=0),
                                                 _SIG)
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_MEGASTAR:
        out = report_action_pick_megastar_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_PLANNER:
        out = report_action_pick_planner_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_PREP:
        _start_battle_feed(gs)
    else:
        raise AssertionError(f'未知呈现屏 {screen}')


def _walk_to(b: SimBackend, plane: int, round_num: int,
             cap: int = 64) -> None:
    """局推进到目标节点窗(P1r1 起点;防失控 cap)。"""
    for _ in range(cap):
        if b.done:
            raise AssertionError('局已终未达目标节点窗')
        node = b.gs.node.value
        if node is not None and (node.plane, node.round_num) == (plane,
                                                                 round_num):
            return
        _obs_step(b)
    raise AssertionError('超过推进步数上限未达目标节点窗')


def test_registry_covers_golden_path_checklist_exactly() -> None:
    """金路径清单覆盖核对:注册表键集与 13 档名清单零差零冗余(清单
    逐行有生成器;清单外注册 = 辖域外屏混入,同样拒绝)。"""
    assert set(registered_screens()) == set(GOLDEN_PATH_SCREEN_NAMES)
    assert len(registered_screens()) == 13


def test_unregistered_screen_raises_named_error() -> None:
    """状态机呈现未注册屏 = LookupError 具名响错(防静默失真测试):金路径
    清单外的档名(如大厅/武装箱弹窗)观察请求必须响亮拒绝,禁产空产物。"""
    b = _backend()
    try:
        assert b.screen_identity() == SCREEN_BRIEFING   # 简报已登记,先确认基线
        b.observe(SCREEN_BRIEFING)
        with pytest.raises(LookupError, match='未注册'):
            b.observe('货币战争-大厅')
    finally:
        uninstall_backend()


def test_gen_briefing_round_trips_three_readings() -> None:
    """简报生成器:三读数(词缀/位面序 boss/难度)自容器直填,经同名
    report 落容器(读到非空恒覆写,同值幂等)。"""
    b = _backend()
    try:
        assert b.screen_identity() == SCREEN_BRIEFING
        obs = b.observe(SCREEN_BRIEFING)
        gs = b.gs
        assert obs.on_screen is True
        assert obs.enemy_affixes == list(gs.enemy_affixes.value)
        assert obs.plane_bosses == list(gs.plane_bosses.value)
        assert obs.enemy_difficulty == gs.enemy_difficulty.value
        # report 分支容器断言:同值覆写后容器与 obs 逐位一致(生成器 →
        # report → 容器全链走通)。
        assert gs.enemy_affixes.value == obs.enemy_affixes
    finally:
        uninstall_backend()


def test_gen_invest_env_candidates_from_container_slot() -> None:
    """投资环境生成器:候选名自容器 opts 槽(M02 采样写点),report 分支
    同值回写幂等;x = 下标派生合成值(身份键,无画面语义)。"""
    b = _backend(seed=11, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    try:
        _open_to_first_window(b, env_present=True)
        assert b.screen_identity() == SCREEN_INVEST_ENV
        opts_before = b.gs.invest_env_opts.value
        assert opts_before is not None and len(opts_before) == 3
        obs = b.observe(SCREEN_INVEST_ENV)
        assert [n for n, _x in obs.options] == opts_before
        assert [x for _n, x in obs.options] == [10, 20, 30]
        assert b.gs.invest_env_opts.value == opts_before, 'report 分支同值回写'
    finally:
        uninstall_backend()


def test_gen_prep_ore_substate_control_signals() -> None:
    """备战生成器·晶矿子态:P1r1 = 奖励节点 → 备战档 ore 子态分派;
    控制信号(shop_open=False/event_overlay=None/substate 标注)随观察
    产出(flow-seam §3);node_path_chain = None 诚实缺位 → report 零写。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        assert b.screen_identity() == SCREEN_PREP
        assert b._sub == 'ore'
        obs = b.observe(SCREEN_PREP)
        assert obs.prep.substate == {'sub': 'ore'}
        assert obs.prep.shop_open is False
        assert obs.prep.event_overlay is None
        assert obs.event_overlay is None
        assert obs.node_path_chain is None
    finally:
        uninstall_backend()


def test_gen_prep_wait_one_one_variant_dispatch() -> None:
    """备战生成器·wait_one_one 变体:同档名子态内部分派(子态不设独立
    注册键);惰性完成前观察 = wait_one_one 标注。"""
    b = _backend()
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        # 注意:screen_identity() 问询会惰性完成等待变体(进 P1r1),
        # 本测必须只查子态载荷、不走问询口。
        assert b._sub == 'wait_one_one'
        obs = b.observe(SCREEN_PREP)
        assert obs.prep.substate == {'sub': 'wait_one_one'}
    finally:
        uninstall_backend()


def test_gen_shop_mirrors_container_receipt_face() -> None:
    """商店生成器:入口回执同面镜像域(gold/hp/level/board/shop/plane/
    round/node_type)自容器直填;开店点击源进商店档后观察合法。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        b._handle_click_source(SCREEN_PREP, '按钮-商店')
        assert b.screen_identity() == SCREEN_SHOP
        obs = b.observe(SCREEN_SHOP)
        gs = b.gs
        assert obs.gold == gs.gold.value
        assert obs.gold_readable is True
        assert obs.hp == gs.hp.value and obs.hp_trusted is True
        assert obs.level == gs.level.value
        node = gs.node.value
        assert (obs.plane, obs.round_num) == (node.plane, node.round_num)
        assert obs.node_type == node.kind
        assert obs.board == dict(gs.board.value or {})
        assert obs.shop == list(gs.shop.value.cards)
    finally:
        uninstall_backend()


def test_gen_battle_wait_on_screen_at_settle_window() -> None:
    """battle_wait 生成器(battle_wait 档名 = sim 战斗窗口呈现屏):出战
    上报 → 结算窗瞬时呈现,生成器答 on_screen;report 为统一形态占位
    (零容器写点,导入契约不炸)。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        _start_battle_feed(b.gs)
        assert b.screen_identity() == SCREEN_SETTLE
        obs = b.observe(SCREEN_SETTLE)
        assert obs.on_screen is True
    finally:
        uninstall_backend()


def test_gen_supply_options_and_refresh_left() -> None:
    """补给生成器:选项载荷自容器呈现写点回读,refresh_left = 容器剩余
    语义观察真值(入口 left=1);report 分支同值回写幂等。"""
    b = _backend(seed=1013)
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        _walk_to(b, 1, 5)
        assert b.screen_identity() == SCREEN_SUPPLY
        obs = b.observe(SCREEN_SUPPLY)
        gs = b.gs
        assert obs.in_node is True
        assert obs.options == list(gs.supply.value.options)
        assert obs.refresh_left == gs.supply_refresh_left.value == 1
        assert gs.supply.value.options == obs.options, 'report 分支同值回写'
    finally:
        uninstall_backend()


def test_gen_invest_strategy_candidates_at_offer_window() -> None:
    """投资策略生成器:P1r3 = U07 固定 offer 日程 → 策略屏呈现,候选名
    自容器 opts 槽回读;逐卡刷新计数自容器按槽名现读(默认局呈现写点
    落基准每卡 1 次,2026-10-19 用户裁定批接入呈现)。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        _walk_to(b, 1, 3)
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY
        opts_before = b.gs.invest_strategy_opts.value
        assert opts_before is not None and len(opts_before) == 3
        obs = b.observe(SCREEN_INVEST_STRATEGY)
        assert obs.entry_ok is True
        assert [n for n, _x, _y in obs.options] == opts_before
        assert obs.refresh_slots == [(1, 10, 20), (1, 20, 20), (1, 30, 20)], \
            '默认局逐卡基准 1 次(呈现写点 → 容器 → 生成器现读)'
        assert b.gs.strategy_refresh_left.value == dict.fromkeys(opts_before, 1), \
            '观察写端逐卡计数落容器'
        assert b.gs.invest_strategy_opts.value == opts_before
    finally:
        uninstall_backend()


def test_gen_boss_briefing_direct_set_idempotent() -> None:
    """boss 简报生成器:obs 门判定 + report 半部 boss 类型直定(目标 =
    现 hist;sim 侧节点锚定已写 boss 类型,直定同值幂等不炸)。"""
    b = _backend(seed=61)
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        _walk_to(b, 1, 9)
        assert b.screen_identity() == SCREEN_BOSS_BRIEFING
        hist_before = b.gs.node_hist_pos
        obs = b.observe(SCREEN_BOSS_BRIEFING)
        assert obs.on_screen is True
        assert b.gs.node_hist_pos == hist_before
        assert b.gs.node.value.kind == 'boss'
    finally:
        uninstall_backend()


def test_gen_plane_transition_chain_absent_honest() -> None:
    """位面过渡生成器:链值诚实缺位(sim 不产底部全亮行识别面)→
    report 按「chain 缺不写」防御语义零写;P2r1 位面过渡屏呈现态。"""
    b = _backend(seed=61)
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        b._enter_node_window((2, 1))
        assert b.screen_identity() == SCREEN_PLANE_TRANSITION
        path_before = b.gs.node_path.value
        obs = b.observe(SCREEN_PLANE_TRANSITION)
        assert obs.on_screen is True
        assert obs.chain is None
        assert b.gs.node_path.value == path_before, '链缺零写(诚实缺位)'
    finally:
        uninstall_backend()


def test_gen_encounter_tier_options_from_container() -> None:
    """遭遇生成器:档位候选自容器呈现写点回读(四档集);report 分支同值
    回写幂等。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        _walk_to(b, 1, 7)
        assert b.screen_identity() == SCREEN_ENCOUNTER
        obs = b.observe(SCREEN_ENCOUNTER)
        assert obs.options == list(b.gs.encounter.value.options)
        assert len(obs.options) == 4, 'U22 四档集'
        assert b.gs.encounter.value.options == obs.options
    finally:
        uninstall_backend()


def test_gen_box_candidates_and_points_same_order() -> None:
    """开箱生成器(武装箱选择档):候选名 + 点击点自容器呈现写点回读,
    同序等长(report 写端守卫同契约);选定分支消费面 = 动作 op 按 idx 取
    xy(合成坐标,身份键)。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        open_out = report_action_open_box_param(
            b.gs, CwActionOpenBoxParam(), _SIG)
        cw_sim_ports.declare_world(open_out.world_decl)
        assert b.screen_identity() == SCREEN_BOX
        names = b.gs.box_card_names.value
        points = b.gs.box_card_names_xy.value
        obs = b.observe(SCREEN_BOX)
        assert obs.on_screen is True
        assert obs.card_names == list(names)
        assert obs.points == list(points)
        assert len(obs.card_names) == len(obs.points) == 4
    finally:
        uninstall_backend()


def test_gen_megastar_candidates_from_container() -> None:
    """巨星生成器:候选(含持星徽贡献与合成坐标)自容器呈现写点回读;
    事实事件触发的呈现态下观察合法。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        # 3.4:呈现数据源 = 容器登记(逻辑写经值回调判据 register;
        # 观察写零回调)。
        b.gs.write_logic(
            b.gs.deployed,
            _dvs([Unit(char_id='大丽花', star=1),
                  Unit(char_id='加拉赫', star=1)], []),
            produced_by='test', evidence='t',
            sig=ChannelSig(family='logic_action', actor='test',
                           mode='compute'))
        assert b.screen_identity() == SCREEN_MEGASTAR
        opts_before = b.gs.megastar_opts.value
        assert opts_before
        obs = b.observe(SCREEN_MEGASTAR)
        assert obs.in_node is True
        assert obs.options == list(opts_before)
        assert b.gs.megastar_opts.value == list(opts_before)
    finally:
        uninstall_backend()


def test_gen_planner_empty_bucket_writes_like_live() -> None:
    """planner 生成器:两卡选项自容器回读;sim 呈现写点缺位 = 空桶,
    与实机「恒写两卡 OCR 桶,空桶照写」语义同形(report 无空门直写)。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        slots: list[BenchSlot | None] = [None] * 9
        slots[0] = BenchSlot(kind='unit', unit=Unit(char_id='银狼LV.999',
                                                    star=1))
        b.gs.observe(b.gs.bench, cw4_bview(slots), sig=_SIG_OBS)
        # 3.4:呈现数据源 = 容器登记(逻辑写经值回调判据 register;
        # 观察写零回调)。
        b.gs.write_logic(
            b.gs.deployed, _dvs([Unit(char_id='银狼LV.999', star=2)], []),
            produced_by='test', evidence='t',
            sig=ChannelSig(family='logic_action', actor='test',
                           mode='compute'))
        assert b.screen_identity() == SCREEN_PLANNER
        obs = b.observe(SCREEN_PLANNER)
        assert obs.on_screen is True
        assert obs.options == list(b.gs.planner_opts.value or [])
        assert b.gs.planner_opts.value is not None, '空桶照写(无空门直写)'
    finally:
        uninstall_backend()


# ============================================================ 商店牌面写回
# (观察层商店缺口修复:牌面 = 节点级持久事实(发牌时定),开店呈现时写回
#  gs.shop(对偶实机「每次进店读屏」);关店清呈现不清记录;节点切换新发
#  牌覆盖记录。病理:3.6 会话模型合法产生同节点两次进店,第二次进店
#  gs.shop 空 → decide_shop_action 按 fail-loud 契约崩。)

def _drive_to_first_prep(b: SimBackend) -> None:
    """驱动到 P1r1 备战(简报下一步 → wait_one_one 惰性完成进节点窗)。"""
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP


def _close_shop_feed(b: SimBackend) -> None:
    """关店动作上报 + 声明喂入(动作 op「上报后一行喂入」同形)。"""
    out = report_action_close_shop_param(b.gs, CwActionCloseShopParam(),
                                         _SIG)
    assert out.applied, f'关店上报未落账: {out.reason!r}'
    cw_sim_ports.declare_world(out.world_decl)


def _open_shop(b: SimBackend) -> None:
    """开店点击(备战按钮-商店;点击源直驱)。"""
    b._handle_click_source(SCREEN_PREP, '按钮-商店')


def test_same_node_second_visit_restores_payload() -> None:
    """同节点二次进店可观察:开店 → 关店 → 再开店 → gs.shop 牌面在且
    同值(3.6 会话模型合法形态,修复主径)。

    首访 = 节点窗起发牌后在屏态,开店保持现值零写;关店清呈现;再
    开店以节点级记录补写——实机对偶 = live 漏斗每次进店重读屏。"""
    b = _backend(seed=7)
    try:
        _drive_to_first_prep(b)
        gs = b.gs
        first = gs.shop.value
        assert first is not None, '前置:节点窗起发牌已写容器'

        _open_shop(b)
        assert b.screen_identity() == SCREEN_SHOP, '开店呈现商店态'
        assert gs.shop.value == first, '首访在屏态保持现值(零写回)'
        obs = b.observe(SCREEN_SHOP)
        assert obs.shop == list(first.cards), '首访观察产物 = 发牌牌面'

        _close_shop_feed(b)
        assert gs.shop.value is None, '关店清呈现(payload 离屏)'
        assert b.screen_identity() == SCREEN_PREP, '纯转移交回备战'

        _open_shop(b)
        assert gs.shop.value is not None, '再开店必须可观察(修复面:缺口即此处崩)'
        assert gs.shop.value == first, '牌面 = 节点级记录同值'
        obs2 = b.observe(SCREEN_SHOP)
        assert obs2.shop == list(first.cards), '再访观察产物同值(策略决策面)'
    finally:
        uninstall_backend()


def test_node_switch_new_deal_overrides_record() -> None:
    """节点切换发牌更新:推进到下一节点 → 新发牌覆盖记录 → 再开店写回
    = 当前节点牌面(非旧节点残值);顺带校验记录与呈现的分界(关店离屏
    期间新发牌在屏,记录跟随新值)。"""
    b = _backend(seed=7)
    try:
        _drive_to_first_prep(b)
        gs = b.gs
        first = gs.shop.value
        assert first is not None, '前置:P1r1 发牌在屏'

        _close_shop_feed(b)
        assert gs.shop.value is None, '离屏后再推进(记录存活,呈现清空)'

        # 节点推进(P1r1 奖励节点:出战 → 结算确认;声明化单轨同形)
        out = report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
        cw_sim_ports.declare_world(out.world_decl)
        adv = report_node_advance(gs, trigger='settle_confirm')
        assert adv.applied, f'节点推进未落账: {adv.reason!r}'
        cw_sim_ports.declare_world(adv.world_decl)
        second = gs.shop.value
        assert second is not None, '前置:节点切换自动全刷新发牌'
        assert second != first, '前置:新旧节点发牌分形(记录覆盖可判)'
        assert b.screen_identity() == SCREEN_SHOP, 'P1r2 窗收尾自动弹店'

        _close_shop_feed(b)
        assert gs.shop.value is None
        _open_shop(b)
        assert gs.shop.value == second, \
            '写回 = 当前节点发牌(记录随节点窗新发牌覆盖)'
    finally:
        uninstall_backend()


# ============================================================ 装配接缝
# (sim 端口接口契约 + CwOperation 覆写面 + controller 桩,flow-seam
#  §1/§2:端口槽缺省关(不装后端 = 纯实机,读屏改道 helper 走原读链);
#  单装配纪律;sim 模式 CwOperation 三条分支;controller 桩直连真实 IO
#  触碰即 AssertionError(双保险兜底)。)

#: 哨兵帧形状(1080p 基准,area 裁剪不崩、识别恒空 = 双保险第一线)
_SENTINEL_SHAPE = (1080, 1920, 3)
#: 真实建档(screen_info currency_war_battle_prep.yml):点击分支测试用
_PREP_SCREEN = '货币战争-备战'


class _ProbeOp(CwOperation):
    """探针 op:直调基类覆写面(不走 execute 循环,零运行态前置)。"""

    def __init__(self, ctx):
        CwOperation.__init__(self, ctx, op_name='sim-seam-probe',
                             need_check_game_win=False)

    @operation_node(name='probe', is_start_node=True)
    def run(self) -> OperationRoundResult:
        return self.round_success()


@pytest.fixture
def _sim_ctx(test_context, monkeypatch):
    """测试 ctx + controller 桩(monkeypatch 自动还原,防污染共享 ctx)。

    桩兜底语义:测试体内任何直连 controller 路径未改道 = 撞桩即炸,
    测试红 = 覆写面漏改,真值可见。
    """
    monkeypatch.setattr(test_context, 'controller', SimControllerStub())
    return test_context


def test_ports_default_off_and_live_read_chain():
    """端口缺省关:不装后端 = 纯实机(判据 1 的缺省前提)。

    读屏改道 helper 未装配时执行原读链(live_read),不触后端口。"""
    assert sim_backend_installed() is False
    assert cw_sim_ports.get_sim_backend() is None
    marker = object()
    assert sim_or_live_observation(_PREP_SCREEN, lambda: marker) is marker


def test_install_discipline_duplicate_raises_uninstall_idempotent():
    """单装配纪律(端口协议测试):重复安装 raise;uninstall 幂等;
    卸载后可再装;teardown 卸载复位。"""
    with sim_backend_fixture() as backend:
        assert sim_backend_installed() is True
        assert cw_sim_ports.get_sim_backend() is backend
        with pytest.raises(RuntimeError, match='重复安装'):
            install_sim_backend(MinimalSimBackend())
    # teardown 必卸
    assert sim_backend_installed() is False
    # uninstall 幂等 + 卸载后可再装
    uninstall_sim_backend()
    assert sim_backend_installed() is False
    with sim_backend_fixture():
        assert sim_backend_installed() is True


def test_screenshot_returns_sentinel_without_touching_controller(_sim_ctx):
    """sim 哨兵帧:装配后端后 CwOperation.screenshot 返回 1080p 空白帧、
    last_screenshot 置位,全程不触 controller(ctx.controller = 桩,触即炸)。
    空白语义:漏改的帧消费者在哨兵帧上真识别 = 恒未找到(双保险第一线)。"""

    with sim_backend_fixture():
        op = _ProbeOp(_sim_ctx)
        frame = op.screenshot()
        assert frame.shape == _SENTINEL_SHAPE
        assert not frame.any()
        assert op.last_screenshot is frame
        assert op.last_screenshot_time > 0


def test_direct_controller_access_raises(_sim_ctx):
    """controller 桩(双保险兜底):sim 装配下直连 controller 任何接口
    = AssertionError 响亮(报「sim 模式触碰真实 IO」)。"""
    with sim_backend_fixture():
        op = _ProbeOp(_sim_ctx)
        with pytest.raises(AssertionError, match='sim 模式触碰真实 IO'):
            _ = op.ctx.controller.click
        with pytest.raises(AssertionError, match='sim 模式触碰真实 IO'):
            _ = op.ctx.controller.game_win


def test_click_leg_archive_point_and_until_polling(_sim_ctx):
    """sim 点击分支(机械镜契约):无 until = 档案点位直成功(node_clicked
    置位);带 until = 先点击后 round_wait,转移证据可见后下一轮
    round_success;轮询重入不重复进后端 click_answer(点击分支不重发);
    屏门 = 问询屏区域可见才点得着(实机「本帧找到才点得着」对偶,防
    越屏偷跑推进);区域未建档 = round_fail 响亮。"""
    click_area = '按钮-商店'
    click_target = (_PREP_SCREEN, click_area)
    until_target = ('货币战争-商店', '标识-商店牌面')
    with sim_backend_fixture() as backend:
        op = _ProbeOp(_sim_ctx)
        # 屏门前置:按钮在本帧可见(点得着的前提)
        backend.visible_areas.add(click_target)
        # ① 无 until:直成功 + 后端收到恰一次点击
        r1 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name=click_area)
        assert r1.result is OperationRoundResultEnum.SUCCESS
        assert op.node_clicked is True
        assert backend.clicked == [click_target]
        # ② until 未满足:round_wait 轮询,且不重复进后端(点击分支已成功)
        r2 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name=click_area,
            until_find_all=[until_target])
        assert r2.result is OperationRoundResultEnum.WAIT
        assert backend.clicked == [click_target]
        # ③ 转移证据可见:下一轮 round_success(轮询分支直接问 visible)
        backend.visible_areas.add(until_target)
        r3 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name=click_area,
            until_find_all=[until_target])
        assert r3.result is OperationRoundResultEnum.SUCCESS
        assert backend.clicked == [click_target]
        # ④ 屏门拒点:按钮不可见(世界已切走)→ retry(防驻留型动作 op
        # 越屏偷跑推进,冒烟批阻断二实证形态; MinimalSimBackend 先记录
        # 请求再委托机械镜,拒绝在镜像层发生,故 clicked 记录增长)
        backend.visible_areas.discard(click_target)
        r4 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name=click_area)
        assert r4.result is OperationRoundResultEnum.RETRY
        assert len(backend.clicked) == 2, '第二次点击到达后端但被屏门拒绝'
        # ⑤ 区域未建档:fail 响亮(与实机 AREA_NO_CONFIG 同形)
        r5 = op.round_by_find_and_click_area(
            screen_name=_PREP_SCREEN, area_name='不存在的区域')
        assert r5.result is OperationRoundResultEnum.FAIL


def test_find_area_leg_visible_query(_sim_ctx):
    """sim find_area 分支:端口 visible 应答(可见 = success,不可见 =
    retry),不触截图识别链。"""
    area = (_PREP_SCREEN, '按钮-商店')
    with sim_backend_fixture() as backend:
        op = _ProbeOp(_sim_ctx)
        r_miss = op.round_by_find_area(None, area[0], area[1])
        assert r_miss.result is OperationRoundResultEnum.RETRY
        backend.visible_areas.add(area)
        r_hit = op.round_by_find_area(None, area[0], area[1])
        assert r_hit.result is OperationRoundResultEnum.SUCCESS


# (事实事件缺省关测试已随事实事件槽退役删除:
#  事实事件槽本体与全部广播调用点同批删除,sim 呈现 =
#  容器登记 + 问询时点懒呈现,由本文件懒呈现两测试覆盖。)


def test_identity_helper_filters_by_screen_list():
    """画面身份读点改道 helper(sim 统一 3.4;flow-seam 附录 A.2
    「sim 画面身份归 screen_identity」):装配后 = 状态机答口,且清单外
    返回 None(与实机 get_match_screen_name 清单过滤同形,备战双锚默认
    分支不受扰);缺省关 = 原识别链零行为变化。"""
    with sim_backend_fixture(MinimalSimBackend(screen='货币战争-补给')):
        assert cw_sim_ports.sim_or_live_identity(
            ('货币战争-补给',), lambda: 'LIVE') == '货币战争-补给'
        assert cw_sim_ports.sim_or_live_identity(
            (_PREP_SCREEN,), lambda: 'LIVE') is None
    assert cw_sim_ports.sim_or_live_identity(
        (_PREP_SCREEN,), lambda: 'LIVE') == 'LIVE'


def test_mechanical_io_allowed_default_true_sim_false():
    """机械 IO 分支检查口(直连旁路 port 检查的共用判定,flow-seam §2):
    实机(未装配)= True 零行为变化;sim 装配后 = False(机械执行分支静默
    跳过,自上报照走)。"""
    assert cw_sim_ports.mechanical_io_allowed() is True
    with sim_backend_fixture():
        assert cw_sim_ports.mechanical_io_allowed() is False
    assert cw_sim_ports.mechanical_io_allowed() is True


def test_action_rng_provider_seeded_on_install_reset_on_uninstall():
    """动作分支采样 rng 注入槽(T-2 偏差申报的归属点接入调用):SimBackend
    install_backend 接通提供槽(流键 rng,同 seed 同调用序确定性);
    uninstall_backend 复位 = 实机未播种口径零变化。断言键面含
    'ore_reward_gen'(挂接生成分支键随 action_sampling_rng 首调自动生效,
    装配方零改动)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        provided_action_rng,
    )

    assert provided_action_rng('collect_ore') is None, '缺省必须关'
    assert provided_action_rng('ore_reward_gen') is None, '缺省必须关'
    install_backend(SimBackend(seed=9, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108)))
    try:
        first = provided_action_rng('collect_ore').random()
        gen_first = provided_action_rng('ore_reward_gen').random()
    finally:
        uninstall_backend()
    assert provided_action_rng('collect_ore') is None, '卸载必须复位'
    assert provided_action_rng('ore_reward_gen') is None, '卸载必须复位'
    install_backend(SimBackend(seed=9, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108)))
    try:
        second = provided_action_rng('collect_ore').random()
        gen_second = provided_action_rng('ore_reward_gen').random()
    finally:
        uninstall_backend()
    assert first == second, '同 seed 同键序采样必须一致(确定性)'
    assert gen_first == gen_second, 'ore_reward_gen 键同 seed 确定性'


def test_equip_env_pick_sim_full_chain() -> None:
    """即时装备环境 sim 全链(迭代 2026-09-23-invest-effects-calc T-31
    设计 §4 锁 6):播种选红钻贵族 → equips = ['红钻']、bench = 4 开局
    手牌 + 1 箱(supply_box);开箱链现役承接新箱(箱画面候选 → 选定 →
    所得经获得链入栏,equips 2 件);同 seed 重放确定。装备入账分支零采样,
    重放确定性不经 rng 注入。"""
    def _run() -> list[str]:
        b = _env_pick_backend()
        try:
            _seed_and_pick_env(b, '红钻贵族')
            assert list(b.gs.equips.value) == ['红钻'], '选卡后装备入栏'
            boxes = [s for s in b.gs.bench.value.slots
                     if s is not None and s.kind == 'supply_box']
            assert len(boxes) == 1, '4 开局手牌 + 1 箱'
            # 开箱链现役承接(环境送的箱 = 标准 supply_box,与火药味同形)
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
            assert cands[2] in b.gs.equips.value, '开箱所得入栏(获得链)'
            assert '红钻' in b.gs.equips.value, '环境装备仍在栏'
            return list(b.gs.equips.value)
        finally:
            uninstall_backend()

    first = _run()
    second = _run()
    assert first == second, '同 seed 重放确定(装备入账分支零采样)'


def test_equip_env_pick_sim_full_chain_blue_diamond() -> None:
    """即时装备环境 sim 全链·蓝钻行(T-32 设计 §4 锁 6):播种选蓝钻贵族
    → equips = ['蓝钻']、bench = 4 开局手牌 + 1 箱(supply_box);开箱链
    现役承接新箱(箱画面候选 → 选定 → 所得经获得链入栏,equips 2 件);
    同 seed 重放确定(装备入账分支零采样,重放确定性不经 rng 注入)。"""
    def _run() -> list[str]:
        b = _env_pick_backend()
        try:
            _seed_and_pick_env(b, '蓝钻贵族')
            assert list(b.gs.equips.value) == ['蓝钻'], '选卡后装备入栏'
            boxes = [s for s in b.gs.bench.value.slots
                     if s is not None and s.kind == 'supply_box']
            assert len(boxes) == 1, '4 开局手牌 + 1 箱'
            # 开箱链现役承接(环境送的箱 = 标准 supply_box,与红钻贵族同形)
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
            assert cands[2] in b.gs.equips.value, '开箱所得入栏(获得链)'
            assert '蓝钻' in b.gs.equips.value, '环境装备仍在栏'
            return list(b.gs.equips.value)
        finally:
            uninstall_backend()

    first = _run()
    second = _run()
    assert first == second, '同 seed 重放确定(装备入账分支零采样)'


def test_delayed_item_open_window_discharge_grants_coexist_replay_safe(
        ) -> None:
    """倒计时件开盒 sim 收尾(T-34 命运礼物设计 §2.4/§4 锁 6,迭代
    2026-09-23-invest-effects-calc):选命运礼物 → 队列登记 (2,4) 解锁位
    (登记零席位写);(1,x) 节点窗与位面过渡屏呈现期未到点条目不弹除;
    (2,1) 节点窗打开 → 到点条目弹除且与定时道具发放同窗并存零互扰
    (特权武装箱照常落备战席,开盒通道零 supply_box 落位 = 零席位写
    集成面);位面过渡点空白点击重放 → 窗口幂等守卫住,零双弹零双落。
    断言面 = 不变量非中间态:完胜回退分支在 sim 长驱中真实生效(奖励关
    白拿帧等 → 解锁位逐帧回退),弹除时点随 seed 漂移是设计行为,故
    只锁「保留集全部未到点(unlock > 当前窗)」与总量守恒,不锁队列
    中间值。seed 61 通道沿定时发放用例:局必经 P1r9 与位面过渡。"""
    b = SimBackend(seed=61, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        gs = b.gs
        gs.write_logic(gs.invest_env_opts,
                       ['命运礼物', '轮岗', '头彩'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        env_out = report_action_pick_invest_env_param(
            gs, SimpleNamespace(idx=0), _SIG)
        assert env_out.applied
        assert gs.active_env.value == '命运礼物'
        cw_sim_ports.declare_world(env_out.world_decl)
        assert gs.pending_item_opens.value == (('惊喜盒', (2, 4)),), \
            '到手分支入队 (1,1)+12 步,零席位写(无 supply_box 落位)'
        # 播种早到条目 (1,2)(下一窗即到点,调用点真触发证据)+ 定时道具
        # (2,1) 发放项(同窗并存输入;opens 播种 = 全表覆盖写,保留
        # (2,4) 条目)
        gs.write_logic(gs.pending_item_opens,
                       (('惊喜盒', (1, 2)), ('惊喜盒', (2, 4))),
                       produced_by='Test', evidence='t:queue', sig=_SIG)
        grants_queued = [{'env': '特权阶级', 'plane': 2, 'round_num': 1,
                          'item': '特权武装箱'}]
        gs.write_logic(gs.pending_item_grants, grants_queued,
                       produced_by='Test', evidence='t:grants', sig=_SIG)
        b._maybe_finish_wait()
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 1)
        assert len(gs.pending_item_opens.value) == 2, '(1,1) 窗未到点零弹'
        # 先行推进一节点:(1,2) 窗收尾弹除到点条目(调用点真触发),
        # 零席位落位
        _start_battle_feed(gs)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 2)
        assert len(gs.pending_item_opens.value) == 1, \
            '(1,2) 窗弹除到点条目((1,2) 早到项),未到点保留'
        boxes_early = [s for s in gs.bench.value.slots
                       if s is not None and s.kind == 'supply_box']
        assert boxes_early == [], '开盒零席位写(无 supply_box 落位)'
        # 推进至 P1r9 BOSS 简报 → 出战结算 → (2,1) 位面过渡
        for _ in range(64):
            if b.done or b.screen_identity() == '货币战争-BOSS简报':
                break
            if b.screen_identity() == SCREEN_SETTLE:
                _node_advance_feed(gs, trigger='settle_confirm')
            else:
                _drive_step(b, 61)
        assert b.screen_identity() == '货币战争-BOSS简报'
        b._handle_click_source('货币战争-BOSS简报', '区域-空白点击')
        assert b.screen_identity() == SCREEN_SHOP, \
            '简报点空白关模态回备战自动弹店(不结算)'
        _close_shop_feed(b)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, 'boss 战由出战动作触发'
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (2, 1)
        assert b.screen_identity() == '货币战争-位面过渡'
        queue_at_transition = gs.pending_item_opens.value
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        assert b.screen_identity() == SCREEN_SHOP, '(2,1) 节点窗收尾自动弹店'
        _close_shop_feed(b)
        assert b.screen_identity() == SCREEN_PREP
        queue_after = gs.pending_item_opens.value
        assert all(unlock > (2, 1) for _n, unlock in queue_after), \
            '不变量:(2,1) 窗后保留集全部未到点(到了及以后都算的反面)'
        assert len(queue_after) <= len(queue_at_transition), \
            '(2,1) 窗只弹不加(总量守恒半边)'
        assert gs.pending_item_grants.value == [], \
            '定时道具发放照常(同窗并存零互扰,既有通道回归)'
        boxes = [s for s in gs.bench.value.slots
                 if s is not None and s.kind == 'supply_box']
        assert len(boxes) == 1, \
            '恰 1 箱落席(定时道具通道);开盒通道零席位写'
        assert gs.overflow_card.value in ('', None), '开盒零溢出写'
        # 位面过渡点空白点击重放(窗口幂等守卫):零双弹零双落
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
        assert gs.pending_item_opens.value == queue_after, '重放零双弹'
        boxes2 = [s for s in gs.bench.value.slots
                  if s is not None and s.kind == 'supply_box']
        assert len(boxes2) == 1, '重放零双落'
    finally:
        uninstall_backend()
