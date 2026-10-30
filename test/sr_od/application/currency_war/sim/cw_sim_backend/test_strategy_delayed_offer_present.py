"""sim 策略延时 offer 呈现腿测试(镜像 src = sim/cw_sim_backend.py 的
_present_due_extra_offer + _present_offer_or_node_screen 尾部挂点)。

测试面依据 = 迭代设计 designs/T-98-huangjin-qihuo.md §4(锁 4 条件矩阵
+ 锁 5 弹除原子性;同窗冲突/多期货两分支现交付域自然不可达,直构):
- 未到点零呈现零写;到点呈现 = 候选全金池 + 空刷新授权 + 队列弹除 +
  序位计数 +1 + 呈现留证披露键;
- 同窗固定日程槽在场 → 日程先呈现、期货顺延(scheduled_slot_occupied
  披露,结构性守卫直构);
- 多期货同窗恰 1 次、余者悬置顺延(window_cap 披露,同直构);
- 呈现即消费:呈现后队列即空,重复进窗不二次呈现。

直构形态先例 = 同目录 test_strategy_pick_xp.py(_backend 装配 +
install/uninstall 端口槽纪律)。"""
from __future__ import annotations

from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    STRATEGY_DELAYED_OFFER_DEFERRED,
    STRATEGY_DELAYED_OFFER_FIRED,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig


def _backend(seed: int = 41) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    test_strategy_pick_xp._backend)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    return b


def _seed_queue(b: SimBackend, queue: tuple) -> None:
    b.gs.write_logic(b.gs.pending_strategy_offers, queue,
                     produced_by='test-seed', evidence='t:queue', sig=_SIG)


def test_not_due_zero_present_zero_write() -> None:
    """未到点(锁 4a):remaining > 0 → 零呈现(落节点屏)、队列零写、
    序位计数零动。"""
    b = _backend()
    try:
        _seed_queue(b, (('黄金期货', 2),))
        ordinal_before = b._invest_pick_ordinal
        b._present_offer_or_node_screen()
        assert b.screen_identity() != SCREEN_INVEST_STRATEGY, '未到点误呈现'
        assert b.gs.pending_strategy_offers.value == (('黄金期货', 2),), \
            f'未到点队列被写: {b.gs.pending_strategy_offers.value}'
        assert b._invest_pick_ordinal == ordinal_before, '未到点序位计数'
    finally:
        uninstall_backend()


def test_due_presents_all_gold_pool_once() -> None:
    """到点呈现(锁 4b):候选全金池(品质钉金 = 登记值,环境品质改写
    不作用于本通道)+ 空刷新授权(卡面「不能刷新」)+ 队列弹除 +
    序位计数 +1 + 呈现留证披露键(值 = 触发卡@frame)。"""
    b = _backend()
    try:
        _seed_queue(b, (('黄金期货', 0),))
        refresh_left_before = b.gs.strategy_refresh_left.value
        b._present_offer_or_node_screen()
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY, '到点未呈现'
        opts = list(b.gs.invest_strategy_opts.value or [])
        assert len(opts) == 3, f'候选数: {opts}'
        assert all(INVESTMENT_STRATEGIES[n].rarity == '金' for n in opts), \
            f'候选混入非金池: {opts}'
        assert b.gs.pending_strategy_offers.value == (), '队列未弹除'
        assert b._invest_pick_ordinal == 1, '序位计数照增'
        assert b.disclosures[STRATEGY_DELAYED_OFFER_FIRED] \
            == '黄金期货@1-1', f'呈现留证: {b.disclosures}'
        assert b._strategy_pick_xp_latch is True, '即时经验腿闩照置'
        assert b._offer_refreshable is False, '定品质禁刷新'
        assert b.gs.strategy_refresh_left.value == refresh_left_before, \
            '空授权不得写刷新计数'
    finally:
        uninstall_backend()


def test_scheduled_slot_occupied_defers() -> None:
    """同窗固定日程槽在场(锁 4c,自然不可达直构):日程槽先呈现,期货
    条目悬置顺延(scheduled_slot_occupied 披露留证)——优先序 = 固定
    日程 > 期货队列,结构性守卫。"""
    b = _backend()
    try:
        _seed_queue(b, (('黄金期货', 0),))
        b.gs.observe(b.gs.node,
                     NodeKey(plane=1, round_num=3, kind='reward'),
                     sig=_SIG_OBS)   # 钉到固定日程首槽 (1,3)
        b._present_offer_or_node_screen()
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY, '日程槽未呈现'
        assert b.gs.pending_strategy_offers.value == (('黄金期货', 0),), \
            f'同窗冲突未顺延: {b.gs.pending_strategy_offers.value}'
        assert b.disclosures[STRATEGY_DELAYED_OFFER_DEFERRED] \
            == 'scheduled_slot_occupied@1', f'顺延留证: {b.disclosures}'
    finally:
        uninstall_backend()


def test_multi_due_one_per_window_cap_disclosed() -> None:
    """多期货同窗恰 1 次(锁 4d,现域不可达直构):本窗呈现首个(登记序
    确定性),余者悬置顺延(window_cap 披露);下一窗检查呈现余者。"""
    b = _backend()
    try:
        _seed_queue(b, (('黄金期货', 0), ('黄金期货', 0)))
        b._present_offer_or_node_screen()
        assert b.gs.pending_strategy_offers.value == (('黄金期货', 0),), \
            '本窗呈现超 1 次'
        assert b.disclosures[STRATEGY_DELAYED_OFFER_DEFERRED] \
            == 'window_cap@1', f'窗口上限留证: {b.disclosures}'
        assert b._invest_pick_ordinal == 1
        b._present_offer_or_node_screen()   # 下一窗检查(直构)
        assert b.gs.pending_strategy_offers.value == (), '余者未顺延呈现'
        assert b._invest_pick_ordinal == 2
    finally:
        uninstall_backend()


def test_present_consumes_eject_atomic_no_double_present() -> None:
    """弹除原子性(锁 5):呈现即消费(选卡前队列已空),重复进窗检查
    不二次呈现(序位计数零动、落点回节点屏)。"""
    b = _backend()
    try:
        _seed_queue(b, (('黄金期货', 0),))
        b._present_offer_or_node_screen()
        assert b.gs.pending_strategy_offers.value == (), '呈现后队列非空'
        ordinal_after_present = b._invest_pick_ordinal
        b._present_offer_or_node_screen()   # 同窗重复检查(直构重入)
        assert b.screen_identity() != SCREEN_INVEST_STRATEGY, '二次呈现'
        assert b._invest_pick_ordinal == ordinal_after_present, \
            '二次呈现序位计数'
    finally:
        uninstall_backend()
