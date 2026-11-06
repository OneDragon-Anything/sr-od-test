"""collect_ore 上报尾部策略卡晶矿开启触发发放类效果条目集成锁(镜像 src =
kernel/cw_action_report/collect_ore.py 尾部调用块;test_collect_ore.py
语义面 = 合并升星/战技点契约既有锁零触碰,本文件按同目录新文件落位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-316-huangjing-kuanggong.md(定稿,REVIEW-T316 无需用户决定 7/7)§4 锁 4:
- 窗序锁:计数入账后、契约效果条目后(env 触发分支写先于只供策略算分的实现分支写);
- 席满跳过点不入色档列(「点开才触发」与计数分支同口径);
- 批尾 spheres 单写含授予点(「一次写一 evidence」);
- opened == 0 早退路径零触发。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_collect_ore_param,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    OreSight,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCollectOreParam,
)

_SEED_SIG = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep',
                  group_id='g1')
_LSIG = ChannelSig(family='logic_action', actor='test-seed', mode='compute')

_CARD = '黄晶矿工'
_SP_ENV = '战技点契约'
_HIT_SEED = 1     # random.Random(1).random() ≈ 0.134 < 0.5(掷中)
_MISS_SEED = 2    # random.Random(2).random() ≥ 0.5(未掷中)

# 两点批(点 1 = 金矿附金奖励 / 点 2 = 金矿附金奖励;色档经载荷序入列)
_PTS = (('gold', 100, 200, 30), ('gold', 300, 400, 30))
_XYS = ((100, 200), (300, 400))


@pytest.fixture
def seeded_provider() -> Iterator[None]:
    """注确定 rng 提供槽(全流键同种子——各分支各取独立实例,期望可现算),
    必达复位。"""
    set_action_rng_provider(lambda tool: random.Random(_HIT_SEED))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def _make_gs(*, bench_units: list[tuple[str, int]],
             held: bool = True, env: str | None = None,
             ore_open_total: int = 0, level: bool = True,
             pt1_char: bool = False) -> GameState:
    """采晶矿场景直构(两点批 + 附着值;bench 按参组装;持卡/环境/计数/
    level 按参播种)。``pt1_char`` = 点 1 附着改角色奖励(占最后一席,
    造「点 2 席满跳过」混合批形态)。"""
    gs = game_state_of(cw4_session())
    if held:
        gs.write_logic(gs.active_strategies, [_CARD],
                       produced_by='test-seed', sig=_LSIG)
    if env:
        gs.observe(gs.active_env, env, sig=_SEED_SIG)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
             for c, s in bench_units]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SEED_SIG)
    gs.observe(gs.spheres, OreSight(count=2, colors=('gold',), points=_PTS),
               sig=_SEED_SIG)
    pt1_attach = (OreReward(kind='char', char_id='银狼', char_star=1)
                  if pt1_char else OreReward(kind='gold', gold=3))
    gs.write_logic(gs.ore_rewards,
                   {'100,200': pt1_attach,
                    '300,400': OreReward(kind='gold', gold=4)},
                   produced_by='test-seed', sig=_LSIG)
    if ore_open_total:
        gs.effects.record_ore_open(ore_open_total)
    if level:
        gs.observe(gs.level, 3, sig=_SEED_SIG)
    return gs


def _record_writes(gs: GameState,
                   monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic_rand/write_logic 记录 (字段名, evidence, 通道)
    写行(先例 = 同目录 test_collect_ore 同名 helper)。"""
    calls: list[tuple[str, str | None, str]] = []

    def _wrap(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((gs._field_name(target), evidence, channel))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'write_logic', _wrap(gs.write_logic, 'logic'))
    return calls


def test_window_order_count_env_then_strategy_leg(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """窗序锁(T-316 设计 §4 锁 4):计数入账(含本批)→ 契约效果条目写
    (env_grant#...)→ 只供策略算分的实现分支写(strategy_ore_open_grant#1,含授予点 +
    附着)。"""
    gs = _make_gs(bench_units=[], env=_SP_ENV, ore_open_total=20)
    calls = _record_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=(_XYS[0],)), sig=_SIG)
    assert out.applied, f'开成: {out.reason}'
    assert gs.effects.ore_open_total == 21, '计数先入账(含本批)'
    assert gs.env_grants_done.value == ((_SP_ENV, 'ore_open#20'),), \
        '契约效果条目照常封账(既有效果条目零扰动)'
    gold_idx = next(i for i, c in enumerate(calls)
                    if c[1] == 'proj_ore_reward_gold#ore1')
    env_idx = next(i for i, c in enumerate(calls)
                   if (c[1] or '').startswith('env_grant#'))
    ore_idx = next(i for i, c in enumerate(calls)
                   if (c[1] or '').startswith('strategy_ore_open_grant#'))
    assert gold_idx < env_idx < ore_idx, \
        f'窗序 = 矿奖励 → 契约发放分支 → 只供策略算分的实现分支: {[c[1] for c in calls]}'
    pts = gs.spheres.value.points if gs.spheres.value else ()
    assert any(p[1] == 10 and p[2] == 10 for p in pts), \
        f'授予点(合成形专用带)在 spheres: {pts}'
    assert '10,10' in (gs.ore_rewards.value or {}), '授予矿附着已生成'


def test_bench_full_skip_point_not_in_tier_list(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """席满跳过点不入色档列锁:点 1 开成(角色奖励占掉最后一席)→ 点 2
    席满跳过 → opened = 1、色档列只含点 1(单掷授予恰 1 点——跳点若误入
    列,掷点数与授予数红灯)。"""
    units = [('停云', 1), ('刃', 1), ('桑博', 1), ('佩拉', 1),
             ('姬子', 1), ('瓦尔特', 1), ('布洛妮娅', 1), ('希儿', 1)]
    gs = _make_gs(bench_units=units, pt1_char=True)
    calls = _record_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=_XYS), sig=_SIG)
    assert out.applied and out.reason == 'ore_partial_open_skipped', \
        f'混合批出参: {out.reason}'
    assert gs.effects.ore_open_total == 1, '只计开成点'
    grant_writes = [c for c in calls
                    if (c[1] or '').startswith('strategy_ore_open_grant#')]
    assert [c[1] for c in grant_writes] == ['strategy_ore_open_grant#1'], \
        f'批尾单写授予 1 点(跳点不入色档列): {[c[1] for c in calls]}'
    pts = gs.spheres.value.points if gs.spheres.value else ()
    assert (('gold', 300, 400, 30) in pts), '席满跳点矿留 spheres'
    assert any(p[1] == 10 and p[2] == 10 for p in pts), '授予点在 spheres'


def test_zero_open_early_return_no_trigger(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """opened == 0 零触发锁:全批席满 → 早退路径零字段写操作(只供策略算分的实现分支零写、
    零掷点)。"""
    gs = _make_gs(bench_units=[('希儿', 1)] * 9)
    calls = _record_writes(gs, monkeypatch)
    out = report_action_collect_ore_param(
        gs, CwActionCollectOreParam(points=_XYS), sig=_SIG)
    assert not out.applied and out.reason == 'bench_full_no_open', \
        f'全跳批出参: {out.reason}'
    assert not calls, f'全跳零字段写操作(只供策略算分的实现分支含零写): {calls}'


def test_miss_seed_zero_strategy_leg_writes(
        monkeypatch: pytest.MonkeyPatch, seeded_provider) -> None:
    """未掷中零写锁(上报集成面):掷点未中 → 只供策略算分的实现分支零写(既有效果条目照常,
    只供策略算分的实现分支不产生任何台账行)。"""
    set_action_rng_provider(lambda tool: random.Random(_MISS_SEED))
    try:
        gs = _make_gs(bench_units=[], held=True, level=True)
        calls = _record_writes(gs, monkeypatch)
        out = report_action_collect_ore_param(
            gs, CwActionCollectOreParam(points=(_XYS[0],)), sig=_SIG)
        assert out.applied, f'开成: {out.reason}'
        assert not any((c[1] or '').startswith('strategy_ore_open_grant')
                       for c in calls), \
            f'未掷中只供策略算分的实现分支零写: {[c[1] for c in calls]}'
        pts = gs.spheres.value.points if gs.spheres.value else ()
        assert not any(p[1] == 10 and p[2] == 10 for p in pts), \
            '零授予点'
    finally:
        set_action_rng_provider(None)
