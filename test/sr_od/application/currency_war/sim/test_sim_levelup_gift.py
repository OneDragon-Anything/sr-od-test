"""节节高升升级发放腿 sim 把结果写进状态副本的实现分支锁(升级上报回调跨级分支 → kernel
发放体;LEVEL_UP 把结果写进状态副本的实现分支家族第二成员,商业间谍 spy 块后置零触碰)。

设计唯一源 = 迭代 T-305 设计稿 §2.2/§4-2(裁决点默认案:不立
EffectSpec/满级费用钳池域/连跳逐级/节点与窗口升级源不挂)。驱动形态 =
test_sim_spy_levelup 同款「上报直驱」(report_action_level_up_param,
sim 装配 = 注入槽流键 rng 即世界真值);采样池 = cw_pool.grant_char_pool
(规格域 ∩ 当时牌库、未解锁专家剔除——授予通道已登记裁定 2026-10-28)。

测试面:
1. 持卡跨级:bench +1 名 2★ 且费用档 = max(1, min(5, 新等级-4))
   (等级 7 → 3 费档);
2. 无卡对照:升级照常、零发放;
3. 满级段:level_cap 早退零触发;
4. 等级 10 钳制:9→10 跨级发 5 费档(池域上钳披露键口径);
5. 连跳 Δ=2:两号各依中间等级费用档(3 费 + 4 费);
6. sim 门 False(实机路径):零采样零写。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import chars_by_cost
from sr_od.application.currency_war.kernel.cw_action_report.level_up import (
    report_action_level_up_param,
)
from sr_od.application.currency_war.kernel.cw_economy import XP_TO_NEXT_LEVEL
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    ShopActionExecuted,
    Unit,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='LevelupGiftTest',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='LevelupGiftTest')
_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _cost_pool_names(cost: int) -> set[str]:
    """费用档注册池名集(采样池静态基底;断言 = 发放名 ∈ 该档)。"""
    return {ch.name for ch in chars_by_cost(cost)}


def _bench_names(gs: GameState) -> list[str]:
    """备战席单位名(身份断言面;溢出落位不计入——本批局面席有余位)。"""
    return [s.unit.char_id for s in gs.bench.value.slots
            if s.kind == 'unit' and s.unit is not None]


def _bench_units(gs: GameState) -> list[Unit]:
    """备战席单位对象(星级断言面)。"""
    return [s.unit for s in gs.bench.value.slots
            if s.kind == 'unit' and s.unit is not None]


def _to_prep(seed: int = 7) -> SimBackend:
    """构造 + 走到 P1r1 备战屏(开局初始值已落);调用方负责卸载。"""
    b = SimBackend(seed=seed, cfg=_CFG)
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _seed_and_levelup(b: SimBackend, *, held: bool, level: int,
                      target_clicks: int):
    """种卡与等级观测后买经验上报(持卡 = 观察直种,测试种子纪律;
    生产写端 = 获得链)。点击数 = 目标跨级所需经验 ÷ 4 经验/击。"""
    b.gs.observe(b.gs.active_strategies, ['节节高升'] if held else [],
                 evidence='test:gift', sig=_SIG_OBS)
    b.gs.observe(b.gs.level, level, evidence='test:gift', sig=_SIG_OBS)
    # 满级无下一级门槛键(分母未定),观测占位值即可——level_cap 早退
    # 先于 xp 读数,该路径 xp 值零消费。
    b.gs.observe(b.gs.xp, (0, XP_TO_NEXT_LEVEL.get(level, 0)),
                 evidence='test:gift', sig=_SIG_OBS)
    return report_action_level_up_param(
        b.gs, SimpleNamespace(cost=4), _SIG,
        executed=ShopActionExecuted(levelup_clicks=target_clicks))


def test_jiejie_levelup_grants_two_star_at_level_cost() -> None:
    """持卡跨级(锁①):6→7 跨级 → bench +1 名 2★,费用档 = 7-4 = 3
    (发放名 ∈ 3 费注册池;星级 = 卡面明写 2★)。"""
    b = _to_prep()
    try:
        before = _bench_names(b.gs)
        out = _seed_and_levelup(b, held=True, level=6,
                                target_clicks=XP_TO_NEXT_LEVEL[6] // 4)
        assert out.applied
        after = _bench_units(b.gs)
        gained = [u for u in after if u.char_id not in before]
        assert len(gained) == 1, f'跨级发放恰 1 名: {len(gained)}'
        assert gained[0].star == 2, f'卡面明写 2★: {gained[0].star}'
        assert gained[0].char_id in _cost_pool_names(3), \
            f'费用档 = 等级减4(7→3费): {gained[0].char_id}'
    finally:
        uninstall_backend()


def test_no_card_zero_grant() -> None:
    """无卡对照(锁②):升级照常生效、备战席零入席。"""
    b = _to_prep()
    try:
        before = _bench_names(b.gs)
        out = _seed_and_levelup(b, held=False, level=6,
                                target_clicks=XP_TO_NEXT_LEVEL[6] // 4)
        assert out.applied, '升级照常生效'
        assert _bench_names(b.gs) == before, '无卡零发放'
    finally:
        uninstall_backend()


def test_level_cap_zero_trigger() -> None:
    """满级段零触发(锁③):10 级购买经验 level_cap 早退先于跨级分支,
    零发放(与商业间谍把结果写进状态副本的实现分支同边界)。"""
    b = _to_prep()
    try:
        before = _bench_names(b.gs)
        out = _seed_and_levelup(b, held=True, level=10, target_clicks=1)
        assert not out.applied and out.reason == 'level_cap', \
            f'满级早退: {out.reason}'
        assert _bench_names(b.gs) == before, '满级段零发放'
    finally:
        uninstall_backend()


def test_level10_cost_clamps_to_pool_domain() -> None:
    """等级 10 钳制(锁④):9→10 跨级费用 = max(1, min(5, 10-4)) = 5
    (满级段费用出池域 → 钳到费用轴注册值域上沿,披露键
    ``level_up_gift_cost_clamp_pool_domain`` 口径)。"""
    b = _to_prep()
    try:
        before = _bench_names(b.gs)
        out = _seed_and_levelup(b, held=True, level=9,
                                target_clicks=XP_TO_NEXT_LEVEL[9] // 4)
        assert out.applied
        gained = [u for u in _bench_units(b.gs) if u.char_id not in before]
        assert len(gained) == 1, f'9→10 跨级发放恰 1 名: {len(gained)}'
        assert gained[0].star == 2 and \
            gained[0].char_id in _cost_pool_names(5), \
            f'等级 10 钳 5 费档: {gained[0].char_id}'
    finally:
        uninstall_backend()


def test_multi_level_jump_grants_per_intermediate_level() -> None:
    """连跳 Δ=2(锁⑤):6→8 单批买经验 → 两号各依中间等级费用档
    (7 级 3 费 + 8 级 4 费,逐级发放 = 卡面「每次升级时」直读)。"""
    b = _to_prep()
    try:
        before = _bench_names(b.gs)
        clicks = (XP_TO_NEXT_LEVEL[6] + XP_TO_NEXT_LEVEL[7]) // 4
        out = _seed_and_levelup(b, held=True, level=6, target_clicks=clicks)
        assert out.applied
        gained = [u for u in _bench_units(b.gs) if u.char_id not in before]
        assert len(gained) == 2, f'Δ=2 逐级发放恰 2 名: {len(gained)}'
        assert all(u.star == 2 for u in gained), '两号均卡面明写 2★'
        costs = {u.char_id for u in gained}
        assert sum(1 for n in costs if n in _cost_pool_names(3)) == 1, \
            f'7 级档发 3 费一名: {costs}'
        assert sum(1 for n in costs if n in _cost_pool_names(4)) == 1, \
            f'8 级档发 4 费一名: {costs}'
    finally:
        uninstall_backend()


def test_live_gate_false_zero_write() -> None:
    """sim 门 False = 实机路径(锁⑥):端口未装 → 持卡跨级也零采样
    零写(实机该角色由游戏引擎发放,bench 观察承接定论;若门失效会
    走回退自掷采样并写 bench,本锁即红)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='垫件', star=1))]
    slots += [BenchSlot(kind='empty')] * 8
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.active_strategies, ['节节高升'],
               evidence='test:gift', sig=_SIG_OBS)
    gs.observe(gs.level, 6, evidence='test:gift', sig=_SIG_OBS)
    gs.observe(gs.xp, (0, XP_TO_NEXT_LEVEL[6]),
               evidence='test:gift', sig=_SIG_OBS)
    gs.observe(gs.gold, 100, evidence='test:gift', sig=_SIG_OBS)
    out = report_action_level_up_param(
        gs, SimpleNamespace(cost=4), _SIG,
        executed=ShopActionExecuted(levelup_clicks=XP_TO_NEXT_LEVEL[6] // 4))
    assert out.applied, '升级照常生效'
    assert _bench_names(gs) == ['垫件'], '实机路径零发放(bench 原样)'
