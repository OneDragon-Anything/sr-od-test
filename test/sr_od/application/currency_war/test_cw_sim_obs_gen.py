"""sim 金路径观察生成器 + 档名注册表回归锁(sim 统一迭代 3.3)。

锁面 = 3.3 完成判据的可执行形态:
- 每生成器单测:构造世界态 → ``backend.observe(档名)`` 生成 obs(生产
  路径 = 注册表分派,产物经同名 ``report_screen_*`` 落容器)→ 容器字段
  断言;
- 状态机呈现未注册屏 = :class:`LookupError` 具名响错(防静默失真锁);
- 金路径清单覆盖核对:13 档名逐行有生成器(注册表 = 清单的代码镜像,
  键集零差零冗余)。

设计依据 = sim- + flow-seam 接缝契约(正本 = sim/sim-
合法引用;正本更新义务归末阶段)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_open_box_param,
    report_action_pick_encounter_param,
    report_action_pick_invest_strategy_param,
    report_action_pick_megastar_param,
    report_action_pick_planner_param,
    report_action_pick_supply_param,
    report_action_start_battle_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
    report_node_advance,
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenBoxParam,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
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
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_obs_gen import (
    GOLDEN_PATH_SCREEN_NAMES,
    registered_screens,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='SimObsGenTest', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='SimObsGenTest')

_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _backend(seed: int = 7, cfg: RunConfig = _CFG) -> SimBackend:
    """构造 + 装配(端口槽 + 事件 sink;调用方负责 uninstall)。"""
    b = SimBackend(seed=seed, cfg=cfg)
    install_backend(b)
    return b


def _open_to_first_window(b: SimBackend, *, env_present: bool = False) -> None:
    """开局序列推进到 P1r1(无环境)或投资环境屏(env_present=True)。"""
    if env_present:
        b.cfg = RunConfig(selected_difficulty='A8', enemy_difficulty=108,
                          env_present=True)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')


def _node_advance_feed(gs, *, trigger: str) -> None:
    """节点推进上报 + 声明喂入(声明化单轨;动作 op「上报后一行喂入」同形)。"""
    from sr_od.application.currency_war.sim import cw_sim_ports
    out = report_node_advance(gs, trigger=trigger)
    assert out.applied, f'节点推进未落账: {out.reason!r}'
    cw_sim_ports.declare_world(out.world_decl)


def _start_battle_feed(gs) -> None:
    """出战上报 + 声明喂入(声明化单轨)。"""
    from sr_od.application.currency_war.sim import cw_sim_ports
    out = report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
    cw_sim_ports.declare_world(out.world_decl)


def _step(b: SimBackend) -> None:
    """单步驱动(按呈现屏分派到对应真实写端;走局推进共用;18 动作全量
    单轨 = 上报 + 声明喂入,动作 op 同形)。"""
    from sr_od.application.currency_war.sim import cw_sim_ports
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
        _node_advance_feed(gs, trigger='supply_confirm')
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
        _step(b)
    raise AssertionError('超过推进步数上限未达目标节点窗')


# ============================================================ 注册表锁

def test_registry_covers_golden_path_checklist_exactly() -> None:
    """金路径清单覆盖核对:注册表键集与 13 档名清单零差零冗余(清单
    逐行有生成器;清单外注册 = 辖域外屏混入,同样拒绝)。"""
    assert set(registered_screens()) == set(GOLDEN_PATH_SCREEN_NAMES)
    assert len(registered_screens()) == 13


def test_unregistered_screen_raises_named_error() -> None:
    """状态机呈现未注册屏 = LookupError 具名响错(防静默失真锁):金路径
    清单外的档名(如大厅/武装箱弹窗)观察请求必须响亮拒绝,禁产空产物。"""
    b = _backend()
    try:
        assert b.screen_identity() == SCREEN_BRIEFING   # 简报在册,先确认基线
        b.observe(SCREEN_BRIEFING)
        with pytest.raises(LookupError, match='未注册'):
            b.observe('货币战争-大厅')
    finally:
        uninstall_backend()


# ============================================================ 逐生成器

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
        # report 腿容器断言:同值覆写后容器与 obs 逐位一致(生成器 →
        # report → 容器全链走通)。
        assert gs.enemy_affixes.value == obs.enemy_affixes
    finally:
        uninstall_backend()


def test_gen_invest_env_candidates_from_container_slot() -> None:
    """投资环境生成器:候选名自容器 opts 槽(M02 采样写点),report 腿
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
        assert b.gs.invest_env_opts.value == opts_before, 'report 腿同值回写'
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
    语义观察真值(入口 left=1);report 腿同值回写幂等。"""
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
        assert gs.supply.value.options == obs.options, 'report 腿同值回写'
    finally:
        uninstall_backend()


def test_gen_invest_strategy_candidates_at_offer_window() -> None:
    """投资策略生成器:P1r3 = U07 固定 offer 日程 → 策略屏呈现,候选名
    自容器 opts 槽回读;refresh_slots 空 → report 逐槽跳写。"""
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
        assert obs.refresh_slots == []
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
    """遭遇生成器:档位候选自容器呈现写点回读(四档集);report 腿同值
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
    同序等长(report 写端守卫同契约);选定腿消费面 = 动作 op 按 idx 取
    xy(合成坐标,身份键)。"""
    b = _backend()
    try:
        _open_to_first_window(b)
        b._maybe_finish_wait()
        from sr_od.application.currency_war.sim import cw_sim_ports
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
