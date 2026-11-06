"""sim 出售发牌腿回归测试(板面重写族出售支:选「出售场上和备战席的
所有角色并获得 5 只随机 2★」类卡,sim 状态副本自持账补全)。

测试面(发牌腿唯一落点 = ``cw_sim_backend._on_invest_picked`` opening=
False 支链尾,decl 分派形态可达;直调上报函数不经分派层 = 存量形态
零扰):
- 全链主锁:出售面(场清空+卖价退款)与发牌面(恰 5 只全 2★,费用
  形状 3费×1/2费×2/1费×2,抽名 ∈ 授予出口现值桶)经声明喂入一拍
  落地;同 seed 重放逐位一致(流键 rng 确定性);
- 先卖后抽时序:预种同名 2★×3 挤空 3 费桶(剩余 = 0),选卡后发牌
  仍可发出该名(种子强制首抽命中 = 确定性断言;时序颠倒则该名不在
  桶,必红);
- 重入防:同局第二次 pick 零重复发放(呈现一次性标志位落地拍消费,无一次性标志位重放
  零写);
- 直调形态零扰:只上报不喂声明 = 出售面照走(kernel 获得链)、发牌腿
  零触发(分派层独占),bench 清空后无凭空补员;
- 空桶防御:注册表漂移态(某费用档桶空)→ 该档零写 + 不炸链,余档
  照发(on_env_gained 随机支同款语义)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTERS,
    chars_by_cost,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
    report_action_start_battle_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
    deployed_rows_of_view,
    report_node_advance,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_pool import grant_bucket_names
from sr_od.application.currency_war.sim import cw_sim_backend, cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_SETTLE,
    SimBackend,
    install_backend,
    stream_rng,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='SimBackendTest', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='TestSigWriter')

_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)

_OPTS = ['人力重组', '躺平', '淘金客']


def _backend(seed: int = 7) -> SimBackend:
    """构造 + 装配(含 kernel 事件钩子订阅;调用方负责 uninstall)。"""
    backend = SimBackend(seed=seed, cfg=_CFG)
    install_backend(backend)
    return backend


def _start_battle_feed(gs) -> None:
    """出战上报 + 声明喂入(声明化单轨,动作 op「上报后一行喂入」同形)。"""
    out = report_action_start_battle_param(gs, SimpleNamespace(), _SIG)
    cw_sim_ports.declare_world(out.world_decl)


def _node_advance_feed(gs, *, trigger: str) -> None:
    """节点推进上报 + 声明喂入。"""
    out = report_node_advance(gs, trigger=trigger)
    assert out.applied, f'节点推进未落账: {out.reason!r}'
    cw_sim_ports.declare_world(out.world_decl)


def _bench_units(gs) -> list[tuple[str, int]]:
    """备战席在席单位 (名, 星级) 列表(槽序)。"""
    return [(s.unit.char_id, s.unit.star)
            for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def _drive_to_strategy_offer(b: SimBackend) -> None:
    """简报 → P1r3(U07 固定 offer 槽)驱动:策略选卡屏呈现即三条效果条目一次性标志位
    置位(发牌腿前置状态)。路径 = 既有 overlay 让路测试同款出战/推进
    序(声明化单轨)。"""
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    gs = b.gs
    _start_battle_feed(gs)
    assert b.screen_identity() == SCREEN_SETTLE
    _node_advance_feed(gs, trigger='settle_confirm')
    assert (gs.node.value.plane, gs.node.value.round_num) == (1, 2)
    _start_battle_feed(gs)
    _node_advance_feed(gs, trigger='settle_confirm')
    assert gs.node.value.round_num == 3
    assert b.screen_identity() == SCREEN_INVEST_STRATEGY, \
        'P1r3 offer 槽呈现(发牌腿呈现一次性标志位置位前提)'


def _pick_card(b: SimBackend, name: str) -> None:
    """选卡上报 + 声明喂入(decl 分派形态:上报走 kernel 获得链,喂入
    走后端 ``advance`` 分派 → ``_on_invest_picked`` 落地腿)。"""
    gs = b.gs
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG,
        session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)


# ============================================================ 锁 1:全链主锁

def test_sell_all_deal_full_chain_decl_dispatch() -> None:
    """decl 分派全链:选人力重组 → 出售面(场清空+退款)+ 发牌面(恰
    5 只全 2★,3费×1/2费×2/1费×2,抽名 ∈ 授予出口现值桶)一拍落地;
    同 seed 重放逐位一致(发牌 rng = 流键派生,sim 确定性契约)。"""
    cost3 = {c.name for c in chars_by_cost(3)}
    cost2 = {c.name for c in chars_by_cost(2)}
    cost1 = {c.name for c in chars_by_cost(1)}
    assert '人力重组' in cw_sim_backend.SELL_ALL_REWRITE_STRATEGIES, \
        '判据派生前提(注册表过滤,禁硬编码名单)'

    def _run_once() -> list[tuple[str, int]]:
        b = _backend(7)
        try:
            _drive_to_strategy_offer(b)
            gs = b.gs
            gs.observe(gs.deployed,
                       _dvs([Unit(char_id='淘金客', star=1)], []),
                       sig=_SIG_OBS)
            gs.write_logic(gs.invest_strategy_opts, _OPTS,
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            gold_before = int(gs.gold.value or 0)
            _pick_card(b, '人力重组')
            _f, _bk = deployed_rows_of_view(gs.deployed.value)
            assert (_f, _bk) == ([], []), '场清空(出售面)'
            assert int(gs.gold.value or 0) > gold_before, '卖价退款入金'
            units = _bench_units(gs)
            assert len(units) == 5, \
                f'恰 5 只发牌(bench 先清空再落 5 只,实际 {len(units)})'
            assert all(st == 2 for _, st in units), '全 2★(卡面明写结构值)'
            assert sum(1 for n, _ in units if n in cost3) == 1, '3费×1'
            assert sum(1 for n, _ in units if n in cost2) == 2, '2费×2'
            assert sum(1 for n, _ in units if n in cost1) == 2, '1费×2'
            for name, _star in units:
                assert name in grant_bucket_names(
                    gs, int(CHARACTERS[name].cost)), \
                    f'抽名 ∈ 授予出口现值桶:{name}'
            return units
        finally:
            uninstall_backend()

    first = _run_once()
    second = _run_once()
    assert first == second, '同 seed 重放确定性(逐位一致)'


# ============================================================ 锁 2:先卖后抽时序

def test_sell_all_deal_draws_after_sell_not_before() -> None:
    """先卖后抽时序(行为面):预种场上同名 2★×3(held = 9 = 固定副本
    数,该名剩余 = 0)→ 选卡 → 发牌仍可发出该名。出售前该名不在桶
    (授予出口过滤剩余 = 0),出售后 held 归零回全集——种子强制首抽
    命中被卖名作确定性断言:时序颠倒(先抽后卖)则该名必缺,必红。"""
    def _pick_once(seed: int) -> list[str]:
        b = _backend(seed)
        try:
            _drive_to_strategy_offer(b)
            gs = b.gs
            # 被卖名 = 首个不在开局手牌的 3 费非专家名(开局手牌已占
            # 副本会破坏「held 恰 = 固定副本数」的挤空前置)。
            hand = {n for n, _ in _bench_units(gs)}
            sold = sorted(
                c.name for c in chars_by_cost(3)
                if not CHARACTERS[c.name].is_expert and c.name not in hand)[0]
            gs.observe(gs.deployed,
                       _dvs([Unit(char_id=sold, star=2)] * 3, []),
                       sig=_SIG_OBS)
            gs.write_logic(gs.invest_strategy_opts, _OPTS,
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            _pick_card(b, '人力重组')
            return [n for n, _ in _bench_units(gs)]
        finally:
            uninstall_backend()

    # 种子搜索:发牌腿首抽 = 3 费桶 rng 放回一抽;出售刚清场 → 桶 =
    # 固定全集,与断言时点现值同集同序(发牌 1 只 2★ 计 3 副本 < 档
    # 副本数,桶成员资格不变)。选使首抽命中被卖名的 seed。
    probe = _backend(7)
    try:
        hand = {n for n, _ in _bench_units(probe.gs)}
        sold = sorted(
            c.name for c in chars_by_cost(3)
            if not CHARACTERS[c.name].is_expert and c.name not in hand)[0]
        bucket3 = grant_bucket_names(probe.gs, 3)
        assert sold in bucket3, '出售后桶含被卖名(时序前提)'
    finally:
        uninstall_backend()
    deal_seed = next(s for s in range(2000)
                     if stream_rng(s, 'M24/sell-all-deal').choice(bucket3)
                     == sold)
    assert sold in _pick_once(deal_seed), \
        '发牌抽到被卖名(先卖后抽实证:先抽后卖时序下该名不在桶)'


# ============================================================ 锁 3:重入防

def test_sell_all_deal_no_repeat_on_second_pick() -> None:
    """同局第二次 pick(选另一张卡)零重复发放:呈现一次性标志位落地拍消费,
    无一次性标志位的再次分派零写(xp/streak 腿同款防重放口径)。"""
    b = _backend(7)
    try:
        _drive_to_strategy_offer(b)
        gs = b.gs
        gs.write_logic(gs.invest_strategy_opts, _OPTS,
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        _pick_card(b, '人力重组')
        after_first = _bench_units(gs)
        assert len(after_first) == 5, '首拍发牌前提'
        _pick_card(b, '躺平')
        assert _bench_units(gs) == after_first, '二拍零重复发放'
    finally:
        uninstall_backend()


# ============================================================ 锁 4:直调形态零扰

def test_sell_all_deal_absent_on_direct_report_form() -> None:
    """直调上报形态(存量锚形,不喂声明 = 不经后端分派层):出售面照走
    (kernel 获得链,场清空)而发牌腿零触发——发牌唯一落点 = 分派层,
    直调路径 bench 清空后无凭空补员(存量直调形态行为零变化)。"""
    b = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        gs.observe(gs.deployed,
                   _dvs([Unit(char_id='淘金客', star=1)], []),
                   sig=_SIG_OBS)
        gs.write_logic(gs.invest_strategy_opts, _OPTS,
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name='人力重组'), _SIG,
            session=SimpleNamespace())
        assert out.applied
        _f, _bk = deployed_rows_of_view(gs.deployed.value)
        assert (_f, _bk) == ([], []), '出售面照走(实机和模拟器两边同链)'
        assert _bench_units(gs) == [], \
            '发牌腿零触发(直调不经分派层,bench 无凭空补员)'
    finally:
        uninstall_backend()


# ============================================================ 锁 5:空桶防御

def test_sell_all_deal_empty_bucket_zero_write_no_crash(monkeypatch) -> None:
    """空桶防御(注册表漂移态):某费用档桶空 → 该档零写 + 不炸链,
    余档照发(on_env_gained 随机支同款语义)。漂移态以授予出口打桩
    模拟(出口现值恒非空,直构不可达)。"""
    real_grant = cw_sim_backend.grant_bucket_names

    def _drifted_grant(gs, cost: int) -> list[str]:
        if cost == 3:
            return []
        return real_grant(gs, cost)

    monkeypatch.setattr(cw_sim_backend, 'grant_bucket_names',
                        _drifted_grant)
    b = _backend(7)
    try:
        _drive_to_strategy_offer(b)
        gs = b.gs
        gs.write_logic(gs.invest_strategy_opts, _OPTS,
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        _pick_card(b, '人力重组')   # 漂移态下不炸链
        cost3 = {c.name for c in chars_by_cost(3)}
        units = _bench_units(gs)
        assert all(n not in cost3 for n, _ in units), '空桶档零写'
        assert len(units) == 4, '余档照发(2费×2 + 1费×2)'
    finally:
        uninstall_backend()
