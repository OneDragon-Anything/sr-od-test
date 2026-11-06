"""sim 策略选卡即时经验效果条目测试(镜像 src = sim/cw_sim_backend.py 的
apply_strategy_pick_xp helper + _on_invest_picked 落地效果条目 + 呈现一次性标志位 +
披露键 strategy_pick_instant_legs)。

测试面依据 = 迭代设计 designs/T-87-jingyan-daozhang.md §2.1/§2.4/§4 七锁:
- 持卡发放真值(锁 1):offer 落地 advance 后 xp 恰 +10(门槛内形态),
  独立 evidence 笔 ``xp:strategy_pick:<卡名>``(与节点经验 ``xp:node``
  笔分账);
- 零值形态合并锁(锁 2):xp_instant 显式 0(孪生素数)与字段缺省
  (特战资金)各一局 → 均无 xp:strategy_pick 笔、xp 零增量;
- 无效载荷零发放(锁 3):opts 含本卡但不落卡(选另一张)→ 零写;
- 跨级结转(锁 4):门槛 −k(k<10)形态 → level+1、余量 10−k;
- 双即时卡各发各的 + 数值矩阵(锁 5):经验到账→成长的快乐两笔独立
  (10+4,无一次聚合笔);伟大征服单选 +12 独立笔;
- 重放防双发(锁 6):同 offer 落地 advance 重放 → 第二次零写。

锁 7(live 链零写)落 kernel/test_gain_chain.py(获得链现址)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改;先例 = 本目录
test_strategy_boss_gold.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_economy import XP_TO_NEXT_LEVEL
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

#: xp 即时效果条目独立笔 evidence 前缀(单一源 = cw_sim_base.sim_evidence
#: 契约:前缀 sim:engine: + 写点 tag xp:strategy_pick:<卡名>)。
_XP_EV_PREFIX = 'sim:engine:xp:strategy_pick:'


def _backend(seed: int = 31) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    test_strategy_boss_gold._backend)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _drive_until(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step——位面过渡屏在其分派表内,
    test_sim_backend._drive_env_grant_step 无该档,达 P2 offer 必经;
    import 复用先例 = test_env_pick_grant_sim_chain._drive_until_pos)。"""
    for _ in range(limit):
        if pred():
            return
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend) -> None:
    """驱动至策略 offer 呈现(固定日程首槽 P1r3 起;呈现即置即时经验
    效果条目一次性标志位——本效果条目生效前提)。"""
    _drive_until(b, lambda: b.screen_identity() == SCREEN_INVEST_STRATEGY)


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;现役 harness
    形态先例 = test_sim_backend 选卡链族)。返回声明供重放用例复喂。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def _seed_level_xp(gs, level: int, cur: int) -> None:
    """等级/经验观察直种(测试种子纪律先例 = test_strategy_boss_gold
    ._hold;level 5 段门槛 20 > 10,门槛内/跨级形态均可表达)。"""
    gs.observe(gs.level, level, sig=_SIG_OBS)
    gs.observe(gs.xp, (cur, XP_TO_NEXT_LEVEL[level]), sig=_SIG_OBS)


def test_pick_grants_exact_instant_xp_within_threshold() -> None:
    """持卡发放真值(锁 1):offer 落地后 xp 恰 +10(门槛内形态不升级),
    独立 evidence 笔与节点经验笔分账(level/xp 双字段同笔)。"""
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_level_xp(gs, 5, 0)
        _pick(b, '经验到账', ['经验到账', '躺平', '淘金客'])
        assert gs.level.value == 5, f'门槛内不升级: {gs.level.value}'
        assert gs.xp.value == (10, XP_TO_NEXT_LEVEL[5]), \
            f'xp 恰 +10: {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV_PREFIX + '经验到账', \
            f'独立笔缺失或来源漂移: {gs.xp.evidence}'
        assert gs.level.evidence == _XP_EV_PREFIX + '经验到账'
    finally:
        uninstall_backend()


def test_zero_value_forms_zero_grant() -> None:
    """零值形态合并锁(锁 2):xp_instant 显式 0(孪生素数)与字段缺省
    (特战资金)各一局落地 → 均无 xp:strategy_pick 笔、xp 零增量
    (缺省 0 与显式 0 同一「>0 才动」语义)。"""
    b = _backend(seed=32)
    try:
        gs = b.gs
        _drive_to_offer(b)
        xp0, ev0 = gs.xp.value, gs.xp.evidence
        _pick(b, '孪生素数', ['孪生素数', '躺平', '淘金客'])
        assert gs.xp.value == xp0 and gs.xp.evidence == ev0, \
            f'显式 0 出现 xp 笔: {gs.xp.value} / {gs.xp.evidence}'
        _drive_to_offer(b)
        xp1, ev1 = gs.xp.value, gs.xp.evidence
        _pick(b, '特战资金', ['特战资金', '躺平', '淘金客'])
        assert gs.xp.value == xp1 and gs.xp.evidence == ev1, \
            f'字段缺省卡出现 xp 笔: {gs.xp.value} / {gs.xp.evidence}'
    finally:
        uninstall_backend()


def test_unpicked_card_zero_grant() -> None:
    """无效载荷零发放(锁 3):opts 含本卡但不落卡(选另一张)→ 落地
    交集空 → 零写(呈现一次性标志位同拍消耗,本次不残留)。"""
    b = _backend(seed=33)
    try:
        gs = b.gs
        _drive_to_offer(b)
        xp0, ev0 = gs.xp.value, gs.xp.evidence
        _pick(b, '躺平', ['经验到账', '躺平', '淘金客'])
        assert '躺平' in (gs.active_strategies.value or [])
        assert '经验到账' not in (gs.active_strategies.value or [])
        assert gs.xp.value == xp0 and gs.xp.evidence == ev0, \
            f'未落卡出现 xp 笔: {gs.xp.value} / {gs.xp.evidence}'
    finally:
        uninstall_backend()


def test_threshold_cross_carry_over() -> None:
    """跨级结转(锁 4):门槛 −k(k=3<10)形态落地 → level+1、
    余量 10−k=7(xp_apply_amount 结转语义经本效果条目的回归)。"""
    b = _backend(seed=34)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_level_xp(gs, 5, XP_TO_NEXT_LEVEL[5] - 3)
        _pick(b, '经验到账', ['经验到账', '躺平', '淘金客'])
        assert gs.level.value == 6, f'升一级: {gs.level.value}'
        assert gs.xp.value == (7, XP_TO_NEXT_LEVEL[6]), \
            f'余量 10−3=7: {gs.xp.value}'
    finally:
        uninstall_backend()


def test_two_instant_cards_independent_legs() -> None:
    """双即时卡各发各的(锁 5):先经验到账(+10)再成长的快乐(+4)
    → 两笔独立 evidence 笔笔分键,合计 +14 无一次聚合笔(第二次落地
    前重种攒度,两条效果条目增量各自可辨)。"""
    b = _backend(seed=35)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_level_xp(gs, 5, 0)
        _pick(b, '经验到账', ['经验到账', '躺平', '淘金客'])
        assert gs.xp.value == (10, XP_TO_NEXT_LEVEL[5])
        assert gs.xp.evidence == _XP_EV_PREFIX + '经验到账', \
            f'首笔独立键: {gs.xp.evidence}'
        _drive_to_offer(b)
        _seed_level_xp(gs, 5, 0)
        _pick(b, '成长的快乐', ['成长的快乐', '躺平', '淘金客'])
        assert gs.xp.value == (4, XP_TO_NEXT_LEVEL[5])
        assert gs.xp.evidence == _XP_EV_PREFIX + '成长的快乐', \
            f'次笔独立键: {gs.xp.evidence}'
    finally:
        uninstall_backend()


def test_great_conquest_single_pick_grant_12() -> None:
    """伟大征服单选(锁 5 辖域矩阵):+12 独立笔(3 卡辖域防「效果条目实为
    经验到账特判」误实现)。"""
    b = _backend(seed=36)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_level_xp(gs, 5, 0)
        _pick(b, '伟大征服', ['伟大征服', '躺平', '淘金客'])
        assert gs.xp.value == (12, XP_TO_NEXT_LEVEL[5])
        assert gs.xp.evidence == _XP_EV_PREFIX + '伟大征服'
    finally:
        uninstall_backend()


def test_mianzhanpai_single_pick_grant_30() -> None:
    """免战牌单选(锁 5 辖域成员,+30;免战牌建模批):xp_instant 注册行
    落地后字段分派通用效果条目自动覆盖(非单卡特判),独立 evidence 笔——
    同时锁条目 payload 与 STRATEGY_ECONOMY 注册行同实例(改回内联或
    换值即红)。30 > 5 级门槛 20 → 跨级结转形态(level 6,余 10)。"""
    b = _backend(seed=38)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_level_xp(gs, 5, 0)
        _pick(b, '免战牌', ['免战牌', '躺平', '淘金客'])
        assert gs.level.value == 6
        assert gs.xp.value == (10, XP_TO_NEXT_LEVEL[6])
        assert gs.xp.evidence == _XP_EV_PREFIX + '免战牌'
    finally:
        uninstall_backend()


def test_replay_advance_zero_double_grant() -> None:
    """重放防双发(锁 6):同 offer 落地 advance 重放一次 → 第二次零写
    (呈现一次性标志位已消费;无新呈现不再置位)。"""
    b = _backend(seed=37)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_level_xp(gs, 5, 0)
        decl = _pick(b, '经验到账', ['经验到账', '躺平', '淘金客'])
        assert gs.xp.value == (10, XP_TO_NEXT_LEVEL[5])
        cw_sim_ports.declare_world(decl)
        assert gs.xp.value == (10, XP_TO_NEXT_LEVEL[5]), \
            f'重放双发: {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV_PREFIX + '经验到账'
    finally:
        uninstall_backend()
