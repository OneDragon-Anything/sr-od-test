"""sim 拿卡拍立即效果条目测试(镜像 src = sim/cw_sim_backend.py 的
_on_invest_picked 尾段立即效果条目调用点 + _present_extra_offer_screen 呈现体)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§2.3/§4(锁 4 即时
呈现效果条目 + 锁 6 双调用点互斥;用户裁定 2026-11-02 完整包复刻):
- 拿卡白银投资 → 拿卡拍立即呈现第二选卡(候选全银池,环境品质改写不
  作用于本通道)+ 逐卡刷新授权 3(refresh_slots/状态容器/槽向量簿记)+ 队列
  弹除 delay-0 条目(delay-3 条目留存)+ 序位计数 +1 + resume='node'
  + 呈现留证键 strategy_immediate_offer_fired;
- 第二选卡落地 → 排除集更新、恢复进节点屏(经同一 report 通道重入
  落地,双调用点互斥 = 立即拍不进窗首检查);
- 期货拿卡(无 delay-0 条目)→ 零立即呈现(常型零扰动);
- 同卡双条目不同拍各呈现一次:立即拍 @0 → 3 后继窗首 @3(递减链
  自然驱动,锁双调用点时序互斥)。

直构形态先例 = 同目录 test_strategy_pick_xp.py(_pick 直写 opts + 上报
+ 声明喂入;_drive_until 步进助手)。"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    DECL_SCREEN_DRIFT,
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SCREEN_SHOP,
    STRATEGY_DELAYED_OFFER_FIRED,
    STRATEGY_IMMEDIATE_OFFER_FIRED,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig


def _backend(seed: int = 43) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    test_strategy_pick_xp._backend)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _drive_until(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step)。"""
    for _ in range(limit):
        if pred():
            return
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend) -> None:
    """驱动至策略 offer 呈现(固定日程首槽 P1r3)。"""
    _drive_until(b, lambda: b.screen_identity() == SCREEN_INVEST_STRATEGY)


def _assert_back_on_node_screen(b: SimBackend) -> None:
    """断言已回节点屏(模态返回落点 = 备战,备战自动弹店形态 = 开商店
    屏——2026-10-29 流程模型「选完关模态回备战自动弹店」,两态均算
    回节点屏)。"""
    assert b.screen_identity() in (SCREEN_PREP, SCREEN_SHOP), \
        f'未回节点屏: {b.screen_identity()}'


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;先例 =
    test_strategy_pick_xp._pick)。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def test_immediate_leg_fires_on_silver_pick_with_refresh_auth() -> None:
    """立即效果条目主锁(锁 4):拿卡白银投资 → 同拍立即呈现第二选卡(不进
    模态返回):候选全银池、逐卡刷新授权 3(状态容器 + 槽向量簿记 + 流水号
    归零)、队列弹除 delay-0 条目(delay-3 留存)、序位计数 +1、
    resume='node'、呈现留证键(值 = 白银投资@1-3)、声明对账零漂移。"""
    b = _backend()
    try:
        _drive_to_offer(b)
        assert b._invest_pick_ordinal == 1, '日程槽呈现序位 = 1'
        _pick(b, '白银投资', ['白银投资', '躺平', '淘金客'])
        assert b.screen_identity() == SCREEN_INVEST_STRATEGY, \
            '立即效果条目未呈现(落回节点屏 = 误入模态返回)'
        opts2 = list(b.gs.invest_strategy_opts.value or [])
        assert len(opts2) == 3, f'第二选卡候选数: {opts2}'
        assert all(INVESTMENT_STRATEGIES[n].rarity == '银' for n in opts2), \
            f'候选混入非银池: {opts2}'
        assert not ({'白银投资', '躺平', '淘金客'} & set(opts2)), \
            f'候选未排除已出选项: {opts2}'
        assert b.gs.pending_strategy_offers.value == (('白银投资', 3),), \
            f'delay-0 未弹除/legs 异常: {b.gs.pending_strategy_offers.value}'
        assert b._invest_pick_ordinal == 2, '序位计数照增'
        assert b._window_resume == 'node', '恢复位'
        assert b._offer_refreshable is True, '可刷系授权在位'
        assert b._offer_forced_slots == ('银', '银', '银'), \
            f'品质承诺簿记: {b._offer_forced_slots!r}'
        assert b._offer_refresh_seq == 0, '刷新流水号归零'
        left_map = dict(b.gs.strategy_refresh_left.value or {})
        assert all(left_map.get(n) == 3 for n in opts2), \
            f'授权状态容器逐卡 3: {left_map!r}'
        assert b.disclosures[STRATEGY_IMMEDIATE_OFFER_FIRED] \
            == '白银投资@1-3', f'呈现留证: {b.disclosures}'
        assert DECL_SCREEN_DRIFT not in b.disclosures, \
            f'声明对账漂移: {b.disclosures.get(DECL_SCREEN_DRIFT)}'
    finally:
        uninstall_backend()


def test_second_pick_lands_and_restores_node_screen() -> None:
    """第二选卡落地(锁 4):立即效果条目呈现后经同一 report 通道重入落地 →
    排除集更新、持卡注册、恢复进节点屏、队列留存 delay-3 条目。"""
    b = _backend()
    try:
        _drive_to_offer(b)
        _pick(b, '白银投资', ['白银投资', '躺平', '淘金客'])
        opts2 = list(b.gs.invest_strategy_opts.value or [])
        excluded_before = set(b.excluded_invest)
        _pick(b, opts2[0], opts2)
        _assert_back_on_node_screen(b)
        active = set(b.gs.active_strategies.value or [])
        assert '白银投资' in active and opts2[0] in active, \
            f'持卡注册: {active!r}'
        assert set(b.excluded_invest) - excluded_before == set(opts2), \
            '排除集未累计第二选卡候选'
        assert b.gs.pending_strategy_offers.value == (('白银投资', 3),), \
            'delay-3 条目留存'
        assert DECL_SCREEN_DRIFT not in b.disclosures, '声明对账漂移'
    finally:
        uninstall_backend()


def test_futures_pick_no_immediate_leg() -> None:
    """期货拿卡零立即呈现(锁 6 常型零扰动):黄金期货(无 delay-0 效果条目)
    拿卡 → 队列只入延时条目、无第二选卡、模态正常返回节点屏、序位
    计数零动、立即留证键缺席。"""
    b = _backend()
    try:
        _drive_to_offer(b)
        _pick(b, '黄金期货', ['黄金期货', '躺平', '淘金客'])
        _assert_back_on_node_screen(b)
        assert b.gs.pending_strategy_offers.value == (('黄金期货', 5),), \
            f'队列: {b.gs.pending_strategy_offers.value}'
        assert b._invest_pick_ordinal == 1, '序位计数误增'
        assert STRATEGY_IMMEDIATE_OFFER_FIRED not in b.disclosures, \
            '立即留证键误置'
    finally:
        uninstall_backend()


def test_two_legs_present_at_different_beats() -> None:
    """同卡双条目不同拍各呈现一次(锁 6):立即拍 @0 → 3 后继窗首 @3
    (自然递减链驱动),两拍序位计数各 +1、留证键分立、双调用点互斥
    (立即拍不抢窗首检查,窗首呈现时队列已无 delay-0 条目)。"""
    b = _backend()
    try:
        _drive_to_offer(b)
        _pick(b, '白银投资', ['白银投资', '躺平', '淘金客'])
        assert b._invest_pick_ordinal == 2, '立即拍序位'
        opts2 = list(b.gs.invest_strategy_opts.value or [])
        _pick(b, opts2[0], opts2)
        _assert_back_on_node_screen(b)
        # 推进 3 节点窗:delay-3 条目 (1,4)/(1,5)/(1,6) 递减归零,
        # (1,6) 窗首到期效果条目呈现(拿卡窗 (1,3) + 3)。
        _drive_until(b, lambda: (
            b.screen_identity() == SCREEN_INVEST_STRATEGY
            and b._invest_pick_ordinal >= 3))
        assert b._invest_pick_ordinal == 3, '窗首拍序位'
        assert b.gs.pending_strategy_offers.value == (), '延时效果条目未弹除'
        assert b.disclosures[STRATEGY_DELAYED_OFFER_FIRED] \
            == '白银投资@1-6', f'窗首留证: {b.disclosures}'
        assert b.disclosures[STRATEGY_IMMEDIATE_OFFER_FIRED] \
            == '白银投资@1-3', '立即留证键应留存'
        opts3 = list(b.gs.invest_strategy_opts.value or [])
        assert all(INVESTMENT_STRATEGIES[n].rarity == '银' for n in opts3), \
            f'窗首候选混入非银池: {opts3}'
    finally:
        uninstall_backend()
